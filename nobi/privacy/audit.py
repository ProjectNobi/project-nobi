"""
Project Nobi — Privacy Audit Logger (Phase C)

Logs all privacy-relevant operations for third-party audit compliance.
Stores metadata about what data was accessed, what noise was added,
and privacy budget consumed.

CRITICAL: Does NOT store actual user data — only operation metadata.
The log file is append-only for tamper-evidence.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from nobi.privacy.config import PRIVACY_CONFIG


class PrivacyAuditLogger:
    """
    Append-only audit logger for privacy operations.

    All entries are JSON lines written to the audit log file.
    Each entry includes a timestamp, operation type, and metadata.
    No actual user data is ever written to this log.
    """

    def __init__(self, log_path: str = None):
        """
        Args:
            log_path: Path to the audit log file. Defaults to config value.
        """
        self.log_path = log_path or PRIVACY_CONFIG["audit_log_path"]
        # Ensure directory exists
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def _write_entry(self, entry: Dict) -> None:
        """Write a single log entry (append-only)."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["epoch"] = time.time()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")

    def log_data_access(self, user_id_hash: str, operation: str,
                        data_type: str) -> None:
        """
        Log when user data is accessed.

        Args:
            user_id_hash: Anonymized (hashed) user identifier.
            operation: What operation was performed (e.g., "generate_signal").
            data_type: Type of data accessed (e.g., "preference", "message").
        """
        self._write_entry({
            "event": "data_access",
            "user_id_hash": user_id_hash,
            "operation": operation,
            "data_type": data_type,
        })

    def log_noise_addition(self, epsilon: float, delta: float,
                           mechanism: str) -> None:
        """
        Log when differential privacy noise is added.

        Args:
            epsilon: Privacy parameter used.
            delta: Delta parameter used.
            mechanism: Noise mechanism (gaussian/laplace).
        """
        self._write_entry({
            "event": "noise_addition",
            "epsilon": epsilon,
            "delta": delta,
            "mechanism": mechanism,
        })

    def log_aggregation(self, num_signals: int, round_id: int) -> None:
        """
        Log a federated aggregation event.

        Args:
            num_signals: Number of signals aggregated.
            round_id: Federated learning round number.
        """
        self._write_entry({
            "event": "aggregation",
            "num_signals": num_signals,
            "round_id": round_id,
        })

    def log_budget_consumption(self, epsilon_consumed: float,
                               total_consumed: float,
                               budget_remaining: float) -> None:
        """
        Log privacy budget consumption.

        Args:
            epsilon_consumed: Epsilon consumed in this operation.
            total_consumed: Total epsilon consumed so far.
            budget_remaining: Remaining privacy budget.
        """
        self._write_entry({
            "event": "budget_consumption",
            "epsilon_consumed": epsilon_consumed,
            "total_consumed": total_consumed,
            "budget_remaining": budget_remaining,
        })

    def generate_audit_report(self, start_date: str = None,
                              end_date: str = None) -> Dict:
        """
        Generate an audit report from the log file.

        Args:
            start_date: Start date filter (ISO format YYYY-MM-DD). Optional.
            end_date: End date filter (ISO format YYYY-MM-DD). Optional.

        Returns:
            Dict with audit statistics:
            - total_events: Total number of events in range.
            - events_by_type: Count of each event type.
            - total_noise_additions: Number of noise additions.
            - total_aggregations: Number of aggregation events.
            - unique_users_accessed: Number of unique user hashes.
            - total_epsilon_consumed: Sum of epsilon from noise events.
        """
        if not os.path.exists(self.log_path):
            return {
                "total_events": 0,
                "events_by_type": {},
                "total_noise_additions": 0,
                "total_aggregations": 0,
                "unique_users_accessed": 0,
                "total_epsilon_consumed": 0.0,
                "date_range": {"start": start_date, "end": end_date},
            }

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

        # Filter by date range
        if start_date:
            entries = [e for e in entries
                       if e.get("timestamp", "") >= start_date]
        if end_date:
            # Include the full end date
            end_filter = end_date + "T23:59:59"
            entries = [e for e in entries
                       if e.get("timestamp", "") <= end_filter]

        # Compute statistics
        events_by_type: Dict[str, int] = {}
        unique_users = set()
        total_epsilon = 0.0

        for entry in entries:
            event_type = entry.get("event", "unknown")
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

            if event_type == "data_access":
                uid = entry.get("user_id_hash")
                if uid:
                    unique_users.add(uid)

            if event_type == "noise_addition":
                total_epsilon += entry.get("epsilon", 0.0)

        return {
            "total_events": len(entries),
            "events_by_type": events_by_type,
            "total_noise_additions": events_by_type.get("noise_addition", 0),
            "total_aggregations": events_by_type.get("aggregation", 0),
            "unique_users_accessed": len(unique_users),
            "total_epsilon_consumed": total_epsilon,
            "date_range": {"start": start_date, "end": end_date},
        }
