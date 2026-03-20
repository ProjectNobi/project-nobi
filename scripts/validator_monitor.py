#!/usr/bin/env python3
"""
Validator Monitor for Project Nobi — SN272 Testnet.

Dedicated monitoring for validator health, weight setting, metagraph status,
and automated issue diagnosis. Works on any server.

Usage:
    python scripts/validator_monitor.py                     # Full report
    python scripts/validator_monitor.py --pm2-name nobi-v   # Specific process
    python scripts/validator_monitor.py --json               # JSON output
    python scripts/validator_monitor.py --check              # Health check only (exit code)

Can be installed as PM2 cron via install_validator_monitor.sh.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("validator_monitor")


class ValidatorMonitor:
    """Monitor a Project Nobi validator on SN272 testnet."""

    def __init__(
        self,
        pm2_name: str,
        netuid: int = 272,
        network: str = "test",
        log_lines: int = 200,
        health_file: Optional[str] = None,
    ):
        self.pm2_name = pm2_name
        self.netuid = netuid
        self.network = network
        self.log_lines = log_lines
        self.health_file = Path(
            health_file or os.path.expanduser("~/.nobi/validator_health.json")
        )

        # Ensure parent dir exists
        self.health_file.parent.mkdir(parents=True, exist_ok=True)

    def _run_cmd(self, cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"

    def _get_pm2_info(self) -> Optional[dict]:
        """Get PM2 process info for the validator."""
        rc, stdout, _ = self._run_cmd(["pm2", "jlist"])
        if rc != 0:
            return None

        try:
            processes = json.loads(stdout)
            for p in processes:
                if isinstance(p, dict) and p.get("name") == self.pm2_name:
                    return p
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _get_pm2_logs(self, lines: Optional[int] = None) -> str:
        """Get recent PM2 logs for the validator."""
        n = lines or self.log_lines
        rc, stdout, stderr = self._run_cmd(
            ["pm2", "logs", self.pm2_name, "--lines", str(n), "--nostream"],
            timeout=15,
        )
        # PM2 logs go to both stdout and stderr
        return f"{stdout}\n{stderr}" if rc == 0 else ""

    def check_health(self) -> dict:
        """Check overall validator health.

        Returns:
            {
                "running": bool,
                "connected": bool,
                "setting_weights": bool,
                "last_weight_set": str or None,
                "uptime": float (seconds),
                "restarts": int,
                "crash_looping": bool,
                "status": str,
                "pm2_id": int or None,
                "timestamp": str
            }
        """
        result = {
            "running": False,
            "connected": False,
            "setting_weights": False,
            "last_weight_set": None,
            "uptime": 0,
            "restarts": 0,
            "crash_looping": False,
            "status": "unknown",
            "pm2_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Get PM2 process info
        info = self._get_pm2_info()
        if info is None:
            result["status"] = "not_found"
            return result

        env = info.get("pm2_env", {})
        result["pm2_id"] = info.get("pm_id")
        result["status"] = env.get("status", "unknown")
        result["running"] = result["status"] == "online"
        result["restarts"] = env.get("restart_time", 0)

        # Uptime
        pm_uptime = env.get("pm_uptime", 0)
        if pm_uptime > 0:
            result["uptime"] = (time.time() * 1000 - pm_uptime) / 1000
        else:
            result["uptime"] = 0

        # Crash-loop detection: many restarts + short uptime
        result["crash_looping"] = result["restarts"] > 5 and result["uptime"] < 60

        # Parse logs for connection and weight setting
        logs = self._get_pm2_logs()
        if logs:
            logs_lower = logs.lower()
            result["connected"] = any(
                p in logs_lower
                for p in ["connected to", "subtensor", "network:", "chain_endpoint"]
            )

            # Check weight setting
            weight_info = self.check_weight_setting(logs)
            result["setting_weights"] = weight_info["successful"]
            result["last_weight_set"] = weight_info["last_set"]

        return result

    def check_weight_setting(self, logs: Optional[str] = None) -> dict:
        """Check if validator is successfully setting weights.

        Returns:
            {
                "last_set": str or None (ISO timestamp or log line),
                "interval": float or None (seconds between last two sets),
                "successful": bool,
                "count_recent": int (weight sets in logs)
            }
        """
        if logs is None:
            logs = self._get_pm2_logs()

        result = {
            "last_set": None,
            "interval": None,
            "successful": False,
            "count_recent": 0,
        }

        if not logs:
            return result

        # Find weight-setting lines
        weight_patterns = [
            r"set_weights",
            r"setting weights",
            r"weights set successfully",
            r"set weights",
        ]

        weight_lines = []
        for line in logs.split("\n"):
            line_lower = line.lower()
            if any(re.search(pat, line_lower) for pat in weight_patterns):
                weight_lines.append(line.strip())

        result["count_recent"] = len(weight_lines)
        result["successful"] = len(weight_lines) > 0

        if weight_lines:
            result["last_set"] = weight_lines[-1][:100]  # Last weight set line, truncated

            # Try to extract timestamps for interval calculation
            timestamps = []
            for wl in weight_lines:
                # Common PM2 timestamp format: YYYY-MM-DDTHH:MM:SS or similar
                ts_match = re.search(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})", wl)
                if ts_match:
                    try:
                        ts = datetime.fromisoformat(ts_match.group(1))
                        timestamps.append(ts)
                    except ValueError:
                        pass

            if len(timestamps) >= 2:
                result["interval"] = (timestamps[-1] - timestamps[-2]).total_seconds()

        return result

    def check_metagraph_status(self) -> dict:
        """Check validator's metagraph position (uid, stake, trust, vtrust, rank).

        Uses btcli or parses logs for metagraph info.

        Returns:
            {
                "uid": int or None,
                "stake": float or None,
                "trust": float or None,
                "vtrust": float or None,
                "rank": float or None,
                "available": bool
            }
        """
        result = {
            "uid": None,
            "stake": None,
            "trust": None,
            "vtrust": None,
            "rank": None,
            "available": False,
        }

        # Try btcli metagraph
        rc, stdout, _ = self._run_cmd(
            ["btcli", "subnet", "metagraph", "--netuid", str(self.netuid),
             "--network", self.network, "--no-prompt"],
            timeout=60,
        )
        if rc != 0 or not stdout:
            # Fall back to parsing logs
            logs = self._get_pm2_logs(lines=100)
            if logs:
                self._parse_metagraph_from_logs(logs, result)
            return result

        result["available"] = True

        # Parse metagraph output — look for our validator's line
        # The format varies, try to find UID and associated values
        lines = stdout.split("\n")
        for line in lines:
            # Look for lines with numeric data
            parts = line.split()
            if len(parts) >= 5:
                try:
                    uid = int(parts[0])
                    result["uid"] = uid
                    # Try to parse trust/vtrust/rank values
                    for i, part in enumerate(parts):
                        try:
                            val = float(part)
                            if 0 <= val <= 1:
                                if result["trust"] is None:
                                    result["trust"] = val
                                elif result["vtrust"] is None:
                                    result["vtrust"] = val
                                elif result["rank"] is None:
                                    result["rank"] = val
                        except ValueError:
                            continue
                    break  # Take first validator entry
                except (ValueError, IndexError):
                    continue

        return result

    def _parse_metagraph_from_logs(self, logs: str, result: dict):
        """Parse metagraph info from validator logs as fallback."""
        logs_lower = logs.lower()

        # Look for uid
        uid_match = re.search(r"uid[:\s]+(\d+)", logs_lower)
        if uid_match:
            result["uid"] = int(uid_match.group(1))

        # Look for vtrust
        vtrust_match = re.search(r"vtrust[:\s]+([\d.]+)", logs_lower)
        if vtrust_match:
            try:
                result["vtrust"] = float(vtrust_match.group(1))
                result["available"] = True
            except ValueError:
                pass

        # Look for trust
        trust_match = re.search(r"(?<!v)trust[:\s]+([\d.]+)", logs_lower)
        if trust_match:
            try:
                result["trust"] = float(trust_match.group(1))
                result["available"] = True
            except ValueError:
                pass

    def get_miner_scores(self) -> list:
        """Extract recent miner scores from validator logs.

        Returns list of dicts: [{uid, score, timestamp}, ...]
        """
        logs = self._get_pm2_logs(lines=500)
        if not logs:
            return []

        scores = []
        # Look for scoring patterns
        score_patterns = [
            r"(?:uid|miner)\s*(\d+)\s*(?:score|reward)[:\s]+([\d.]+)",
            r"scores?\s*[:\[{]\s*([\d.,\s]+)",
            r"scoring\s+(?:uid|miner)\s+(\d+)[:\s]+([\d.]+)",
        ]

        for line in logs.split("\n"):
            line_lower = line.lower()
            if "score" not in line_lower and "reward" not in line_lower:
                continue

            for pattern in score_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        try:
                            scores.append({
                                "uid": int(groups[0]),
                                "score": float(groups[1]),
                                "line": line.strip()[:150],
                            })
                        except (ValueError, IndexError):
                            pass
                    break

        return scores[-50:]  # Last 50 scores

    def diagnose_issues(self) -> list[str]:
        """Auto-detect common validator issues.

        Returns a list of issue descriptions.
        """
        issues = []
        health = self.check_health()

        # Not running
        if not health["running"]:
            if health["status"] == "not_found":
                issues.append("CRITICAL: Validator PM2 process not found. "
                              f"Expected process name: {self.pm2_name}")
            else:
                issues.append(f"CRITICAL: Validator is not running (status: {health['status']})")

        # Crash looping
        if health["crash_looping"]:
            issues.append(f"CRITICAL: Validator is crash-looping! "
                          f"Restarts: {health['restarts']}, Uptime: {health['uptime']:.0f}s")

        # Not connected
        if health["running"] and not health["connected"]:
            issues.append("WARNING: Validator running but no subtensor connection detected in logs")

        # Not setting weights
        if health["running"] and not health["setting_weights"]:
            issues.append("WARNING: Validator running but no weight-setting activity detected in recent logs")

        # High restart count
        if health["restarts"] > 10 and not health["crash_looping"]:
            issues.append(f"INFO: High restart count ({health['restarts']}). "
                          "May indicate intermittent issues.")

        # Parse logs for specific errors
        logs = self._get_pm2_logs(lines=100)
        if logs:
            self._diagnose_from_logs(logs, issues)

        return issues

    def _diagnose_from_logs(self, logs: str, issues: list):
        """Parse logs for specific known error patterns."""
        logs_lower = logs.lower()

        error_patterns = {
            "wallet": ("WARNING: Wallet-related errors detected in logs. "
                       "Check wallet configuration and keys."),
            "insufficient stake": ("WARNING: Insufficient stake for weight setting. "
                                   "Need more TAO staked to this hotkey."),
            "rate limit": ("INFO: Rate limiting detected. Validator may need to wait "
                           "before setting weights again."),
            "timeout": ("WARNING: Network timeout errors detected. "
                        "Check subtensor connectivity."),
            "out of memory": ("CRITICAL: Out of memory errors detected. "
                              "Consider increasing server RAM or reducing batch size."),
            "permission denied": ("WARNING: Permission denied errors in logs. "
                                  "Check file/network permissions."),
            "connection refused": ("WARNING: Connection refused errors. "
                                   "Subtensor node may be down."),
            "no peers": ("WARNING: No peers found. Network connectivity issue."),
        }

        seen = set()
        for pattern, message in error_patterns.items():
            if pattern in logs_lower and message not in seen:
                issues.append(message)
                seen.add(message)

    def get_report(self) -> str:
        """Generate a human-readable validator status report."""
        health = self.check_health()
        weight_info = self.check_weight_setting()
        issues = self.diagnose_issues()

        lines = [
            "=" * 60,
            f"  Validator Monitor Report — {self.pm2_name}",
            f"  Network: {self.network} | NetUID: {self.netuid}",
            f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60,
            "",
            "📊 Health Status:",
            f"  Running:        {'✅ Yes' if health['running'] else '❌ No'} ({health['status']})",
            f"  Connected:      {'✅ Yes' if health['connected'] else '⚠️ Unknown/No'}",
            f"  Setting Weights: {'✅ Yes' if health['setting_weights'] else '⚠️ No'}",
            f"  Uptime:         {self._format_uptime(health['uptime'])}",
            f"  Restarts:       {health['restarts']}",
            f"  Crash-looping:  {'🔴 YES' if health['crash_looping'] else '🟢 No'}",
            "",
            "⚖️ Weight Setting:",
            f"  Recent weight sets: {weight_info['count_recent']}",
        ]

        if weight_info["last_set"]:
            lines.append(f"  Last set: {weight_info['last_set']}")
        if weight_info["interval"]:
            lines.append(f"  Interval: {weight_info['interval']:.0f}s between sets")

        # Metagraph (skip if btcli not available)
        meta = self.check_metagraph_status()
        if meta["available"]:
            lines.extend([
                "",
                "🔗 Metagraph:",
                f"  UID:    {meta['uid']}",
                f"  Stake:  {meta['stake']}",
                f"  Trust:  {meta['trust']}",
                f"  VTrust: {meta['vtrust']}",
                f"  Rank:   {meta['rank']}",
            ])

        # Issues
        if issues:
            lines.extend(["", "🚨 Issues Detected:"])
            for issue in issues:
                lines.append(f"  • {issue}")
        else:
            lines.extend(["", "✅ No issues detected"])

        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    def _format_uptime(self, seconds: float) -> str:
        """Format seconds into human-readable uptime."""
        if seconds <= 0:
            return "N/A"
        if seconds < 60:
            return f"{seconds:.0f}s"
        if seconds < 3600:
            return f"{seconds / 60:.1f}m"
        if seconds < 86400:
            return f"{seconds / 3600:.1f}h"
        return f"{seconds / 86400:.1f}d"

    def save_health(self):
        """Save current health status to JSON file."""
        health = self.check_health()
        weight_info = self.check_weight_setting()
        issues = self.diagnose_issues()

        report = {
            "pm2_name": self.pm2_name,
            "netuid": self.netuid,
            "network": self.network,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": health,
            "weight_setting": weight_info,
            "issues": issues,
        }

        # Read existing data (support multiple validators)
        data = {}
        if self.health_file.exists():
            try:
                with open(self.health_file, "r") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
            except (json.JSONDecodeError, IOError):
                data = {}

        data[self.pm2_name] = report

        try:
            with open(self.health_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info("Health saved to %s", self.health_file)
        except IOError as e:
            logger.error("Failed to save health: %s", e)


def detect_validator_processes() -> list[str]:
    """Auto-detect validator PM2 processes."""
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        processes = json.loads(result.stdout)
        return [
            p["name"]
            for p in processes
            if isinstance(p, dict)
            and ("validator" in p.get("name", "").lower()
                 or "nobi-v" in p.get("name", "").lower())
        ]
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return []


def main():
    parser = argparse.ArgumentParser(description="Project Nobi Validator Monitor")
    parser.add_argument(
        "--pm2-name", type=str, default="",
        help="PM2 process name (auto-detected if empty)",
    )
    parser.add_argument(
        "--netuid", type=int, default=272,
        help="Subnet UID (default: 272)",
    )
    parser.add_argument(
        "--network", type=str, default="test",
        help="Network: test or finney (default: test)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Health check only — exit 0 if healthy, 1 if not",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Save health to ~/.nobi/validator_health.json",
    )
    parser.add_argument(
        "--health-file", type=str, default="",
        help="Path to health JSON file (default: ~/.nobi/validator_health.json)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Auto-detect validator
    pm2_names = []
    if args.pm2_name:
        pm2_names = [args.pm2_name]
    else:
        pm2_names = detect_validator_processes()
        if not pm2_names:
            print("No validator PM2 processes detected.")
            print("Use --pm2-name to specify manually.")
            sys.exit(1)

    exit_code = 0
    for name in pm2_names:
        monitor = ValidatorMonitor(
            pm2_name=name,
            netuid=args.netuid,
            network=args.network,
            health_file=args.health_file or None,
        )

        if args.check:
            health = monitor.check_health()
            if health["running"] and not health["crash_looping"]:
                print(f"{name}: HEALTHY")
            else:
                print(f"{name}: UNHEALTHY ({health['status']})")
                exit_code = 1
        elif args.json:
            health = monitor.check_health()
            weight_info = monitor.check_weight_setting()
            issues = monitor.diagnose_issues()
            output = {
                "pm2_name": name,
                "health": health,
                "weight_setting": weight_info,
                "issues": issues,
            }
            print(json.dumps(output, indent=2))
        else:
            print(monitor.get_report())
            print()

        if args.save:
            monitor.save_health()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
