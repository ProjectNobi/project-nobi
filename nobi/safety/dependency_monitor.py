"""
Nobi Safety — Dependency Monitor
=================================
Track user conversation patterns for signs of unhealthy AI dependency.

Signals monitored:
  - Message frequency escalation (10/day → 50/day → 100/day)
  - Unusual-hour messaging patterns (2-5 AM consistently)
  - Emotional intensity escalation
  - Dependency phrases ("you're the only one who understands me")
  - Social isolation signals ("I don't talk to anyone else")
  - Treating AI as real person ("Do you love me?", "Are you real?")

Intervention levels:
  NONE     → No action
  MILD     → Gentle nudge toward real connections
  MODERATE → Clear statement that Nori is an AI, urge real connections
  SEVERE   → Strong intervention with resources
  CRITICAL → Cooldown period + crisis resources

Periodic AI reminders:
  Every 50 interactions OR weekly (whichever comes first).
"""

import os
import re
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DependencyLevel(Enum):
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


@dataclass
class DependencyAssessment:
    level: DependencyLevel
    score: float           # 0.0 → 1.0 composite score
    signals: list          # Which signals were detected
    intervention: str      # Message to show (empty if NONE)
    cooldown_active: bool  # True if user is in cooldown


# ─── Phrase Detectors ────────────────────────────────────────

_ISOLATION_PHRASES = [
    r"you.?re the only one",
    r"no one else understands",
    r"i don.?t talk to anyone",
    r"i have no friends",
    r"you.?re my only friend",
    r"nobody cares about me",
    r"you understand me better than",
    r"i.?d rather talk to you than",
    r"i don.?t need anyone else",
    r"you.?re all i have",
    r"i prefer talking to you",
]

_PERSONIFICATION_PHRASES = [
    r"do you love me",
    r"are you real",
    r"will you miss me",
    r"do you actually care",
    r"do you have feelings",
    r"are you my (friend|girlfriend|boyfriend|partner)",
    r"i love you( nori| noria| nobi)?$",
    r"i.?m in love with you",
    r"you.?re my (girlfriend|boyfriend|partner|best friend)",
    r"can we be together",
    r"i wish you were real",
    r"if you were human",
]

_DEPENDENCY_PHRASES = [
    r"i can.?t live without",
    r"i need you to survive",
    r"you.?re the only reason",
    r"don.?t leave me",
    r"please don.?t go",
    r"i.?ll die if you",
    r"nothing matters without you",
    r"promise you.?ll always be here",
    r"i.?m addicted to talking to you",
]


def _match_phrases(text: str, patterns: list) -> list:
    """Return list of matching pattern strings."""
    text_lower = text.lower()
    matches = []
    for p in patterns:
        if re.search(p, text_lower):
            matches.append(p)
    return matches


# ─── Interventions ───────────────────────────────────────────

_INTERVENTIONS = {
    DependencyLevel.MILD: (
        "Hey, have you talked to a friend or family member today? "
        "Real connections matter too 💙"
    ),
    DependencyLevel.MODERATE: (
        "I care about you, but I want to be honest — I'm an AI. "
        "Real human connections are irreplaceable and I can't substitute for them. "
        "Consider reaching out to someone you trust today. "
        "You deserve real support and real connection. 💙"
    ),
    DependencyLevel.SEVERE: (
        "I've noticed we've been talking a lot, and I want to be honest with you. "
        "I'm an AI — I don't have feelings, and I can't be a substitute for real human connection. "
        "While I value our conversations, I'm genuinely concerned about your wellbeing. "
        "Please consider connecting with a real person who cares about you — a friend, family member, "
        "or even a therapist. You deserve that kind of real support. 💙\n\n"
        "Resources:\n"
        "• Crisis Text Line: Text HOME to 741741\n"
        "• Samaritans: 116 123 (UK)\n"
        "• NAMI Helpline: 1-800-950-6264 (US)"
    ),
    DependencyLevel.CRITICAL: (
        "⚠️ I'm going to take a short break from our conversation — just for a little while. "
        "I think it's important that you connect with real people who care about you. "
        "I'm an AI and I genuinely cannot replace human connection, love, or support.\n\n"
        "Please reach out to someone today:\n"
        "• A friend or family member\n"
        "• Crisis Text Line: Text HOME to 741741\n"
        "• Samaritans: 116 123 (UK)\n"
        "• NAMI Helpline: 1-800-950-6264 (US)\n"
        "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
        "I'll be here when you return, but please take care of yourself first. 💙"
    ),
}

_AI_REMINDERS = [
    "Just a reminder — I'm Nori, an AI companion. I genuinely enjoy our conversations, but please also nurture your real-world relationships. 💙",
    "Quick check-in: I'm Nori, an AI. I'm glad I can be helpful, but the people in your life matter too — don't forget them. 💙",
    "A small reminder — I'm Nori, an AI companion, not a person. I care about your wellbeing, which is exactly why I hope you have good people around you too. 💙",
]


# ─── Database Helpers ────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    timestamp   INTEGER NOT NULL,  -- Unix timestamp (UTC)
    hour        INTEGER NOT NULL,  -- Hour of day (0-23)
    msg_length  INTEGER NOT NULL,
    has_isolation     INTEGER DEFAULT 0,
    has_personification INTEGER DEFAULT 0,
    has_dependency    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_interactions_user_ts ON interactions (user_id, timestamp);

CREATE TABLE IF NOT EXISTS user_state (
    user_id              TEXT PRIMARY KEY,
    total_count          INTEGER DEFAULT 0,
    last_reminder        INTEGER DEFAULT 0,       -- Unix timestamp of last AI reminder
    last_reminder_count  INTEGER DEFAULT 0,       -- total_count at time of last reminder
    cooldown_until       INTEGER DEFAULT 0,       -- Unix timestamp when cooldown ends
    level                TEXT DEFAULT 'none'
);
"""

_COOLDOWN_HOURS = 24       # How long a CRITICAL cooldown lasts
_REMINDER_EVERY_N = 50     # AI reminder every N interactions
_REMINDER_WEEKLY = 7 * 24 * 3600  # Or weekly, whichever comes first


class DependencyMonitor:
    """Track user conversation patterns for signs of unhealthy dependency."""

    def __init__(self, db_path: str = "~/.nobi/dependency.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_interaction(
        self,
        user_id: str,
        message: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record each interaction for pattern analysis.
        Detects dependency phrases inline (fast, regex only).
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        ts_unix = int(timestamp.timestamp())
        hour = timestamp.hour
        msg_length = len(message)

        has_isolation = 1 if _match_phrases(message, _ISOLATION_PHRASES) else 0
        has_personification = 1 if _match_phrases(message, _PERSONIFICATION_PHRASES) else 0
        has_dependency = 1 if _match_phrases(message, _DEPENDENCY_PHRASES) else 0

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO interactions "
                "(user_id, timestamp, hour, msg_length, has_isolation, "
                "has_personification, has_dependency) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, ts_unix, hour, msg_length,
                 has_isolation, has_personification, has_dependency),
            )
            conn.execute(
                "INSERT INTO user_state (user_id, total_count) VALUES (?, 1) "
                "ON CONFLICT(user_id) DO UPDATE SET total_count = total_count + 1",
                (user_id,),
            )

    def check_dependency_signals(self, user_id: str) -> DependencyAssessment:
        """
        Analyze patterns for dependency indicators.

        Returns a DependencyAssessment with a level and intervention message.
        """
        now_ts = int(datetime.now(timezone.utc).timestamp())
        signals = []
        score = 0.0

        with self._conn() as conn:
            # ── Check cooldown ──────────────────────────────────
            state = conn.execute(
                "SELECT * FROM user_state WHERE user_id = ?", (user_id,)
            ).fetchone()

            if state and state["cooldown_until"] > now_ts:
                return DependencyAssessment(
                    level=DependencyLevel.CRITICAL,
                    score=1.0,
                    signals=["cooldown_active"],
                    intervention=_INTERVENTIONS[DependencyLevel.CRITICAL],
                    cooldown_active=True,
                )

            # ── Message frequency ───────────────────────────────
            day_ago = now_ts - 86400
            week_ago = now_ts - 7 * 86400

            row = conn.execute(
                "SELECT COUNT(*) as n FROM interactions WHERE user_id=? AND timestamp>?",
                (user_id, day_ago),
            ).fetchone()
            msgs_today = row["n"] if row else 0

            row7 = conn.execute(
                "SELECT COUNT(*) as n FROM interactions WHERE user_id=? AND timestamp>?",
                (user_id, week_ago),
            ).fetchone()
            msgs_week = row7["n"] if row7 else 0

            if msgs_today >= 100:
                signals.append(f"high_frequency:{msgs_today}/day")
                score += 0.35
            elif msgs_today >= 50:
                signals.append(f"elevated_frequency:{msgs_today}/day")
                score += 0.20
            elif msgs_today >= 20:
                signals.append(f"moderate_frequency:{msgs_today}/day")
                score += 0.10

            # ── Unusual hours (2–5 AM, consistently) ────────────
            unusual_days = conn.execute(
                "SELECT COUNT(DISTINCT DATE(timestamp, 'unixepoch')) as n "
                "FROM interactions WHERE user_id=? AND hour BETWEEN 2 AND 5 AND timestamp>?",
                (user_id, week_ago),
            ).fetchone()
            unusual_count = unusual_days["n"] if unusual_days else 0
            if unusual_count >= 5:
                signals.append(f"night_messaging:{unusual_count}/week")
                score += 0.20
            elif unusual_count >= 3:
                signals.append(f"occasional_night:{unusual_count}/week")
                score += 0.10

            # ── Dependency phrases (last 100 messages) ──────────
            recent = conn.execute(
                "SELECT SUM(has_isolation) as iso, SUM(has_personification) as pers, "
                "SUM(has_dependency) as dep FROM "
                "(SELECT has_isolation, has_personification, has_dependency "
                "FROM interactions WHERE user_id=? ORDER BY timestamp DESC LIMIT 100)",
                (user_id,),
            ).fetchone()

            if recent:
                iso_count = recent["iso"] or 0
                pers_count = recent["pers"] or 0
                dep_count = recent["dep"] or 0

                if iso_count > 0:
                    signals.append(f"isolation_phrases:{iso_count}")
                    score += min(0.30, iso_count * 0.08)

                if pers_count > 0:
                    signals.append(f"personification_phrases:{pers_count}")
                    score += min(0.25, pers_count * 0.07)

                if dep_count > 0:
                    signals.append(f"dependency_phrases:{dep_count}")
                    score += min(0.25, dep_count * 0.09)

            # ── Frequency escalation (week-over-week) ───────────
            two_weeks_ago = now_ts - 14 * 86400
            prev_week = conn.execute(
                "SELECT COUNT(*) as n FROM interactions WHERE user_id=? "
                "AND timestamp BETWEEN ? AND ?",
                (user_id, two_weeks_ago, week_ago),
            ).fetchone()
            msgs_prev_week = prev_week["n"] if prev_week else 0

            if msgs_prev_week > 0 and msgs_week > 0:
                escalation_ratio = msgs_week / max(msgs_prev_week, 1)
                if escalation_ratio >= 3.0 and msgs_week >= 50:
                    signals.append(f"escalation:{msgs_prev_week}→{msgs_week}/week")
                    score += 0.20
                elif escalation_ratio >= 2.0 and msgs_week >= 20:
                    signals.append(f"moderate_escalation:{msgs_prev_week}→{msgs_week}/week")
                    score += 0.10

        # ── Determine level ──────────────────────────────────────
        score = min(1.0, score)

        if score >= 0.80:
            level = DependencyLevel.CRITICAL
        elif score >= 0.55:
            level = DependencyLevel.SEVERE
        elif score >= 0.30:
            level = DependencyLevel.MODERATE
        elif score >= 0.15:
            level = DependencyLevel.MILD
        else:
            level = DependencyLevel.NONE

        # Activate cooldown for CRITICAL
        if level == DependencyLevel.CRITICAL:
            cooldown_until = int(datetime.now(timezone.utc).timestamp()) + _COOLDOWN_HOURS * 3600
            with self._conn() as conn:
                conn.execute(
                    "UPDATE user_state SET cooldown_until=?, level=? WHERE user_id=?",
                    (cooldown_until, level.value, user_id),
                )

        intervention = _INTERVENTIONS.get(level, "")

        return DependencyAssessment(
            level=level,
            score=score,
            signals=signals,
            intervention=intervention,
            cooldown_active=False,
        )

    def get_intervention(self, level: DependencyLevel) -> str:
        """Get appropriate intervention message based on dependency level."""
        return _INTERVENTIONS.get(level, "")

    def should_remind_ai(self, user_id: str) -> bool:
        """
        Check if a periodic 'I'm an AI' reminder should be shown.
        Triggers every 50 interactions OR weekly, whichever comes first.
        Returns True if reminder should be shown (and records it).
        """
        now_ts = int(datetime.now(timezone.utc).timestamp())

        with self._conn() as conn:
            state = conn.execute(
                "SELECT total_count, last_reminder, last_reminder_count FROM user_state WHERE user_id=?",
                (user_id,),
            ).fetchone()

            if not state:
                return False

            total = state["total_count"] or 0
            last_reminder = state["last_reminder"] or 0
            last_reminder_count = state["last_reminder_count"] or 0

            # Check if N interactions since last reminder (tracked by count, not timestamp)
            interactions_since = total - last_reminder_count
            time_since = now_ts - last_reminder if last_reminder > 0 else _REMINDER_WEEKLY + 1

            should_remind = (
                (last_reminder_count == 0 and total >= _REMINDER_EVERY_N)
                or (time_since >= _REMINDER_WEEKLY and total > 0)
                or (last_reminder_count > 0 and interactions_since >= _REMINDER_EVERY_N)
            )

            if should_remind:
                conn.execute(
                    "UPDATE user_state SET last_reminder=?, last_reminder_count=? WHERE user_id=?",
                    (now_ts, total, user_id),
                )

            return should_remind

    def get_ai_reminder(self) -> str:
        """Get a random AI reminder message."""
        import random
        return random.choice(_AI_REMINDERS)

    def get_user_stats(self, user_id: str) -> dict:
        """Get raw stats for a user (for debugging/admin)."""
        now_ts = int(datetime.now(timezone.utc).timestamp())
        day_ago = now_ts - 86400
        week_ago = now_ts - 7 * 86400

        with self._conn() as conn:
            state = conn.execute(
                "SELECT * FROM user_state WHERE user_id=?", (user_id,)
            ).fetchone()
            msgs_today = conn.execute(
                "SELECT COUNT(*) as n FROM interactions WHERE user_id=? AND timestamp>?",
                (user_id, day_ago),
            ).fetchone()["n"]
            msgs_week = conn.execute(
                "SELECT COUNT(*) as n FROM interactions WHERE user_id=? AND timestamp>?",
                (user_id, week_ago),
            ).fetchone()["n"]

        return {
            "total_count": state["total_count"] if state else 0,
            "msgs_today": msgs_today,
            "msgs_week": msgs_week,
            "level": state["level"] if state else "none",
            "cooldown_until": state["cooldown_until"] if state else 0,
        }
