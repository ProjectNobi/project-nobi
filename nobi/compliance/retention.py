"""
Project Nobi — Data Retention Policy
======================================
Implements configurable data retention with automated cleanup.

Default policy (all configurable via environment variables):
- memories:       12 months
- conversations:  6 months
- inactive users: 12 months (no activity at all)
- billing records: 7 years (legal requirement)
- feedback:       24 months

All deletions are logged to an audit table.
"""

import logging
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nobi-retention")

# ─── Default retention periods (months) ──────────────────────
DEFAULTS = {
    "memories":       int(os.environ.get("NOBI_RETENTION_MEMORIES_MONTHS",       "12")),
    "conversations":  int(os.environ.get("NOBI_RETENTION_CONV_MONTHS",           "6")),
    "inactive_users": int(os.environ.get("NOBI_RETENTION_INACTIVE_MONTHS",       "12")),
    "billing":        int(os.environ.get("NOBI_RETENTION_BILLING_MONTHS",        "84")),  # 7 years
    "feedback":       int(os.environ.get("NOBI_RETENTION_FEEDBACK_MONTHS",       "24")),
}


class RetentionPolicy:
    """Automated data retention and cleanup.

    Usage:
        rp = RetentionPolicy()
        summary = rp.run_retention_pass()  # safe to call on a schedule
    """

    def __init__(
        self,
        memory_db_path: str = "~/.nobi/memories.db",
        billing_db_path: str = "~/.nobi/billing.db",
        feedback_db_path: str = "~/.nobi/feedback.db",
        retention_db_path: str = "~/.nobi/retention_audit.db",
        policy: Optional[Dict[str, int]] = None,
    ):
        self.memory_db_path = os.path.expanduser(memory_db_path)
        self.billing_db_path = os.path.expanduser(billing_db_path)
        self.feedback_db_path = os.path.expanduser(feedback_db_path)
        self.retention_db_path = os.path.expanduser(retention_db_path)
        self.policy = {**DEFAULTS, **(policy or {})}
        self._lock = threading.Lock()
        self._init_audit_db()

    # ─── Internal ────────────────────────────────────────────

    def _init_audit_db(self):
        os.makedirs(os.path.dirname(self.retention_db_path), exist_ok=True)
        conn = sqlite3.connect(self.retention_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_audit (
                id          TEXT PRIMARY KEY,
                run_at      TEXT NOT NULL,
                data_type   TEXT NOT NULL,
                deleted_rows INTEGER NOT NULL DEFAULT 0,
                cutoff_date TEXT,
                details     TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS restricted_users (
                user_id     TEXT PRIMARY KEY,
                restricted_at TEXT NOT NULL,
                reason      TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _log_deletion(self, data_type: str, deleted_rows: int, cutoff: str, details: str = ""):
        conn = sqlite3.connect(self.retention_db_path)
        conn.execute(
            "INSERT INTO retention_audit (id, run_at, data_type, deleted_rows, cutoff_date, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), data_type, deleted_rows, cutoff, details),
        )
        conn.commit()
        conn.close()

    def _cutoff_iso(self, months: int) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
        return cutoff.isoformat()

    # ─── Per-type cleanup ─────────────────────────────────────

    def purge_old_memories(self) -> int:
        """Delete memories older than retention policy."""
        if not os.path.exists(self.memory_db_path):
            return 0
        cutoff = self._cutoff_iso(self.policy["memories"])
        try:
            conn = sqlite3.connect(self.memory_db_path)
            r = conn.execute(
                "DELETE FROM memories WHERE created_at < ?", (cutoff,)
            )
            deleted = r.rowcount
            conn.commit()
            conn.close()
            self._log_deletion("memories", deleted, cutoff)
            if deleted:
                logger.info(f"[Retention] Purged {deleted} old memories (cutoff={cutoff})")
            return deleted
        except Exception as e:
            logger.error(f"[Retention] purge_old_memories error: {e}")
            return 0

    def purge_old_conversations(self) -> int:
        """Delete conversations older than retention policy."""
        if not os.path.exists(self.memory_db_path):
            return 0
        cutoff = self._cutoff_iso(self.policy["conversations"])
        try:
            conn = sqlite3.connect(self.memory_db_path)
            r = conn.execute(
                "DELETE FROM conversations WHERE created_at < ?", (cutoff,)
            )
            deleted = r.rowcount
            conn.commit()
            conn.close()
            self._log_deletion("conversations", deleted, cutoff)
            if deleted:
                logger.info(f"[Retention] Purged {deleted} old conversations (cutoff={cutoff})")
            return deleted
        except Exception as e:
            logger.error(f"[Retention] purge_old_conversations error: {e}")
            return 0

    def purge_inactive_users(self) -> List[str]:
        """Delete all data for users who have been inactive longer than the policy.

        Inactive = no conversation turns recorded after the cutoff.
        Billing records are NOT deleted (legal retention requirement).
        """
        if not os.path.exists(self.memory_db_path):
            return []
        cutoff = self._cutoff_iso(self.policy["inactive_users"])
        purged_users: List[str] = []
        try:
            conn = sqlite3.connect(self.memory_db_path)
            conn.row_factory = sqlite3.Row

            # Find users with no conversation since cutoff
            inactive = conn.execute("""
                SELECT DISTINCT user_id FROM user_profiles
                WHERE last_seen < ? OR last_seen IS NULL
            """, (cutoff,)).fetchall()

            for row in inactive:
                uid = row["user_id"]
                conn.execute("DELETE FROM memories WHERE user_id = ?", (uid,))
                conn.execute("DELETE FROM conversations WHERE user_id = ?", (uid,))
                conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (uid,))
                try:
                    conn.execute("DELETE FROM archived_memories WHERE user_id = ?", (uid,))
                except Exception:
                    pass
                purged_users.append(uid)

            conn.commit()
            conn.close()
            if purged_users:
                self._log_deletion("inactive_users", len(purged_users), cutoff,
                                   f"users={purged_users[:10]}")
                logger.info(f"[Retention] Purged {len(purged_users)} inactive users (cutoff={cutoff})")
        except Exception as e:
            logger.error(f"[Retention] purge_inactive_users error: {e}")
        return purged_users

    def purge_old_feedback(self) -> int:
        """Delete feedback older than retention policy."""
        if not os.path.exists(self.feedback_db_path):
            return 0
        cutoff = self._cutoff_iso(self.policy["feedback"])
        try:
            conn = sqlite3.connect(self.feedback_db_path)
            r = conn.execute("DELETE FROM feedback WHERE created_at < ?", (cutoff,))
            deleted = r.rowcount
            conn.commit()
            conn.close()
            self._log_deletion("feedback", deleted, cutoff)
            return deleted
        except Exception as e:
            logger.error(f"[Retention] purge_old_feedback error: {e}")
            return 0

    # ─── Full retention pass ──────────────────────────────────

    def run_retention_pass(self) -> Dict[str, Any]:
        """Run all retention cleanup tasks. Safe to call from a scheduler.

        Returns a summary dict of what was cleaned up.
        """
        with self._lock:
            logger.info("[Retention] Starting retention pass")
            start = time.monotonic()
            result = {
                "run_at": datetime.now(timezone.utc).isoformat(),
                "memories_deleted": self.purge_old_memories(),
                "conversations_deleted": self.purge_old_conversations(),
                "inactive_users_purged": len(self.purge_inactive_users()),
                "feedback_deleted": self.purge_old_feedback(),
            }
            result["duration_s"] = round(time.monotonic() - start, 3)
            logger.info(f"[Retention] Pass complete: {result}")
            return result

    # ─── User flags ───────────────────────────────────────────

    def flag_restricted_user(self, user_id: str, reason: str = "gdpr_restriction"):
        """Mark a user as restricted (no new processing)."""
        conn = sqlite3.connect(self.retention_db_path)
        conn.execute(
            "INSERT OR REPLACE INTO restricted_users (user_id, restricted_at, reason) VALUES (?, ?, ?)",
            (user_id, datetime.now(timezone.utc).isoformat(), reason),
        )
        conn.commit()
        conn.close()

    def clear_user_flags(self, user_id: str):
        """Clear restriction flag when user is erased."""
        conn = sqlite3.connect(self.retention_db_path)
        conn.execute("DELETE FROM restricted_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    def is_restricted(self, user_id: str) -> bool:
        """Check if a user has active processing restriction."""
        if not os.path.exists(self.retention_db_path):
            return False
        conn = sqlite3.connect(self.retention_db_path)
        row = conn.execute(
            "SELECT 1 FROM restricted_users WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return row is not None

    # ─── Audit log ────────────────────────────────────────────

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent retention audit log entries."""
        if not os.path.exists(self.retention_db_path):
            return []
        conn = sqlite3.connect(self.retention_db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM retention_audit ORDER BY run_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─── Background scheduler ─────────────────────────────────

    def start_background_scheduler(self, interval_hours: int = 24):
        """Start a background thread that runs retention passes on a schedule.

        Call once at application startup. Thread is a daemon so it won't
        block graceful shutdown.
        """
        def _loop():
            while True:
                try:
                    self.run_retention_pass()
                except Exception as e:
                    logger.error(f"[Retention] Scheduler error: {e}")
                time.sleep(interval_hours * 3600)

        t = threading.Thread(target=_loop, daemon=True, name="nobi-retention-scheduler")
        t.start()
        logger.info(f"[Retention] Background scheduler started (interval={interval_hours}h)")
        return t
