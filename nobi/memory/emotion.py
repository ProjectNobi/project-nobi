"""
Emotion Time-Series Tracking for Nori.

Tracks emotional state per message and builds trend analysis over time.
Emotions: joy, sadness, anger, fear, surprise, neutral

Features:
  - Per-message emotion detection via LLM
  - SQLite persistence in emotion_readings table
  - 7-day trend analysis
  - Current mood inference for system prompt injection
  - Mood-aware response tuning
"""

import os
import json
import logging
import sqlite3
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger("nobi-emotion")

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# Emotion labels
EMOTIONS = ("joy", "sadness", "anger", "fear", "surprise", "neutral")

# Non-neutral threshold — below this intensity, mood = "neutral"
NEUTRAL_THRESHOLD = 0.35

_EMOTION_PROMPT = """Analyze the emotional content of this message and output a JSON object.

Message: "{text}"

Output ONLY valid JSON (no explanation, no markdown):
{{
  "joy": 0.0,
  "sadness": 0.0,
  "anger": 0.0,
  "fear": 0.0,
  "surprise": 0.0,
  "neutral": 0.0,
  "dominant": "joy|sadness|anger|fear|surprise|neutral",
  "intensity": 0.0
}}

Rules:
- All emotion values must be between 0.0 and 1.0
- Values should sum to approximately 1.0
- dominant = emotion with highest value
- intensity = how strongly the user expresses any emotion (0.0 = very flat, 1.0 = very intense)
- For neutral/casual messages, set neutral >= 0.7 and intensity < 0.3
"""


@dataclass
class EmotionReading:
    """Emotion reading for a single message."""
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    fear: float = 0.0
    surprise: float = 0.0
    neutral: float = 1.0
    dominant: str = "neutral"
    intensity: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "joy": self.joy,
            "sadness": self.sadness,
            "anger": self.anger,
            "fear": self.fear,
            "surprise": self.surprise,
            "neutral": self.neutral,
            "dominant": self.dominant,
            "intensity": self.intensity,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EmotionReading":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                ts = datetime.now(timezone.utc)
        elif ts is None:
            ts = datetime.now(timezone.utc)
        return cls(
            joy=float(data.get("joy", 0.0)),
            sadness=float(data.get("sadness", 0.0)),
            anger=float(data.get("anger", 0.0)),
            fear=float(data.get("fear", 0.0)),
            surprise=float(data.get("surprise", 0.0)),
            neutral=float(data.get("neutral", 1.0)),
            dominant=str(data.get("dominant", "neutral")),
            intensity=float(data.get("intensity", 0.0)),
            timestamp=ts,
        )

    @property
    def is_neutral(self) -> bool:
        return self.dominant == "neutral" or self.intensity < NEUTRAL_THRESHOLD


@dataclass
class EmotionTrend:
    """Emotion trend over a time window."""
    user_id: str
    days: int
    avg_joy: float = 0.0
    avg_sadness: float = 0.0
    avg_anger: float = 0.0
    avg_fear: float = 0.0
    avg_surprise: float = 0.0
    avg_neutral: float = 1.0
    avg_intensity: float = 0.0
    dominant_mood: str = "neutral"
    reading_count: int = 0
    trend_direction: str = "stable"  # improving, declining, stable

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "days": self.days,
            "avg_joy": round(self.avg_joy, 3),
            "avg_sadness": round(self.avg_sadness, 3),
            "avg_anger": round(self.avg_anger, 3),
            "avg_fear": round(self.avg_fear, 3),
            "avg_surprise": round(self.avg_surprise, 3),
            "avg_neutral": round(self.avg_neutral, 3),
            "avg_intensity": round(self.avg_intensity, 3),
            "dominant_mood": self.dominant_mood,
            "reading_count": self.reading_count,
            "trend_direction": self.trend_direction,
        }


def _get_llm_client():
    if not _OPENAI_AVAILABLE:
        return None
    api_key = os.environ.get("CHUTES_API_KEY", "")
    if not api_key:
        return None
    base_url = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")
    return OpenAI(base_url=base_url, api_key=api_key)


def _get_model() -> str:
    return os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")


def _ensure_emotion_table(conn: sqlite3.Connection):
    """Create emotion_readings table if not exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emotion_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            message_hash TEXT NOT NULL,
            joy REAL DEFAULT 0.0,
            sadness REAL DEFAULT 0.0,
            anger REAL DEFAULT 0.0,
            fear REAL DEFAULT 0.0,
            surprise REAL DEFAULT 0.0,
            neutral REAL DEFAULT 1.0,
            dominant TEXT DEFAULT 'neutral',
            intensity REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_emotion_user ON emotion_readings(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_emotion_ts ON emotion_readings(user_id, timestamp)")
    conn.commit()


def _parse_json_safely(text: str) -> Dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


async def detect_emotion(text: str) -> EmotionReading:
    """
    Detect emotion in text using LLM.

    Args:
        text: Message text to analyse.

    Returns:
        EmotionReading with scores for all emotions.
        Falls back to neutral reading if LLM unavailable.
    """
    if not text or len(text.strip()) < 3:
        return EmotionReading()

    client = _get_llm_client()
    if not client:
        # Fallback: keyword-based emotion detection
        return _keyword_emotion_detect(text)

    # Truncate for token efficiency
    text_truncated = text[:500]
    prompt = _EMOTION_PROMPT.format(text=text_truncated.replace('"', '\\"'))

    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        data = _parse_json_safely(raw)

        if not data:
            return _keyword_emotion_detect(text)

        # Clamp all values
        reading = EmotionReading(
            joy=max(0.0, min(1.0, float(data.get("joy", 0.0)))),
            sadness=max(0.0, min(1.0, float(data.get("sadness", 0.0)))),
            anger=max(0.0, min(1.0, float(data.get("anger", 0.0)))),
            fear=max(0.0, min(1.0, float(data.get("fear", 0.0)))),
            surprise=max(0.0, min(1.0, float(data.get("surprise", 0.0)))),
            neutral=max(0.0, min(1.0, float(data.get("neutral", 0.0)))),
            dominant=str(data.get("dominant", "neutral")),
            intensity=max(0.0, min(1.0, float(data.get("intensity", 0.0)))),
        )
        # Validate dominant is a known emotion
        if reading.dominant not in EMOTIONS:
            reading.dominant = "neutral"

        return reading

    except Exception as e:
        logger.warning(f"[Emotion] LLM detection failed: {e}")
        return _keyword_emotion_detect(text)


def _keyword_emotion_detect(text: str) -> EmotionReading:
    """Simple keyword-based emotion detection as fallback."""
    text_lower = text.lower()

    JOY_WORDS = {"happy", "glad", "excited", "love", "great", "amazing", "wonderful", "yay", "😊", "😄", "❤️", "haha", "lol"}
    SAD_WORDS = {"sad", "unhappy", "depressed", "cry", "crying", "miss", "lonely", "heartbreak", "😢", "😭", "😔"}
    ANGER_WORDS = {"angry", "mad", "furious", "hate", "annoyed", "frustrated", "wtf", "damn", "😤", "😠", "🤬"}
    FEAR_WORDS = {"scared", "afraid", "worried", "anxious", "nervous", "panic", "terrified", "😰", "😨", "😱"}
    SURPRISE_WORDS = {"wow", "omg", "surprised", "unexpected", "shocked", "whoa", "seriously", "😮", "😲", "🤯"}

    scores = {
        "joy": sum(1 for w in JOY_WORDS if w in text_lower) / max(len(JOY_WORDS), 1),
        "sadness": sum(1 for w in SAD_WORDS if w in text_lower) / max(len(SAD_WORDS), 1),
        "anger": sum(1 for w in ANGER_WORDS if w in text_lower) / max(len(ANGER_WORDS), 1),
        "fear": sum(1 for w in FEAR_WORDS if w in text_lower) / max(len(FEAR_WORDS), 1),
        "surprise": sum(1 for w in SURPRISE_WORDS if w in text_lower) / max(len(SURPRISE_WORDS), 1),
    }

    # Normalise
    total = sum(scores.values())
    if total > 0:
        for k in scores:
            scores[k] = min(1.0, scores[k] * 5)  # scale up keyword hits
    else:
        scores["neutral"] = 1.0

    dominant = max(scores, key=scores.get) if scores else "neutral"
    intensity = min(1.0, max(scores.values()) * 2) if scores else 0.0
    neutral_val = 1.0 - intensity

    return EmotionReading(
        joy=scores.get("joy", 0.0),
        sadness=scores.get("sadness", 0.0),
        anger=scores.get("anger", 0.0),
        fear=scores.get("fear", 0.0),
        surprise=scores.get("surprise", 0.0),
        neutral=neutral_val,
        dominant=dominant if intensity > NEUTRAL_THRESHOLD else "neutral",
        intensity=intensity,
    )


async def store_emotion_reading(
    user_id: str,
    message: str,
    reading: EmotionReading,
    db_path: str = "~/.nobi/bot_memories.db",
):
    """Store an emotion reading to SQLite."""
    db_path_expanded = os.path.expanduser(db_path)
    db_dir = os.path.dirname(db_path_expanded)
    if db_dir and not os.path.exists(db_dir):
        return

    message_hash = hashlib.sha256(f"{user_id}:{message[:200]}".encode()).hexdigest()[:16]

    conn = sqlite3.connect(db_path_expanded)
    try:
        _ensure_emotion_table(conn)
        conn.execute(
            """INSERT INTO emotion_readings
               (user_id, message_hash, joy, sadness, anger, fear, surprise, neutral,
                dominant, intensity, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                user_id, message_hash,
                reading.joy, reading.sadness, reading.anger,
                reading.fear, reading.surprise, reading.neutral,
                reading.dominant, reading.intensity,
                reading.timestamp.isoformat(),
            ]
        )
        conn.commit()
    except Exception as e:
        logger.error(f"[Emotion] Store error: {e}")
        conn.rollback()
    finally:
        conn.close()


async def get_emotion_trend(
    user_id: str,
    days: int = 7,
    db_path: str = "~/.nobi/bot_memories.db",
) -> EmotionTrend:
    """
    Calculate emotion trend over the last N days.

    Args:
        user_id: User identifier.
        days: Number of days to look back.
        db_path: SQLite DB path.

    Returns:
        EmotionTrend with averages and dominant mood.
    """
    db_path_expanded = os.path.expanduser(db_path)
    trend = EmotionTrend(user_id=user_id, days=days)

    if not os.path.exists(db_path_expanded):
        return trend

    conn = sqlite3.connect(db_path_expanded)
    conn.row_factory = sqlite3.Row

    try:
        _ensure_emotion_table(conn)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """SELECT joy, sadness, anger, fear, surprise, neutral, intensity, timestamp
               FROM emotion_readings
               WHERE user_id = ? AND timestamp > ?
               ORDER BY timestamp ASC""",
            [user_id, cutoff]
        ).fetchall()

        if not rows:
            return trend

        n = len(rows)
        trend.reading_count = n

        totals = {e: 0.0 for e in EMOTIONS}
        total_intensity = 0.0

        for row in rows:
            for e in EMOTIONS:
                totals[e] += float(row[e] or 0.0)
            total_intensity += float(row["intensity"] or 0.0)

        trend.avg_joy = totals["joy"] / n
        trend.avg_sadness = totals["sadness"] / n
        trend.avg_anger = totals["anger"] / n
        trend.avg_fear = totals["fear"] / n
        trend.avg_surprise = totals["surprise"] / n
        trend.avg_neutral = totals["neutral"] / n
        trend.avg_intensity = total_intensity / n

        # Determine dominant mood
        avg_scores = {
            "joy": trend.avg_joy,
            "sadness": trend.avg_sadness,
            "anger": trend.avg_anger,
            "fear": trend.avg_fear,
            "surprise": trend.avg_surprise,
            "neutral": trend.avg_neutral,
        }
        trend.dominant_mood = max(avg_scores, key=avg_scores.get)

        # Trend direction: compare first half vs second half intensity
        if n >= 4:
            mid = n // 2
            first_half_intensity = sum(float(r["intensity"] or 0) for r in rows[:mid]) / mid
            second_half_intensity = sum(float(r["intensity"] or 0) for r in rows[mid:]) / (n - mid)
            first_half_joy = sum(float(r["joy"] or 0) for r in rows[:mid]) / mid
            second_half_joy = sum(float(r["joy"] or 0) for r in rows[mid:]) / (n - mid)

            joy_delta = second_half_joy - first_half_joy
            if joy_delta > 0.1:
                trend.trend_direction = "improving"
            elif joy_delta < -0.1:
                trend.trend_direction = "declining"
            else:
                trend.trend_direction = "stable"

        return trend

    except Exception as e:
        logger.error(f"[Emotion] Trend error: {e}")
        return trend
    finally:
        conn.close()


async def get_current_mood(
    user_id: str,
    db_path: str = "~/.nobi/bot_memories.db",
    lookback_messages: int = 5,
) -> str:
    """
    Get user's current mood based on recent messages.

    Args:
        user_id: User identifier.
        db_path: SQLite DB path.
        lookback_messages: Number of recent messages to consider.

    Returns:
        Mood string: "happy", "sad", "angry", "anxious", "surprised", or "neutral"
    """
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return "neutral"

    conn = sqlite3.connect(db_path_expanded)
    conn.row_factory = sqlite3.Row

    try:
        _ensure_emotion_table(conn)
        rows = conn.execute(
            """SELECT joy, sadness, anger, fear, surprise, neutral, intensity
               FROM emotion_readings
               WHERE user_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            [user_id, lookback_messages]
        ).fetchall()

        if not rows:
            return "neutral"

        n = len(rows)
        avg_scores = {e: 0.0 for e in EMOTIONS}
        avg_intensity = 0.0

        for row in rows:
            for e in EMOTIONS:
                avg_scores[e] += float(row[e] or 0.0) / n
            avg_intensity += float(row["intensity"] or 0.0) / n

        if avg_intensity < NEUTRAL_THRESHOLD:
            return "neutral"

        dominant = max(
            {k: v for k, v in avg_scores.items() if k != "neutral"},
            key=avg_scores.get,
            default="neutral"
        )

        # Map to friendly mood name
        mood_map = {
            "joy": "happy",
            "sadness": "sad",
            "anger": "angry",
            "fear": "anxious",
            "surprise": "surprised",
            "neutral": "neutral",
        }
        return mood_map.get(dominant, "neutral")

    except Exception as e:
        logger.error(f"[Emotion] Get mood error: {e}")
        return "neutral"
    finally:
        conn.close()


async def clear_emotion_data(user_id: str, db_path: str = "~/.nobi/bot_memories.db") -> int:
    """GDPR: Clear all emotion readings for a user. Returns count deleted."""
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return 0
    conn = sqlite3.connect(db_path_expanded)
    try:
        _ensure_emotion_table(conn)
        r = conn.execute("DELETE FROM emotion_readings WHERE user_id = ?", [user_id])
        conn.commit()
        count = r.rowcount
        logger.info(f"[Emotion] GDPR clear: deleted {count} readings for user={user_id}")
        return count
    except Exception as e:
        logger.error(f"[Emotion] GDPR clear error: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def build_mood_context(mood: str, trend: Optional[EmotionTrend] = None) -> str:
    """
    Build mood context string for injection into system prompt.

    Args:
        mood: Current mood string.
        trend: Optional EmotionTrend for richer context.

    Returns:
        Formatted string to inject into system prompt. Empty if neutral.
    """
    if mood == "neutral":
        return ""

    mood_instructions = {
        "happy": "The user is currently in a good mood. Match their positive energy! Be upbeat and celebratory.",
        "sad": "The user seems sad or down right now. Be extra warm, empathetic, and supportive. Don't be dismissive.",
        "angry": "The user may be frustrated or angry. Stay calm, validate their feelings, avoid being dismissive or adding fuel.",
        "anxious": "The user seems worried or anxious. Be reassuring, grounding, and calm. Help them feel safe.",
        "surprised": "The user seems surprised or shocked. Acknowledge what they're experiencing and respond with appropriate energy.",
    }

    instruction = mood_instructions.get(mood, "")
    if not instruction:
        return ""

    context = f"== USER EMOTIONAL STATE ==\nCurrent mood: {mood.upper()}\n{instruction}"

    if trend and trend.reading_count >= 3:
        if trend.trend_direction == "declining" and trend.avg_sadness > 0.3:
            context += "\n⚠️ Note: User has been trending sadder over the past week. Be especially attentive."
        elif trend.trend_direction == "improving":
            context += "\nNote: User's mood has been improving recently — reinforce positive momentum."

    return context
