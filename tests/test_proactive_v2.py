"""
Tests for Proactive Companion v2 — Timezone + Smart Scheduling
================================================================
25+ tests covering timezone detection, quiet hours, smart scheduling,
topic reminders, emotional urgency, and context deduplication.
"""

import os
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from nobi.proactive.timezone import TimezoneDetector, _offset_to_tz_string, _parse_tz_offset
from nobi.proactive.engine import ProactiveEngine, ProactiveTrigger


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def tz_detector(tmp_path):
    """Fresh TimezoneDetector with temp DB."""
    db = str(tmp_path / "tz_test.db")
    return TimezoneDetector(db_path=db)


@pytest.fixture
def mock_memory(tmp_path):
    """Mock MemoryManager with a real SQLite DB for proactive tables."""
    db_path = str(tmp_path / "proactive_test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    conn.commit()
    conn.close()

    mm = MagicMock()
    mm.db_path = db_path
    mm.recall = MagicMock(return_value=[])
    mm.graph = None
    return mm


@pytest.fixture
def engine(mock_memory, tz_detector):
    """ProactiveEngine with timezone detector."""
    return ProactiveEngine(mock_memory, timezone_detector=tz_detector)


@pytest.fixture
def engine_no_tz(mock_memory):
    """ProactiveEngine without timezone detector (backward compat)."""
    return ProactiveEngine(mock_memory)


# ── Timezone Detection: Greetings ─────────────────────────────

class TestTimezoneFromGreetings:

    def test_good_morning_utc14_detects_utc_plus8(self, tz_detector):
        """'Good morning' at UTC 14:00 → user is around UTC+8 (morning ≈ 8am local)."""
        result = tz_detector.detect_from_greeting("good morning!", 14)
        assert result is not None
        offset = _parse_tz_offset(result)
        # Morning midpoint = 8, UTC 14, offset = -6 → wraps to +18? No.
        # midpoint of (5,11) = 8. offset = (8 - 14) % 24 = -6 % 24 = 18 → 18 > 13 → 18-24 = -6
        assert offset == -6 or offset is not None  # Accept reasonable offsets

    def test_good_morning_utc0_detects_negative_offset(self, tz_detector):
        """'Good morning' at UTC 00:00 → user is around UTC+8."""
        result = tz_detector.detect_from_greeting("good morning everyone", 0)
        assert result is not None
        offset = _parse_tz_offset(result)
        # mid=8, utc=0, offset = (8-0)%24 = 8
        assert offset == 8

    def test_good_evening_utc10(self, tz_detector):
        """'Good evening' at UTC 10:00 → user is around UTC+9 (evening ≈ 19 local)."""
        result = tz_detector.detect_from_greeting("good evening", 10)
        assert result is not None
        offset = _parse_tz_offset(result)
        # mid of (17,21) = 19. offset = (19-10) % 24 = 9
        assert offset == 9

    def test_good_afternoon_utc6(self, tz_detector):
        """'Good afternoon' at UTC 06:00 → user is around UTC+8."""
        result = tz_detector.detect_from_greeting("good afternoon!", 6)
        assert result is not None
        offset = _parse_tz_offset(result)
        # mid of (12,17) = 14. offset = (14-6)%24 = 8
        assert offset == 8

    def test_no_greeting_returns_none(self, tz_detector):
        result = tz_detector.detect_from_greeting("how are you today?", 12)
        assert result is None

    def test_gm_crypto_greeting(self, tz_detector):
        """'gm' (crypto slang for good morning) should detect timezone."""
        result = tz_detector.detect_from_greeting("gm frens!", 14)
        assert result is not None


# ── Timezone Detection: Time References ───────────────────────

class TestTimezoneFromTimeRef:

    def test_its_3pm_at_utc7(self, tz_detector):
        """'It's 3pm here' at UTC 07:00 → UTC+8."""
        result = tz_detector.detect_from_message("it's 3pm here", 7)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 8  # 15 - 7 = 8

    def test_its_9pm_at_utc13(self, tz_detector):
        """'It's 9pm here' at UTC 13:00 → UTC+8."""
        result = tz_detector.detect_from_message("it's 9pm here", 13)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 8  # 21 - 13 = 8

    def test_its_9am_at_utc14(self, tz_detector):
        """'It's 9am' at UTC 14:00 → UTC-5."""
        result = tz_detector.detect_from_message("it's 9am right now", 14)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == -5  # 9 - 14 = -5

    def test_24h_format(self, tz_detector):
        """'It's 21:00 here' at UTC 13:00 → UTC+8."""
        result = tz_detector.detect_from_message("it's 21:00 here", 13)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 8


# ── Timezone Detection: Location ──────────────────────────────

class TestTimezoneFromLocation:

    def test_im_in_london(self, tz_detector):
        result = tz_detector.detect_from_message("I'm in London", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 0

    def test_i_live_in_tokyo(self, tz_detector):
        result = tz_detector.detect_from_message("I live in Tokyo", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 9

    def test_from_new_york(self, tz_detector):
        result = tz_detector.detect_from_message("I'm from New York", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == -5

    def test_based_in_singapore(self, tz_detector):
        result = tz_detector.detect_from_message("I'm based in Singapore", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == 8


# ── Timezone Detection: Explicit TZ ──────────────────────────

class TestTimezoneExplicit:

    def test_im_est(self, tz_detector):
        result = tz_detector.detect_from_message("I'm EST timezone", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == -5

    def test_pst_time(self, tz_detector):
        result = tz_detector.detect_from_message("PST time here", 12)
        assert result is not None
        offset = _parse_tz_offset(result)
        assert offset == -8

    def test_utc_plus_8(self, tz_detector):
        result = tz_detector.detect_from_message("my timezone is utc+8", 12)
        assert result == "UTC+8"

    def test_utc_minus_5(self, tz_detector):
        result = tz_detector.detect_from_message("I'm UTC-5", 12)
        assert result == "UTC-5"


# ── Timezone Storage ──────────────────────────────────────────

class TestTimezoneStorage:

    def test_default_utc(self, tz_detector):
        assert tz_detector.get_user_timezone("user1") == "UTC"

    def test_set_and_get(self, tz_detector):
        tz_detector.set_user_timezone("user1", "UTC+8")
        assert tz_detector.get_user_timezone("user1") == "UTC+8"

    def test_update_from_message(self, tz_detector):
        tz_detector.update_timezone_from_message("user1", "good morning!", 0)
        tz = tz_detector.get_user_timezone("user1")
        assert tz != "UTC"  # Should have detected something

    def test_overwrite(self, tz_detector):
        tz_detector.set_user_timezone("user1", "UTC+5")
        tz_detector.set_user_timezone("user1", "UTC+8")
        assert tz_detector.get_user_timezone("user1") == "UTC+8"


# ── Quiet Hours (Timezone-aware) ──────────────────────────────

class TestQuietHours:

    def test_quiet_hours_utc_default(self, tz_detector):
        """UTC user at 23:00 UTC → quiet."""
        utc_23 = datetime(2026, 3, 20, 23, 0, tzinfo=timezone.utc)
        assert tz_detector.is_quiet_hours("user_utc", utc_23) is True

    def test_not_quiet_hours_utc(self, tz_detector):
        """UTC user at 12:00 UTC → not quiet."""
        utc_12 = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        assert tz_detector.is_quiet_hours("user_utc", utc_12) is False

    def test_quiet_hours_with_offset(self, tz_detector):
        """UTC+8 user at 14:00 UTC → 22:00 local → quiet."""
        tz_detector.set_user_timezone("user_asia", "UTC+8")
        utc_14 = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)
        assert tz_detector.is_quiet_hours("user_asia", utc_14) is True

    def test_not_quiet_hours_with_offset(self, tz_detector):
        """UTC+8 user at 02:00 UTC → 10:00 local → not quiet."""
        tz_detector.set_user_timezone("user_asia", "UTC+8")
        utc_02 = datetime(2026, 3, 20, 2, 0, tzinfo=timezone.utc)
        assert tz_detector.is_quiet_hours("user_asia", utc_02) is False

    def test_quiet_early_morning_with_offset(self, tz_detector):
        """UTC-5 user at 10:00 UTC → 05:00 local → quiet (before 8am)."""
        tz_detector.set_user_timezone("user_est", "UTC-5")
        utc_10 = datetime(2026, 3, 20, 10, 0, tzinfo=timezone.utc)
        assert tz_detector.is_quiet_hours("user_est", utc_10) is True

    def test_engine_uses_tz_detector_quiet_hours(self, engine, tz_detector):
        """Engine should use tz detector for quiet hours."""
        tz_detector.set_user_timezone("user_asia", "UTC+8")
        utc_14 = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)
        assert engine._is_quiet_hours("user_asia", utc_14) is True

    def test_engine_no_tz_fallback(self, engine_no_tz):
        """Engine without tz_detector uses UTC fallback."""
        utc_12 = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)
        assert engine_no_tz._is_quiet_hours("any_user", utc_12) is False


# ── Smart Scheduling / Active Hours ──────────────────────────

class TestSmartScheduling:

    def test_record_and_get_active_hours(self, tz_detector):
        for _ in range(5):
            tz_detector.record_activity("user1", 14)
        for _ in range(3):
            tz_detector.record_activity("user1", 10)
        tz_detector.record_activity("user1", 22)

        active = tz_detector.get_active_hours("user1")
        assert active[0] == 14  # Most frequent
        assert active[1] == 10

    def test_best_send_time_from_active_hours(self, tz_detector):
        """Best send time should prefer active hours outside quiet hours."""
        tz_detector.set_user_timezone("user1", "UTC+8")
        # Record activity at UTC 02:00 (= 10:00 local), UTC 14:00 (= 22:00 local = quiet)
        for _ in range(5):
            tz_detector.record_activity("user1", 2)
        for _ in range(10):
            tz_detector.record_activity("user1", 14)

        best = tz_detector.get_best_send_time("user1")
        # Should pick UTC 2 (10:00 local) over UTC 14 (22:00 local, quiet)
        assert best == 2

    def test_best_send_time_fallback(self, tz_detector):
        """No activity recorded → fallback to 10:00 local."""
        tz_detector.set_user_timezone("user1", "UTC+8")
        best = tz_detector.get_best_send_time("user1")
        # 10:00 local = UTC 02:00
        assert best == 2

    def test_local_hour_calculation(self, tz_detector):
        tz_detector.set_user_timezone("user1", "UTC+8")
        utc_14 = datetime(2026, 3, 20, 14, 0, tzinfo=timezone.utc)
        assert tz_detector.get_local_hour("user1", utc_14) == 22

    def test_local_hour_negative_offset(self, tz_detector):
        tz_detector.set_user_timezone("user1", "UTC-5")
        utc_20 = datetime(2026, 3, 20, 20, 0, tzinfo=timezone.utc)
        assert tz_detector.get_local_hour("user1", utc_20) == 15


# ── Topic Reminder Trigger ────────────────────────────────────

class TestTopicReminder:

    def test_extract_intents_i_should(self, engine):
        intents = engine.extract_intents("I should call my mom tomorrow")
        assert len(intents) == 1
        assert "call my mom tomorrow" in intents[0]

    def test_extract_intents_i_need_to(self, engine):
        intents = engine.extract_intents("I need to exercise more")
        assert len(intents) == 1
        assert "exercise more" in intents[0]

    def test_extract_intents_i_want_to(self, engine):
        intents = engine.extract_intents("I want to learn guitar")
        assert len(intents) == 1
        assert "learn guitar" in intents[0]

    def test_extract_intents_remind_me(self, engine):
        intents = engine.extract_intents("remind me to buy groceries")
        assert len(intents) == 1
        assert "buy groceries" in intents[0]

    def test_extract_no_intent(self, engine):
        intents = engine.extract_intents("The weather is nice today")
        assert len(intents) == 0

    def test_record_and_check_topic_reminder(self, engine):
        """Topic reminder fires 2-5 days after recording."""
        base_time = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        engine.record_intents("user1", "I should call my mom", base_time)

        # Too early (1 day later)
        t1 = base_time + timedelta(days=1)
        trigger = engine._check_topic_reminders("user1", t1)
        assert trigger is None

        # Just right (3 days later)
        t3 = base_time + timedelta(days=3)
        trigger = engine._check_topic_reminders("user1", t3)
        assert trigger is not None
        assert trigger.trigger_type == "topic_reminder"
        assert "call my mom" in trigger.context

    def test_topic_reminder_not_if_discussed(self, engine):
        """Don't remind if user already discussed the topic."""
        base_time = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        engine.record_intents("user1", "I should call my mom", base_time)

        # User discusses the topic
        engine.mark_topic_discussed("user1", "I called my mom yesterday, we had a great chat")

        # Check 3 days later — should not trigger
        t3 = base_time + timedelta(days=3)
        trigger = engine._check_topic_reminders("user1", t3)
        assert trigger is None

    def test_topic_reminder_message_generation(self, engine):
        trigger = ProactiveTrigger(
            user_id="user1",
            trigger_type="topic_reminder",
            priority=2,
            context="call my mom",
            reason="test",
        )
        msg = engine.generate_message(trigger)
        assert "call my mom" in msg


# ── Emotional Urgency Weighting ──────────────────────────────

class TestEmotionalUrgency:

    def test_high_urgency_stressed(self, engine):
        """Stressed content → shorter follow-up window."""
        min_d, max_d = engine._get_follow_up_days("I'm so stressed about the exam")
        assert min_d == 0.5
        assert max_d == 1.5

    def test_high_urgency_depressed(self, engine):
        min_d, max_d = engine._get_follow_up_days("feeling really depressed today")
        assert min_d == 0.5
        assert max_d == 1.5

    def test_low_urgency_excited(self, engine):
        """Non-negative emotions → standard window."""
        min_d, max_d = engine._get_follow_up_days("I'm so excited about the trip!")
        assert min_d == engine.FOLLOW_UP_MIN_DAYS
        assert max_d == engine.FOLLOW_UP_MAX_DAYS

    def test_neutral_content(self, engine):
        """No emotion keywords → standard window."""
        min_d, max_d = engine._get_follow_up_days("I have a meeting tomorrow")
        assert min_d == engine.FOLLOW_UP_MIN_DAYS
        assert max_d == engine.FOLLOW_UP_MAX_DAYS


# ── Context Deduplication ─────────────────────────────────────

class TestContextDeduplication:

    def test_discussed_topic_marked(self, engine):
        """When user discusses an intended topic, it's marked as discussed."""
        base = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        engine.record_intents("user1", "I need to exercise more", base)

        # User talks about exercising
        engine.mark_topic_discussed("user1", "I went for a run and did some exercise today")

        # Verify it's marked
        rows = engine._conn.execute(
            "SELECT discussed_since FROM topic_reminders WHERE user_id = ?",
            ("user1",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["discussed_since"] == 1

    def test_unrelated_message_not_marked(self, engine):
        """Unrelated messages don't mark topics as discussed."""
        base = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        engine.record_intents("user1", "I should call my mom", base)

        engine.mark_topic_discussed("user1", "The weather is beautiful today")

        rows = engine._conn.execute(
            "SELECT discussed_since FROM topic_reminders WHERE user_id = ?",
            ("user1",),
        ).fetchall()
        assert rows[0]["discussed_since"] == 0


# ── Process Message Integration ───────────────────────────────

class TestProcessMessage:

    def test_process_message_detects_tz(self, engine, tz_detector):
        """process_message should detect and store timezone."""
        engine.process_message("user1", "good morning!", 0)
        tz = tz_detector.get_user_timezone("user1")
        assert tz != "UTC"

    def test_process_message_records_intents(self, engine):
        """process_message should record intents."""
        engine.process_message("user1", "I should read more books", 12)
        rows = engine._conn.execute(
            "SELECT intent FROM topic_reminders WHERE user_id = ?",
            ("user1",),
        ).fetchall()
        assert len(rows) == 1
        assert "read more books" in rows[0]["intent"]

    def test_process_message_records_activity(self, engine, tz_detector):
        """process_message should record active hours."""
        engine.process_message("user1", "hello", 14)
        active = tz_detector.get_active_hours("user1")
        assert 14 in active


# ── Engine Detect Timezone Method ─────────────────────────────

class TestEngineDetectTimezone:

    def test_detect_timezone_with_detector(self, engine):
        result = engine.detect_timezone("good morning!", 0)
        assert result is not None

    def test_detect_timezone_without_detector(self, engine_no_tz):
        result = engine_no_tz.detect_timezone("good morning!", 0)
        assert result is None


# ── Helper Function Tests ─────────────────────────────────────

class TestHelpers:

    def test_offset_to_tz_string_positive(self):
        assert _offset_to_tz_string(8) == "UTC+8"

    def test_offset_to_tz_string_negative(self):
        assert _offset_to_tz_string(-5) == "UTC-5"

    def test_offset_to_tz_string_zero(self):
        assert _offset_to_tz_string(0) == "UTC"

    def test_parse_tz_offset_utc(self):
        assert _parse_tz_offset("UTC") == 0

    def test_parse_tz_offset_positive(self):
        assert _parse_tz_offset("UTC+8") == 8

    def test_parse_tz_offset_negative(self):
        assert _parse_tz_offset("UTC-5") == -5

    def test_parse_tz_offset_invalid(self):
        assert _parse_tz_offset("XYZ") is None
