#!/usr/bin/env python3
"""
HA Watcher — Standalone failover watchdog for Project Nobi validators.

Runs as a PM2 process and continuously monitors primary/backup validators,
triggering automatic failover when the primary goes down.

Usage:
    python3 scripts/ha_watcher.py --primary-host localhost --backup-host server4 --interval 60

PM2 install:
    pm2 start scripts/ha_watcher.py --name ha-watcher --interpreter python3 -- \
        --primary-host localhost --backup-host server4 --interval 60
"""

import argparse
import logging
import signal
import sys
import time

from nobi.ha.failover import ValidatorFailover

logger = logging.getLogger("ha_watcher")
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down...", signum)
    _running = False


def main():
    parser = argparse.ArgumentParser(
        description="HA Watcher — Validator failover watchdog"
    )
    parser.add_argument(
        "--primary-host", type=str, default="localhost",
        help="Primary validator host (default: localhost)",
    )
    parser.add_argument(
        "--backup-host", type=str, required=True,
        help="Backup validator host",
    )
    parser.add_argument(
        "--pm2-name", type=str, default="nobi-validator",
        help="PM2 process name for the validator (default: nobi-validator)",
    )
    parser.add_argument(
        "--ssh-user", type=str, default="root",
        help="SSH user for remote hosts (default: root)",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Check interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--down-threshold", type=int, default=300,
        help="Seconds primary must be down before failover (default: 300)",
    )
    parser.add_argument(
        "--recovery-cooldown", type=int, default=600,
        help="Seconds primary must be stable before stopping backup (default: 600)",
    )
    parser.add_argument(
        "--log-file", type=str, default="",
        help="Path to HA log file (default: ~/.nobi/ha_failover.json)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info(
        "Starting HA Watcher: primary=%s, backup=%s, pm2=%s, interval=%ds",
        args.primary_host, args.backup_host, args.pm2_name, args.interval,
    )

    failover = ValidatorFailover(
        primary_host=args.primary_host,
        backup_host=args.backup_host,
        pm2_name=args.pm2_name,
        ssh_user=args.ssh_user,
        primary_down_threshold=args.down_threshold,
        recovery_cooldown=args.recovery_cooldown,
        log_file=args.log_file or None,
    )

    # Restore persisted state
    failover.load_state()

    cycle = 0
    while _running:
        cycle += 1
        try:
            result = failover.auto_failover()
            action = result["action"]
            msg = result["message"]

            if action in ("failover", "alert"):
                logger.warning("[Cycle %d] %s — %s", cycle, action.upper(), msg)
            elif action == "none":
                logger.debug("[Cycle %d] %s", cycle, msg)
            else:
                logger.info("[Cycle %d] %s — %s", cycle, action, msg)

        except Exception:
            logger.exception("Error in failover cycle %d", cycle)

        # Sleep in small increments for responsive shutdown
        for _ in range(args.interval):
            if not _running:
                break
            time.sleep(1)

    logger.info("HA Watcher stopped after %d cycles.", cycle)


if __name__ == "__main__":
    main()
