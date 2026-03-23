"""
Project Nobi — API Key Manager
================================
SQLite-backed API key management with SHA-256 hashing,
tiered rate limiting, and usage tracking.

Key format: nobi_ + 32-char random hex (e.g. nobi_a1b2c3d4e5f6...)
Storage: Only SHA-256 hash stored, never the raw key.
"""

import hashlib
import os
import sqlite3
import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("nobi-api-auth")

# ── Rate limit tiers ──────────────────────────────────────────────────────────

RATE_LIMITS: Dict[str, int] = {
    "free": 100,
    "plus": 1000,
    "pro": 10000,
}

KEY_PREFIX = "nobi_"
KEY_HEX_LENGTH = 32  # 32 hex chars = 16 bytes of randomness


def _hash_key(api_key: str) -> str:
    """SHA-256 hash of an API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _generate_key() -> str:
    """Generate a new API key: nobi_ + 32 hex chars."""
    return KEY_PREFIX + os.urandom(KEY_HEX_LENGTH // 2).hex()


def _key_prefix(api_key: str) -> str:
    """Extract display prefix from key (first 12 chars after nobi_)."""
    if api_key.startswith(KEY_PREFIX):
        return api_key[len(KEY_PREFIX):len(KEY_PREFIX) + 12]
    return api_key[:12]


class ApiKeyManager:
    """Manages API keys with SQLite storage, rate limiting, and usage tracking."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()  # Protect concurrent writes from async handlers
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                key_prefix TEXT NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT 'default',
                tier TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL,
                last_used TEXT,
                revoked INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
            CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);

            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (key_hash) REFERENCES api_keys(key_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_api_usage_key_hash ON api_usage(key_hash);
            CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp);
        """)
        self._conn.commit()

    def create_key(self, user_id: str, name: str = "default", tier: str = "free") -> dict:
        """
        Create a new API key for a user.
        Returns dict with raw key (only time it's available), prefix, and name.
        """
        if tier not in RATE_LIMITS:
            raise ValueError(f"Invalid tier: {tier}. Must be one of: {list(RATE_LIMITS.keys())}")

        raw_key = _generate_key()
        key_hash = _hash_key(raw_key)
        prefix = _key_prefix(raw_key)
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._conn.execute(
                """INSERT INTO api_keys (key_hash, key_prefix, user_id, name, tier, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (key_hash, prefix, user_id, name, tier, now),
            )
            self._conn.commit()

        logger.info(f"Created API key for user={user_id} name={name} tier={tier} prefix={prefix}")
        return {
            "key": raw_key,
            "key_prefix": prefix,
            "name": name,
        }

    def validate_key(self, api_key: str) -> Optional[dict]:
        """
        Validate an API key. Returns key info dict or None if invalid/revoked.
        """
        if not api_key or not api_key.startswith(KEY_PREFIX):
            return None

        key_hash = _hash_key(api_key)
        row = self._conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0",
            (key_hash,),
        ).fetchone()

        if not row:
            return None

        # Update last_used
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "UPDATE api_keys SET last_used = ? WHERE key_hash = ?",
                (now, key_hash),
            )
            self._conn.commit()

        return {
            "key_hash": row["key_hash"],
            "key_prefix": row["key_prefix"],
            "user_id": row["user_id"],
            "name": row["name"],
            "tier": row["tier"],
            "created_at": row["created_at"],
            "last_used": now,
        }

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key. Returns True if key was found and revoked."""
        key_hash = _hash_key(api_key)
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE key_hash = ? AND revoked = 0",
                (key_hash,),
            )
            self._conn.commit()
        revoked = cursor.rowcount > 0
        if revoked:
            logger.info(f"Revoked API key hash={key_hash[:16]}...")
        return revoked

    def revoke_key_by_prefix(self, key_prefix: str) -> bool:
        """Revoke an API key by its prefix. Returns True if found and revoked."""
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE key_prefix = ? AND revoked = 0",
                (key_prefix,),
            )
            self._conn.commit()
        revoked = cursor.rowcount > 0
        if revoked:
            logger.info(f"Revoked API key by prefix={key_prefix}")
        return revoked

    def list_keys(self, user_id: str) -> list:
        """List all API keys for a user (without the actual key, just metadata)."""
        rows = self._conn.execute(
            """SELECT key_prefix, name, tier, created_at, last_used, revoked
               FROM api_keys WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()

        return [
            {
                "key_prefix": row["key_prefix"],
                "name": row["name"],
                "tier": row["tier"],
                "created_at": row["created_at"],
                "last_used": row["last_used"],
                "revoked": bool(row["revoked"]),
            }
            for row in rows
        ]

    def record_usage(self, api_key: str, endpoint: str):
        """Record an API call for usage tracking."""
        key_hash = _hash_key(api_key)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO api_usage (key_hash, endpoint, timestamp) VALUES (?, ?, ?)",
                (key_hash, endpoint, now),
            )
            self._conn.commit()

    def get_usage(self, api_key: str, days: int = 30) -> dict:
        """Get usage statistics for an API key over the given number of days."""
        key_hash = _hash_key(api_key)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Total requests in period
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_usage WHERE key_hash = ? AND timestamp >= ?",
            (key_hash, cutoff),
        ).fetchone()["cnt"]

        # Requests per endpoint
        endpoints = self._conn.execute(
            """SELECT endpoint, COUNT(*) as cnt FROM api_usage
               WHERE key_hash = ? AND timestamp >= ?
               GROUP BY endpoint ORDER BY cnt DESC""",
            (key_hash, cutoff),
        ).fetchall()

        # Requests today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        today_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_usage WHERE key_hash = ? AND timestamp >= ?",
            (key_hash, today_start),
        ).fetchone()["cnt"]

        return {
            "total_requests": total,
            "requests_today": today_count,
            "period_days": days,
            "by_endpoint": {row["endpoint"]: row["cnt"] for row in endpoints},
        }

    def get_usage_by_hash(self, key_hash: str, days: int = 30) -> dict:
        """Get usage statistics by key hash (for when raw key isn't available)."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_usage WHERE key_hash = ? AND timestamp >= ?",
            (key_hash, cutoff),
        ).fetchone()["cnt"]

        endpoints = self._conn.execute(
            """SELECT endpoint, COUNT(*) as cnt FROM api_usage
               WHERE key_hash = ? AND timestamp >= ?
               GROUP BY endpoint ORDER BY cnt DESC""",
            (key_hash, cutoff),
        ).fetchall()

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        today_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_usage WHERE key_hash = ? AND timestamp >= ?",
            (key_hash, today_start),
        ).fetchone()["cnt"]

        return {
            "total_requests": total,
            "requests_today": today_count,
            "period_days": days,
            "by_endpoint": {row["endpoint"]: row["cnt"] for row in endpoints},
        }

    def check_rate_limit(self, api_key: str) -> Tuple[bool, str]:
        """
        Check if an API key is within its rate limit.
        Returns (allowed: bool, reason: str).
        """
        key_info = self.validate_key(api_key)
        if not key_info:
            return False, "Invalid or revoked API key"

        tier = key_info["tier"]
        limit = RATE_LIMITS.get(tier, RATE_LIMITS["free"])

        # Count requests today
        key_hash = _hash_key(api_key)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM api_usage WHERE key_hash = ? AND timestamp >= ?",
            (key_hash, today_start),
        ).fetchone()["cnt"]

        if count >= limit:
            return False, f"Rate limit exceeded: {count}/{limit} requests today ({tier} tier)"

        return True, f"OK: {count}/{limit} requests today ({tier} tier)"

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
