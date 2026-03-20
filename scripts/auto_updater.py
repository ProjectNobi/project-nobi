#!/usr/bin/env python3
"""
Auto-Update Daemon for Project Nobi Validators & Miners.

Polls the git remote for new commits and automatically pulls updates,
runs health checks, restarts PM2 processes, and rolls back on failure.

Enhanced with:
- Validator-specific graceful restart (waits for epoch/step completion)
- Post-update health verification (PM2 status, subtensor connection, weight setting)
- Website sync (docs/landing/* → /var/www/projectnobi/)
- Dependency change detection (auto pip install -e . when requirements.txt changes)
- Configurable per-process restart strategies

Usage:
    python scripts/auto_updater.py          # Run as daemon (continuous loop)
    python scripts/auto_updater.py --once   # Single check-and-update, then exit

Environment Variables:
    AUTO_UPDATE_INTERVAL   - Check interval in seconds (default: 300)
    AUTO_UPDATE_PM2_NAMES  - Comma-separated PM2 process names (auto-detected if empty)
    AUTO_UPDATE_ENABLED    - Set to "false" to disable (default: "true")
    AUTO_UPDATE_BRANCH     - Git branch to track (default: "main")
    AUTO_UPDATE_LOG_DIR    - Log directory (default: ~/.nobi)
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("auto_updater")

# Restart strategies
RESTART_GRACEFUL = "graceful"  # Wait for step completion before restart
RESTART_HARD = "hard"          # Immediate restart

# Default restart strategies by process name pattern
DEFAULT_RESTART_STRATEGIES = {
    "validator": RESTART_GRACEFUL,
    "miner": RESTART_HARD,
}

# Graceful restart settings
GRACEFUL_TIMEOUT = 60  # Max seconds to wait for step completion
GRACEFUL_POLL_INTERVAL = 2  # How often to check logs during graceful wait
STEP_COMPLETE_PATTERNS = ["step completed", "step_completed", "epoch completed", "epoch_completed", "forward pass complete"]


class AutoUpdater:
    """Auto-update daemon for Project Nobi miners and validators."""

    def __init__(
        self,
        repo_path: str,
        check_interval: int = 300,
        pm2_names: Optional[list] = None,
        branch: str = "main",
        log_dir: Optional[str] = None,
        restart_strategies: Optional[dict] = None,
        website_dir: Optional[str] = None,
    ):
        self.repo_path = os.path.abspath(repo_path)
        self.check_interval = max(30, check_interval)  # minimum 30s
        self.branch = branch
        self.pm2_names = pm2_names or []
        self.log_dir = Path(log_dir or os.path.expanduser("~/.nobi"))
        self.log_file = self.log_dir / "update_log.json"
        self.website_dir = website_dir or "/var/www/projectnobi"
        self._lock = threading.Lock()
        self._running = False

        # Per-process restart strategies: {process_name: "graceful"|"hard"}
        self.restart_strategies = restart_strategies or {}

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect PM2 names if not provided
        if not self.pm2_names:
            self.pm2_names = self._detect_pm2_processes()

        logger.info(
            "AutoUpdater initialized: repo=%s, interval=%ds, branch=%s, pm2=%s",
            self.repo_path, self.check_interval, self.branch, self.pm2_names,
        )

    def _run_cmd(self, cmd: list[str], cwd: Optional[str] = None, timeout: int = 120) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error("Command timed out: %s", " ".join(cmd))
            return -1, "", "Command timed out"
        except FileNotFoundError:
            logger.error("Command not found: %s", cmd[0])
            return -1, "", f"Command not found: {cmd[0]}"

    def _detect_pm2_processes(self) -> list[str]:
        """Auto-detect nobi-related PM2 processes."""
        rc, stdout, _ = self._run_cmd(["pm2", "jlist"], cwd="/tmp")
        if rc != 0:
            logger.warning("Could not list PM2 processes")
            return []

        try:
            processes = json.loads(stdout)
            names = [
                p["name"]
                for p in processes
                if isinstance(p, dict)
                and "nobi" in p.get("name", "").lower()
            ]
            logger.info("Auto-detected PM2 processes: %s", names)
            return names
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse PM2 process list")
            return []

    def _get_current_commit(self) -> str:
        """Get the current HEAD commit hash."""
        rc, stdout, _ = self._run_cmd(["git", "rev-parse", "HEAD"])
        if rc != 0:
            raise RuntimeError("Failed to get current commit hash")
        return stdout

    def _has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted local changes."""
        rc, stdout, _ = self._run_cmd(["git", "status", "--porcelain"])
        return rc == 0 and len(stdout) > 0

    def _get_restart_strategy(self, process_name: str) -> str:
        """Determine restart strategy for a given process.

        Checks explicit strategies first, then falls back to pattern matching.
        """
        # Check explicit config
        if process_name in self.restart_strategies:
            return self.restart_strategies[process_name]

        # Pattern matching against defaults
        name_lower = process_name.lower()
        for pattern, strategy in DEFAULT_RESTART_STRATEGIES.items():
            if pattern in name_lower:
                return strategy

        # Default: hard restart
        return RESTART_HARD

    def _wait_for_step_completion(self, process_name: str, timeout: int = GRACEFUL_TIMEOUT) -> bool:
        """Wait for a validator to complete its current step before restart.

        Checks PM2 logs for step completion patterns. Returns True if step
        completed (or process not running), False if timed out.
        """
        logger.info("Waiting for %s to complete current step (timeout=%ds)...", process_name, timeout)

        start = time.time()
        while time.time() - start < timeout:
            # Get recent logs (last 20 lines)
            rc, stdout, _ = self._run_cmd(
                ["pm2", "logs", process_name, "--lines", "20", "--nostream"],
                cwd="/tmp",
                timeout=10,
            )
            if rc != 0:
                # Process might not be running — safe to restart
                logger.info("Could not get logs for %s — proceeding with restart", process_name)
                return True

            # Check if any step completion pattern is in recent output
            combined = stdout.lower()
            for pattern in STEP_COMPLETE_PATTERNS:
                if pattern in combined:
                    logger.info("Step completed for %s — safe to restart", process_name)
                    return True

            time.sleep(GRACEFUL_POLL_INTERVAL)

        logger.warning("Timeout waiting for step completion on %s — proceeding anyway", process_name)
        return False

    def _check_pm2_process_health(self, process_name: str) -> dict:
        """Check health of a specific PM2 process after restart.

        Returns dict with: {running, restarts, uptime_seconds, crash_looping}
        """
        rc, stdout, _ = self._run_cmd(["pm2", "jlist"], cwd="/tmp")
        if rc != 0:
            return {"running": False, "restarts": -1, "uptime_seconds": 0, "crash_looping": False}

        try:
            processes = json.loads(stdout)
            for p in processes:
                if not isinstance(p, dict):
                    continue
                if p.get("name") == process_name:
                    env = p.get("pm2_env", {})
                    status = env.get("status", "unknown")
                    restarts = env.get("restart_time", 0)
                    uptime = env.get("pm_uptime", 0)
                    # Calculate uptime in seconds
                    if uptime > 0:
                        uptime_secs = (time.time() * 1000 - uptime) / 1000
                    else:
                        uptime_secs = 0

                    # Crash-looping: more than 5 restarts and uptime < 30s
                    crash_looping = restarts > 5 and uptime_secs < 30

                    return {
                        "running": status == "online",
                        "restarts": restarts,
                        "uptime_seconds": uptime_secs,
                        "crash_looping": crash_looping,
                    }
        except (json.JSONDecodeError, KeyError):
            pass

        return {"running": False, "restarts": -1, "uptime_seconds": 0, "crash_looping": False}

    def _check_validator_post_restart(self, process_name: str, wait_seconds: int = 15) -> dict:
        """After restarting a validator, verify it's actually healthy.

        Checks: running, connected to subtensor, not crash-looping.
        Returns a health report dict.
        """
        logger.info("Waiting %ds for %s to stabilize...", wait_seconds, process_name)
        time.sleep(wait_seconds)

        health = self._check_pm2_process_health(process_name)

        # Check logs for connection
        rc, stdout, _ = self._run_cmd(
            ["pm2", "logs", process_name, "--lines", "50", "--nostream"],
            cwd="/tmp",
            timeout=10,
        )
        log_text = stdout.lower() if rc == 0 else ""

        health["connected"] = any(
            p in log_text for p in ["connected to", "subtensor", "network:", "chain_endpoint"]
        )
        health["errors"] = []
        for line in (stdout or "").split("\n"):
            line_lower = line.lower()
            if any(err in line_lower for err in ["error", "exception", "traceback", "failed"]):
                health["errors"].append(line.strip())

        return health

    def check_for_updates(self) -> bool:
        """Fetch from remote and check if there are new commits.

        Returns True if updates are available, False otherwise.
        """
        with self._lock:
            # Safety: never update with uncommitted changes
            if self._has_uncommitted_changes():
                logger.warning("Uncommitted local changes detected — skipping update check")
                self._log_event("skip", "Uncommitted local changes present")
                return False

            # Fetch from remote
            rc, _, stderr = self._run_cmd(
                ["git", "fetch", "origin", self.branch]
            )
            if rc != 0:
                logger.error("git fetch failed: %s", stderr)
                return False

            # Compare HEAD with remote
            rc_local, local_hash, _ = self._run_cmd(["git", "rev-parse", "HEAD"])
            rc_remote, remote_hash, _ = self._run_cmd(
                ["git", "rev-parse", f"origin/{self.branch}"]
            )

            if rc_local != 0 or rc_remote != 0:
                logger.error("Failed to compare commits")
                return False

            has_updates = local_hash != remote_hash
            if has_updates:
                logger.info(
                    "Updates available: %s -> %s", local_hash[:8], remote_hash[:8]
                )
            else:
                logger.debug("No updates available (at %s)", local_hash[:8])

            return has_updates

    def pull_update(self) -> tuple[bool, str]:
        """Pull the latest changes from the remote.

        Returns (success, commit_message_or_error).
        """
        with self._lock:
            # Safety check again
            if self._has_uncommitted_changes():
                return False, "Uncommitted local changes — refusing to pull"

            rc, stdout, stderr = self._run_cmd(
                ["git", "pull", "origin", self.branch]
            )
            if rc != 0:
                logger.error("git pull failed: %s", stderr)
                return False, stderr

            # Get the new commit message
            rc2, commit_msg, _ = self._run_cmd(
                ["git", "log", "-1", "--pretty=%s"]
            )
            commit_msg = commit_msg if rc2 == 0 else "unknown"

            logger.info("Pulled update: %s", commit_msg)
            return True, commit_msg

    def check_dependency_changes(self) -> bool:
        """Check if requirements.txt changed in the last commit.

        Returns True if dependencies changed.
        """
        rc, stdout, _ = self._run_cmd(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"]
        )
        if rc != 0:
            logger.warning("Could not check diff for dependency changes")
            return False

        changed_files = stdout.split("\n") if stdout else []
        req_files = ["requirements.txt", "setup.py", "setup.cfg", "pyproject.toml"]
        changed = any(f.strip() in req_files for f in changed_files)

        if changed:
            logger.info("Dependency files changed — will reinstall")
        return changed

    def install_dependencies(self) -> bool:
        """Run pip install -e . to update dependencies.

        Returns True on success.
        """
        logger.info("Installing updated dependencies...")
        rc, stdout, stderr = self._run_cmd(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            timeout=300,
        )
        if rc != 0:
            logger.error("Dependency installation failed: %s", stderr)
            return False

        logger.info("Dependencies installed successfully")
        return True

    def sync_website(self) -> bool:
        """Copy docs/landing/* to website directory if both exist.

        Returns True if sync was performed, False if skipped/failed.
        """
        landing_dir = Path(self.repo_path) / "docs" / "landing"
        website_path = Path(self.website_dir)

        if not landing_dir.exists():
            logger.debug("No docs/landing directory — skipping website sync")
            return False

        if not website_path.exists():
            logger.debug("Website dir %s does not exist — skipping sync", self.website_dir)
            return False

        try:
            # Copy all files from landing to website dir
            copied = 0
            for item in landing_dir.iterdir():
                dest = website_path / item.name
                if item.is_file():
                    shutil.copy2(str(item), str(dest))
                    copied += 1
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(str(dest))
                    shutil.copytree(str(item), str(dest))
                    copied += 1

            logger.info("Website sync: copied %d items from docs/landing to %s", copied, self.website_dir)
            self._log_event("website_sync", f"Synced {copied} items to {self.website_dir}")
            return True
        except (OSError, shutil.Error) as e:
            logger.error("Website sync failed: %s", e)
            self._log_event("website_sync_failed", str(e))
            return False

    def run_health_check(self) -> bool:
        """Run health checks to verify the codebase is functional.

        Returns True if all checks pass.
        """
        # Check 1: Can import nobi
        rc, stdout, stderr = self._run_cmd(
            [sys.executable, "-c", "import nobi; print('ok')"],
            timeout=30,
        )
        if rc != 0 or "ok" not in stdout:
            logger.error("Health check failed (import): %s", stderr)
            return False

        # Check 2: Quick syntax/import test on key modules
        rc2, stdout2, stderr2 = self._run_cmd(
            [sys.executable, "-c", "from nobi import __version__; print('version_ok')"],
            timeout=30,
        )
        if rc2 != 0 or "version_ok" not in stdout2:
            logger.warning("Version check failed (non-fatal): %s", stderr2)
            # Non-fatal — some versions might not have __version__

        logger.info("Health check passed")
        return True

    def restart_processes(self) -> dict:
        """Restart all configured PM2 processes with per-process strategies.

        Returns a dict of {process_name: success_bool}.
        """
        results = {}
        for name in self.pm2_names:
            strategy = self._get_restart_strategy(name)

            if strategy == RESTART_GRACEFUL:
                # Wait for step completion before restart
                logger.info("Graceful restart for %s", name)
                self._wait_for_step_completion(name)

            rc, stdout, stderr = self._run_cmd(
                ["pm2", "restart", name], cwd="/tmp"
            )
            success = rc == 0
            results[name] = success

            if success:
                logger.info("Restarted PM2 process: %s (strategy=%s)", name, strategy)

                # For validators, do post-restart health check
                if strategy == RESTART_GRACEFUL:
                    post_health = self._check_validator_post_restart(name, wait_seconds=10)
                    if post_health.get("crash_looping"):
                        logger.error("ALERT: %s is crash-looping after restart!", name)
                        self._log_event("crash_loop_detected", f"{name} crash-looping", post_health)
                    elif not post_health.get("running"):
                        logger.error("ALERT: %s is not running after restart!", name)
                        self._log_event("restart_failed", f"{name} not online after restart", post_health)
            else:
                logger.error("Failed to restart %s: %s", name, stderr)

        return results

    def rollback(self, commit_hash: str) -> bool:
        """Rollback to a previous commit.

        Returns True if rollback succeeded.
        """
        with self._lock:
            logger.warning("Rolling back to commit %s", commit_hash[:8])
            rc, _, stderr = self._run_cmd(
                ["git", "checkout", commit_hash]
            )
            if rc != 0:
                logger.error("Rollback failed: %s", stderr)
                return False

            # Also reset to make it clean
            rc2, _, _ = self._run_cmd(["git", "checkout", self.branch])
            rc3, _, stderr3 = self._run_cmd(
                ["git", "reset", "--hard", commit_hash]
            )
            if rc3 != 0:
                logger.error("Hard reset failed: %s", stderr3)
                return False

            logger.info("Rollback successful to %s", commit_hash[:8])
            return True

    def _log_event(self, event_type: str, message: str, details: Optional[dict] = None):
        """Log an update event to the JSON log file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "message": message,
        }
        if details:
            entry["details"] = details

        # Read existing log
        log_data = []
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    log_data = json.load(f)
                if not isinstance(log_data, list):
                    log_data = []
            except (json.JSONDecodeError, IOError):
                log_data = []

        log_data.append(entry)

        # Keep last 1000 entries
        if len(log_data) > 1000:
            log_data = log_data[-1000:]

        try:
            with open(self.log_file, "w") as f:
                json.dump(log_data, f, indent=2)
        except IOError as e:
            logger.error("Failed to write log: %s", e)

    def update_cycle(self) -> bool:
        """Run a single update cycle: check → pull → deps → health → restart → website.

        Returns True if an update was applied successfully.
        """
        logger.info("Starting update cycle...")

        # Step 1: Check for updates
        if not self.check_for_updates():
            logger.debug("No updates available")
            return False

        # Save current commit for potential rollback
        try:
            previous_commit = self._get_current_commit()
        except RuntimeError:
            logger.error("Could not get current commit — aborting")
            self._log_event("error", "Could not get current commit hash")
            return False

        # Step 2: Pull update
        success, message = self.pull_update()
        if not success:
            self._log_event("pull_failed", message)
            return False

        new_commit = self._get_current_commit()
        self._log_event("pulled", f"Updated to {new_commit[:8]}: {message}", {
            "from": previous_commit[:8],
            "to": new_commit[:8],
        })

        # Step 3: Check for dependency changes and install if needed
        if self.check_dependency_changes():
            if not self.install_dependencies():
                logger.warning("Dependency install failed — continuing anyway")
                self._log_event("dep_install_failed", "pip install -e . failed after dependency change")

        # Step 4: Health check
        if not self.run_health_check():
            logger.error("Health check failed after update — rolling back!")
            self._log_event("health_check_failed", "Rolling back", {
                "rollback_to": previous_commit[:8],
            })
            if self.rollback(previous_commit):
                self._log_event("rollback_success", f"Rolled back to {previous_commit[:8]}")
            else:
                self._log_event("rollback_failed", "CRITICAL: Rollback also failed!")
            return False

        # Step 5: Restart processes (with per-process strategies)
        if self.pm2_names:
            results = self.restart_processes()
            self._log_event("restarted", "Processes restarted", {"results": results})
            failed = [name for name, ok in results.items() if not ok]
            if failed:
                logger.warning("Some processes failed to restart: %s", failed)
        else:
            logger.info("No PM2 processes configured — skipping restart")

        # Step 6: Sync website
        self.sync_website()

        self._log_event("update_complete", f"Successfully updated to {new_commit[:8]}: {message}")
        logger.info("Update cycle complete: %s -> %s", previous_commit[:8], new_commit[:8])
        return True

    def run(self):
        """Main daemon loop: continuously check for updates."""
        self._running = True
        logger.info(
            "Auto-updater daemon started (interval=%ds, pm2=%s)",
            self.check_interval, self.pm2_names,
        )
        self._log_event("started", "Auto-updater daemon started", {
            "interval": self.check_interval,
            "pm2_names": self.pm2_names,
            "branch": self.branch,
        })

        while self._running:
            try:
                self.update_cycle()
            except Exception as e:
                logger.exception("Unexpected error in update cycle: %s", e)
                self._log_event("error", str(e))

            # Sleep in small increments so we can stop gracefully
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Auto-updater daemon stopped")
        self._log_event("stopped", "Auto-updater daemon stopped")

    def stop(self):
        """Signal the daemon to stop."""
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="Project Nobi Auto-Updater")
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single update check and exit",
    )
    parser.add_argument(
        "--repo", type=str,
        default=os.environ.get("AUTO_UPDATE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        help="Path to the git repository",
    )
    parser.add_argument(
        "--interval", type=int,
        default=int(os.environ.get("AUTO_UPDATE_INTERVAL", "300")),
        help="Check interval in seconds (default: 300)",
    )
    parser.add_argument(
        "--branch", type=str,
        default=os.environ.get("AUTO_UPDATE_BRANCH", "main"),
        help="Git branch to track (default: main)",
    )
    parser.add_argument(
        "--pm2-names", type=str,
        default=os.environ.get("AUTO_UPDATE_PM2_NAMES", ""),
        help="Comma-separated PM2 process names (auto-detected if empty)",
    )
    parser.add_argument(
        "--log-dir", type=str,
        default=os.environ.get("AUTO_UPDATE_LOG_DIR", ""),
        help="Log directory (default: ~/.nobi)",
    )
    parser.add_argument(
        "--website-dir", type=str,
        default=os.environ.get("AUTO_UPDATE_WEBSITE_DIR", "/var/www/projectnobi"),
        help="Website directory for syncing docs/landing (default: /var/www/projectnobi)",
    )
    args = parser.parse_args()

    # Check if disabled
    if os.environ.get("AUTO_UPDATE_ENABLED", "true").lower() == "false":
        print("Auto-updater is disabled (AUTO_UPDATE_ENABLED=false)")
        sys.exit(0)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    pm2_names = [n.strip() for n in args.pm2_names.split(",") if n.strip()] if args.pm2_names else None

    updater = AutoUpdater(
        repo_path=args.repo,
        check_interval=args.interval,
        pm2_names=pm2_names,
        branch=args.branch,
        log_dir=args.log_dir or None,
        website_dir=args.website_dir,
    )

    if args.once:
        logger.info("Running single update check...")
        updated = updater.update_cycle()
        sys.exit(0 if updated else 1)
    else:
        try:
            updater.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            updater.stop()


if __name__ == "__main__":
    main()
