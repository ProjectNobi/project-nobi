"""
Project Nobi — FeedbackManager
================================
SQLite-based feedback collection and management.

Privacy-first: all data stays on-server.
"""

import csv
import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from io import StringIO
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.expanduser("~/.nobi/feedback.db")


# ─── Enums ───────────────────────────────────────────────────

class FeedbackCategory(str, Enum):
    BUG_REPORT = "bug_report"
    FEATURE_REQUEST = "feature_request"
    GENERAL_FEEDBACK = "general_feedback"
    QUESTION = "question"
    COMPLAINT = "complaint"


class FeedbackStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    DUPLICATE = "duplicate"


# ─── Auto-categorize keywords ────────────────────────────────

CATEGORY_KEYWORDS: Dict[FeedbackCategory, List[str]] = {
    FeedbackCategory.BUG_REPORT: [
        "bug", "broken", "error", "crash", "fail", "not working", "doesn't work",
        "does not work", "issue", "problem", "glitch", "freeze", "hang", "stuck",
        "exception", "traceback", "500", "wrong", "incorrect", "malfunction",
    ],
    FeedbackCategory.FEATURE_REQUEST: [
        "feature", "request", "suggest", "suggestion", "would be nice", "wish",
        "add", "could you", "can you add", "please add", "want", "need",
        "idea", "improvement", "enhance", "upgrade", "new",
    ],
    FeedbackCategory.QUESTION: [
        "how", "what", "when", "where", "why", "?", "help", "understand",
        "explain", "does it", "is it", "can i", "should i", "clarify",
    ],
    FeedbackCategory.COMPLAINT: [
        "complain", "complaint", "unhappy", "disappointed", "frustrated",
        "terrible", "awful", "hate", "worst", "bad experience", "unacceptable",
        "angry", "upset", "annoyed", "disgusted",
    ],
}


def auto_categorize(message: str) -> FeedbackCategory:
    """Detect category from message content using keyword matching."""
    lower = message.lower()
    scores: Dict[FeedbackCategory, int] = {cat: 0 for cat in FeedbackCategory}

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[category] += 1

    best = max(scores, key=lambda c: scores[c])
    if scores[best] == 0:
        return FeedbackCategory.GENERAL_FEEDBACK
    return best


# ─── Data class ──────────────────────────────────────────────

@dataclass
class Feedback:
    id: str
    user_id: str
    platform: str
    category: FeedbackCategory
    message: str
    status: FeedbackStatus
    created_at: str
    resolved_at: Optional[str]
    admin_notes: Optional[str]


# ─── Manager ─────────────────────────────────────────────────

class FeedbackManager:
    """
    SQLite-backed feedback management system.

    Stores all user feedback on-server. Privacy-first.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ── DB Init ──────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    platform    TEXT NOT NULL DEFAULT 'unknown',
                    category    TEXT NOT NULL DEFAULT 'general_feedback',
                    message     TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'open',
                    created_at  TEXT NOT NULL,
                    resolved_at TEXT,
                    admin_notes TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_status   ON feedback(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_category ON feedback(category)")
            conn.commit()

    # ── Core CRUD ────────────────────────────────────────────

    def submit_feedback(
        self,
        message: str,
        user_id: str,
        platform: str = "unknown",
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a new feedback entry.

        If category is None or 'auto', it is inferred from the message text.
        Returns the created feedback as a dict.
        """
        if not message or not message.strip():
            raise ValueError("Feedback message cannot be empty")
        if len(message) > 10_000:
            raise ValueError("Feedback message too long (max 10,000 chars)")

        if category is None or category == "auto":
            cat = auto_categorize(message)
        else:
            try:
                cat = FeedbackCategory(category)
            except ValueError:
                cat = FeedbackCategory.GENERAL_FEEDBACK

        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO feedback (id, user_id, platform, category, message,
                                      status, created_at, resolved_at, admin_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (feedback_id, user_id, platform, cat.value, message.strip(),
                 FeedbackStatus.OPEN.value, now),
            )
            conn.commit()

        logger.info("Feedback submitted: %s [%s] from %s@%s", feedback_id, cat.value, user_id, platform)
        return self._row_to_dict({
            "id": feedback_id, "user_id": user_id, "platform": platform,
            "category": cat.value, "message": message.strip(),
            "status": FeedbackStatus.OPEN.value, "created_at": now,
            "resolved_at": None, "admin_notes": None,
        })

    def get_feedback(
        self,
        feedback_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve feedback entries. Filter by id, user_id, status, and/or category.
        """
        clauses: List[str] = []
        params: List[Any] = []

        if feedback_id:
            clauses.append("id = ?")
            params.append(feedback_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if category:
            clauses.append("category = ?")
            params.append(category)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params += [limit, offset]

        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM feedback {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()

        return [self._row_to_dict(dict(r)) for r in rows]

    def update_status(
        self,
        feedback_id: str,
        status: str,
        admin_notes: Optional[str] = None,
    ) -> bool:
        """
        Update the status (and optionally admin_notes) of a feedback entry.
        Returns True if the row was updated.
        """
        try:
            new_status = FeedbackStatus(status)
        except ValueError:
            raise ValueError(f"Invalid status: {status!r}. Must be one of {[s.value for s in FeedbackStatus]}")

        now = datetime.now(timezone.utc).isoformat()
        resolved_at = now if new_status == FeedbackStatus.RESOLVED else None

        with self._get_conn() as conn:
            if admin_notes is not None:
                result = conn.execute(
                    """
                    UPDATE feedback SET status=?, resolved_at=?, admin_notes=?
                    WHERE id=?
                    """,
                    (new_status.value, resolved_at, admin_notes, feedback_id),
                )
            else:
                result = conn.execute(
                    "UPDATE feedback SET status=?, resolved_at=? WHERE id=?",
                    (new_status.value, resolved_at, feedback_id),
                )
            conn.commit()
            return result.rowcount > 0

    def search_feedback(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search over message and admin_notes fields."""
        if not query or not query.strip():
            return []
        pattern = f"%{query.strip()}%"
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM feedback
                WHERE message LIKE ? OR admin_notes LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, limit),
            ).fetchall()
        return [self._row_to_dict(dict(r)) for r in rows]

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated stats about all feedback entries."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            by_status = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT status, COUNT(*) FROM feedback GROUP BY status"
                ).fetchall()
            }
            by_category = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT category, COUNT(*) FROM feedback GROUP BY category"
                ).fetchall()
            }
            # Average resolution time in hours (only resolved entries)
            avg_row = conn.execute(
                """
                SELECT AVG(
                    (julianday(resolved_at) - julianday(created_at)) * 24
                ) FROM feedback
                WHERE resolved_at IS NOT NULL AND status = 'resolved'
                """
            ).fetchone()
            avg_resolution_hours = round(avg_row[0], 2) if avg_row[0] else None

        resolved_count = by_status.get(FeedbackStatus.RESOLVED.value, 0)
        open_count = by_status.get(FeedbackStatus.OPEN.value, 0)

        return {
            "total": total,
            "open": open_count,
            "resolved": resolved_count,
            "by_status": by_status,
            "by_category": by_category,
            "avg_resolution_hours": avg_resolution_hours,
        }

    # ── Export ───────────────────────────────────────────────

    def export_json(self, user_id: Optional[str] = None) -> str:
        """Export all (or user-specific) feedback as JSON string."""
        entries = self.get_feedback(user_id=user_id, limit=100_000)
        return json.dumps(entries, indent=2, ensure_ascii=False)

    def export_csv(self, user_id: Optional[str] = None) -> str:
        """Export all (or user-specific) feedback as CSV string."""
        entries = self.get_feedback(user_id=user_id, limit=100_000)
        if not entries:
            return ""
        buf = StringIO()
        writer = csv.DictWriter(buf, fieldnames=entries[0].keys())
        writer.writeheader()
        writer.writerows(entries)
        return buf.getvalue()

    # ── Internal helpers ─────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "platform": row["platform"],
            "category": row["category"],
            "message": row["message"],
            "status": row["status"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
            "admin_notes": row["admin_notes"],
        }
