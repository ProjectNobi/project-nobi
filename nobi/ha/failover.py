"""
High-Availability Validator Failover for Project Nobi.

Monitors primary and backup validators, automatically promoting the backup
if the primary goes down, and demoting the backup once the primary recovers.

Safety invariant: Never have zero validators running.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nobi.ha.failover")


class ValidatorFailover:
    """Manages automatic failover between primary and backup validators.

    Args:
        primary_host: Hostname/IP of primary validator (use "localhost" for local).
        backup_host: Hostname/IP of backup validator.
        pm2_name: PM2 process name for the validator on each host.
        ssh_user: SSH user for remote commands.
        primary_down_threshold: Seconds primary must be down before failover (default 300 = 5 min).
        recovery_cooldown: Seconds primary must be stable before demoting backup (default 600 = 10 min).
        max_restarts_window: Max restarts in restart_window_seconds to be considered crash-looping.
        restart_window_seconds: Window for crash-loop detection.
        weight_timeout: Seconds since last weight-set to consider weights stale.
        log_file: Path to HA failover log (JSON).
    """

    # States
    STATE_NORMAL = "normal"              # Primary active, backup stopped
    STATE_FAILOVER = "failover"          # Primary down, backup promoted
    STATE_BOTH_RUNNING = "both_running"  # Primary recovering, both running
    STATE_DEGRADED = "degraded"          # Both down — alert!

    def __init__(
        self,
        primary_host: str,
        backup_host: str,
        pm2_name: str = "nobi-validator",
        ssh_user: str = "root",
        primary_down_threshold: int = 300,
        recovery_cooldown: int = 600,
        max_restarts_window: int = 3,
        restart_window_seconds: int = 300,
        weight_timeout: int = 1800,
        log_file: Optional[str] = None,
    ):
        self.primary_host = primary_host
        self.backup_host = backup_host
        self.pm2_name = pm2_name
        self.ssh_user = ssh_user
        self.primary_down_threshold = primary_down_threshold
        self.recovery_cooldown = recovery_cooldown
        self.max_restarts_window = max_restarts_window
        self.restart_window_seconds = restart_window_seconds
        self.weight_timeout = weight_timeout

        self.log_file = Path(
            log_file or os.path.expanduser("~/.nobi/ha_failover.json")
        )
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Internal state tracking
        self._state = self.STATE_NORMAL
        self._primary_down_since: Optional[float] = None
        self._primary_recovered_since: Optional[float] = None
        self._events: list[dict] = []

    @property
    def state(self) -> str:
        return self._state

    # ─── Remote command execution ────────────────────────────────────

    def _is_local(self, host: str) -> bool:
        """Check if a host refers to this machine."""
        return host in ("localhost", "127.0.0.1", "::1")

    def _run_remote(
        self, host: str, cmd: list[str], timeout: int = 30
    ) -> tuple[int, str, str]:
        """Run a command on a remote (or local) host.

        Returns (returncode, stdout, stderr).
        """
        if self._is_local(host):
            full_cmd = cmd
        else:
            full_cmd = [
                "ssh", "-o", "ConnectTimeout=10",
                "-o", "StrictHostKeyChecking=no",
                f"{self.ssh_user}@{host}",
            ] + cmd

        try:
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", f"Command not found: {full_cmd[0]}"
        except Exception as e:
            return -1, "", str(e)

    # ─── Health checks ───────────────────────────────────────────────

    def _check_host_health(self, host: str) -> dict:
        """Check validator health on a given host.

        Returns:
            {
                "online": bool,
                "status": str,
                "uptime": float,
                "restarts": int,
                "crash_looping": bool,
                "setting_weights": bool,
                "reachable": bool,
                "error": str or None,
            }
        """
        result = {
            "online": False,
            "status": "unknown",
            "uptime": 0.0,
            "restarts": 0,
            "crash_looping": False,
            "setting_weights": False,
            "reachable": False,
            "error": None,
        }

        # Get PM2 process info as JSON
        rc, stdout, stderr = self._run_remote(
            host, ["pm2", "jlist"], timeout=15
        )

        if rc != 0:
            result["error"] = stderr or "Failed to reach host or run pm2"
            return result

        result["reachable"] = True

        try:
            processes = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            result["error"] = "Failed to parse PM2 output"
            return result

        # Find our process
        proc = None
        for p in processes:
            if isinstance(p, dict) and p.get("name") == self.pm2_name:
                proc = p
                break

        if proc is None:
            result["status"] = "not_found"
            result["error"] = f"PM2 process '{self.pm2_name}' not found"
            return result

        env = proc.get("pm2_env", {})
        result["status"] = env.get("status", "unknown")
        result["online"] = result["status"] == "online"
        result["restarts"] = env.get("restart_time", 0)

        # Uptime in seconds
        pm_uptime = env.get("pm_uptime", 0)
        if pm_uptime > 0:
            result["uptime"] = max(0, (time.time() * 1000 - pm_uptime) / 1000)

        # Crash-loop detection
        result["crash_looping"] = (
            result["restarts"] >= self.max_restarts_window
            and result["uptime"] < self.restart_window_seconds
        )

        # Check weight setting from logs
        rc2, log_stdout, log_stderr = self._run_remote(
            host,
            ["pm2", "logs", self.pm2_name, "--lines", "100", "--nostream"],
            timeout=15,
        )
        logs = f"{log_stdout}\n{log_stderr}" if rc2 == 0 else ""
        if logs:
            logs_lower = logs.lower()
            weight_keywords = ["set_weights", "setting weights", "weights set successfully", "set weights"]
            result["setting_weights"] = any(kw in logs_lower for kw in weight_keywords)

        return result

    def check_primary(self) -> bool:
        """Check if primary validator is healthy.

        Returns True if primary is online, not crash-looping.
        """
        health = self._check_host_health(self.primary_host)
        return health["online"] and not health["crash_looping"]

    def check_backup(self) -> bool:
        """Check if backup validator is healthy.

        Returns True if backup is online, not crash-looping.
        """
        health = self._check_host_health(self.backup_host)
        return health["online"] and not health["crash_looping"]

    # ─── Actions ─────────────────────────────────────────────────────

    def promote_backup(self) -> bool:
        """Start/restart the backup validator to take over.

        Returns True if backup was successfully started.
        """
        logger.info("Promoting backup validator on %s", self.backup_host)
        self._log_event("promote_backup", f"Promoting backup on {self.backup_host}")

        # Try restart first (handles both stopped and errored states)
        rc, stdout, stderr = self._run_remote(
            self.backup_host, ["pm2", "restart", self.pm2_name], timeout=30
        )

        if rc == 0:
            logger.info("Backup promoted successfully")
            return True

        # If restart failed, try start
        rc, stdout, stderr = self._run_remote(
            self.backup_host, ["pm2", "start", self.pm2_name], timeout=30
        )

        if rc == 0:
            logger.info("Backup started successfully")
            return True

        logger.error("Failed to promote backup: %s", stderr)
        self._log_event("promote_backup_failed", stderr)
        return False

    def demote_primary(self) -> bool:
        """Stop the unhealthy primary validator.

        Returns True if primary was successfully stopped.
        """
        logger.info("Demoting primary validator on %s", self.primary_host)
        self._log_event("demote_primary", f"Stopping primary on {self.primary_host}")

        rc, stdout, stderr = self._run_remote(
            self.primary_host, ["pm2", "stop", self.pm2_name], timeout=30
        )

        if rc == 0:
            logger.info("Primary stopped successfully")
            return True

        logger.error("Failed to stop primary: %s", stderr)
        self._log_event("demote_primary_failed", stderr)
        return False

    def _stop_backup(self) -> bool:
        """Stop the backup validator (after primary has recovered)."""
        logger.info("Stopping backup validator on %s", self.backup_host)
        self._log_event("stop_backup", f"Stopping backup on {self.backup_host} (primary recovered)")

        rc, stdout, stderr = self._run_remote(
            self.backup_host, ["pm2", "stop", self.pm2_name], timeout=30
        )
        return rc == 0

    # ─── Auto failover logic ────────────────────────────────────────

    def auto_failover(self) -> dict:
        """Run one cycle of the failover check.

        Returns a status dict describing what happened:
            {
                "action": str,         # "none", "failover", "recovery", "alert", "cooldown"
                "state": str,          # Current HA state
                "primary_healthy": bool,
                "backup_healthy": bool,
                "message": str,
                "timestamp": str,
            }
        """
        now = time.time()
        primary_healthy = self.check_primary()
        backup_healthy = self.check_backup()

        result = {
            "action": "none",
            "state": self._state,
            "primary_healthy": primary_healthy,
            "backup_healthy": backup_healthy,
            "message": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # ── STATE: NORMAL (primary is active, backup stopped) ──
        if self._state == self.STATE_NORMAL:
            if primary_healthy:
                self._primary_down_since = None
                result["message"] = "Primary healthy. No action needed."
            else:
                # Primary just went down — start tracking
                if self._primary_down_since is None:
                    self._primary_down_since = now
                    result["message"] = (
                        "Primary appears unhealthy. "
                        f"Waiting {self.primary_down_threshold}s before failover."
                    )
                    result["action"] = "monitoring"
                else:
                    elapsed = now - self._primary_down_since
                    if elapsed >= self.primary_down_threshold:
                        # Threshold exceeded — failover!
                        logger.warning(
                            "Primary down for %.0fs (threshold: %ds). Initiating failover.",
                            elapsed, self.primary_down_threshold,
                        )
                        promoted = self.promote_backup()
                        if promoted:
                            self._state = self.STATE_FAILOVER
                            result["action"] = "failover"
                            result["state"] = self.STATE_FAILOVER
                            result["message"] = (
                                f"Primary down for {elapsed:.0f}s. "
                                "Backup promoted successfully."
                            )
                            self._log_event("failover", result["message"])
                        else:
                            # Both could be down
                            self._state = self.STATE_DEGRADED
                            result["action"] = "alert"
                            result["state"] = self.STATE_DEGRADED
                            result["message"] = (
                                "Primary down and backup promotion FAILED. DEGRADED STATE."
                            )
                            self._log_event("degraded", result["message"])
                    else:
                        remaining = self.primary_down_threshold - elapsed
                        result["message"] = (
                            f"Primary unhealthy for {elapsed:.0f}s. "
                            f"Failover in {remaining:.0f}s if not recovered."
                        )
                        result["action"] = "monitoring"

        # ── STATE: FAILOVER (backup is active, primary was down) ──
        elif self._state == self.STATE_FAILOVER:
            if primary_healthy:
                # Primary recovered! Start cooldown.
                self._primary_recovered_since = now
                self._primary_down_since = None
                self._state = self.STATE_BOTH_RUNNING
                result["action"] = "recovery"
                result["state"] = self.STATE_BOTH_RUNNING
                result["message"] = (
                    "Primary recovered. Both validators running. "
                    f"Will stop backup after {self.recovery_cooldown}s cooldown."
                )
                self._log_event("primary_recovered", result["message"])

            elif not backup_healthy:
                # Both down!
                self._state = self.STATE_DEGRADED
                result["action"] = "alert"
                result["state"] = self.STATE_DEGRADED
                result["message"] = "CRITICAL: Both primary and backup are down!"
                self._log_event("both_down", result["message"])
            else:
                result["message"] = "Primary still down. Backup is serving."

        # ── STATE: BOTH_RUNNING (primary recovering, cooldown period) ──
        elif self._state == self.STATE_BOTH_RUNNING:
            if not primary_healthy:
                # Primary went down again during cooldown — back to failover
                self._primary_recovered_since = None
                self._state = self.STATE_FAILOVER
                result["action"] = "failover"
                result["state"] = self.STATE_FAILOVER
                result["message"] = "Primary went down again during cooldown. Back to failover."
                self._log_event("primary_relapsed", result["message"])
            elif self._primary_recovered_since is not None:
                elapsed = now - self._primary_recovered_since
                if elapsed >= self.recovery_cooldown:
                    # Cooldown complete — stop backup
                    self._stop_backup()
                    self._state = self.STATE_NORMAL
                    self._primary_recovered_since = None
                    result["action"] = "recovery"
                    result["state"] = self.STATE_NORMAL
                    result["message"] = (
                        f"Primary stable for {elapsed:.0f}s. "
                        "Backup stopped. Back to normal."
                    )
                    self._log_event("normal_restored", result["message"])
                else:
                    remaining = self.recovery_cooldown - elapsed
                    result["action"] = "cooldown"
                    result["message"] = (
                        f"Both running. Cooldown: {remaining:.0f}s remaining."
                    )

        # ── STATE: DEGRADED (both down) ──
        elif self._state == self.STATE_DEGRADED:
            if primary_healthy:
                self._state = self.STATE_NORMAL
                self._primary_down_since = None
                result["action"] = "recovery"
                result["state"] = self.STATE_NORMAL
                result["message"] = "Primary recovered from degraded state."
                self._log_event("recovered_from_degraded", result["message"])
            elif backup_healthy:
                self._state = self.STATE_FAILOVER
                result["action"] = "failover"
                result["state"] = self.STATE_FAILOVER
                result["message"] = "Backup recovered from degraded state."
                self._log_event("backup_recovered_degraded", result["message"])
            else:
                # Still degraded — try to start anything
                result["action"] = "alert"
                result["message"] = "CRITICAL: Still degraded. Attempting backup promotion."
                self.promote_backup()

        return result

    def get_status(self) -> dict:
        """Get current HA status without triggering any actions.

        Returns:
            {
                "state": str,
                "primary": dict (health),
                "backup": dict (health),
                "active": str ("primary", "backup", "both", "none"),
                "primary_down_since": str or None,
                "primary_recovered_since": str or None,
                "recent_events": list,
                "timestamp": str,
            }
        """
        primary_health = self._check_host_health(self.primary_host)
        backup_health = self._check_host_health(self.backup_host)

        # Determine which is active
        if primary_health["online"] and backup_health["online"]:
            active = "both"
        elif primary_health["online"]:
            active = "primary"
        elif backup_health["online"]:
            active = "backup"
        else:
            active = "none"

        return {
            "state": self._state,
            "primary": primary_health,
            "backup": backup_health,
            "active": active,
            "primary_down_since": (
                datetime.fromtimestamp(self._primary_down_since, tz=timezone.utc).isoformat()
                if self._primary_down_since else None
            ),
            "primary_recovered_since": (
                datetime.fromtimestamp(self._primary_recovered_since, tz=timezone.utc).isoformat()
                if self._primary_recovered_since else None
            ),
            "recent_events": self._events[-20:],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─── Event logging ───────────────────────────────────────────────

    def _log_event(self, event_type: str, message: str):
        """Log a failover event to memory and disk."""
        event = {
            "type": event_type,
            "message": message,
            "state": self._state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event)
        logger.info("[HA %s] %s", event_type, message)

        # Persist to log file
        self._save_log()

    def _save_log(self):
        """Save events and state to the JSON log file."""
        data = {
            "state": self._state,
            "primary_host": self.primary_host,
            "backup_host": self.backup_host,
            "pm2_name": self.pm2_name,
            "primary_down_since": self._primary_down_since,
            "primary_recovered_since": self._primary_recovered_since,
            "events": self._events[-100:],  # Keep last 100 events
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with open(self.log_file, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            logger.error("Failed to save HA log: %s", e)

    def load_state(self):
        """Load persisted state from log file (for restart recovery)."""
        if not self.log_file.exists():
            return

        try:
            with open(self.log_file, "r") as f:
                data = json.load(f)

            self._state = data.get("state", self.STATE_NORMAL)
            self._primary_down_since = data.get("primary_down_since")
            self._primary_recovered_since = data.get("primary_recovered_since")
            self._events = data.get("events", [])
            logger.info("Loaded HA state: %s", self._state)
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning("Failed to load HA state: %s", e)
