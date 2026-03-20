"""
Project Nobi — Timezone Detection & Scheduling
================================================
Detects user timezone from message clues (greetings, time references,
location mentions, explicit timezone strings) and provides timezone-aware
scheduling helpers (quiet hours, best send time, local hour).
"""

import re
import sqlite3
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger("nobi-timezone")


# ── Timezone offset maps ──────────────────────────────────────

# Greeting → expected local hour ranges
_GREETING_HOURS: Dict[str, tuple] = {
    "good morning": (5, 11),
    "morning": (5, 11),
    "good afternoon": (12, 17),
    "good evening": (17, 21),
    "good night": (21, 4),       # wraps around midnight
    "gm": (5, 11),               # crypto/internet "gm"
}

# Named timezone abbreviations → UTC offset in hours
_TZ_ABBREVIATIONS: Dict[str, int] = {
    "utc": 0, "gmt": 0,
    "est": -5, "edt": -4,
    "cst": -6, "cdt": -5,
    "mst": -7, "mdt": -6,
    "pst": -8, "pdt": -7,
    "ist": 5,   # India (5:30 rounded)
    "jst": 9,   # Japan
    "kst": 9,   # Korea
    "cet": 1,   # Central European
    "cest": 2,  # Central European Summer
    "eet": 2,   # Eastern European
    "eest": 3,  # Eastern European Summer
    "aest": 10, # Australian Eastern Standard
    "aedt": 11, # Australian Eastern Daylight
    "awst": 8,  # Australian Western Standard
    "nzst": 12, # New Zealand Standard
    "nzdt": 13, # New Zealand Daylight
    "hkt": 8,   # Hong Kong
    "sgt": 8,   # Singapore
    "wib": 7,   # Western Indonesia
    "wit": 9,   # Eastern Indonesia
    "brt": -3,  # Brasília
    "art": -3,  # Argentina
}

# City/country → UTC offset
_LOCATION_OFFSETS: Dict[str, int] = {
    "london": 0, "uk": 0, "britain": 0, "england": 0,
    "new york": -5, "nyc": -5, "boston": -5, "miami": -5,
    "los angeles": -8, "la": -8, "san francisco": -8, "seattle": -8,
    "chicago": -6, "dallas": -6, "houston": -6,
    "denver": -7, "phoenix": -7,
    "tokyo": 9, "japan": 9, "osaka": 9,
    "seoul": 9, "korea": 9,
    "beijing": 8, "shanghai": 8, "china": 8, "hong kong": 8,
    "singapore": 8,
    "bangkok": 7, "thailand": 7, "vietnam": 7, "hanoi": 7, "ho chi minh": 7, "saigon": 7,
    "jakarta": 7, "indonesia": 7,
    "mumbai": 5, "delhi": 5, "india": 5, "bangalore": 5,
    "dubai": 4, "abu dhabi": 4,
    "moscow": 3, "russia": 3,
    "paris": 1, "berlin": 1, "amsterdam": 1, "rome": 1, "madrid": 1,
    "france": 1, "germany": 1, "italy": 1, "spain": 1, "netherlands": 1,
    "sydney": 10, "melbourne": 10, "australia": 10,
    "auckland": 12, "new zealand": 12,
    "toronto": -5, "canada": -5, "vancouver": -8, "montreal": -5,
    "são paulo": -3, "sao paulo": -3, "rio": -3, "brazil": -3,
    "cairo": 2, "egypt": 2,
    "nairobi": 3, "kenya": 3,
    "lagos": 1, "nigeria": 1,
    "johannesburg": 2, "south africa": 2,
    "manila": 8, "philippines": 8,
    "taipei": 8, "taiwan": 8,
    "kuala lumpur": 8, "malaysia": 8,
}


def _offset_to_tz_string(offset_hours: int) -> str:
    """Convert integer offset to 'UTC+X' or 'UTC-X' string."""
    if offset_hours == 0:
        return "UTC"
    sign = "+" if offset_hours > 0 else "-"
    return f"UTC{sign}{abs(offset_hours)}"


def _parse_tz_offset(tz_str: str) -> Optional[int]:
    """Parse a timezone string like 'UTC+8', 'UTC-5', 'UTC' → offset int."""
    if not tz_str:
        return None
    tz_str = tz_str.strip().upper()
    if tz_str == "UTC":
        return 0
    m = re.match(r'^UTC([+-])(\d{1,2})$', tz_str)
    if m:
        sign = 1 if m.group(1) == '+' else -1
        return sign * int(m.group(2))
    return None


class TimezoneDetector:
    """
    Detects user timezone from messages and provides timezone-aware
    helpers for the proactive engine.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Path to SQLite DB. If None, uses in-memory DB.
        """
        self._db_path = db_path or ":memory:"
        self._local = threading.local()
        self._init_tables()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS user_timezone (
                user_id TEXT PRIMARY KEY,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                confidence REAL NOT NULL DEFAULT 0.0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_active_hours (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                utc_hour INTEGER NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_active_hours_user
                ON user_active_hours(user_id);
        """)
        self._conn.commit()

    # ── Core Detection ────────────────────────────────────────

    def detect_from_message(self, message: str, current_utc_hour: int) -> Optional[str]:
        """
        Try all detection methods on a message. Returns 'UTC+X' string or None.
        Tries: explicit tz → time reference → greeting → location.
        """
        if not message:
            return None

        msg_lower = message.lower().strip()

        # 1. Explicit UTC offset: "I'm UTC+8", "my timezone is UTC-5" (check before abbreviations)
        m = re.search(r'utc\s*([+-]\s*\d{1,2})', msg_lower)
        if m:
            offset = int(m.group(1).replace(" ", ""))
            if -12 <= offset <= 14:
                return _offset_to_tz_string(offset)

        # 2. Explicit timezone abbreviation: "I'm EST", "PST time", "my timezone is CET"
        result = self._detect_explicit_tz(msg_lower)
        if result is not None:
            return result

        # 3. Time reference: "it's 3pm here", "it's 21:00"
        result = self._detect_from_time_ref(msg_lower, current_utc_hour)
        if result is not None:
            return result

        # 4. Greeting-based detection
        result = self.detect_from_greeting(msg_lower, current_utc_hour)
        if result is not None:
            return result

        # 5. Location-based detection
        result = self._detect_from_location(msg_lower)
        if result is not None:
            return result

        return None

    def _detect_explicit_tz(self, msg_lower: str) -> Optional[str]:
        """Detect explicit timezone abbreviation mentions."""
        # Patterns like "I'm EST", "I'm in PST", "my timezone is CET"
        for abbr, offset in _TZ_ABBREVIATIONS.items():
            # Match the abbreviation as a standalone word
            pattern = r'\b' + re.escape(abbr) + r'\b'
            if re.search(pattern, msg_lower):
                # Avoid false positives for common words
                if abbr in ("ist", "art", "wit") and not any(
                    kw in msg_lower for kw in ("timezone", "time zone", "i'm", "i am", "my time")
                ):
                    continue
                return _offset_to_tz_string(offset)
        return None

    def _detect_from_time_ref(self, msg_lower: str, current_utc_hour: int) -> Optional[str]:
        """Detect timezone from time references like 'it's 3pm here'."""
        # Pattern: "it's Xpm/am", "it is X:XX", "X o'clock here"
        patterns = [
            # "it's 3pm" / "it's 3 pm" / "it is 15:00"
            r"it(?:'s| is)\s+(\d{1,2})\s*([ap]m)",
            r"it(?:'s| is)\s+(\d{1,2}):(\d{2})\s*(?:here|now)?",
            r"(\d{1,2})\s*([ap]m)\s+here",
            r"(\d{1,2}):(\d{2})\s+here",
        ]

        for pat in patterns:
            m = re.search(pat, msg_lower)
            if m:
                groups = m.groups()
                local_hour = None

                if len(groups) == 2 and groups[1] in ("am", "pm"):
                    h = int(groups[0])
                    if 1 <= h <= 12:
                        if groups[1] == "pm" and h != 12:
                            local_hour = h + 12
                        elif groups[1] == "am" and h == 12:
                            local_hour = 0
                        else:
                            local_hour = h
                elif len(groups) == 2:
                    h = int(groups[0])
                    if 0 <= h <= 23:
                        local_hour = h

                if local_hour is not None:
                    offset = (local_hour - current_utc_hour) % 24
                    # Normalize to -12..+13
                    if offset > 13:
                        offset -= 24
                    return _offset_to_tz_string(offset)

        return None

    def detect_from_greeting(self, message: str, current_utc_hour: int) -> Optional[str]:
        """
        Detect timezone from time-of-day greetings.
        E.g., "good morning" at UTC 14:00 → user is ~UTC+8 (morning = 6-10).
        """
        msg_lower = message.lower().strip() if isinstance(message, str) else message

        for greeting, (start_hour, end_hour) in _GREETING_HOURS.items():
            if greeting in msg_lower:
                # Use midpoint of expected local hour range
                if start_hour <= end_hour:
                    mid = (start_hour + end_hour) // 2
                else:
                    # Wraps around midnight (e.g., good night: 21-4)
                    mid = ((start_hour + end_hour + 24) // 2) % 24

                offset = (mid - current_utc_hour) % 24
                if offset > 13:
                    offset -= 24
                return _offset_to_tz_string(offset)

        return None

    def _detect_from_location(self, msg_lower: str) -> Optional[str]:
        """Detect timezone from location mentions."""
        # Patterns: "I'm in London", "I live in Tokyo", "from New York"
        location_patterns = [
            r"i(?:'m| am) (?:in|from|based in|living in)\s+(.+?)(?:\.|,|!|\?|$)",
            r"i live in\s+(.+?)(?:\.|,|!|\?|$)",
            r"(?:located|based) in\s+(.+?)(?:\.|,|!|\?|$)",
        ]

        for pat in location_patterns:
            m = re.search(pat, msg_lower)
            if m:
                location = m.group(1).strip().lower()
                # Check each known location
                for loc_name, offset in _LOCATION_OFFSETS.items():
                    if loc_name in location or location in loc_name:
                        return _offset_to_tz_string(offset)

        # Direct location mention without "I'm in" prefix
        for loc_name, offset in sorted(_LOCATION_OFFSETS.items(), key=lambda x: -len(x[0])):
            if len(loc_name) > 3 and loc_name in msg_lower:
                # Only match if it's near location-related words
                if any(kw in msg_lower for kw in ("from", "in", "live", "based", "timezone", "time")):
                    return _offset_to_tz_string(offset)

        return None

    # ── Storage ───────────────────────────────────────────────

    def get_user_timezone(self, user_id: str) -> str:
        """Get stored timezone for user, or 'UTC' if unknown."""
        row = self._conn.execute(
            "SELECT timezone FROM user_timezone WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["timezone"] if row else "UTC"

    def set_user_timezone(self, user_id: str, tz: str):
        """Store timezone for user."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT INTO user_timezone (user_id, timezone, confidence, updated_at)
               VALUES (?, ?, 1.0, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               timezone = excluded.timezone, confidence = excluded.confidence,
               updated_at = excluded.updated_at""",
            (user_id, tz, now),
        )
        self._conn.commit()

    def update_timezone_from_message(self, user_id: str, message: str, current_utc_hour: int):
        """
        Attempt to detect timezone from message and update if found.
        Only updates if new detection has higher or equal confidence.
        """
        detected = self.detect_from_message(message, current_utc_hour)
        if detected:
            self.set_user_timezone(user_id, detected)

    # ── Active Hours Tracking ─────────────────────────────────

    def record_activity(self, user_id: str, utc_hour: Optional[int] = None):
        """Record that a user was active at this UTC hour."""
        if utc_hour is None:
            utc_hour = datetime.now(timezone.utc).hour
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO user_active_hours (user_id, utc_hour, recorded_at) VALUES (?, ?, ?)",
            (user_id, utc_hour, now),
        )
        self._conn.commit()

    def get_active_hours(self, user_id: str) -> List[int]:
        """
        Get the user's most common active UTC hours (sorted by frequency, descending).
        Returns list of UTC hour integers.
        """
        rows = self._conn.execute(
            """SELECT utc_hour, COUNT(*) as cnt
               FROM user_active_hours WHERE user_id = ?
               GROUP BY utc_hour ORDER BY cnt DESC""",
            (user_id,),
        ).fetchall()
        return [row["utc_hour"] for row in rows]

    # ── Time Helpers ──────────────────────────────────────────

    def get_local_hour(self, user_id: str, utc_now: Optional[datetime] = None) -> int:
        """Get current local hour for user based on their stored timezone."""
        if utc_now is None:
            utc_now = datetime.now(timezone.utc)
        tz_str = self.get_user_timezone(user_id)
        offset = _parse_tz_offset(tz_str)
        if offset is None:
            offset = 0
        return (utc_now.hour + offset) % 24

    def is_quiet_hours(self, user_id: str, utc_now: Optional[datetime] = None) -> bool:
        """Check if it's quiet hours (22:00-08:00) in the user's local timezone."""
        local_hour = self.get_local_hour(user_id, utc_now)
        return local_hour >= 22 or local_hour < 8

    def get_best_send_time(self, user_id: str) -> int:
        """
        Get the best UTC hour to send a proactive message.
        Prefers user's most active hours that aren't during quiet hours.
        Falls back to 10:00 local time.
        """
        active_hours = self.get_active_hours(user_id)
        tz_str = self.get_user_timezone(user_id)
        offset = _parse_tz_offset(tz_str) or 0

        # Filter active hours that aren't during quiet hours
        for utc_hour in active_hours:
            local_hour = (utc_hour + offset) % 24
            if 8 <= local_hour < 22:
                return utc_hour

        # Fallback: 10:00 local time
        return (10 - offset) % 24
