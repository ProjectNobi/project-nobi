"""
Nobi Burn Tracker
==================
Maintains a local history of all ALPHA burn events for Project Nobi.
Used by the API and dashboard to show transparent burn records.

The burn history is stored at ~/.nobi/burn_history.json by default.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any


# Default history file location
DEFAULT_HISTORY_PATH = Path(
    os.environ.get("BURN_HISTORY_PATH", Path.home() / ".nobi/burn_history.json")
)


class BurnTracker:
    """
    Maintains and queries the ALPHA burn history for Project Nobi.

    Example:
        tracker = BurnTracker()
        total = tracker.get_total_burned()
        history = tracker.get_burn_history()
        latest = tracker.get_latest_burn()
    """

    def __init__(self, history_path: Optional[Path] = None):
        self.history_path = Path(history_path or DEFAULT_HISTORY_PATH)
        self._history: Optional[List[Dict[str, Any]]] = None  # lazy-loaded cache

    # ─── Private ─────────────────────────────────────────────────────────

    def _load(self) -> List[Dict[str, Any]]:
        """Load history from disk (with simple cache invalidation by mtime)."""
        if self.history_path.exists():
            try:
                return json.loads(self.history_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save(self, history: List[Dict[str, Any]]) -> None:
        """Persist history to disk."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(history, indent=2))
        self._history = history  # update cache

    def _fresh(self) -> List[Dict[str, Any]]:
        """Always reads from disk (no stale cache)."""
        return self._load()

    # ─── Public API ──────────────────────────────────────────────────────

    def get_burn_history(
        self,
        network: Optional[str] = None,
        netuid: Optional[int] = None,
        limit: Optional[int] = None,
        dry_runs: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Return the full list of burn records.

        Args:
            network: Filter by network ('testnet' or 'mainnet'). None = all.
            netuid: Filter by subnet ID. None = all.
            limit: Maximum number of records to return (most recent first).
            dry_runs: If False (default), exclude dry-run entries.

        Returns:
            List of burn record dicts, sorted newest-first.
        """
        history = self._fresh()

        # Filter
        if not dry_runs:
            history = [r for r in history if not r.get("dry_run", False)]
        if network:
            history = [r for r in history if r.get("network") == network]
        if netuid is not None:
            history = [r for r in history if r.get("netuid") == netuid]

        # Sort newest first
        history = sorted(history, key=lambda r: r.get("timestamp", ""), reverse=True)

        if limit:
            history = history[:limit]

        return history

    def get_total_burned(
        self,
        network: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> float:
        """
        Return the cumulative ALPHA burned (excluding dry-runs).

        Args:
            network: Filter by network. None = all networks.
            netuid: Filter by subnet. None = all subnets.

        Returns:
            Total ALPHA burned as a float.
        """
        history = self.get_burn_history(network=network, netuid=netuid, dry_runs=False)
        return sum(r.get("amount_alpha", 0.0) for r in history)

    def get_latest_burn(
        self,
        network: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the most recent burn record (excluding dry-runs).

        Returns:
            Most recent burn record dict, or None if no burns yet.
        """
        history = self.get_burn_history(network=network, netuid=netuid, dry_runs=False)
        return history[0] if history else None

    def get_burn_count(
        self,
        network: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> int:
        """Return the total number of burn events (excluding dry-runs)."""
        return len(self.get_burn_history(network=network, netuid=netuid, dry_runs=False))

    def add_burn(
        self,
        amount_alpha: float,
        block: int,
        tx_hash: str,
        network: str = "testnet",
        netuid: int = 272,
        dry_run: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record a new burn event.

        Args:
            amount_alpha: Amount of ALPHA burned.
            block: Block number when the burn occurred.
            tx_hash: On-chain transaction hash.
            network: Network ('testnet' or 'mainnet').
            netuid: Subnet ID.
            dry_run: Whether this was a simulation.
            extra: Optional additional fields to include.

        Returns:
            The created burn record.
        """
        record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "amount_alpha": amount_alpha,
            "block": block,
            "tx_hash": tx_hash,
            "network": network,
            "netuid": netuid,
            "dry_run": dry_run,
        }
        if extra:
            record.update(extra)

        history = self._fresh()
        history.append(record)
        self._save(history)
        return record

    def export_json(
        self,
        network: Optional[str] = None,
        netuid: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Export burn data as a structured JSON-serialisable dict for APIs/dashboards.

        Returns:
            Dict with total_burned, burn_count, latest_burn, history, and metadata.
        """
        history = self.get_burn_history(network=network, netuid=netuid)
        total = sum(r.get("amount_alpha", 0.0) for r in history)
        latest = history[0] if history else None

        return {
            "total_burned_alpha": total,
            "burn_count": len(history),
            "latest_burn": latest,
            "history": history,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "network": network,
                "netuid": netuid,
            },
        }

    def clear_history(self) -> None:
        """Clear all burn history (use with caution — for testing only)."""
        self._save([])
