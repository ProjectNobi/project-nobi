"""
Project Nobi — Proactive Outreach Engine
==========================================
Generates reasons for Nori to reach out to users first.

Trigger types:
  - birthday   — Birthday reminders from memory/graph
  - follow_up  — Contextual follow-ups on emotional/event memories
  - check_in   — Haven't heard from you in a while
  - milestone  — Chat anniversary milestones
  - encouragement — Warm check-ins based on graph context

Rate-limited: max 1 proactive message per user per 24h,
quiet hours enforced (22:00–08:00), and no messages if
the user was active in the last 2 hours.
"""

import os
import re
import json
import sqlite3
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger("nobi-proactive")


# ── Data Classes ──────────────────────────────────────────────

@dataclass
class ProactiveTrigger:
    """A reason for Nori to reach out to a user."""
    user_id: str
    trigger_type: str       # birthday, follow_up, check_in, milestone, encouragement
    priority: int           # 1=high, 2=medium, 3=low
    context: str            # Relevant info for message generation
    reason: str             # Why we're reaching out


# ── Date Parsing Helpers ──────────────────────────────────────

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def parse_birthday(text: str) -> Optional[tuple]:
    """
    Parse a birthday from text. Returns (month, day) or None.

    Supports:
      - "March 15", "15 March", "march 15th"
      - "15/03", "03/15", "03-15", "15-03"
      - "1990-03-15" (ISO)
    """
    if not text:
        return None

    text = text.strip().lower()

    # Pattern 1: "Month Day" or "Month Day, Year"
    m = re.search(
        r'\b(' + '|'.join(_MONTH_NAMES.keys()) + r')\s+(\d{1,2})(?:st|nd|rd|th)?\b',
        text,
    )
    if m:
        month = _MONTH_NAMES[m.group(1)]
        day = int(m.group(2))
        if 1 <= day <= 31:
            return (month, day)

    # Pattern 2: "Day Month" — "15 March", "15th of March"
    m = re.search(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(' + '|'.join(_MONTH_NAMES.keys()) + r')\b',
        text,
    )
    if m:
        day = int(m.group(1))
        month = _MONTH_NAMES[m.group(2)]
        if 1 <= day <= 31:
            return (month, day)

    # Pattern 3: ISO "YYYY-MM-DD"
    m = re.search(r'\b\d{4}-(\d{2})-(\d{2})\b', text)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return (month, day)

    # Pattern 4: "DD/MM" or "MM-DD" (ambiguous — try MM/DD first, then DD/MM)
    m = re.search(r'\b(\d{1,2})[/\-](\d{1,2})\b', text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # If first > 12, it's DD/MM
        if a > 12 and 1 <= b <= 12 and 1 <= a <= 31:
            return (b, a)
        # Otherwise treat as MM/DD (US format)
        if 1 <= a <= 12 and 1 <= b <= 31:
            return (a, b)

    return None


# ── Follow-up Keywords ────────────────────────────────────────

_EVENT_KEYWORDS = [
    "interview", "exam", "test", "meeting", "appointment",
    "trip", "travel", "surgery", "operation", "presentation",
    "deadline", "audition", "date", "move", "moving",
    "wedding", "graduation", "concert", "flight",
]

_EMOTION_KEYWORDS = [
    "stressed", "anxious", "worried", "nervous", "scared",
    "excited", "thrilled", "happy", "sad", "depressed",
    "overwhelmed", "frustrated", "angry", "upset", "lonely",
]


# ── Proactive Engine ─────────────────────────────────────────

class ProactiveEngine:
    """
    Checks user memories/graph for proactive outreach opportunities.
    Rate-limited, quiet-hours-aware, and opt-in/out configurable.
    """

    # Days thresholds
    CHECK_IN_DAYS = 3       # No activity for 3+ days → check-in
    FOLLOW_UP_MIN_DAYS = 1  # Follow up on events/emotions from 1–3 days ago
    FOLLOW_UP_MAX_DAYS = 3
    MILESTONE_DAYS = [7, 30, 60, 90, 180, 365]  # Chat anniversaries

    def __init__(self, memory_manager, memory_graph=None):
        """
        Args:
            memory_manager: MemoryManager instance.
            memory_graph: Optional MemoryGraph instance. If None, uses
                          memory_manager.graph if available.
        """
        self.memory = memory_manager
        self.graph = memory_graph or getattr(memory_manager, "graph", None)
        self._local = threading.local()
        self._init_proactive_tables()

    # ── DB helpers ────────────────────────────────────────────

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local SQLite connection (reuses memory manager's DB)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.memory.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_proactive_tables(self):
        """Create proactive-specific tables."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS proactive_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                message TEXT DEFAULT '',
                sent_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_proactive_user
                ON proactive_log(user_id, sent_at);

            CREATE TABLE IF NOT EXISTS proactive_settings (
                user_id TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 1,
                timezone TEXT DEFAULT 'UTC',
                updated_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    # ── Settings (opt-in / opt-out) ──────────────────────────

    def is_opted_in(self, user_id: str) -> bool:
        """Check if user has proactive messages enabled (default: True)."""
        row = self._conn.execute(
            "SELECT enabled FROM proactive_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return bool(row["enabled"]) if row else True  # default ON

    def set_opted_in(self, user_id: str, enabled: bool):
        """Set user's proactive message preference."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO proactive_settings (user_id, enabled, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               enabled = excluded.enabled, updated_at = excluded.updated_at""",
            (user_id, int(enabled), now),
        )
        self._conn.commit()

    def get_user_timezone(self, user_id: str) -> str:
        """Get user's timezone string (default: 'UTC')."""
        row = self._conn.execute(
            "SELECT timezone FROM proactive_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["timezone"] if row and row["timezone"] else "UTC"

    def set_user_timezone(self, user_id: str, tz: str):
        """Set user's timezone."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO proactive_settings (user_id, enabled, timezone, updated_at)
               VALUES (?, 1, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               timezone = excluded.timezone, updated_at = excluded.updated_at""",
            (user_id, tz, now),
        )
        self._conn.commit()

    # ── Rate Limiting ────────────────────────────────────────

    def _last_proactive_sent(self, user_id: str) -> Optional[datetime]:
        """Get the datetime of the last proactive message sent to this user."""
        row = self._conn.execute(
            "SELECT sent_at FROM proactive_log WHERE user_id = ? ORDER BY sent_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row and row["sent_at"]:
            try:
                return datetime.fromisoformat(row["sent_at"])
            except (ValueError, TypeError):
                pass
        return None

    def _last_user_interaction(self, user_id: str) -> Optional[datetime]:
        """Get last user interaction time from user_profiles."""
        row = self._conn.execute(
            "SELECT last_seen FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and row["last_seen"]:
            try:
                return datetime.fromisoformat(row["last_seen"])
            except (ValueError, TypeError):
                pass
        return None

    def _first_user_seen(self, user_id: str) -> Optional[datetime]:
        """Get first user interaction time from user_profiles."""
        row = self._conn.execute(
            "SELECT first_seen FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row and row["first_seen"]:
            try:
                return datetime.fromisoformat(row["first_seen"])
            except (ValueError, TypeError):
                pass
        return None

    def _is_quiet_hours(self, user_id: str, now: Optional[datetime] = None) -> bool:
        """
        Check if it's quiet hours (22:00–08:00) in the user's timezone.
        Only supports UTC offset-based checking for simplicity.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        # For simplicity, we only apply quiet hours in UTC
        # A more complete implementation would parse timezone offsets
        hour = now.hour
        return hour >= 22 or hour < 8

    def should_reach_out(self, user_id: str, now: Optional[datetime] = None) -> bool:
        """
        Check all rate-limiting conditions:
          - User is opted in
          - Max 1 proactive message per 24h
          - User hasn't interacted in the last 2h (they're active)
          - Not quiet hours (22:00–08:00)
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # 1. Opt-in check
        if not self.is_opted_in(user_id):
            return False

        # 2. Quiet hours
        if self._is_quiet_hours(user_id, now):
            return False

        # 3. Max 1 per 24h
        last_sent = self._last_proactive_sent(user_id)
        if last_sent:
            # Ensure timezone-aware comparison
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            if (now - last_sent) < timedelta(hours=24):
                return False

        # 4. No message if user was active in last 2h
        last_active = self._last_user_interaction(user_id)
        if last_active:
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            if (now - last_active) < timedelta(hours=2):
                return False

        return True

    def mark_sent(self, user_id: str, trigger_type: str, message: str = ""):
        """Record that a proactive message was sent."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO proactive_log (user_id, trigger_type, message, sent_at) VALUES (?, ?, ?, ?)",
            (user_id, trigger_type, message, now),
        )
        self._conn.commit()

    # ── Trigger Checks ───────────────────────────────────────

    def check_triggers(self, user_id: str, now: Optional[datetime] = None) -> List[ProactiveTrigger]:
        """
        Check all trigger types for a user. Returns list of triggers
        sorted by priority (highest first).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        triggers: List[ProactiveTrigger] = []

        try:
            # Birthday check
            bday = self._check_birthday(user_id, now)
            if bday:
                triggers.append(bday)

            # Follow-up check
            followups = self._check_follow_ups(user_id, now)
            triggers.extend(followups)

            # Check-in
            checkin = self._check_check_in(user_id, now)
            if checkin:
                triggers.append(checkin)

            # Milestone
            milestone = self._check_milestone(user_id, now)
            if milestone:
                triggers.append(milestone)

            # Encouragement
            encouragement = self._check_encouragement(user_id, now)
            if encouragement:
                triggers.append(encouragement)

        except Exception as e:
            logger.error(f"[Proactive] Error checking triggers for {user_id}: {e}")

        # Sort by priority (1=highest)
        triggers.sort(key=lambda t: t.priority)
        return triggers

    def _check_birthday(self, user_id: str, now: datetime) -> Optional[ProactiveTrigger]:
        """Check if today is the user's birthday."""
        birthday_date = None

        # Check graph for born_on relationship
        if self.graph is not None:
            try:
                rels = self.graph.get_relationships(user_id, "user")
                for rel in rels:
                    if rel.get("relationship_type") == "born_on":
                        parsed = parse_birthday(rel.get("target", ""))
                        if parsed:
                            birthday_date = parsed
                            break
            except Exception as e:
                logger.debug(f"[Proactive] Graph birthday check error: {e}")

        # Check memories for birthday info
        if birthday_date is None:
            try:
                memories = self.memory.recall(
                    user_id, query="birthday born", limit=10, use_semantic=False,
                )
                for mem in memories:
                    content = mem.get("content", "")
                    parsed = parse_birthday(content)
                    if parsed:
                        birthday_date = parsed
                        break
            except Exception as e:
                logger.debug(f"[Proactive] Memory birthday check error: {e}")

        if birthday_date is None:
            return None

        month, day = birthday_date
        if now.month == month and now.day == day:
            return ProactiveTrigger(
                user_id=user_id,
                trigger_type="birthday",
                priority=1,
                context=f"Birthday: {month}/{day}",
                reason="Today is the user's birthday!",
            )

        return None

    def _check_follow_ups(self, user_id: str, now: datetime) -> List[ProactiveTrigger]:
        """Check for emotional/event memories from 1–3 days ago worth following up on."""
        triggers = []

        try:
            # Get recent memories
            memories = self.memory.recall(user_id, limit=30, use_semantic=False)
        except Exception:
            return triggers

        for mem in memories:
            try:
                created = datetime.fromisoformat(mem.get("created_at", ""))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            age_days = (now - created).total_seconds() / 86400.0
            if not (self.FOLLOW_UP_MIN_DAYS <= age_days <= self.FOLLOW_UP_MAX_DAYS):
                continue

            content_lower = mem.get("content", "").lower()
            mem_type = mem.get("type", "")

            # Event-based follow-ups
            for kw in _EVENT_KEYWORDS:
                if kw in content_lower:
                    triggers.append(ProactiveTrigger(
                        user_id=user_id,
                        trigger_type="follow_up",
                        priority=2,
                        context=mem.get("content", ""),
                        reason=f"User mentioned '{kw}' {age_days:.0f} day(s) ago",
                    ))
                    break

            # Emotion-based follow-ups
            if mem_type == "emotion" or any(kw in content_lower for kw in _EMOTION_KEYWORDS):
                triggers.append(ProactiveTrigger(
                    user_id=user_id,
                    trigger_type="follow_up",
                    priority=2,
                    context=mem.get("content", ""),
                    reason=f"User expressed emotion {age_days:.0f} day(s) ago",
                ))

        # Deduplicate — only keep first follow-up trigger
        if triggers:
            triggers = [triggers[0]]

        return triggers

    def _check_check_in(self, user_id: str, now: datetime) -> Optional[ProactiveTrigger]:
        """Check if user hasn't been active for CHECK_IN_DAYS+ days."""
        last_active = self._last_user_interaction(user_id)
        if last_active is None:
            return None

        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)

        days_inactive = (now - last_active).total_seconds() / 86400.0

        if days_inactive >= self.CHECK_IN_DAYS:
            return ProactiveTrigger(
                user_id=user_id,
                trigger_type="check_in",
                priority=3,
                context=f"Last active {days_inactive:.0f} days ago",
                reason=f"Haven't heard from user in {days_inactive:.0f} days",
            )
        return None

    def _check_milestone(self, user_id: str, now: datetime) -> Optional[ProactiveTrigger]:
        """Check if today is a chat anniversary milestone."""
        first_seen = self._first_user_seen(user_id)
        if first_seen is None:
            return None

        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=timezone.utc)

        days_chatting = int((now - first_seen).total_seconds() / 86400.0)

        for milestone in self.MILESTONE_DAYS:
            if days_chatting == milestone:
                return ProactiveTrigger(
                    user_id=user_id,
                    trigger_type="milestone",
                    priority=3,
                    context=f"{milestone} days since first chat",
                    reason=f"Chat milestone: {milestone} days!",
                )
        return None

    def _check_encouragement(self, user_id: str, now: datetime) -> Optional[ProactiveTrigger]:
        """
        Generate encouragement triggers based on graph context
        (work, study, hobbies).
        """
        if self.graph is None:
            return None

        try:
            rels = self.graph.get_relationships(user_id, "user")
        except Exception:
            return None

        for rel in rels:
            rtype = rel.get("relationship_type", "")
            target = rel.get("target", "")

            if rtype in ("works_as", "works_at", "studies", "studies_at"):
                # Only send encouragement if user hasn't been active in 1+ day
                last_active = self._last_user_interaction(user_id)
                if last_active:
                    if last_active.tzinfo is None:
                        last_active = last_active.replace(tzinfo=timezone.utc)
                    days_inactive = (now - last_active).total_seconds() / 86400.0
                    if days_inactive < 1:
                        continue

                label = {
                    "works_as": "work",
                    "works_at": "work",
                    "studies": "studies",
                    "studies_at": "studies",
                }.get(rtype, "activities")

                return ProactiveTrigger(
                    user_id=user_id,
                    trigger_type="encouragement",
                    priority=3,
                    context=f"{rtype}: {target}",
                    reason=f"Encouragement about their {label}",
                )
        return None

    # ── Message Generation ────────────────────────────────────

    def generate_message(self, trigger: ProactiveTrigger) -> str:
        """
        Generate a natural, warm proactive message for the given trigger.
        Returns plain text (no markdown).
        """
        t = trigger.trigger_type
        ctx = trigger.context

        if t == "birthday":
            return (
                "Happy birthday! 🎂🎉\n"
                "I hope today is filled with awesome moments! "
                "Got any fun plans?"
            )

        if t == "follow_up":
            # Try to extract what to follow up on
            ctx_lower = ctx.lower()
            for kw in _EVENT_KEYWORDS:
                if kw in ctx_lower:
                    return (
                        f"Hey! I was thinking about you. "
                        f"How did that {kw} go? 😊"
                    )
            # Generic emotional follow-up
            return (
                "Hey! Just checking in. "
                "How are you doing since we last talked? 💙"
            )

        if t == "check_in":
            return (
                "Hey! Haven't heard from you in a while. "
                "How are things going? 😊"
            )

        if t == "milestone":
            # Extract days from context
            m = re.search(r'(\d+)\s+days', ctx)
            days = m.group(1) if m else "a while"
            return (
                f"Fun fact: we've been chatting for {days} days now! 🎉\n"
                "Thanks for hanging out with me. How's life?"
            )

        if t == "encouragement":
            # Extract what they do
            parts = ctx.split(":", 1)
            activity = parts[1].strip() if len(parts) > 1 else "everything"
            return (
                f"Just thinking about you! "
                f"Hope your {activity} is going well. "
                "You've got this! 💪"
            )

        # Fallback
        return "Hey! Just wanted to check in. How's everything going? 😊"

    # ── Pending Outreach ─────────────────────────────────────

    def get_pending_outreach(self, now: Optional[datetime] = None) -> List[dict]:
        """
        Check all known users and return a list of pending outreach items.
        Each item: {"user_id", "trigger", "message"}.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        results = []

        # Get all known user IDs from user_profiles
        try:
            rows = self._conn.execute("SELECT user_id FROM user_profiles").fetchall()
        except Exception:
            return results

        for row in rows:
            uid = row["user_id"]

            if not self.should_reach_out(uid, now):
                continue

            triggers = self.check_triggers(uid, now)
            if not triggers:
                continue

            # Pick highest priority trigger
            best = triggers[0]
            message = self.generate_message(best)

            results.append({
                "user_id": uid,
                "trigger": best,
                "message": message,
            })

        return results
