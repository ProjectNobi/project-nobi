"""
Tests for the Proactive Companion System
==========================================
Tests cover: birthday detection, follow-up triggers, check-in timing,
milestone detection, rate limiting, quiet hours, opt-in/out, message
generation, scheduler integration, and edge cases.
"""

import os
import sys
import json
import asyncio
import sqlite3
import tempfile
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.proactive.engine import (
    ProactiveEngine,
    ProactiveTrigger,
    parse_birthday,
)
from nobi.proactive.scheduler import ProactiveScheduler


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database path."""
    return str(tmp_path / "test_proactive.db")


@pytest.fixture
def memory_manager(tmp_db):
    """Create a mock-like MemoryManager with a real SQLite DB."""
    mm = MagicMock()
    mm.db_path = tmp_db
    mm.graph = None

    # Initialize the DB tables that MemoryManager would create
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory_type TEXT NOT NULL DEFAULT 'fact',
            content TEXT NOT NULL,
            importance REAL NOT NULL DEFAULT 0.5,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            summary TEXT DEFAULT '',
            personality_notes TEXT DEFAULT '',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            total_messages INTEGER DEFAULT 0,
            memory_count_at_last_summary INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    # recall returns list of dicts
    mm.recall.return_value = []
    return mm


@pytest.fixture
def engine(memory_manager):
    """Create a ProactiveEngine with the mock memory manager."""
    return ProactiveEngine(memory_manager, memory_graph=None)


@pytest.fixture
def engine_with_graph(memory_manager):
    """Create a ProactiveEngine with a mock graph."""
    graph = MagicMock()
    graph.get_relationships.return_value = []
    memory_manager.graph = graph
    return ProactiveEngine(memory_manager, memory_graph=graph)


def _add_user_profile(db_path, user_id, first_seen, last_seen, total_messages=10):
    """Helper: insert a user profile directly into the DB."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO user_profiles
           (user_id, first_seen, last_seen, total_messages)
           VALUES (?, ?, ?, ?)""",
        (user_id, first_seen.isoformat(), last_seen.isoformat(), total_messages),
    )
    conn.commit()
    conn.close()


def _add_memory(db_path, user_id, content, memory_type="fact", created_at=None, importance=0.5):
    """Helper: insert a memory directly into the DB."""
    import uuid
    if created_at is None:
        created_at = datetime.now(timezone.utc)
    mid = str(uuid.uuid4())[:12]
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO memories (id, user_id, memory_type, content, importance,
           tags, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '[]', ?, ?)""",
        (mid, user_id, memory_type, content, importance,
         created_at.isoformat(), created_at.isoformat()),
    )
    conn.commit()
    conn.close()
    return mid


# ── Birthday Parsing Tests ───────────────────────────────────

class TestBirthdayParsing:
    def test_month_day_format(self):
        assert parse_birthday("March 15") == (3, 15)

    def test_month_day_with_suffix(self):
        assert parse_birthday("march 15th") == (3, 15)

    def test_day_month_format(self):
        assert parse_birthday("15 March") == (3, 15)

    def test_day_of_month_format(self):
        assert parse_birthday("15th of March") == (3, 15)

    def test_iso_format(self):
        assert parse_birthday("1990-03-15") == (3, 15)

    def test_slash_mm_dd(self):
        assert parse_birthday("03/15") == (3, 15)

    def test_slash_dd_mm(self):
        # 25 > 12, so must be DD/MM
        assert parse_birthday("25/03") == (3, 25)

    def test_dash_format(self):
        assert parse_birthday("03-15") == (3, 15)

    def test_abbreviated_month(self):
        assert parse_birthday("Jan 1") == (1, 1)
        assert parse_birthday("Dec 25") == (12, 25)

    def test_invalid_returns_none(self):
        assert parse_birthday("") is None
        assert parse_birthday("no date here") is None
        assert parse_birthday("13/32") is None

    def test_embedded_in_sentence(self):
        assert parse_birthday("My birthday is March 15") == (3, 15)
        assert parse_birthday("born on 1990-07-04") == (7, 4)


# ── Opt-in/Opt-out Tests ────────────────────────────────────

class TestOptInOut:
    def test_default_opted_in(self, engine):
        assert engine.is_opted_in("user_123") is True

    def test_opt_out(self, engine):
        engine.set_opted_in("user_123", False)
        assert engine.is_opted_in("user_123") is False

    def test_opt_back_in(self, engine):
        engine.set_opted_in("user_123", False)
        engine.set_opted_in("user_123", True)
        assert engine.is_opted_in("user_123") is True

    def test_opted_out_blocks_outreach(self, engine):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=5),
        )
        engine.set_opted_in("user_1", False)
        assert engine.should_reach_out("user_1", now) is False


# ── Rate Limiting Tests ──────────────────────────────────────

class TestRateLimiting:
    def test_should_reach_out_basic(self, engine):
        """User with no recent proactive messages — should be OK."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=3),
        )
        assert engine.should_reach_out("user_1", now) is True

    def test_max_one_per_day(self, engine):
        """After sending one message, can't send another for 24h."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=3),
        )
        engine.mark_sent("user_1", "check_in", "test message")
        assert engine.should_reach_out("user_1", now) is False

    def test_can_send_after_24h(self, engine):
        """After 24h+ since last proactive message, should be OK again."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=3),
        )
        # Manually insert a proactive log entry from 25h ago
        conn = sqlite3.connect(engine.memory.db_path)
        sent_at = (now - timedelta(hours=25)).isoformat()
        conn.execute(
            "INSERT INTO proactive_log (user_id, trigger_type, message, sent_at) VALUES (?, ?, ?, ?)",
            ("user_1", "check_in", "old message", sent_at),
        )
        conn.commit()
        conn.close()
        assert engine.should_reach_out("user_1", now) is True

    def test_no_message_if_active_recently(self, engine):
        """Don't send proactive if user was active in last 2h."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=1),  # active 1h ago
        )
        assert engine.should_reach_out("user_1", now) is False


# ── Quiet Hours Tests ────────────────────────────────────────

class TestQuietHours:
    def test_quiet_at_23(self, engine):
        now = datetime(2026, 3, 20, 23, 0, tzinfo=timezone.utc)
        assert engine._is_quiet_hours("user_1", now) is True

    def test_quiet_at_3am(self, engine):
        now = datetime(2026, 3, 20, 3, 0, tzinfo=timezone.utc)
        assert engine._is_quiet_hours("user_1", now) is True

    def test_not_quiet_at_noon(self, engine):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        assert engine._is_quiet_hours("user_1", now) is False

    def test_not_quiet_at_8am(self, engine):
        now = datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc)
        assert engine._is_quiet_hours("user_1", now) is False

    def test_quiet_hours_block_outreach(self, engine):
        """During quiet hours, should_reach_out returns False."""
        now = datetime(2026, 3, 20, 23, 30, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=5),
        )
        assert engine.should_reach_out("user_1", now) is False


# ── Birthday Trigger Tests ───────────────────────────────────

class TestBirthdayTrigger:
    def test_birthday_from_memory(self, engine):
        """Detects birthday from memory content."""
        now = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)  # March 15
        engine.memory.recall.return_value = [
            {"content": "User's birthday is March 15", "type": "fact"},
        ]
        trigger = engine._check_birthday("user_1", now)
        assert trigger is not None
        assert trigger.trigger_type == "birthday"
        assert trigger.priority == 1

    def test_no_birthday_wrong_day(self, engine):
        """No birthday trigger if today isn't the day."""
        now = datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc)  # March 16
        engine.memory.recall.return_value = [
            {"content": "User's birthday is March 15", "type": "fact"},
        ]
        trigger = engine._check_birthday("user_1", now)
        assert trigger is None

    def test_birthday_from_graph(self, engine_with_graph):
        """Detects birthday from graph born_on relationship."""
        now = datetime(2026, 7, 4, 12, 0, tzinfo=timezone.utc)  # July 4
        engine_with_graph.graph.get_relationships.return_value = [
            {"relationship_type": "born_on", "target": "July 4"},
        ]
        trigger = engine_with_graph._check_birthday("user_1", now)
        assert trigger is not None
        assert trigger.trigger_type == "birthday"


# ── Follow-up Trigger Tests ─────────────────────────────────

class TestFollowUpTrigger:
    def test_event_follow_up(self, engine):
        """Detects follow-up opportunity from event memory."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        two_days_ago = (now - timedelta(days=2)).isoformat()
        engine.memory.recall.return_value = [
            {
                "content": "I have a job interview tomorrow",
                "type": "event",
                "created_at": two_days_ago,
            },
        ]
        triggers = engine._check_follow_ups("user_1", now)
        assert len(triggers) == 1
        assert triggers[0].trigger_type == "follow_up"

    def test_emotion_follow_up(self, engine):
        """Detects follow-up from emotional memory."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        yesterday = (now - timedelta(days=1, hours=5)).isoformat()
        engine.memory.recall.return_value = [
            {
                "content": "I'm feeling stressed about the deadline",
                "type": "emotion",
                "created_at": yesterday,
            },
        ]
        triggers = engine._check_follow_ups("user_1", now)
        assert len(triggers) >= 1
        assert triggers[0].trigger_type == "follow_up"

    def test_no_follow_up_too_old(self, engine):
        """No follow-up for memories older than 3 days."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        five_days_ago = (now - timedelta(days=5)).isoformat()
        engine.memory.recall.return_value = [
            {
                "content": "I have an exam tomorrow",
                "type": "event",
                "created_at": five_days_ago,
            },
        ]
        triggers = engine._check_follow_ups("user_1", now)
        assert len(triggers) == 0

    def test_no_follow_up_too_recent(self, engine):
        """No follow-up for memories less than 1 day old."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        hours_ago = (now - timedelta(hours=6)).isoformat()
        engine.memory.recall.return_value = [
            {
                "content": "I have an interview later today",
                "type": "event",
                "created_at": hours_ago,
            },
        ]
        triggers = engine._check_follow_ups("user_1", now)
        assert len(triggers) == 0


# ── Check-in Trigger Tests ──────────────────────────────────

class TestCheckInTrigger:
    def test_check_in_after_3_days(self, engine):
        """Trigger check-in if user inactive for 3+ days."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=4),
        )
        trigger = engine._check_check_in("user_1", now)
        assert trigger is not None
        assert trigger.trigger_type == "check_in"

    def test_no_check_in_active_user(self, engine):
        """No check-in if user was active recently."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=12),
        )
        trigger = engine._check_check_in("user_1", now)
        assert trigger is None

    def test_no_check_in_no_profile(self, engine):
        """No check-in if no profile exists."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        trigger = engine._check_check_in("nonexistent_user", now)
        assert trigger is None


# ── Milestone Trigger Tests ──────────────────────────────────

class TestMilestoneTrigger:
    def test_7_day_milestone(self, engine):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=7), now - timedelta(hours=3),
        )
        trigger = engine._check_milestone("user_1", now)
        assert trigger is not None
        assert trigger.trigger_type == "milestone"
        assert "7" in trigger.context

    def test_30_day_milestone(self, engine):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(hours=3),
        )
        trigger = engine._check_milestone("user_1", now)
        assert trigger is not None
        assert "30" in trigger.context

    def test_no_milestone_non_special_day(self, engine):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=15), now - timedelta(hours=3),
        )
        trigger = engine._check_milestone("user_1", now)
        assert trigger is None


# ── Encouragement Trigger Tests ──────────────────────────────

class TestEncouragementTrigger:
    def test_encouragement_from_graph(self, engine_with_graph):
        """Generates encouragement from graph work/study context."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        engine_with_graph.graph.get_relationships.return_value = [
            {"relationship_type": "works_as", "target": "software developer"},
        ]
        _add_user_profile(
            engine_with_graph.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=2),
        )
        trigger = engine_with_graph._check_encouragement("user_1", now)
        assert trigger is not None
        assert trigger.trigger_type == "encouragement"
        assert "software developer" in trigger.context

    def test_no_encouragement_without_graph(self, engine):
        """No encouragement if graph is not available."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        trigger = engine._check_encouragement("user_1", now)
        assert trigger is None


# ── Message Generation Tests ─────────────────────────────────

class TestMessageGeneration:
    def test_birthday_message(self, engine):
        trigger = ProactiveTrigger("u1", "birthday", 1, "Birthday: 3/15", "birthday")
        msg = engine.generate_message(trigger)
        assert "birthday" in msg.lower() or "🎂" in msg

    def test_follow_up_event_message(self, engine):
        trigger = ProactiveTrigger(
            "u1", "follow_up", 2,
            "I have a job interview tomorrow", "event follow-up",
        )
        msg = engine.generate_message(trigger)
        assert "interview" in msg.lower()

    def test_check_in_message(self, engine):
        trigger = ProactiveTrigger("u1", "check_in", 3, "5 days", "inactive")
        msg = engine.generate_message(trigger)
        assert len(msg) > 10

    def test_milestone_message(self, engine):
        trigger = ProactiveTrigger(
            "u1", "milestone", 3, "30 days since first chat", "milestone",
        )
        msg = engine.generate_message(trigger)
        assert "30" in msg

    def test_encouragement_message(self, engine):
        trigger = ProactiveTrigger(
            "u1", "encouragement", 3,
            "works_as: teacher", "encouragement",
        )
        msg = engine.generate_message(trigger)
        assert "teacher" in msg.lower()

    def test_messages_are_not_empty(self, engine):
        """All trigger types should produce non-empty messages."""
        types = ["birthday", "follow_up", "check_in", "milestone", "encouragement"]
        for t in types:
            trigger = ProactiveTrigger("u1", t, 2, "test context", "test")
            msg = engine.generate_message(trigger)
            assert msg and len(msg.strip()) > 0, f"Empty message for {t}"


# ── Full Pipeline Tests ──────────────────────────────────────

class TestCheckTriggers:
    def test_triggers_sorted_by_priority(self, engine):
        """Triggers should be returned sorted by priority (lowest number first)."""
        now = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        # Birthday today + inactive for 5 days
        engine.memory.recall.return_value = [
            {"content": "User's birthday is March 15", "type": "fact"},
        ]
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=5),
        )
        triggers = engine.check_triggers("user_1", now)
        assert len(triggers) >= 2
        # Birthday (priority 1) should come first
        assert triggers[0].trigger_type == "birthday"
        assert triggers[0].priority <= triggers[-1].priority

    def test_empty_triggers_for_new_user(self, engine):
        """New user with no data should produce no triggers."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        triggers = engine.check_triggers("brand_new_user", now)
        assert triggers == []


# ── Pending Outreach Tests ───────────────────────────────────

class TestPendingOutreach:
    def test_get_pending_outreach(self, engine):
        """get_pending_outreach returns items for eligible users."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=5),
        )
        items = engine.get_pending_outreach(now)
        # Should have at least check-in trigger
        assert len(items) >= 1
        assert items[0]["user_id"] == "user_1"
        assert items[0]["message"]

    def test_no_outreach_for_opted_out(self, engine):
        """Opted-out users should not appear in pending outreach."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            now - timedelta(days=30), now - timedelta(days=5),
        )
        engine.set_opted_in("user_1", False)
        items = engine.get_pending_outreach(now)
        assert len(items) == 0


# ── Scheduler Tests ──────────────────────────────────────────

class TestScheduler:
    @pytest.mark.asyncio
    async def test_run_once_sends_messages(self, engine):
        """run_once should invoke send_callback for pending outreach."""
        # Use a fixed non-quiet-hours time
        fixed_now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            fixed_now - timedelta(days=30), fixed_now - timedelta(days=5),
        )

        send_mock = AsyncMock()
        scheduler = ProactiveScheduler(engine, send_mock)

        # Patch get_pending_outreach to use our fixed time
        original_get = engine.get_pending_outreach
        engine.get_pending_outreach = lambda: original_get(now=fixed_now)

        count = await scheduler.run_once()
        assert count >= 1
        send_mock.assert_called()

    @pytest.mark.asyncio
    async def test_run_once_no_outreach(self, engine):
        """run_once should return 0 when no outreach pending."""
        send_mock = AsyncMock()
        scheduler = ProactiveScheduler(engine, send_mock)
        count = await scheduler.run_once()
        assert count == 0
        send_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """Scheduler starts and stops cleanly."""
        send_mock = AsyncMock()
        scheduler = ProactiveScheduler(engine, send_mock)
        await scheduler.start(interval_seconds=3600)
        assert scheduler._running is True
        assert scheduler._task is not None
        await scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_scheduler_marks_sent(self, engine):
        """After sending, scheduler marks the message as sent (rate limit)."""
        fixed_now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        _add_user_profile(
            engine.memory.db_path, "user_1",
            fixed_now - timedelta(days=30), fixed_now - timedelta(days=5),
        )

        send_mock = AsyncMock()
        scheduler = ProactiveScheduler(engine, send_mock)

        original_get = engine.get_pending_outreach
        engine.get_pending_outreach = lambda: original_get(now=fixed_now)

        await scheduler.run_once()

        # Second run should send nothing (rate limited)
        count2 = await scheduler.run_once()
        assert count2 == 0


# ── ProactiveTrigger Dataclass Tests ────────────────────────

class TestProactiveTriggerDataclass:
    def test_creation(self):
        t = ProactiveTrigger("u1", "birthday", 1, "ctx", "reason")
        assert t.user_id == "u1"
        assert t.trigger_type == "birthday"
        assert t.priority == 1
        assert t.context == "ctx"
        assert t.reason == "reason"

    def test_equality(self):
        t1 = ProactiveTrigger("u1", "birthday", 1, "ctx", "reason")
        t2 = ProactiveTrigger("u1", "birthday", 1, "ctx", "reason")
        assert t1 == t2


# ── Edge Cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_mark_sent_records_in_db(self, engine):
        """mark_sent should write to proactive_log table."""
        engine.mark_sent("user_1", "check_in", "Hello!")
        conn = sqlite3.connect(engine.memory.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM proactive_log WHERE user_id = 'user_1'"
        ).fetchone()
        assert row is not None
        assert row["trigger_type"] == "check_in"
        assert row["message"] == "Hello!"
        conn.close()

    def test_engine_handles_recall_error(self, engine):
        """Engine should not crash if recall raises an exception."""
        engine.memory.recall.side_effect = Exception("DB error")
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        # Should not raise
        triggers = engine.check_triggers("user_1", now)
        assert isinstance(triggers, list)

    def test_timezone_setting(self, engine):
        """Can set and get user timezone."""
        engine.set_user_timezone("user_1", "Asia/Tokyo")
        assert engine.get_user_timezone("user_1") == "Asia/Tokyo"

    def test_default_timezone_utc(self, engine):
        assert engine.get_user_timezone("nonexistent") == "UTC"

    def test_generate_message_unknown_type(self, engine):
        """Unknown trigger type should produce a fallback message."""
        trigger = ProactiveTrigger("u1", "unknown_type", 3, "", "")
        msg = engine.generate_message(trigger)
        assert len(msg) > 0

    def test_follow_up_deduplicates(self, engine):
        """Multiple matching memories should only produce one follow-up."""
        now = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        two_days_ago = (now - timedelta(days=2)).isoformat()
        engine.memory.recall.return_value = [
            {"content": "I have an interview tomorrow", "type": "event", "created_at": two_days_ago},
            {"content": "My exam is next week", "type": "event", "created_at": two_days_ago},
        ]
        triggers = engine._check_follow_ups("user_1", now)
        assert len(triggers) == 1  # deduplicated to 1
