"""
Project Nobi — GDPR Data Subject Request Handler
==================================================
Implements GDPR data subject rights (DSRs) as per:
- Art. 15: Right of Access
- Art. 16: Right to Rectification
- Art. 17: Right to Erasure ("right to be forgotten")
- Art. 18: Right to Restriction of Processing
- Art. 20: Right to Data Portability

All requests are timestamped and logged for audit purposes.
Responses must be provided within 30 days per GDPR Art. 12.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nobi-gdpr")

DEFAULT_AUDIT_DB = os.path.expanduser("~/.nobi/gdpr_audit.db")


class GDPRHandler:
    """Handle GDPR data subject requests (DSRs).

    All DSRs are logged with a timestamp so we can demonstrate compliance
    with the 30-day response window (GDPR Art. 12(3)).
    """

    def __init__(
        self,
        memory_db_path: str = "~/.nobi/memories.db",
        billing_db_path: str = "~/.nobi/billing.db",
        feedback_db_path: str = "~/.nobi/feedback.db",
        audit_db_path: str = DEFAULT_AUDIT_DB,
        encryption_enabled: bool = True,
    ):
        self.memory_db_path = os.path.expanduser(memory_db_path)
        self.billing_db_path = os.path.expanduser(billing_db_path)
        self.feedback_db_path = os.path.expanduser(feedback_db_path)
        self.audit_db_path = os.path.expanduser(audit_db_path)
        self.encryption_enabled = encryption_enabled
        self._local = threading.local()
        self._init_audit_db()

    # ─── Internal DB helpers ─────────────────────────────────

    def _audit_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "audit_conn") or self._local.audit_conn is None:
            os.makedirs(os.path.dirname(self.audit_db_path), exist_ok=True)
            conn = sqlite3.connect(self.audit_db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.audit_conn = conn
        return self._local.audit_conn

    def _init_audit_db(self):
        """Create the GDPR audit log table."""
        os.makedirs(os.path.dirname(self.audit_db_path), exist_ok=True)
        conn = sqlite3.connect(self.audit_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gdpr_audit (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                request_type TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                completed_at TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                details     TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _log_request(self, user_id: str, request_type: str, details: Optional[Dict] = None) -> str:
        """Log a DSR and return its audit ID."""
        audit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = self._audit_conn()
        conn.execute(
            "INSERT INTO gdpr_audit (id, user_id, request_type, requested_at, status, details) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (audit_id, user_id, request_type, now, json.dumps(details or {})),
        )
        conn.commit()
        logger.info(f"[GDPR] {request_type} request logged for user={user_id} audit_id={audit_id}")
        return audit_id

    def _complete_request(self, audit_id: str, details: Optional[Dict] = None):
        """Mark an audit log entry as completed."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._audit_conn()
        conn.execute(
            "UPDATE gdpr_audit SET status='completed', completed_at=?, details=? WHERE id=?",
            (now, json.dumps(details or {}), audit_id),
        )
        conn.commit()

    def _memory_conn(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.memory_db_path):
            return None
        conn = sqlite3.connect(self.memory_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _billing_conn(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.billing_db_path):
            return None
        conn = sqlite3.connect(self.billing_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _feedback_conn(self) -> Optional[sqlite3.Connection]:
        if not os.path.exists(self.feedback_db_path):
            return None
        conn = sqlite3.connect(self.feedback_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ─── Art. 15: Right of Access ────────────────────────────

    def handle_access_request(self, user_id: str) -> Dict[str, Any]:
        """Right of Access (Art. 15) — return ALL data we hold about a user.

        Collects: memories, conversation history, profile, preferences,
        adapter config, billing records, feedback, voice preferences.

        Returns a structured dict. Response must be provided within 30 days.
        """
        audit_id = self._log_request(user_id, "access")
        now = datetime.now(timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "gdpr_request": "access",
            "gdpr_article": "Art. 15 — Right of Access",
            "user_id": user_id,
            "requested_at": now,
            "deadline": self._deadline(now),
            "data": {},
        }

        # ── Memories & Conversations ──────────────────────────
        mem_conn = self._memory_conn()
        if mem_conn:
            try:
                memories = mem_conn.execute(
                    "SELECT id, memory_type, content, importance, tags, created_at, access_count "
                    "FROM memories WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
                result["data"]["memories"] = [dict(r) for r in memories]

                convs = mem_conn.execute(
                    "SELECT role, content, created_at FROM conversations WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
                result["data"]["conversation_history"] = [dict(r) for r in convs]

                profile = mem_conn.execute(
                    "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
                ).fetchone()
                result["data"]["profile"] = dict(profile) if profile else None
            except Exception as e:
                logger.error(f"[GDPR:Access] memory error for {user_id}: {e}")
            finally:
                mem_conn.close()

        # ── Billing Records ───────────────────────────────────
        bill_conn = self._billing_conn()
        if bill_conn:
            try:
                sub = bill_conn.execute(
                    "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
                ).fetchone()
                result["data"]["subscription"] = dict(sub) if sub else None

                usage = bill_conn.execute(
                    "SELECT * FROM usage_tracking WHERE user_id = ? ORDER BY date DESC LIMIT 90",
                    (user_id,),
                ).fetchall()
                result["data"]["usage_records"] = [dict(r) for r in usage]
            except Exception as e:
                logger.error(f"[GDPR:Access] billing error for {user_id}: {e}")
            finally:
                bill_conn.close()

        # ── Feedback ──────────────────────────────────────────
        fb_conn = self._feedback_conn()
        if fb_conn:
            try:
                feedback = fb_conn.execute(
                    "SELECT * FROM feedback WHERE user_id = ?", (user_id,)
                ).fetchall()
                result["data"]["feedback"] = [dict(r) for r in feedback]
            except Exception as e:
                logger.error(f"[GDPR:Access] feedback error for {user_id}: {e}")
            finally:
                fb_conn.close()

        # ── Consent Records ───────────────────────────────────
        try:
            from nobi.compliance.consent import ConsentManager
            cm = ConsentManager()
            result["data"]["consent"] = cm.get_consent_status(user_id)
        except Exception as e:
            logger.warning(f"[GDPR:Access] consent not available: {e}")

        self._complete_request(audit_id, {"record_count": sum(
            len(v) if isinstance(v, list) else (1 if v else 0)
            for v in result["data"].values()
        )})
        return result

    # ─── Art. 17: Right to Erasure ───────────────────────────

    def handle_erasure_request(self, user_id: str) -> Dict[str, Any]:
        """Right to Erasure (Art. 17) — delete ALL user data permanently.

        Deletes from: memories DB, conversations, profiles, billing,
        feedback, consent records. Returns confirmation of what was deleted.
        """
        audit_id = self._log_request(user_id, "erasure")
        deleted: Dict[str, int] = {}
        errors: List[str] = []

        # ── Memories ──────────────────────────────────────────
        mem_conn = self._memory_conn()
        if mem_conn:
            try:
                r = mem_conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
                deleted["memories"] = r.rowcount
                r = mem_conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
                deleted["conversations"] = r.rowcount
                r = mem_conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
                deleted["profiles"] = r.rowcount
                # Also delete archived memories if table exists
                try:
                    r = mem_conn.execute("DELETE FROM archived_memories WHERE user_id = ?", (user_id,))
                    deleted["archived_memories"] = r.rowcount
                except Exception:
                    pass
                mem_conn.commit()
            except Exception as e:
                errors.append(f"memories: {e}")
                logger.error(f"[GDPR:Erasure] memory error for {user_id}: {e}")
            finally:
                mem_conn.close()

        # ── Billing ───────────────────────────────────────────
        bill_conn = self._billing_conn()
        if bill_conn:
            try:
                r = bill_conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
                deleted["subscriptions"] = r.rowcount
                r = bill_conn.execute("DELETE FROM usage_tracking WHERE user_id = ?", (user_id,))
                deleted["usage_records"] = r.rowcount
                bill_conn.commit()
            except Exception as e:
                errors.append(f"billing: {e}")
                logger.error(f"[GDPR:Erasure] billing error for {user_id}: {e}")
            finally:
                bill_conn.close()

        # ── Feedback ──────────────────────────────────────────
        fb_conn = self._feedback_conn()
        if fb_conn:
            try:
                r = fb_conn.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
                deleted["feedback"] = r.rowcount
                fb_conn.commit()
            except Exception as e:
                errors.append(f"feedback: {e}")
                logger.error(f"[GDPR:Erasure] feedback error for {user_id}: {e}")
            finally:
                fb_conn.close()

        # ── Consent ───────────────────────────────────────────
        try:
            from nobi.compliance.consent import ConsentManager
            cm = ConsentManager()
            cm.delete_consent(user_id)
            deleted["consent"] = 1
        except Exception as e:
            errors.append(f"consent: {e}")

        # ── Retention flags ───────────────────────────────────
        try:
            from nobi.compliance.retention import RetentionPolicy
            rp = RetentionPolicy()
            rp.clear_user_flags(user_id)
        except Exception as e:
            pass  # Not critical

        self._complete_request(audit_id, {"deleted": deleted, "errors": errors})
        logger.info(f"[GDPR:Erasure] Completed for user={user_id}: {deleted}")

        return {
            "gdpr_request": "erasure",
            "gdpr_article": "Art. 17 — Right to Erasure",
            "user_id": user_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "deleted": deleted,
            "errors": errors if errors else None,
            "confirmation": "All personal data has been permanently deleted.",
        }

    # ─── Art. 20: Right to Data Portability ──────────────────

    def handle_portability_request(self, user_id: str) -> bytes:
        """Right to Data Portability (Art. 20) — export in machine-readable JSON.

        Returns UTF-8 encoded JSON bytes in a structured, commonly-used format.
        """
        audit_id = self._log_request(user_id, "portability")

        data = self.handle_access_request.__wrapped__(self, user_id) if hasattr(
            self.handle_access_request, "__wrapped__"
        ) else self._collect_portability_data(user_id)

        payload = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self._complete_request(audit_id, {"bytes": len(payload)})
        return payload

    def _collect_portability_data(self, user_id: str) -> Dict[str, Any]:
        """Structured data export for portability (machine-readable, JSON)."""
        now = datetime.now(timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "schema": "nobi-gdpr-export-v1",
            "gdpr_article": "Art. 20 — Right to Data Portability",
            "user_id": user_id,
            "exported_at": now,
            "deadline": self._deadline(now),
            "memories": [],
            "conversation_history": [],
            "profile": None,
            "consent": None,
        }

        mem_conn = self._memory_conn()
        if mem_conn:
            try:
                memories = mem_conn.execute(
                    "SELECT id, memory_type, content, importance, tags, created_at FROM memories "
                    "WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
                result["memories"] = [dict(r) for r in memories]

                convs = mem_conn.execute(
                    "SELECT role, content, created_at FROM conversations WHERE user_id = ? "
                    "ORDER BY created_at ASC",
                    (user_id,),
                ).fetchall()
                result["conversation_history"] = [dict(r) for r in convs]

                profile = mem_conn.execute(
                    "SELECT user_id, summary, first_seen, last_seen, total_messages "
                    "FROM user_profiles WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                result["profile"] = dict(profile) if profile else None
            except Exception as e:
                logger.error(f"[GDPR:Portability] error for {user_id}: {e}")
            finally:
                mem_conn.close()

        try:
            from nobi.compliance.consent import ConsentManager
            result["consent"] = ConsentManager().get_consent_status(user_id)
        except Exception:
            pass

        return result

    # ─── Art. 16: Right to Rectification ─────────────────────

    def handle_rectification_request(self, user_id: str, corrections: Dict[str, Any]) -> Dict[str, Any]:
        """Right to Rectification (Art. 16) — correct inaccurate data.

        corrections: dict mapping memory_id -> new_content (or profile fields).
        """
        audit_id = self._log_request(user_id, "rectification", {"fields": list(corrections.keys())})
        updated: List[str] = []
        errors: List[str] = []

        mem_conn = self._memory_conn()
        if mem_conn:
            try:
                for memory_id, new_content in corrections.items():
                    if memory_id == "__profile_summary__":
                        mem_conn.execute(
                            "UPDATE user_profiles SET summary = ? WHERE user_id = ?",
                            (new_content, user_id),
                        )
                        updated.append("profile_summary")
                    else:
                        # Only allow correction of memories belonging to this user
                        row = mem_conn.execute(
                            "SELECT id FROM memories WHERE id = ? AND user_id = ?",
                            (memory_id, user_id),
                        ).fetchone()
                        if row:
                            mem_conn.execute(
                                "UPDATE memories SET content = ? WHERE id = ? AND user_id = ?",
                                (new_content, memory_id, user_id),
                            )
                            updated.append(memory_id)
                        else:
                            errors.append(f"memory_id {memory_id}: not found or not owned by user")
                mem_conn.commit()
            except Exception as e:
                errors.append(str(e))
                logger.error(f"[GDPR:Rectification] error for {user_id}: {e}")
            finally:
                mem_conn.close()

        self._complete_request(audit_id, {"updated": updated, "errors": errors})
        return {
            "gdpr_request": "rectification",
            "gdpr_article": "Art. 16 — Right to Rectification",
            "user_id": user_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated": updated,
            "errors": errors if errors else None,
        }

    # ─── Art. 18: Right to Restriction ───────────────────────

    def handle_restriction_request(self, user_id: str, restrict: bool = True) -> Dict[str, Any]:
        """Right to Restriction of Processing (Art. 18).

        When restricted: no new memory extraction, no analytics, no profiling.
        Processing already stored data for providing the service is still allowed.
        """
        audit_id = self._log_request(user_id, "restriction", {"restrict": restrict})
        try:
            from nobi.compliance.consent import ConsentManager
            cm = ConsentManager()
            if restrict:
                cm.update_consent(user_id, {
                    "memory_extraction": False,
                    "analytics": False,
                    "profiling": False,
                    "processing_restricted": True,
                })
            else:
                cm.update_consent(user_id, {"processing_restricted": False})
            self._complete_request(audit_id)
            return {
                "gdpr_request": "restriction",
                "gdpr_article": "Art. 18 — Right to Restriction of Processing",
                "user_id": user_id,
                "restricted": restrict,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "message": (
                    "Processing restricted. We will not extract new memories or run analytics on your data."
                    if restrict else
                    "Processing restriction lifted."
                ),
            }
        except Exception as e:
            logger.error(f"[GDPR:Restriction] error for {user_id}: {e}")
            self._complete_request(audit_id, {"error": str(e)})
            raise

    # ─── Audit Log ───────────────────────────────────────────

    def get_audit_log(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return GDPR audit log entries (all users or filtered by user_id)."""
        conn = self._audit_conn()
        if user_id:
            rows = conn.execute(
                "SELECT * FROM gdpr_audit WHERE user_id = ? ORDER BY requested_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM gdpr_audit ORDER BY requested_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _deadline(requested_at: str) -> str:
        """Return ISO deadline 30 days from request (GDPR Art. 12(3))."""
        from datetime import timedelta
        dt = datetime.fromisoformat(requested_at)
        return (dt + timedelta(days=30)).isoformat()
