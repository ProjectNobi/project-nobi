"""
Project Nobi — Consent Management
====================================
Tracks user consent for GDPR-required processing activities.

Consent types tracked:
  - data_processing:      Basic processing to provide the service
  - memory_extraction:    LLM-based memory extraction from conversations
  - analytics:            Anonymised usage analytics
  - profiling:            Building a personality/preference profile
  - marketing:            Promotional communications
  - third_party_sharing:  Sharing data with third parties (none currently)

Features:
  - Consent versioning: if ToS changes, users must re-consent
  - Withdrawal: consent can be withdrawn at any time
  - Age verification: records 18+ confirmation
  - Audit trail: all consent changes are logged
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nobi-consent")

DEFAULT_CONSENT_DB = os.path.expanduser("~/.nobi/consent.db")

# Current ToS / Privacy Policy version — bump this when policy changes
# and all existing users will be prompted to re-consent.
CURRENT_POLICY_VERSION = os.environ.get("NOBI_POLICY_VERSION", "1.0.0")

CONSENT_TYPES = [
    "data_processing",
    "memory_extraction",
    "analytics",
    "profiling",
    "marketing",
    "third_party_sharing",
]


class ConsentManager:
    """Manage user consent records with full audit trail."""

    def __init__(
        self,
        db_path: str = DEFAULT_CONSENT_DB,
        policy_version: str = CURRENT_POLICY_VERSION,
    ):
        self.db_path = os.path.expanduser(db_path)
        self.policy_version = policy_version
        self._local = threading.local()
        self._init_db()

    # ─── DB helpers ──────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consent_records (
                id                  TEXT PRIMARY KEY,
                user_id             TEXT NOT NULL,
                policy_version      TEXT NOT NULL,
                data_processing     INTEGER NOT NULL DEFAULT 0,
                memory_extraction   INTEGER NOT NULL DEFAULT 0,
                analytics           INTEGER NOT NULL DEFAULT 0,
                profiling           INTEGER NOT NULL DEFAULT 0,
                marketing           INTEGER NOT NULL DEFAULT 0,
                third_party_sharing INTEGER NOT NULL DEFAULT 0,
                processing_restricted INTEGER NOT NULL DEFAULT 0,
                age_verified        INTEGER NOT NULL DEFAULT 0,
                age_verified_at     TEXT,
                consented_at        TEXT NOT NULL,
                updated_at          TEXT,
                withdrawn_at        TEXT,
                ip_hash             TEXT,
                source              TEXT DEFAULT 'unknown'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consent_audit (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                action      TEXT NOT NULL,
                old_state   TEXT,
                new_state   TEXT,
                changed_at  TEXT NOT NULL,
                source      TEXT
            )
        """)
        # Index for fast user lookups
        conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_audit_user ON consent_audit(user_id)")
        conn.commit()
        conn.close()

    def _audit(self, user_id: str, action: str, old_state: Optional[Dict], new_state: Optional[Dict], source: str = "api"):
        conn = self._conn()
        conn.execute(
            "INSERT INTO consent_audit (id, user_id, action, old_state, new_state, changed_at, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                user_id,
                action,
                json.dumps(old_state) if old_state else None,
                json.dumps(new_state) if new_state else None,
                datetime.now(timezone.utc).isoformat(),
                source,
            ),
        )
        conn.commit()

    # ─── Core operations ─────────────────────────────────────

    def record_consent(
        self,
        user_id: str,
        consent: Dict[str, bool],
        age_verified: bool = False,
        source: str = "unknown",
        ip_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record initial consent for a user.

        consent: dict with any of CONSENT_TYPES as keys, values are True/False.
        age_verified: True if user confirmed they are 18+.
        """
        now = datetime.now(timezone.utc).isoformat()
        record_id = str(uuid.uuid4())
        conn = self._conn()

        new_state = {
            "data_processing":      int(consent.get("data_processing", False)),
            "memory_extraction":    int(consent.get("memory_extraction", False)),
            "analytics":            int(consent.get("analytics", False)),
            "profiling":            int(consent.get("profiling", False)),
            "marketing":            int(consent.get("marketing", False)),
            "third_party_sharing":  int(consent.get("third_party_sharing", False)),
            "processing_restricted": 0,
            "age_verified":         int(age_verified),
            "age_verified_at":      now if age_verified else None,
        }

        conn.execute(
            """INSERT INTO consent_records
               (id, user_id, policy_version, data_processing, memory_extraction,
                analytics, profiling, marketing, third_party_sharing,
                processing_restricted, age_verified, age_verified_at,
                consented_at, ip_hash, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (
                record_id, user_id, self.policy_version,
                new_state["data_processing"], new_state["memory_extraction"],
                new_state["analytics"], new_state["profiling"],
                new_state["marketing"], new_state["third_party_sharing"],
                new_state["processing_restricted"],
                new_state["age_verified"], new_state["age_verified_at"],
                now, ip_hash, source,
            ),
        )
        conn.commit()
        self._audit(user_id, "initial_consent", None, new_state, source)
        logger.info(f"[Consent] Recorded initial consent for user={user_id}")
        return {"id": record_id, "consented_at": now, **new_state}

    def update_consent(
        self,
        user_id: str,
        updates: Dict[str, Any],
        source: str = "api",
    ) -> Dict[str, Any]:
        """Update specific consent fields for a user. Creates record if not exists."""
        conn = self._conn()
        existing = conn.execute(
            "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consented_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()

        old_state = dict(existing) if existing else None
        now = datetime.now(timezone.utc).isoformat()

        if not existing:
            # Auto-create minimal record
            self.record_consent(user_id, {}, source=source)
            existing = conn.execute(
                "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consented_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        # Build UPDATE set clauses for valid fields
        allowed_fields = set(CONSENT_TYPES) | {"processing_restricted", "age_verified"}
        set_clauses = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                params.append(int(v) if isinstance(v, bool) else v)

        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now)
            params.append(user_id)
            conn.execute(
                f"UPDATE consent_records SET {', '.join(set_clauses)} WHERE user_id = ?",
                params,
            )
            conn.commit()

        new_row = conn.execute(
            "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consented_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        new_state = dict(new_row) if new_row else {}
        self._audit(user_id, "update_consent", old_state, new_state, source)
        return new_state

    def withdraw_consent(self, user_id: str, consent_types: Optional[List[str]] = None, source: str = "api"):
        """Withdraw all or specific consent types.

        consent_types: list of types to withdraw; None = withdraw ALL.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()

        if consent_types is None:
            # Withdraw all
            updates = {ct: False for ct in CONSENT_TYPES}
            updates["withdrawn_at"] = now
        else:
            updates = {ct: False for ct in consent_types if ct in CONSENT_TYPES}

        old_row = conn.execute(
            "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consented_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        old_state = dict(old_row) if old_row else None

        self.update_consent(user_id, updates, source=source)

        # Also set withdrawn_at timestamp if full withdrawal
        if consent_types is None:
            conn.execute(
                "UPDATE consent_records SET withdrawn_at = ? WHERE user_id = ?",
                (now, user_id),
            )
            conn.commit()

        self._audit(user_id, "withdraw_consent", old_state, updates, source)
        logger.info(f"[Consent] Withdrawal for user={user_id} types={consent_types or 'all'}")

    def delete_consent(self, user_id: str):
        """Permanently delete all consent records (called during erasure)."""
        conn = self._conn()
        conn.execute("DELETE FROM consent_records WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM consent_audit WHERE user_id = ?", (user_id,))
        conn.commit()
        logger.info(f"[Consent] Deleted all consent records for user={user_id}")

    # ─── Queries ─────────────────────────────────────────────

    def get_consent_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return current consent status for a user."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consented_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def has_consent(self, user_id: str, consent_type: str) -> bool:
        """Check if a user has given consent for a specific processing type."""
        status = self.get_consent_status(user_id)
        if not status:
            return False
        if status.get("processing_restricted"):
            return False
        return bool(status.get(consent_type, False))

    def requires_reconsent(self, user_id: str) -> bool:
        """Return True if user needs to re-consent (policy version changed)."""
        status = self.get_consent_status(user_id)
        if not status:
            return True
        return status.get("policy_version") != self.policy_version

    def is_age_verified(self, user_id: str) -> bool:
        """Return True if user has completed age verification (18+)."""
        status = self.get_consent_status(user_id)
        return bool(status.get("age_verified", False)) if status else False

    def verify_age(self, user_id: str, source: str = "api"):
        """Record that a user has confirmed they are 18+."""
        self.update_consent(user_id, {"age_verified": True}, source=source)
        logger.info(f"[Consent] Age verified for user={user_id}")

    def get_audit_trail(self, user_id: str) -> List[Dict[str, Any]]:
        """Return full audit trail for a user's consent changes."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT * FROM consent_audit WHERE user_id = ? ORDER BY changed_at ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_users_needing_reconsent(self) -> List[str]:
        """Return user_ids that need to re-consent due to policy version change."""
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM consent_records WHERE policy_version != ?",
            (self.policy_version,),
        ).fetchall()
        return [r["user_id"] for r in rows]
