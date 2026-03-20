"""
PersonalityTuner — Analyzes conversations, detects issues,
tracks quality metrics, and suggests prompt improvements.
"""

import re
import sqlite3
import json
import time
import unicodedata
from typing import Optional

from nobi.personality.mood import detect_mood


# ─── Emoji helpers ───────────────────────────────────────────

def _count_emoji(text: str) -> int:
    """Count emoji characters in text."""
    count = 0
    for ch in text:
        # Check Unicode category: So (Symbol, other) covers most emoji
        if unicodedata.category(ch) in ("So", "Sk"):
            count += 1
        # Also catch regional indicators, modifiers, etc.
        elif 0x1F600 <= ord(ch) <= 0x1F9FF:
            count += 1
        elif 0x2600 <= ord(ch) <= 0x27BF:
            count += 1
        elif 0x1FA00 <= ord(ch) <= 0x1FAFF:
            count += 1
    return count


# ─── Robotic phrases ────────────────────────────────────────

_ROBOTIC_PHRASES = [
    r"as an ai\b",
    r"i don'?t have feelings",
    r"i'?m just a (language )?model",
    r"as a language model",
    r"i don'?t have (personal )?(experiences?|opinions?|emotions?)",
    r"i'?m an artificial intelligence",
    r"i lack the ability",
    r"i cannot experience",
    r"i was programmed to",
    r"my training data",
    r"i don'?t have consciousness",
]

_GENERIC_PHRASES = [
    r"^(hey there!? )?how can i (help|assist) you",
    r"^i'?m here to help",
    r"^hello!? (how can i|what can i)",
    r"^sure!? i'?d be happy to help",
    r"^of course!? (let me|i can|i'?d be)",
    r"^great question!",
    r"^that'?s a (great|good|interesting) question",
    r"^absolutely!? (let me|i can)",
]


class PersonalityTuner:
    """Analyzes and tunes Nori's personality based on conversation data."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, timeout=30)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        c = self._conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_message TEXT NOT NULL,
                nori_response TEXT NOT NULL,
                tone TEXT,
                engagement_level REAL,
                follow_up_quality REAL,
                warmth_score REAL,
                verbosity REAL,
                quality_score REAL,
                detected_mood TEXT,
                issues TEXT  -- JSON list of detected issues
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                user_id TEXT NOT NULL,
                response_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # ─── Analysis ────────────────────────────────────────────

    def analyze_conversation(self, user_message: str, nori_response: str) -> dict:
        """
        Analyze a conversation exchange and return metrics.

        Returns dict with keys:
            tone, engagement_level, follow_up_quality, warmth_score, verbosity
        """
        issues = self.detect_issues(nori_response)
        quality = self.get_response_quality_score(nori_response)
        mood = detect_mood(user_message)

        # Tone detection
        tone = self._detect_tone(nori_response)

        # Engagement: does Nori ask questions?
        has_question = "?" in nori_response
        engagement = 0.8 if has_question else 0.4

        # Follow-up quality: references user content?
        user_words = set(user_message.lower().split())
        response_words = set(nori_response.lower().split())
        overlap = len(user_words & response_words - {"i", "a", "the", "is", "are", "to", "and", "of", "in", "it"})
        follow_up = min(1.0, overlap / max(len(user_words), 1) + (0.3 if has_question else 0.0))

        # Warmth: emoji, personal language, empathetic words
        warmth = self._score_warmth(nori_response)

        # Verbosity: ratio of response length to message length
        verbosity = len(nori_response) / max(len(user_message), 1)

        result = {
            "tone": tone,
            "engagement_level": round(engagement, 2),
            "follow_up_quality": round(follow_up, 2),
            "warmth_score": round(warmth, 2),
            "verbosity": round(verbosity, 2),
            "quality_score": round(quality, 2),
            "detected_mood": mood,
            "issues": issues,
        }

        # Store in DB
        c = self._conn.cursor()
        c.execute(
            """INSERT INTO conversation_metrics
               (timestamp, user_message, nori_response, tone, engagement_level,
                follow_up_quality, warmth_score, verbosity, quality_score,
                detected_mood, issues)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(), user_message, nori_response,
                result["tone"], result["engagement_level"],
                result["follow_up_quality"], result["warmth_score"],
                result["verbosity"], result["quality_score"],
                result["detected_mood"], json.dumps(result["issues"]),
            ),
        )
        self._conn.commit()

        return result

    def _detect_tone(self, response: str) -> str:
        """Detect the overall tone of a response."""
        text = response.lower()
        emoji_count = _count_emoji(response)

        # Check for warmth indicators
        warm_words = ["love", "glad", "happy", "wonderful", "great", "amazing", "awesome", "❤", "💛", "🤗"]
        warm_count = sum(1 for w in warm_words if w in text)

        if warm_count >= 2 or emoji_count >= 2:
            return "warm"
        elif any(re.search(p, text) for p in _ROBOTIC_PHRASES):
            return "robotic"
        elif "!" in response and emoji_count >= 1:
            return "enthusiastic"
        elif "?" in response:
            return "engaging"
        else:
            return "neutral"

    def _score_warmth(self, response: str) -> float:
        """Score warmth from 0-1."""
        text = response.lower()
        score = 0.5  # baseline

        # Emoji presence (moderate)
        emoji_count = _count_emoji(response)
        if 1 <= emoji_count <= 3:
            score += 0.15
        elif emoji_count > 3:
            score += 0.05  # too many is try-hard

        # Personal/warm words
        warm_patterns = [
            r"\b(glad|happy|love|wonderful|great|awesome|amazing)\b",
            r"\b(friend|care|support|here for you|proud of you)\b",
            r"\b(you'?re|your)\b",  # Addressing the user directly
        ]
        for p in warm_patterns:
            if re.search(p, text):
                score += 0.1

        # Robotic language penalizes warmth
        for p in _ROBOTIC_PHRASES:
            if re.search(p, text):
                score -= 0.2

        return max(0.0, min(1.0, score))

    # ─── Issue Detection ─────────────────────────────────────

    def detect_issues(self, nori_response: str) -> list[str]:
        """
        Detect personality issues in a response.

        Returns list of issue strings.
        """
        issues = []
        text = nori_response
        lower = text.lower()

        # Too verbose (>300 chars for what could be a simple reply)
        if len(text) > 300:
            issues.append("too_verbose")

        # Too robotic
        for pattern in _ROBOTIC_PHRASES:
            if re.search(pattern, lower):
                issues.append("too_robotic")
                break

        # Too generic
        for pattern in _GENERIC_PHRASES:
            if re.search(pattern, lower):
                issues.append("too_generic")
                break

        # Over-emoji (>3 emoji)
        emoji_count = _count_emoji(text)
        if emoji_count > 3:
            issues.append("over_emoji")

        # Under-emoji (0 emoji in a casual-length response)
        if emoji_count == 0 and 20 < len(text) < 300:
            issues.append("under_emoji")

        # Wall of text without line breaks
        if len(text) > 200 and "\n" not in text:
            issues.append("wall_of_text")

        # Starts with "I" too often
        if text.strip().startswith("I ") or text.strip().startswith("I'"):
            issues.append("starts_with_i")

        # No follow-up question
        if "?" not in text and len(text) > 30:
            issues.append("no_follow_up")

        return issues

    # ─── Quality Scoring ─────────────────────────────────────

    def get_response_quality_score(self, response: str) -> float:
        """
        Quick heuristic quality check (0-1).

        Higher = better quality response.
        """
        if not response or not response.strip():
            return 0.0

        score = 0.7  # baseline for any non-empty response

        issues = self.detect_issues(response)

        # Deductions per issue
        deductions = {
            "too_verbose": 0.1,
            "too_robotic": 0.25,
            "too_generic": 0.2,
            "over_emoji": 0.1,
            "under_emoji": 0.05,
            "wall_of_text": 0.1,
            "starts_with_i": 0.05,
            "no_follow_up": 0.1,
        }

        for issue in issues:
            score -= deductions.get(issue, 0.05)

        # Bonuses
        # Has a question mark (engaging)
        if "?" in response:
            score += 0.1

        # Good length range (50-250 chars)
        length = len(response)
        if 50 <= length <= 250:
            score += 0.1
        elif length < 10:
            score -= 0.2

        # Has emoji but not too many
        emoji_count = _count_emoji(response)
        if 1 <= emoji_count <= 2:
            score += 0.05

        return max(0.0, min(1.0, round(score, 2)))

    # ─── Feedback ────────────────────────────────────────────

    def record_feedback(self, user_id: str, response_id: str, rating: int, comment: str = ""):
        """Record user feedback for a response (rating 1-5)."""
        c = self._conn.cursor()
        c.execute(
            "INSERT INTO feedback (timestamp, user_id, response_id, rating, comment) VALUES (?, ?, ?, ?, ?)",
            (time.time(), user_id, response_id, rating, comment),
        )
        self._conn.commit()

    # ─── Stats ───────────────────────────────────────────────

    def get_personality_stats(self) -> dict:
        """
        Return aggregate personality stats from stored conversation metrics.
        """
        c = self._conn.cursor()
        c.execute("""
            SELECT
                AVG(warmth_score) as avg_warmth,
                AVG(engagement_level) as avg_engagement,
                AVG(quality_score) as avg_quality,
                AVG(verbosity) as avg_verbosity,
                COUNT(*) as total_conversations
            FROM conversation_metrics
        """)
        row = c.fetchone()

        if not row or row["total_conversations"] == 0:
            return {
                "avg_warmth": 0.0,
                "avg_engagement": 0.0,
                "avg_quality": 0.0,
                "avg_verbosity": 0.0,
                "total_conversations": 0,
                "common_issues": [],
            }

        # Get common issues
        c.execute("SELECT issues FROM conversation_metrics WHERE issues != '[]'")
        all_issues: dict[str, int] = {}
        for r in c.fetchall():
            for issue in json.loads(r["issues"]):
                all_issues[issue] = all_issues.get(issue, 0) + 1

        common = sorted(all_issues.items(), key=lambda x: -x[1])[:5]

        return {
            "avg_warmth": round(row["avg_warmth"] or 0.0, 2),
            "avg_engagement": round(row["avg_engagement"] or 0.0, 2),
            "avg_quality": round(row["avg_quality"] or 0.0, 2),
            "avg_verbosity": round(row["avg_verbosity"] or 0.0, 2),
            "total_conversations": row["total_conversations"],
            "common_issues": [{"issue": k, "count": v} for k, v in common],
        }

    # ─── Suggestions ─────────────────────────────────────────

    def suggest_improvements(self) -> list[str]:
        """
        Based on accumulated data, suggest prompt/behavior changes.
        """
        stats = self.get_personality_stats()
        suggestions = []

        if stats["total_conversations"] == 0:
            return ["No conversation data yet. Start analyzing conversations to get suggestions."]

        if stats["avg_warmth"] < 0.5:
            suggestions.append(
                "Warmth is low (avg {:.2f}). Consider adding more empathetic language, "
                "personal touches, and appropriate emoji to responses.".format(stats["avg_warmth"])
            )

        if stats["avg_engagement"] < 0.6:
            suggestions.append(
                "Engagement is low (avg {:.2f}). Nori should ask more follow-up questions "
                "to show genuine curiosity about the user's life.".format(stats["avg_engagement"])
            )

        if stats["avg_verbosity"] > 5.0:
            suggestions.append(
                "Responses are too verbose (avg ratio {:.1f}x). Keep replies concise — "
                "2-3 sentences for casual chat.".format(stats["avg_verbosity"])
            )

        if stats["avg_quality"] < 0.5:
            suggestions.append(
                "Overall quality is low (avg {:.2f}). Review common issues and "
                "address the most frequent problems.".format(stats["avg_quality"])
            )

        # Issue-specific suggestions
        issue_map = {i["issue"]: i["count"] for i in stats["common_issues"]}

        if issue_map.get("too_robotic", 0) > 0:
            suggestions.append(
                "Robotic language detected {} times. Remove phrases like 'As an AI' or "
                "'I don't have feelings' from responses.".format(issue_map["too_robotic"])
            )

        if issue_map.get("too_generic", 0) > 0:
            suggestions.append(
                "Generic responses detected {} times. Personalize replies — reference "
                "user context, use their name, mention past conversations.".format(issue_map["too_generic"])
            )

        if issue_map.get("no_follow_up", 0) > 0:
            suggestions.append(
                "Missing follow-up questions in {} responses. Add a genuine question "
                "to keep the conversation flowing.".format(issue_map["no_follow_up"])
            )

        if issue_map.get("wall_of_text", 0) > 0:
            suggestions.append(
                "Wall of text detected {} times. Break long responses into shorter "
                "paragraphs with line breaks.".format(issue_map["wall_of_text"])
            )

        if not suggestions:
            suggestions.append("Looking good! No major issues detected. Keep monitoring.")

        return suggestions
