"""
Project Nobi — Subscription Manager
=====================================
SQLite-backed subscription and usage tracking.
Thread-safe. Works without Stripe (free tier for everyone).
"""

import os
import uuid
import sqlite3
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Tuple

logger = logging.getLogger("nobi-billing")

# ─── Tier Definitions ────────────────────────────────────────

TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "price_label": "Free",
        "messages_per_day": 200,
        "memory_slots": 100,
        "voice_per_day": 5,
        "image_per_day": 3,
        "proactive_messages": False,
        "priority_response": False,
        "export_memories": True,
        "group_mode": False,
    },
    "plus": {
        "name": "Plus",
        "price": 4.99,
        "price_label": "$4.99/mo",
        "messages_per_day": 500,
        "memory_slots": 1000,
        "voice_per_day": 50,
        "image_per_day": 30,
        "proactive_messages": True,
        "priority_response": False,
        "export_memories": True,
        "group_mode": True,
    },
    "pro": {
        "name": "Pro",
        "price": 9.99,
        "price_label": "$9.99/mo",
        "messages_per_day": -1,  # Unlimited
        "memory_slots": -1,     # Unlimited
        "voice_per_day": -1,    # Unlimited
        "image_per_day": -1,    # Unlimited
        "proactive_messages": True,
        "priority_response": True,
        "export_memories": True,
        "group_mode": True,
    },
}

# Map action names to tier limit keys
ACTION_LIMIT_MAP = {
    "message": "messages_per_day",
    "voice": "voice_per_day",
    "image": "image_per_day",
}


class SubscriptionManager:
    """
    Manages subscriptions, customers, and usage tracking.
    Thread-safe with per-connection locking.
    """

    def __init__(self, db_path: str = "~/.nobi/billing.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._lock:
            c = self._conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    user_id TEXT PRIMARY KEY,
                    email TEXT DEFAULT '',
                    customer_id TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL DEFAULT 'free',
                    status TEXT NOT NULL DEFAULT 'active',
                    started_at TEXT NOT NULL,
                    expires_at TEXT DEFAULT NULL,
                    payment_id TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES customers(user_id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 1,
                    date TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_user_date
                ON usage (user_id, action, date)
            """)
            self._conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _today_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ─── Customer Management ─────────────────────────────────

    def create_customer(self, user_id: str, email: str = "") -> str:
        """Create a customer record. Returns customer_id. Idempotent."""
        with self._lock:
            row = self._conn.execute(
                "SELECT customer_id FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row:
                # Update email if provided
                if email:
                    self._conn.execute(
                        "UPDATE customers SET email = ? WHERE user_id = ?",
                        (email, user_id),
                    )
                    self._conn.commit()
                return row["customer_id"]

            customer_id = f"cust_{uuid.uuid4().hex[:16]}"
            self._conn.execute(
                "INSERT INTO customers (user_id, email, customer_id, created_at) VALUES (?, ?, ?, ?)",
                (user_id, email, customer_id, self._now_iso()),
            )
            # Create default free subscription
            self._conn.execute(
                "INSERT OR IGNORE INTO subscriptions (user_id, tier, status, started_at) VALUES (?, 'free', 'active', ?)",
                (user_id, self._now_iso()),
            )
            self._conn.commit()
            logger.info(f"Created customer {customer_id} for user {user_id}")
            return customer_id

    def get_customer(self, user_id: str) -> Optional[Dict]:
        """Get customer record."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_customer_by_customer_id(self, customer_id: str) -> Optional[Dict]:
        """Look up customer by Stripe customer_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM customers WHERE customer_id = ?",
                (customer_id,),
            ).fetchone()
            return dict(row) if row else None

    # ─── Subscription Management ─────────────────────────────

    def get_subscription(self, user_id: str) -> Dict:
        """Get user's subscription. Returns free tier defaults if none exists."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()

        if not row:
            return {
                "user_id": user_id,
                "tier": "free",
                "status": "active",
                "started_at": self._now_iso(),
                "expires_at": None,
                "payment_id": "",
            }

        result = dict(row)

        # Check if expired
        if result.get("expires_at"):
            try:
                expires = datetime.fromisoformat(result["expires_at"])
                if expires < datetime.now(timezone.utc):
                    # Expired — downgrade to free
                    self._do_downgrade(user_id)
                    result["tier"] = "free"
                    result["status"] = "expired"
            except (ValueError, TypeError):
                pass

        return result

    def upgrade(self, user_id: str, tier: str, payment_id: str = "") -> bool:
        """Upgrade user to a paid tier."""
        if tier not in TIERS:
            logger.warning(f"Invalid tier: {tier}")
            return False

        with self._lock:
            # Ensure customer exists
            row = self._conn.execute(
                "SELECT user_id FROM customers WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row:
                # Auto-create customer
                customer_id = f"cust_{uuid.uuid4().hex[:16]}"
                self._conn.execute(
                    "INSERT INTO customers (user_id, email, customer_id, created_at) VALUES (?, '', ?, ?)",
                    (user_id, customer_id, self._now_iso()),
                )

            now = self._now_iso()
            expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

            existing = self._conn.execute(
                "SELECT user_id FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if existing:
                self._conn.execute(
                    "UPDATE subscriptions SET tier = ?, status = 'active', started_at = ?, expires_at = ?, payment_id = ? WHERE user_id = ?",
                    (tier, now, expires, payment_id, user_id),
                )
            else:
                self._conn.execute(
                    "INSERT INTO subscriptions (user_id, tier, status, started_at, expires_at, payment_id) VALUES (?, ?, 'active', ?, ?, ?)",
                    (user_id, tier, now, expires, payment_id),
                )

            self._conn.commit()
            logger.info(f"Upgraded {user_id} to {tier} (payment: {payment_id or 'none'})")
            return True

    def downgrade(self, user_id: str) -> bool:
        """Downgrade user to free tier."""
        return self._do_downgrade(user_id)

    def _do_downgrade(self, user_id: str) -> bool:
        """Internal downgrade — can be called with or without lock."""
        try:
            self._conn.execute(
                "UPDATE subscriptions SET tier = 'free', status = 'active', expires_at = NULL, payment_id = '' WHERE user_id = ?",
                (user_id,),
            )
            self._conn.commit()
            logger.info(f"Downgraded {user_id} to free")
            return True
        except Exception as e:
            logger.error(f"Downgrade error: {e}")
            return False

    def cancel(self, user_id: str) -> bool:
        """Cancel subscription (set status to cancelled, keep tier until expiry)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT tier, expires_at FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if not row or row["tier"] == "free":
                return False

            self._conn.execute(
                "UPDATE subscriptions SET status = 'cancelled' WHERE user_id = ?",
                (user_id,),
            )
            self._conn.commit()
            logger.info(f"Cancelled subscription for {user_id}")
            return True

    def is_premium(self, user_id: str) -> bool:
        """Check if user has an active paid subscription."""
        sub = self.get_subscription(user_id)
        return sub["tier"] in ("plus", "pro") and sub["status"] in ("active", "cancelled")

    def get_tier(self, user_id: str) -> str:
        """Get user's current tier name."""
        sub = self.get_subscription(user_id)
        return sub["tier"]

    def get_tier_config(self, user_id: str) -> Dict:
        """Get the full tier configuration for a user."""
        tier = self.get_tier(user_id)
        return TIERS.get(tier, TIERS["free"])

    # ─── Usage Tracking ──────────────────────────────────────

    def record_usage(self, user_id: str, action: str):
        """Record one unit of usage for an action today."""
        today = self._today_str()
        with self._lock:
            row = self._conn.execute(
                "SELECT id, count FROM usage WHERE user_id = ? AND action = ? AND date = ?",
                (user_id, action, today),
            ).fetchone()

            if row:
                self._conn.execute(
                    "UPDATE usage SET count = count + 1 WHERE id = ?",
                    (row["id"],),
                )
            else:
                self._conn.execute(
                    "INSERT INTO usage (user_id, action, count, date) VALUES (?, ?, 1, ?)",
                    (user_id, action, today),
                )
            self._conn.commit()

    def get_usage(self, user_id: str) -> Dict:
        """Get usage stats for today."""
        today = self._today_str()
        with self._lock:
            rows = self._conn.execute(
                "SELECT action, count FROM usage WHERE user_id = ? AND date = ?",
                (user_id, today),
            ).fetchall()

        usage = {}
        for row in rows:
            usage[row["action"]] = row["count"]

        tier_config = self.get_tier_config(user_id)
        sub = self.get_subscription(user_id)

        return {
            "tier": sub["tier"],
            "status": sub["status"],
            "messages_today": usage.get("message", 0),
            "messages_limit": tier_config["messages_per_day"],
            "voice_today": usage.get("voice", 0),
            "voice_limit": tier_config["voice_per_day"],
            "image_today": usage.get("image", 0),
            "image_limit": tier_config["image_per_day"],
            "date": today,
        }

    def check_limits(self, user_id: str, action: str) -> Tuple[bool, str]:
        """
        Check if user can perform an action.
        Returns (allowed, reason).
        """
        if action not in ACTION_LIMIT_MAP:
            return True, "ok"

        tier_config = self.get_tier_config(user_id)
        limit_key = ACTION_LIMIT_MAP[action]
        limit = tier_config[limit_key]

        # -1 means unlimited
        if limit == -1:
            return True, "ok"

        # Check today's usage
        today = self._today_str()
        with self._lock:
            row = self._conn.execute(
                "SELECT count FROM usage WHERE user_id = ? AND action = ? AND date = ?",
                (user_id, action, today),
            ).fetchone()

        current = row["count"] if row else 0
        tier_name = tier_config["name"]

        if current >= limit:
            friendly_action = {
                "message": "messages",
                "voice": "voice messages",
                "image": "image analyses",
            }.get(action, action)
            reason = (
                f"You've used all {limit} {friendly_action} for today on the {tier_name} plan! "
                f"Upgrade for more 😊"
            )
            return False, reason

        return True, "ok"

    def check_feature(self, user_id: str, feature: str) -> bool:
        """Check if a feature is available on the user's tier."""
        tier_config = self.get_tier_config(user_id)
        return tier_config.get(feature, False)

    def check_memory_limit(self, user_id: str, current_count: int) -> Tuple[bool, str]:
        """Check if user can store more memories."""
        tier_config = self.get_tier_config(user_id)
        limit = tier_config["memory_slots"]

        if limit == -1:
            return True, "ok"

        if current_count >= limit:
            return False, (
                f"You've reached the {limit} memory limit on the {tier_config['name']} plan! "
                f"Upgrade for more memory slots 😊"
            )

        return True, "ok"

    # ─── Cleanup ─────────────────────────────────────────────

    def close(self):
        """Close the database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
