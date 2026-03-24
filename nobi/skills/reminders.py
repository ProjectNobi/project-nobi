"""
Reminders skill for Nori — stores reminders in SQLite and delivers them via Telegram.
"""
import asyncio
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger("nobi-skills-reminders")

# Default DB path (mirrors MemoryManager)
_DEFAULT_DB = os.path.expanduser("~/.nobi/bot_memories.db")


class ReminderManager:
    """Manages reminder storage and background delivery."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create reminders table if it doesn't exist."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        reminder_text TEXT NOT NULL,
                        remind_at REAL NOT NULL,
                        created_at REAL NOT NULL,
                        delivered INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(remind_at, delivered)")
                conn.commit()
            finally:
                conn.close()

    def store(self, user_id: str, reminder_text: str, remind_at: datetime) -> int:
        """Store a new reminder. Returns the reminder ID."""
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "INSERT INTO reminders (user_id, reminder_text, remind_at, created_at, delivered) VALUES (?, ?, ?, ?, 0)",
                    (user_id, reminder_text, remind_at.timestamp(), now),
                )
                conn.commit()
                return cur.lastrowid
            finally:
                conn.close()

    def get_pending(self, user_id: str) -> List[dict]:
        """Get all pending (undelivered) reminders for a user, ordered by time."""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT id, reminder_text, remind_at FROM reminders "
                    "WHERE user_id = ? AND delivered = 0 ORDER BY remind_at ASC",
                    (user_id,),
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "text": r["reminder_text"],
                        "remind_at": datetime.fromtimestamp(r["remind_at"], tz=timezone.utc),
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def get_due(self) -> List[dict]:
        """Get all due reminders (remind_at <= now, not yet delivered)."""
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT id, user_id, reminder_text, remind_at FROM reminders "
                    "WHERE delivered = 0 AND remind_at <= ?",
                    (now,),
                ).fetchall()
                return [
                    {
                        "id": r["id"],
                        "user_id": r["user_id"],
                        "text": r["reminder_text"],
                        "remind_at": datetime.fromtimestamp(r["remind_at"], tz=timezone.utc),
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def mark_delivered(self, reminder_id: int):
        """Mark a reminder as delivered."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("UPDATE reminders SET delivered = 1 WHERE id = ?", (reminder_id,))
                conn.commit()
            finally:
                conn.close()

    def delete(self, reminder_id: int, user_id: str) -> bool:
        """Delete a specific reminder (only if owned by user_id)."""
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                    (reminder_id, user_id),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def format_pending_list(self, user_id: str) -> str:
        """Format a user's pending reminders as readable text."""
        pending = self.get_pending(user_id)
        if not pending:
            return "You have no pending reminders."

        lines = [f"Your reminders ({len(pending)} pending):\n"]
        for r in pending:
            dt = r["remind_at"]
            # Format: "Wed 25 Mar at 09:00 UTC"
            dt_str = dt.strftime("%a %d %b at %H:%M UTC")
            lines.append(f"• [{r['id']}] {r['text']} — {dt_str}")
        return "\n".join(lines)


# ── Time parsing ─────────────────────────────────────────────

_NOW_PATTERNS = [
    # "in X minutes/hours/days" OR "for X minutes/hours/days" OR "timer X minutes"
    (re.compile(r"\b(?:in|for)\s+(\d+)\s+min(?:ute)?s?", re.I), "minutes"),
    (re.compile(r"\b(?:in|for)\s+(\d+)\s+hours?", re.I), "hours"),
    (re.compile(r"\b(?:in|for)\s+(\d+)\s+days?", re.I), "days"),
    (re.compile(r"\b(?:in|for)\s+half\s+an?\s+hour", re.I), "half_hour"),
    (re.compile(r"\b(?:in|for)\s+an?\s+hour", re.I), "one_hour"),
    # "timer 10 minutes/mins"
    (re.compile(r"\btimer\s+(\d+)\s+min(?:ute)?s?", re.I), "minutes"),
    (re.compile(r"\btimer\s+(\d+)\s+hours?", re.I), "hours"),
]

_TIME_OF_DAY = re.compile(
    r"\b(?:at|for)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I
)

_TOMORROW = re.compile(r"\btomorrow\b", re.I)
_TODAY = re.compile(r"\btoday\b", re.I)
_NEXT_WEEK = re.compile(r"\bnext\s+week\b", re.I)

# Day name patterns
_DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}
_DAY_PATTERN = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b",
    re.I,
)


def parse_reminder_time(message: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse a natural language time expression from a reminder message.
    Returns a UTC datetime or None if parsing fails.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    msg = message.lower()

    # "in X minutes/hours/days"
    for pattern, unit in _NOW_PATTERNS:
        m = pattern.search(msg)
        if m:
            if unit == "half_hour":
                return now + timedelta(minutes=30)
            if unit == "one_hour":
                return now + timedelta(hours=1)
            n = int(m.group(1))
            if unit == "minutes":
                return now + timedelta(minutes=n)
            if unit == "hours":
                return now + timedelta(hours=n)
            if unit == "days":
                return now + timedelta(days=n)

    # Base date
    base_date = None

    if _TOMORROW.search(msg):
        base_date = (now + timedelta(days=1)).date()
    elif _NEXT_WEEK.search(msg):
        base_date = (now + timedelta(weeks=1)).date()
    elif _TODAY.search(msg):
        base_date = now.date()

    # Day names ("next Friday", "on Monday")
    day_match = _DAY_PATTERN.search(msg)
    if day_match and base_date is None:
        day_name = day_match.group(1).lower()
        target_weekday = _DAY_NAMES[day_name]
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # Next occurrence
        base_date = (now + timedelta(days=days_ahead)).date()

    # Time of day "at 9am", "at 14:30", "at 3pm"
    time_match = _TIME_OF_DAY.search(msg)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        ampm = time_match.group(3)

        if ampm:
            if ampm.lower() == "pm" and hour != 12:
                hour += 12
            elif ampm.lower() == "am" and hour == 12:
                hour = 0
        else:
            # No am/pm — use 24h but fix ambiguous small hours
            # e.g. "at 9" → 9am, "at 3" → 3pm (if >= current hour? heuristic)
            if hour < 7:
                hour += 12  # assume pm for early morning ambiguous times

        if base_date is None:
            base_date = now.date()

        target = datetime(
            base_date.year, base_date.month, base_date.day,
            hour, minute, 0, tzinfo=timezone.utc
        )
        # If the time has already passed today, add 1 day
        if target <= now and _TOMORROW.search(msg) is None:
            target += timedelta(days=1)
        return target

    # If we only got a base date (no time), default to 9am
    if base_date is not None:
        return datetime(
            base_date.year, base_date.month, base_date.day,
            9, 0, 0, tzinfo=timezone.utc
        )

    return None


def extract_reminder_text(message: str) -> str:
    """
    Extract the reminder content from the user's message.
    Strips trigger phrases like "remind me to", "remind me in 30 minutes to".
    """
    msg = message.strip()

    # Remove leading trigger
    msg = re.sub(
        r"^(?:please\s+)?(?:set\s+a\s+)?(?:remind(?:er)?|timer|alert|notify|ping)\s+(?:me\s+)?(?:to\s+)?",
        "",
        msg,
        flags=re.I,
    )

    # Remove time expressions from start/end
    time_patterns_to_strip = [
        r"^in\s+\d+\s+(?:minute|hour|day)s?\s*(?:to\s+)?",
        r"^in\s+(?:half\s+an?|an?)\s+hour\s*(?:to\s+)?",
        r"^tomorrow(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?\s*(?:to\s+)?",
        r"^(?:at|for)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*(?:to\s+)?",
        r"^next\s+week\s*(?:to\s+)?",
        # Strip time from end of string
        r"\s*(?:tomorrow|today|next\s+week)\s*(?:at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?$",
        r"\s*at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?$",
        r"\s*in\s+\d+\s+(?:minute|hour|day)s?$",
        r"\s*in\s+(?:half\s+an?|an?)\s+hour$",
    ]
    for pat in time_patterns_to_strip:
        msg = re.sub(pat, "", msg, flags=re.I).strip()

    # Remove trailing punctuation
    msg = msg.rstrip(".,!?").strip()

    return msg if msg else message.strip()


# ── Trigger detection ────────────────────────────────────────

_REMINDER_TRIGGER = re.compile(
    r"(?:remind\s+me|set\s+a\s+reminder|set\s+a\s+timer|remind\s+me\s+to|"
    r"don't\s+let\s+me\s+forget|timer\s+\d+\s*(?:min|hour|sec)|alert\s+me|notify\s+me|"
    r"wake\s+me|ping\s+me)",
    re.I,
)


def detect_reminder_query(message: str) -> bool:
    """Returns True if the message looks like a reminder request."""
    return bool(_REMINDER_TRIGGER.search(message))


def format_confirmation(text: str, remind_at: datetime) -> str:
    """Format a confirmation message for a stored reminder."""
    dt_str = remind_at.strftime("%A %d %b %Y at %H:%M UTC")
    return (
        f"Got it! I'll remind you to: {text}\n\n"
        f"When: {dt_str}\n\n"
        f"Use /reminders to see all your pending reminders."
    )


# ── Background task ──────────────────────────────────────────

async def reminder_delivery_loop(
    manager: ReminderManager,
    send_fn: Callable[[str, str], None],
    interval_seconds: int = 60,
):
    """
    Background asyncio task that checks for due reminders every `interval_seconds`.
    `send_fn(user_id, message)` is called for each due reminder.
    """
    logger.info(f"[Reminders] Delivery loop started (interval={interval_seconds}s)")
    while True:
        try:
            due = manager.get_due()
            for reminder in due:
                user_id = reminder["user_id"]
                text = reminder["text"]
                rid = reminder["id"]
                try:
                    msg = f"⏰ Reminder: {text}"
                    await send_fn(user_id, msg)
                    manager.mark_delivered(rid)
                    logger.info(f"[Reminders] Delivered reminder {rid} to {user_id}")
                except Exception as e:
                    logger.error(f"[Reminders] Failed to deliver reminder {rid} to {user_id}: {e}")
        except Exception as e:
            logger.error(f"[Reminders] Loop error: {e}")

        await asyncio.sleep(interval_seconds)
