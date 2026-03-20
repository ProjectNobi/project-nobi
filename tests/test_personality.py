"""
Tests for the Nori Personality Tuning System.
Covers: issue detection, mood detection, quality scoring,
dynamic prompt selection, personality variants, feedback recording.
"""

import pytest
from nobi.personality.tuner import PersonalityTuner, _count_emoji
from nobi.personality.mood import detect_mood, get_mood_emoji
from nobi.personality.prompts import (
    get_dynamic_prompt,
    get_variant_for_mood,
    PERSONALITY_VARIANTS,
)


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def tuner():
    t = PersonalityTuner(":memory:")
    yield t
    t.close()


# ─── Emoji counting ─────────────────────────────────────────

class TestEmojiCount:
    def test_no_emoji(self):
        assert _count_emoji("Hello world") == 0

    def test_single_emoji(self):
        assert _count_emoji("Hello 😊") == 1

    def test_multiple_emoji(self):
        assert _count_emoji("🎉🔥✨💕") >= 3

    def test_mixed_text_emoji(self):
        assert _count_emoji("Great job! 👍 Keep it up! 🚀") == 2


# ─── Issue Detection ────────────────────────────────────────

class TestIssueDetection:
    def test_too_verbose(self, tuner):
        long_text = "This is a very long response. " * 20
        issues = tuner.detect_issues(long_text)
        assert "too_verbose" in issues

    def test_not_verbose_short(self, tuner):
        issues = tuner.detect_issues("Hey! How's it going? 😊")
        assert "too_verbose" not in issues

    def test_too_robotic_as_an_ai(self, tuner):
        issues = tuner.detect_issues("As an AI, I don't have personal experiences.")
        assert "too_robotic" in issues

    def test_too_robotic_language_model(self, tuner):
        issues = tuner.detect_issues("I'm just a language model, I can't feel emotions.")
        assert "too_robotic" in issues

    def test_not_robotic(self, tuner):
        issues = tuner.detect_issues("That sounds really exciting! Tell me more about your trip 😊")
        assert "too_robotic" not in issues

    def test_too_generic(self, tuner):
        issues = tuner.detect_issues("How can I help you today?")
        assert "too_generic" in issues

    def test_too_generic_sure(self, tuner):
        issues = tuner.detect_issues("Sure! I'd be happy to help with that.")
        assert "too_generic" in issues

    def test_over_emoji(self, tuner):
        issues = tuner.detect_issues("OMG 🎉🔥✨💕🚀 that's amazing!!!")
        assert "over_emoji" in issues

    def test_under_emoji(self, tuner):
        issues = tuner.detect_issues("That sounds really nice, I hope you enjoy it.")
        assert "under_emoji" in issues

    def test_wall_of_text(self, tuner):
        wall = "A" * 250  # Long text, no line breaks
        issues = tuner.detect_issues(wall)
        assert "wall_of_text" in issues

    def test_not_wall_with_breaks(self, tuner):
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here and some more text to make it longer than 200 characters total so we can verify line breaks help."
        issues = tuner.detect_issues(text)
        assert "wall_of_text" not in issues

    def test_starts_with_i(self, tuner):
        issues = tuner.detect_issues("I think that's a great idea!")
        assert "starts_with_i" in issues

    def test_no_follow_up(self, tuner):
        issues = tuner.detect_issues("That's great, I'm glad to hear it. Keep going!")
        assert "no_follow_up" in issues

    def test_has_follow_up(self, tuner):
        issues = tuner.detect_issues("That's great! What inspired you to start?")
        assert "no_follow_up" not in issues


# ─── Mood Detection ─────────────────────────────────────────

class TestMoodDetection:
    def test_sad_mood(self):
        assert detect_mood("I'm feeling really sad today") == "sad"

    def test_sad_rough_day(self):
        assert detect_mood("had a rough day") == "sad"

    def test_happy_mood(self):
        assert detect_mood("I'm so happy right now! 😊") == "happy"

    def test_excited_mood(self):
        assert detect_mood("OMG this is amazing!!!") == "excited"

    def test_stressed_mood(self):
        assert detect_mood("I'm so stressed and overwhelmed with everything") == "stressed"

    def test_angry_mood(self):
        assert detect_mood("I'm so angry and furious about this") == "angry"

    def test_curious_mood(self):
        assert detect_mood("I'm curious, how does this work??") == "curious"

    def test_playful_mood(self):
        assert detect_mood("haha lol that's so funny 😂") == "playful"

    def test_neutral_mood(self):
        assert detect_mood("ok") == "neutral"

    def test_empty_message(self):
        assert detect_mood("") == "neutral"

    def test_mood_emoji_helper(self):
        assert get_mood_emoji("happy") == "😊"
        assert get_mood_emoji("sad") == "😢"
        assert get_mood_emoji("unknown") == "😐"


# ─── Quality Scoring ────────────────────────────────────────

class TestQualityScoring:
    def test_good_response(self, tuner):
        response = "That sounds awesome! How long have you been working on it? 😊"
        score = tuner.get_response_quality_score(response)
        assert score >= 0.6

    def test_robotic_response_low_score(self, tuner):
        response = "As an AI, I don't have feelings, but I can help you with that."
        score = tuner.get_response_quality_score(response)
        assert score < 0.6

    def test_empty_response_zero(self, tuner):
        assert tuner.get_response_quality_score("") == 0.0

    def test_very_short_response(self, tuner):
        score = tuner.get_response_quality_score("ok")
        assert score < 0.6

    def test_score_range(self, tuner):
        for text in ["Hello!", "A" * 500, "As an AI, I cannot do that.", "Great! How are you? 😊"]:
            score = tuner.get_response_quality_score(text)
            assert 0.0 <= score <= 1.0


# ─── Conversation Analysis ──────────────────────────────────

class TestConversationAnalysis:
    def test_analyze_returns_all_keys(self, tuner):
        result = tuner.analyze_conversation("How are you?", "I'm doing great! How about you? 😊")
        assert "tone" in result
        assert "engagement_level" in result
        assert "follow_up_quality" in result
        assert "warmth_score" in result
        assert "verbosity" in result
        assert "quality_score" in result
        assert "detected_mood" in result
        assert "issues" in result

    def test_analyze_stores_in_db(self, tuner):
        tuner.analyze_conversation("Hello!", "Hey there! How's your day going? 😊")
        stats = tuner.get_personality_stats()
        assert stats["total_conversations"] == 1

    def test_engagement_with_question(self, tuner):
        result = tuner.analyze_conversation("I got a new job!", "That's amazing! What's the role?")
        assert result["engagement_level"] >= 0.7

    def test_engagement_without_question(self, tuner):
        result = tuner.analyze_conversation("I got a new job!", "That's nice.")
        assert result["engagement_level"] < 0.6


# ─── Feedback ────────────────────────────────────────────────

class TestFeedback:
    def test_record_feedback(self, tuner):
        tuner.record_feedback("user123", "resp456", 5, "Great response!")
        # Verify it was stored
        c = tuner._conn.cursor()
        c.execute("SELECT * FROM feedback")
        rows = c.fetchall()
        assert len(rows) == 1
        assert rows[0]["rating"] == 5
        assert rows[0]["user_id"] == "user123"

    def test_record_feedback_no_comment(self, tuner):
        tuner.record_feedback("user123", "resp789", 3)
        c = tuner._conn.cursor()
        c.execute("SELECT comment FROM feedback")
        assert c.fetchone()["comment"] == ""


# ─── Personality Stats ───────────────────────────────────────

class TestPersonalityStats:
    def test_empty_stats(self, tuner):
        stats = tuner.get_personality_stats()
        assert stats["total_conversations"] == 0
        assert stats["avg_warmth"] == 0.0

    def test_stats_after_conversations(self, tuner):
        tuner.analyze_conversation("Hi!", "Hey! How are you doing today? 😊")
        tuner.analyze_conversation("I'm sad", "I'm sorry to hear that 💛 What happened?")
        stats = tuner.get_personality_stats()
        assert stats["total_conversations"] == 2
        assert stats["avg_warmth"] > 0
        assert stats["avg_engagement"] > 0


# ─── Suggestions ─────────────────────────────────────────────

class TestSuggestions:
    def test_no_data_suggestion(self, tuner):
        suggestions = tuner.suggest_improvements()
        assert len(suggestions) == 1
        assert "No conversation data" in suggestions[0]

    def test_suggestions_with_robotic_data(self, tuner):
        tuner.analyze_conversation("Hi", "As an AI, I don't have feelings but hello.")
        suggestions = tuner.suggest_improvements()
        assert any("robotic" in s.lower() for s in suggestions)


# ─── Dynamic Prompts ────────────────────────────────────────

class TestDynamicPrompts:
    def test_all_variants_exist(self):
        assert "default" in PERSONALITY_VARIANTS
        assert "warmer" in PERSONALITY_VARIANTS
        assert "concise" in PERSONALITY_VARIANTS
        assert "playful" in PERSONALITY_VARIANTS
        assert "professional" in PERSONALITY_VARIANTS

    def test_variants_non_empty(self):
        for key, val in PERSONALITY_VARIANTS.items():
            assert len(val) > 50, f"Variant '{key}' is too short"

    def test_sad_mood_gets_warmer(self):
        assert get_variant_for_mood("sad") == "warmer"

    def test_excited_mood_gets_playful(self):
        assert get_variant_for_mood("excited") == "playful"

    def test_curious_mood_gets_professional(self):
        assert get_variant_for_mood("curious") == "professional"

    def test_neutral_mood_gets_default(self):
        assert get_variant_for_mood("neutral") == "default"

    def test_dynamic_prompt_returns_string(self):
        prompt = get_dynamic_prompt("user1", "I'm feeling down today", "sad")
        assert isinstance(prompt, str)
        assert "Nori" in prompt
        assert "empathetic" in prompt.lower() or "gentle" in prompt.lower()

    def test_dynamic_prompt_auto_detects_mood(self):
        prompt = get_dynamic_prompt("user1", "This is so exciting!!!", None)
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_dynamic_prompt_stressed(self):
        prompt = get_dynamic_prompt("user1", "I'm overwhelmed", "stressed")
        assert "stressed" in prompt.lower() or "pressure" in prompt.lower()
