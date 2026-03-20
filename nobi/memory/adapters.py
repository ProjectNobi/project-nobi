"""
Project Nobi — Per-User LoRA Adapter Foundation (Phase B)
==========================================================
Manages per-user personality adapters.

Phase B: Store adapter configs (personality traits, communication style preferences)
as structured JSON data. These travel with the user, not stored on any single miner.

Phase C (future): These become actual LoRA weight deltas trained on-device.
"""

import os
import re
import json
import logging
import sqlite3
import threading
from typing import Dict, Optional

logger = logging.getLogger("nobi-adapters")

# Default adapter config for new users
DEFAULT_ADAPTER = {
    "tone": "warm",           # warm | neutral | professional
    "formality": 0.5,         # 0.0 (very casual) → 1.0 (very formal)
    "humor_level": 0.5,       # 0.0 (serious) → 1.0 (very humorous)
    "verbosity": 0.5,         # 0.0 (concise) → 1.0 (detailed)
    "emoji_usage": 0.5,       # 0.0 (none) → 1.0 (lots)
    "technical_depth": 0.5,   # 0.0 (simple) → 1.0 (very technical)
    "topics_of_interest": [], # learned topics the user engages with
    "message_count": 0,       # how many messages analyzed
}

# Formality markers
_FORMAL_MARKERS = {
    "please", "kindly", "would you", "could you", "thank you", "appreciate",
    "regarding", "furthermore", "nevertheless", "however", "therefore",
    "sincerely", "respectfully", "accordingly",
}
_CASUAL_MARKERS = {
    "lol", "haha", "lmao", "omg", "tbh", "ngl", "idk", "imo",
    "gonna", "wanna", "gotta", "ya", "yep", "nope", "nah",
    "dude", "bro", "bruh", "yo", "sup", "hey",
}

# Emoji regex
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


class UserAdapterManager:
    """
    Manages per-user personality adapters.

    Phase B: Stores adapter configs as structured JSON in SQLite user_profiles.
    Phase C (future): These become actual LoRA weight deltas trained on-device.
    """

    def __init__(self, db_path: str = "~/.nobi/memories.db"):
        self.db_path = os.path.expanduser(db_path)
        self._local = threading.local()
        self._ensure_schema()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=10000")
        return self._local.conn

    def _ensure_schema(self):
        """Ensure personality_notes column exists in user_profiles."""
        try:
            self._conn.execute("SELECT personality_notes FROM user_profiles LIMIT 1")
        except sqlite3.OperationalError:
            try:
                self._conn.execute(
                    "ALTER TABLE user_profiles ADD COLUMN personality_notes TEXT DEFAULT ''"
                )
                self._conn.commit()
            except Exception:
                pass  # Table might not exist yet — MemoryManager creates it

    def get_adapter_config(self, user_id: str) -> dict:
        """
        Return the user's personality adapter config.
        Returns default config if no adapter exists yet.
        """
        try:
            row = self._conn.execute(
                "SELECT personality_notes FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row and row["personality_notes"]:
                config = json.loads(row["personality_notes"])
                # Merge with defaults to handle new fields added in future versions
                merged = dict(DEFAULT_ADAPTER)
                merged.update(config)
                return merged
        except (json.JSONDecodeError, Exception) as e:
            logger.debug(f"[Adapter] Error loading config for {user_id}: {e}")

        return dict(DEFAULT_ADAPTER)

    def _save_adapter_config(self, user_id: str, config: dict):
        """Save adapter config to user_profiles.personality_notes."""
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            config_json = json.dumps(config)

            self._conn.execute(
                """INSERT INTO user_profiles (user_id, personality_notes, first_seen, last_seen)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   personality_notes = excluded.personality_notes,
                   last_seen = excluded.last_seen""",
                (user_id, config_json, now, now),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"[Adapter] Failed to save config for {user_id}: {e}")

    def update_adapter_from_conversation(
        self, user_id: str, message: str, response: str
    ):
        """
        Learn personality preferences from conversation patterns.

        Analyzes:
        - Message length → verbosity preference
        - Emoji usage → emoji preference
        - Formality markers → formality level
        - Question patterns → technical depth interest
        - Topic keywords → topics of interest
        """
        config = self.get_adapter_config(user_id)
        count = config.get("message_count", 0)

        # Use exponential moving average — recent messages matter more
        # alpha starts high (0.3) for new users, decreases as we learn more
        alpha = max(0.05, 0.3 / (1 + count * 0.02))

        msg_lower = message.lower()
        words = msg_lower.split()
        word_count = len(words)

        # --- Verbosity ---
        # Short (<10 words) → prefer concise; Long (>50 words) → prefer detailed
        if word_count < 10:
            msg_verbosity = 0.2
        elif word_count < 30:
            msg_verbosity = 0.5
        elif word_count < 60:
            msg_verbosity = 0.7
        else:
            msg_verbosity = 0.9
        config["verbosity"] = config["verbosity"] * (1 - alpha) + msg_verbosity * alpha

        # --- Emoji usage ---
        emoji_count = len(_EMOJI_RE.findall(message))
        if emoji_count == 0:
            msg_emoji = 0.1
        elif emoji_count <= 2:
            msg_emoji = 0.5
        else:
            msg_emoji = 0.9
        config["emoji_usage"] = config["emoji_usage"] * (1 - alpha) + msg_emoji * alpha

        # --- Formality ---
        formal_count = sum(1 for m in _FORMAL_MARKERS if m in msg_lower)
        casual_count = sum(1 for m in _CASUAL_MARKERS if m in msg_lower)
        if formal_count > casual_count:
            msg_formality = min(1.0, 0.6 + formal_count * 0.1)
        elif casual_count > formal_count:
            msg_formality = max(0.0, 0.4 - casual_count * 0.1)
        else:
            msg_formality = 0.5
        config["formality"] = config["formality"] * (1 - alpha) + msg_formality * alpha

        # --- Technical depth ---
        tech_markers = {
            "how does", "explain", "why does", "what is the difference",
            "technically", "algorithm", "implementation", "architecture",
            "api", "code", "function", "database", "protocol", "debug",
        }
        tech_count = sum(1 for m in tech_markers if m in msg_lower)
        if tech_count > 0:
            msg_tech = min(1.0, 0.6 + tech_count * 0.15)
        else:
            msg_tech = 0.4
        config["technical_depth"] = config["technical_depth"] * (1 - alpha) + msg_tech * alpha

        # --- Tone ---
        # Determine from formality + emoji combined
        if config["formality"] > 0.7:
            config["tone"] = "professional"
        elif config["emoji_usage"] > 0.6 or config["formality"] < 0.3:
            config["tone"] = "warm"
        else:
            config["tone"] = "neutral"

        # --- Humor ---
        humor_markers = {"haha", "lol", "lmao", "😂", "🤣", "funny", "joke", "hilarious"}
        if any(m in msg_lower or m in message for m in humor_markers):
            config["humor_level"] = config["humor_level"] * (1 - alpha) + 0.8 * alpha
        else:
            # Slight decay toward neutral
            config["humor_level"] = config["humor_level"] * (1 - alpha * 0.3) + 0.5 * (alpha * 0.3)

        # --- Topics of interest ---
        # Simple keyword extraction for repeated topics
        topic_keywords = {
            "music", "gaming", "sports", "cooking", "travel", "fitness",
            "books", "movies", "tech", "science", "art", "photography",
            "crypto", "finance", "health", "education", "programming",
            "nature", "pets", "fashion", "food", "politics", "history",
        }
        found_topics = [t for t in topic_keywords if t in msg_lower]
        existing_topics = config.get("topics_of_interest", [])
        for topic in found_topics:
            if topic not in existing_topics:
                existing_topics.append(topic)
        # Keep only last 10 topics
        config["topics_of_interest"] = existing_topics[-10:]

        config["message_count"] = count + 1

        # Clamp all float values
        for key in ["formality", "humor_level", "verbosity", "emoji_usage", "technical_depth"]:
            config[key] = round(max(0.0, min(1.0, config[key])), 3)

        self._save_adapter_config(user_id, config)

    def apply_adapter_to_prompt(self, base_prompt: str, adapter_config: dict) -> str:
        """
        Modify the system prompt based on user's adapter config.
        Appends personality guidance to help the LLM match the user's style.
        """
        if not adapter_config or adapter_config.get("message_count", 0) < 3:
            # Not enough data yet — don't modify prompt
            return base_prompt

        hints = []

        # Verbosity
        v = adapter_config.get("verbosity", 0.5)
        if v < 0.3:
            hints.append("This user prefers SHORT, concise responses. Keep it brief.")
        elif v > 0.7:
            hints.append("This user likes detailed, thorough responses. Feel free to elaborate.")

        # Formality
        f = adapter_config.get("formality", 0.5)
        if f < 0.3:
            hints.append("This user is very casual. Use informal, relaxed language.")
        elif f > 0.7:
            hints.append("This user prefers formal, professional communication.")

        # Emoji
        e = adapter_config.get("emoji_usage", 0.5)
        if e < 0.2:
            hints.append("This user rarely uses emoji. Minimize emoji in your responses.")
        elif e > 0.7:
            hints.append("This user loves emoji! Feel free to use them expressively.")

        # Technical depth
        t = adapter_config.get("technical_depth", 0.5)
        if t > 0.7:
            hints.append("This user appreciates technical depth and detailed explanations.")
        elif t < 0.3:
            hints.append("This user prefers simple, non-technical explanations.")

        # Humor
        h = adapter_config.get("humor_level", 0.5)
        if h > 0.7:
            hints.append("This user enjoys humor. Be playful and witty when appropriate.")
        elif h < 0.25:
            hints.append("This user prefers straightforward responses without much humor.")

        # Topics of interest
        topics = adapter_config.get("topics_of_interest", [])
        if topics:
            hints.append(f"This user is interested in: {', '.join(topics[:5])}.")

        # Tone
        tone = adapter_config.get("tone", "warm")
        if tone == "professional":
            hints.append("Overall tone: professional and polished.")
        elif tone == "warm":
            hints.append("Overall tone: warm and friendly.")

        if not hints:
            return base_prompt

        adapter_section = "\n\n== PERSONALIZATION (learned from this user's style) ==\n" + "\n".join(
            f"- {h}" for h in hints
        )

        return base_prompt + adapter_section
