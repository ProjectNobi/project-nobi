"""
Tests for natural language proactive check-in toggle phrases.
Verifies that common user phrases correctly match the phrase lists
and that normal conversation doesn't false-positive.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_phrases():
    """Import phrase lists from bot module without starting the bot."""
    # Read the phrase lists directly from the source file to avoid
    # importing the full bot (which requires env vars / telegram)
    import ast
    bot_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "bot.py",
    )
    with open(bot_path) as f:
        source = f.read()

    tree = ast.parse(source)
    phrases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in (
                    "_PROACTIVE_OFF_PHRASES", "_PROACTIVE_ON_PHRASES"
                ):
                    phrases[target.id] = ast.literal_eval(node.value)
    return phrases["_PROACTIVE_OFF_PHRASES"], phrases["_PROACTIVE_ON_PHRASES"]


OFF_PHRASES, ON_PHRASES = _load_phrases()


def _matches_off(message: str) -> bool:
    msg_lower = message.lower()
    return any(phrase in msg_lower for phrase in OFF_PHRASES)


def _matches_on(message: str) -> bool:
    msg_lower = message.lower()
    return any(phrase in msg_lower for phrase in ON_PHRASES)


# ── OFF Phrases ──────────────────────────────────────────────

class TestProactiveOff:
    """Messages that SHOULD trigger proactive OFF."""

    @pytest.mark.parametrize("msg", [
        "stop checking in",
        "Stop checking in on me",
        "please stop check-ins",
        "turn off check-ins",
        "Turn Off Check Ins",
        "disable check-ins",
        "no more check-ins",
        "don't check in on me",
        "dont check in",
        "stop proactive",
        "disable proactive",
        "turn off proactive",
        "no proactive",
        "pause check-ins",
        "I don't want check-ins",
        "i dont want check ins",
        "stop the check-ins please",
        "can you stop reaching out",
        "stop sending me check-ins",
        "Hey Nori, stop checking in please",
    ])
    def test_off_phrase_matches(self, msg):
        assert _matches_off(msg), f"Expected OFF match for: {msg!r}"

    @pytest.mark.parametrize("msg", [
        "stop checking in",
        "STOP CHECK-INS",
        "Stop Checking In On Me",
        "TURN OFF CHECK-INS",
    ])
    def test_off_case_insensitive(self, msg):
        assert _matches_off(msg), f"Case insensitive OFF failed for: {msg!r}"


# ── ON Phrases ───────────────────────────────────────────────

class TestProactiveOn:
    """Messages that SHOULD trigger proactive ON."""

    @pytest.mark.parametrize("msg", [
        "start checking in",
        "Start checking in on me",
        "turn on check-ins",
        "Turn On Check Ins",
        "enable check-ins",
        "enable proactive",
        "turn on proactive",
        "start proactive",
        "please check in on me",
        "you can check in on me",
        "check on me sometimes",
        "resume check-ins",
        "i want check-ins",
        "I want check ins back",
    ])
    def test_on_phrase_matches(self, msg):
        assert _matches_on(msg), f"Expected ON match for: {msg!r}"


# ── False Positives ──────────────────────────────────────────

class TestNoFalsePositives:
    """Normal conversation that should NOT trigger the toggle."""

    @pytest.mark.parametrize("msg", [
        "Hello!",
        "How are you?",
        "Tell me about checking accounts",
        "I need to check in at the hotel",
        "Can you help me check in for my flight?",
        "What time should I check in?",
        "I was checking in on my friend",
        "Let me check in with my boss",
        "The doctor wants to check in next week",
        "I love the proactive approach to learning",
        "Being proactive is important",
        "I should stop procrastinating",
        "Can you turn off the lights?",
        "I want to check something",
        "Stop it you're making me laugh",
        "Don't forget to check the oven",
        "I want to start a new hobby",
        "Please disable my alarm",
        "No more excuses",
        "I need to pause for a moment",
    ])
    def test_no_false_positive_off(self, msg):
        assert not _matches_off(msg), f"False positive OFF for: {msg!r}"

    @pytest.mark.parametrize("msg", [
        "Hello!",
        "How are you?",
        "I need to check in at the hotel",
        "Can you start the timer?",
        "Turn on the lights",
        "Enable dark mode",
        "I want to resume my workout",
        "Check on the weather",
        "Check in at the airport",
        "I want to start cooking",
    ])
    def test_no_false_positive_on(self, msg):
        assert not _matches_on(msg), f"False positive ON for: {msg!r}"


# ── Mutual Exclusivity ──────────────────────────────────────

class TestMutualExclusivity:
    """OFF phrases should not match ON and vice versa."""

    def test_off_not_on(self):
        for phrase in OFF_PHRASES:
            assert not _matches_on(phrase), (
                f"OFF phrase matched ON: {phrase!r}"
            )

    def test_on_not_off(self):
        for phrase in ON_PHRASES:
            # "start checking in" contains "checking in" but shouldn't match OFF
            # unless an OFF phrase is a substring — check carefully
            if _matches_off(phrase):
                # Only acceptable if it's a legitimate substring overlap
                # e.g. "start checking in on me" contains "stop checking in on me"? No.
                pytest.fail(f"ON phrase matched OFF: {phrase!r}")
