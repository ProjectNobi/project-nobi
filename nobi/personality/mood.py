"""
Mood detection from user messages.
Lightweight keyword/pattern matching — no LLM calls.
"""

import re
from typing import Optional


# Patterns ordered by specificity (more specific first)
_MOOD_PATTERNS: list[tuple[str, list[str]]] = [
    ("angry", [
        r"\b(angry|furious|pissed|pissed off|mad as hell|livid|enraged|fuming|outraged)\b",
        r"\b(hate this|hate it|so annoying|ugh+|argh+)\b",
        r"\b(wtf|what the hell|are you kidding)\b",
        r"(!{3,})",  # Multiple exclamation marks with negative words nearby
    ]),
    ("sad", [
        r"\b(sad|depressed|down|upset|unhappy|miserable|heartbroken|devastated|lonely)\b",
        r"\b(feeling (low|bad|terrible|awful|empty|lost|hopeless))\b",
        r"\b(crying|cried|tears|can'?t stop crying)\b",
        r"\b(miss (you|him|her|them|it)|i miss)\b",
        r"\b(rough (day|week|time|patch))\b",
        r"(😢|😭|💔|😞|😔)",
    ]),
    ("stressed", [
        r"\b(stressed|overwhelmed|anxious|nervous|panicking|freaking out|burned out|burnout)\b",
        r"\b(too much|can'?t handle|can'?t cope|falling apart|losing it)\b",
        r"\b(deadline|pressure|swamped|drowning in)\b",
        r"\b(anxiety|panic attack|worried sick)\b",
    ]),
    ("excited", [
        r"\b(excited|thrilled|pumped|stoked|hyped|ecstatic|amazing|awesome|incredible)\b",
        r"\b(can'?t wait|so happy|best (day|thing|news)|omg|oh my god)\b",
        r"(!{2,})",  # Multiple exclamation marks
        r"(🎉|🥳|🎊|🔥|💥|🚀|✨)",
        r"\b(let'?s go+|yes+|woo+|yay+)\b",
    ]),
    ("happy", [
        r"\b(happy|glad|pleased|joyful|grateful|thankful|blessed|content|cheerful|delighted)\b",
        r"\b(good (day|mood|vibes|news|time))\b",
        r"\b(feeling (great|good|wonderful|fantastic))\b",
        r"(😊|😄|😁|🥰|❤️|💕|😍)",
        r"\b(love it|love this|love that)\b",
    ]),
    ("curious", [
        r"\b(wondering|curious|interested|how does|what is|why does|tell me about)\b",
        r"\b(explain|teach me|help me understand|what do you think)\b",
        r"(\?{2,})",  # Multiple question marks
        r"\b(hmm+|huh|really\?)\b",
    ]),
    ("playful", [
        r"\b(haha|hehe|lol|lmao|rofl|😂|🤣|😜|😝|😏)\b",
        r"\b(just kidding|jk|joking|funny|hilarious|lolol)\b",
        r"\b(dare you|bet you|challenge|game on)\b",
        r"\b(meme|vibes|vibe check|no cap|slay|based)\b",
    ]),
]


def detect_mood(message: str) -> str:
    """
    Detect the dominant mood from a user message.

    Returns one of: happy, sad, stressed, excited, neutral, angry, curious, playful
    """
    if not message or not message.strip():
        return "neutral"

    text = message.lower().strip()
    scores: dict[str, int] = {}

    for mood, patterns in _MOOD_PATTERNS:
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                scores[mood] = scores.get(mood, 0) + len(matches)

    if not scores:
        return "neutral"

    # Return the mood with the highest score
    return max(scores, key=scores.get)


def get_mood_emoji(mood: str) -> str:
    """Get a representative emoji for a mood."""
    return {
        "happy": "😊",
        "sad": "😢",
        "stressed": "😰",
        "excited": "🎉",
        "neutral": "😐",
        "angry": "😠",
        "curious": "🤔",
        "playful": "😜",
    }.get(mood, "😐")
