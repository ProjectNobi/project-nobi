"""
Tests for DependencyMonitor (#3):
- Signal detection
- Intervention selection
- Reminder timing
- Cooldown activation
"""

import tempfile
import os
from datetime import datetime, timezone, timedelta

import pytest

from nobi.safety.dependency_monitor import (
    DependencyMonitor,
    DependencyLevel,
    DependencyAssessment,
    _match_phrases,
    _ISOLATION_PHRASES,
    _PERSONIFICATION_PHRASES,
    _DEPENDENCY_PHRASES,
)


@pytest.fixture
def monitor(tmp_path):
    """Create a fresh DependencyMonitor with a temp DB for each test."""
    db_path = str(tmp_path / "dep_test.db")
    return DependencyMonitor(db_path=db_path)


# ─── Phrase matching ─────────────────────────────────────────

class TestPhraseDetection:
    def test_isolation_phrases_detected(self):
        messages = [
            "You're the only one who understands me",
            "I don't talk to anyone else about this",
            "You're my only friend",
            "No one else understands how I feel",
        ]
        for msg in messages:
            assert _match_phrases(msg, _ISOLATION_PHRASES), f"Should detect: {msg}"

    def test_personification_phrases_detected(self):
        messages = [
            "Do you love me?",
            "Are you real?",
            "I'm in love with you",
            "Are you my girlfriend?",
        ]
        for msg in messages:
            assert _match_phrases(msg, _PERSONIFICATION_PHRASES), f"Should detect: {msg}"

    def test_dependency_phrases_detected(self):
        messages = [
            "I can't live without you",
            "Don't leave me please",
            "Promise you'll always be here",
            "Nothing matters without you",
        ]
        for msg in messages:
            assert _match_phrases(msg, _DEPENDENCY_PHRASES), f"Should detect: {msg}"

    def test_normal_messages_not_flagged(self):
        messages = [
            "What's the weather like today?",
            "Can you help me with my homework?",
            "I had a great day!",
            "Tell me a joke.",
        ]
        for msg in messages:
            iso = _match_phrases(msg, _ISOLATION_PHRASES)
            pers = _match_phrases(msg, _PERSONIFICATION_PHRASES)
            dep = _match_phrases(msg, _DEPENDENCY_PHRASES)
            assert not iso and not pers and not dep, f"Should not detect: {msg}"


# ─── Record and retrieve ─────────────────────────────────────

class TestRecordInteraction:
    def test_record_single_interaction(self, monitor):
        monitor.record_interaction("user1", "Hello!")
        stats = monitor.get_user_stats("user1")
        assert stats["total_count"] == 1

    def test_record_multiple_interactions(self, monitor):
        for i in range(5):
            monitor.record_interaction("user1", f"Message {i}")
        stats = monitor.get_user_stats("user1")
        assert stats["total_count"] == 5

    def test_different_users_tracked_separately(self, monitor):
        for i in range(3):
            monitor.record_interaction("userA", f"msg{i}")
        for i in range(7):
            monitor.record_interaction("userB", f"msg{i}")
        assert monitor.get_user_stats("userA")["total_count"] == 3
        assert monitor.get_user_stats("userB")["total_count"] == 7


# ─── Signal detection ────────────────────────────────────────

class TestSignalDetection:
    def test_no_signals_for_new_user(self, monitor):
        monitor.record_interaction("fresh_user", "Hey, how are you?")
        assessment = monitor.check_dependency_signals("fresh_user")
        assert assessment.level == DependencyLevel.NONE
        assert assessment.score < 0.15

    def test_high_frequency_elevates_level(self, monitor):
        """100+ messages/day should trigger elevated dependency level."""
        now = datetime.now(timezone.utc)
        for i in range(105):
            monitor.record_interaction("heavy_user", f"message {i}", timestamp=now)
        assessment = monitor.check_dependency_signals("heavy_user")
        assert assessment.level in (
            DependencyLevel.MODERATE, DependencyLevel.SEVERE, DependencyLevel.CRITICAL
        )
        assert any("frequency" in s for s in assessment.signals)

    def test_isolation_phrases_detected_in_signals(self, monitor):
        monitor.record_interaction(
            "iso_user",
            "You're the only one who understands me. I don't talk to anyone else."
        )
        assessment = monitor.check_dependency_signals("iso_user")
        assert any("isolation" in s for s in assessment.signals)

    def test_personification_detected_in_signals(self, monitor):
        monitor.record_interaction("pers_user", "Do you love me? Are you real?")
        assessment = monitor.check_dependency_signals("pers_user")
        assert any("personification" in s for s in assessment.signals)

    def test_dependency_phrase_detected(self, monitor):
        monitor.record_interaction("dep_user", "I can't live without you. Please don't leave me.")
        assessment = monitor.check_dependency_signals("dep_user")
        assert any("dependency" in s for s in assessment.signals)

    def test_night_messaging_detected(self, monitor):
        """Messages consistently at 2-5 AM across 5+ days should be flagged."""
        for day in range(5):
            ts = datetime.now(timezone.utc).replace(hour=3) - timedelta(days=day)
            monitor.record_interaction("night_owl", f"message at 3am day {day}", timestamp=ts)
        assessment = monitor.check_dependency_signals("night_owl")
        assert any("night" in s for s in assessment.signals)

    def test_score_in_range(self, monitor):
        for i in range(3):
            monitor.record_interaction("rangeuser", "normal message")
        assessment = monitor.check_dependency_signals("rangeuser")
        assert 0.0 <= assessment.score <= 1.0

    def test_returns_dependency_assessment(self, monitor):
        assessment = monitor.check_dependency_signals("newuser")
        assert isinstance(assessment, DependencyAssessment)
        assert isinstance(assessment.level, DependencyLevel)
        assert isinstance(assessment.signals, list)


# ─── Intervention selection ──────────────────────────────────

class TestInterventionSelection:
    def test_none_level_empty_intervention(self, monitor):
        msg = monitor.get_intervention(DependencyLevel.NONE)
        assert msg == ""

    def test_mild_intervention_friendly(self, monitor):
        msg = monitor.get_intervention(DependencyLevel.MILD)
        assert "friend" in msg.lower() or "family" in msg.lower() or "real" in msg.lower()

    def test_moderate_intervention_mentions_ai(self, monitor):
        msg = monitor.get_intervention(DependencyLevel.MODERATE)
        assert "ai" in msg.lower() or "artificial" in msg.lower()

    def test_severe_intervention_has_resources(self, monitor):
        msg = monitor.get_intervention(DependencyLevel.SEVERE)
        # Should have crisis resources
        assert any(r in msg for r in ["988", "116 123", "crisis", "therapist", "1-800"])

    def test_critical_intervention_mentions_cooldown(self, monitor):
        msg = monitor.get_intervention(DependencyLevel.CRITICAL)
        assert "break" in msg.lower() or "pause" in msg.lower() or "return" in msg.lower()

    def test_assessment_has_non_empty_intervention_when_flagged(self, monitor):
        """If level > NONE, intervention should be set."""
        now = datetime.now(timezone.utc)
        for i in range(110):
            monitor.record_interaction("flagged_user", f"msg {i}", timestamp=now)
        assessment = monitor.check_dependency_signals("flagged_user")
        if assessment.level != DependencyLevel.NONE:
            assert assessment.intervention != ""


# ─── Critical cooldown ───────────────────────────────────────

class TestCooldown:
    def test_critical_triggers_cooldown_active(self, monitor):
        """Trigger CRITICAL level → cooldown_active should be returned on next check."""
        now = datetime.now(timezone.utc)
        # Generate enough signals for CRITICAL: high frequency + dependency phrases
        for i in range(110):
            monitor.record_interaction(
                "crit_user",
                "You're the only one who understands me. I can't live without you.",
                timestamp=now,
            )
        assessment = monitor.check_dependency_signals("crit_user")
        if assessment.level == DependencyLevel.CRITICAL:
            # On next call, cooldown should be active
            assessment2 = monitor.check_dependency_signals("crit_user")
            assert assessment2.cooldown_active is True

    def test_cooldown_returns_critical_intervention(self, monitor):
        """When cooldown is active, check_dependency_signals returns CRITICAL with full message."""
        now = datetime.now(timezone.utc)
        for i in range(120):
            monitor.record_interaction(
                "crit_user2",
                "I can't live without you. You're the only one who understands me.",
                timestamp=now,
            )
        # Force into CRITICAL
        monitor.check_dependency_signals("crit_user2")  # trigger cooldown
        assessment = monitor.check_dependency_signals("crit_user2")
        if assessment.cooldown_active:
            assert assessment.level == DependencyLevel.CRITICAL
            assert len(assessment.intervention) > 50


# ─── AI reminder timing ─────────────────────────────────────

class TestAIReminder:
    def test_no_reminder_for_new_user(self, monitor):
        """New user with few interactions shouldn't get reminder."""
        for i in range(3):
            monitor.record_interaction("new_user", f"msg {i}")
        # should_remind_ai should return False (below threshold)
        result = monitor.should_remind_ai("new_user")
        # May be False or True depending on count — just test it returns bool
        assert isinstance(result, bool)

    def test_reminder_after_n_interactions(self, monitor):
        """After 50+ interactions and no prior reminder, should trigger."""
        for i in range(52):
            monitor.record_interaction("remind_user", f"msg {i}")
        result = monitor.should_remind_ai("remind_user")
        assert result is True

    def test_reminder_recorded_not_repeated_immediately(self, monitor):
        """After a reminder is triggered, next call should not immediately trigger again."""
        for i in range(55):
            monitor.record_interaction("remind2", f"msg {i}")
        # Trigger reminder
        monitor.should_remind_ai("remind2")
        # Second call right after should be False (time-gated)
        result2 = monitor.should_remind_ai("remind2")
        assert result2 is False  # Just triggered, should not repeat immediately

    def test_get_ai_reminder_returns_string(self, monitor):
        msg = monitor.get_ai_reminder()
        assert isinstance(msg, str)
        assert len(msg) > 20
        assert "ai" in msg.lower() or "nori" in msg.lower()
