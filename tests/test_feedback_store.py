"""
Tests for the self-improving feedback loop (FeedbackStore).
"""

import os
import tempfile
import pytest
from nobi.feedback.feedback_store import FeedbackStore


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    """Create a FeedbackStore with a temp DB path."""
    db_path = str(tmp_path / "test_lessons.db")
    return FeedbackStore(db_path=db_path)


# ─── Detection Tests ──────────────────────────────────────────

class TestCorrectionDetection:
    def test_no_i_said(self, store):
        assert store.detect_correction("no, I said tomorrow not today") is True

    def test_thats_wrong(self, store):
        assert store.detect_correction("That's wrong, I never told you that") is True

    def test_youre_wrong(self, store):
        assert store.detect_correction("you're wrong about my job") is True

    def test_i_already_told_you(self, store):
        assert store.detect_correction("I already told you my name is Alex") is True

    def test_you_forgot(self, store):
        assert store.detect_correction("you forgot what I said about my schedule") is True

    def test_not_what_i_asked(self, store):
        assert store.detect_correction("that's not what I asked for") is True

    def test_i_meant(self, store):
        assert store.detect_correction("I meant next week, not this week") is True

    def test_actually_correction(self, store):
        assert store.detect_correction("actually, my name is Sarah not Emma") is True

    def test_correct_yourself(self, store):
        assert store.detect_correction("please correct yourself, that was wrong") is True

    def test_you_misunderstood(self, store):
        assert store.detect_correction("you misunderstood what I said") is True

    def test_you_already_asked(self, store):
        assert store.detect_correction("you already asked me that question") is True

    def test_i_told_you_before(self, store):
        assert store.detect_correction("I told you that before, please remember") is True

    def test_stop_repeating(self, store):
        assert store.detect_correction("stop repeating yourself!") is True

    def test_you_keep_forgetting(self, store):
        assert store.detect_correction("you keep forgetting my preferences") is True

    def test_please_remember(self, store):
        assert store.detect_correction("please remember what I said earlier") is True

    def test_no_my_name(self, store):
        assert store.detect_correction("no, my name is Alex not Bob") is True

    def test_incorrect(self, store):
        assert store.detect_correction("that is incorrect") is True

    def test_wrong_answer(self, store):
        assert store.detect_correction("that's a wrong answer") is True

    def test_normal_message_no_correction(self, store):
        assert store.detect_correction("Hello, how are you today?") is False

    def test_how_are_you(self, store):
        assert store.detect_correction("How are you?") is False

    def test_weather_question(self, store):
        assert store.detect_correction("What's the weather like in London?") is False

    def test_empty_message(self, store):
        assert store.detect_correction("") is False

    def test_none_message(self, store):
        assert store.detect_correction(None) is False

    def test_greeting(self, store):
        assert store.detect_correction("Good morning! I had a great day yesterday.") is False

    def test_actually_not_correction(self, store):
        # "actually I'm fine" should NOT be detected as correction
        # The pattern excludes "actually i'm", "actually i am", "actually the/a/this/it"
        # This tests our smart exclusion pattern
        result = store.detect_correction("actually I'm doing great today!")
        # This is a borderline case — we accept either outcome but it shouldn't be a hard false positive
        # The regex excludes "actually i'm" — so this should be False
        assert result is False

    def test_case_insensitive(self, store):
        assert store.detect_correction("YOU FORGOT MY NAME") is True

    def test_typo_variant(self, store):
        assert store.detect_correction("thats wrong, i said tuesday") is True


# ─── Storage Tests ────────────────────────────────────────────

class TestLessonStorage:
    def test_save_and_retrieve(self, store):
        lesson_id = store.save_lesson(
            user_id="user123",
            correction="no, my name is Alex",
            lesson="Always verify the user's name from memory before using it.",
        )
        assert lesson_id > 0

        lessons = store.get_active_lessons(limit=10)
        assert len(lessons) == 1
        assert lessons[0]["lesson"] == "Always verify the user's name from memory before using it."
        assert lessons[0]["user_id"] == "user123"

    def test_multiple_lessons_ordered_by_recency(self, store):
        store.save_lesson("u1", "correction 1", "Lesson A: always do X.")
        store.save_lesson("u2", "correction 2", "Lesson B: never do Y.")
        store.save_lesson("u3", "correction 3", "Lesson C: verify Z first.")

        lessons = store.get_active_lessons(limit=10)
        assert len(lessons) == 3
        # Most recent first
        assert lessons[0]["lesson"] == "Lesson C: verify Z first."

    def test_limit_respected(self, store):
        for i in range(10):
            store.save_lesson("u1", f"correction {i}", f"Unique lesson number {i} for testing.")
        lessons = store.get_active_lessons(limit=5)
        assert len(lessons) <= 5

    def test_deduplication(self, store):
        # Same lesson saved twice should appear once
        store.save_lesson("u1", "c1", "Always verify the user's name before responding.")
        store.save_lesson("u2", "c2", "Always verify the user's name before responding.")
        lessons = store.get_active_lessons(limit=10)
        assert len(lessons) == 1

    def test_get_lesson_count(self, store):
        assert store.get_lesson_count() == 0
        store.save_lesson("u1", "c1", "Lesson one for counting test.")
        store.save_lesson("u2", "c2", "Lesson two for counting test.")
        assert store.get_lesson_count() == 2

    def test_mark_applied(self, store):
        lesson_id = store.save_lesson("u1", "correction", "Test lesson for applied marking.")
        # Should not raise
        store.mark_applied(lesson_id)

    def test_empty_db_returns_empty_list(self, store):
        lessons = store.get_active_lessons()
        assert lessons == []

    def test_lesson_dict_keys(self, store):
        store.save_lesson("u1", "correction", "Check memory before answering questions.")
        lessons = store.get_active_lessons()
        assert len(lessons) == 1
        lesson = lessons[0]
        assert "id" in lesson
        assert "lesson" in lesson
        assert "timestamp" in lesson
        assert "user_id" in lesson


# ─── Fallback Lesson Tests ────────────────────────────────────

class TestFallbackLesson:
    def test_name_correction_fallback(self, store):
        lesson = store._fallback_lesson("no my name is Alex")
        assert "name" in lesson.lower()

    def test_already_told_fallback(self, store):
        lesson = store._fallback_lesson("I already told you this")
        assert lesson  # Just check it returns something

    def test_forget_fallback(self, store):
        lesson = store._fallback_lesson("you forgot what I said")
        assert "memory" in lesson.lower() or "recall" in lesson.lower()

    def test_generic_fallback(self, store):
        lesson = store._fallback_lesson("this is a strange message")
        assert len(lesson) > 10


# ─── Async Lesson Extraction Tests ───────────────────────────

class TestLessonExtractionFallback:
    """Test extract_lesson when no LLM client is available (fallback mode)."""

    @pytest.mark.asyncio
    async def test_extract_lesson_no_client(self, store):
        lesson = await store.extract_lesson(
            user_message="I already told you my name is Sarah",
            bot_response="Hello, nice to meet you!",
            correction="I already told you my name is Sarah",
            llm_client=None,
        )
        assert len(lesson) > 10
        assert isinstance(lesson, str)

    @pytest.mark.asyncio
    async def test_extract_lesson_returns_string(self, store):
        lesson = await store.extract_lesson(
            user_message="that's wrong",
            bot_response="some response",
            correction="that's wrong, the answer is 42",
            llm_client=None,
        )
        assert isinstance(lesson, str)
        assert len(lesson) > 5


# ─── Pruning Tests ────────────────────────────────────────────

class TestPruning:
    def test_prune_duplicates(self, store):
        # Insert 5 lessons with same prefix (first 30 chars)
        for i in range(5):
            store._conn().execute(
                "INSERT INTO nori_lessons (timestamp, user_id, correction_text, lesson_extracted, applied) "
                "VALUES ('2024-01-01', 'u1', 'c', 'Always verify user name before using it.', 0)"
            )
        store._conn().commit()

        assert store.get_lesson_count() == 5
        store._prune_oldest_duplicates(keep_per_prefix=2)
        # Should keep at most 3 (the param) - but we saved 5, keep 2
        count = store.get_lesson_count()
        assert count <= 3
