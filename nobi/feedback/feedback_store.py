"""
Project Nobi — FeedbackStore: Self-Improving Feedback Loop
===========================================================
Detects when users correct Nori, extracts generalizable lessons via LLM,
and stores them in SQLite. Lessons are injected into future system prompts
so Nori continuously improves from real user interactions.

This makes Nori the first self-improving AI companion on Bittensor.

Schema:
  nori_lessons(id, timestamp, user_id, correction_text, lesson_extracted, applied)
"""

import os
import re
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("nobi-feedback")

# ─── Correction Detection Patterns ───────────────────────────
# These signal that the user is correcting the bot

_CORRECTION_PATTERNS = [
    # Explicit corrections
    r"\bno[,.]?\s+i\s+said\b",
    r"\bthat'?s?\s+wrong\b",
    r"\byou'?re?\s+wrong\b",
    r"\bincorrect\b",
    r"\bthat'?s?\s+not\s+(right|correct|true|accurate)\b",
    r"\bi\s+already\s+told\s+you\b",
    r"\byou\s+forgot\b",
    r"\byou\s+don'?t\s+remember\b",
    r"\bnot\s+what\s+i\s+(said|asked|meant|told)\b",
    r"\bi\s+meant\b",
    r"\bactually[,.]?\s+(?!i'm|i am|the|a\s+good|that|this|it|not)",  # "actually, X" but not "actually i'm fine"
    r"\bwrong\s+(answer|response|information|info|name|date|fact)\b",
    r"\bcorrect\s+yourself\b",
    r"\bno[,.]?\s+that'?s?\s+not\b",
    r"\byou\s+misunderstood\b",
    r"\byou\s+got\s+(that\s+)?wrong\b",
    r"\bthat'?s?\s+not\s+what\s+i\b",
    r"\bno[,!]\s+my\s+(name|job|age|city|country|hobby|interest)\b",
    r"\byou\s+asked\s+(me\s+)?that\s+already\b",
    r"\byou\s+already\s+asked\b",
    r"\bi\s+told\s+you\s+(that\s+)?before\b",
    r"\bstop\s+(repeating|asking)\b",
    r"\bwhy\s+(do\s+you\s+keep|are\s+you\s+still)\s+asking\b",
    r"\byou\s+keep\s+(forgetting|asking|repeating)\b",
    r"\bplease\s+remember\b",
    r"\bi\s+already\s+mentioned\b",
    r"\bthat'?s?\s+not\s+my\s+(name|age|job|hobby)\b",
    r"\bmy\s+(name|age|job|hobby)\s+is\s+not\b",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _CORRECTION_PATTERNS]

# ─── Lesson Extraction Prompt ─────────────────────────────────

_LESSON_EXTRACTION_PROMPT = """\
You are analyzing a user correction to an AI companion called Nori.
Extract a SHORT, GENERALIZABLE lesson that Nori should remember going forward.

The lesson should:
- Be actionable and specific (what Nori should DO differently)
- Be generalizable (apply beyond just this user if possible)
- Be concise (1 sentence, max 25 words)
- Start with an action verb (Always, Never, Check, Verify, Remember, etc.)

User's original message: {user_message}
Nori's response that caused the correction: {bot_response}
User's correction: {correction}

Return ONLY the lesson text, nothing else. No quotes, no explanation.
If you cannot extract a clear lesson, return: "Check user's stated preferences before responding."

Examples of good lessons:
- "Always use the user's stated name from memory before addressing them."
- "Never repeat a question that was already answered in the same conversation."
- "Verify user's profession before suggesting career advice."
- "Remember the user's timezone before suggesting meeting times."
"""


class FeedbackStore:
    """
    Stores user corrections and extracted lessons in SQLite.
    Lessons are injected into Nori's system prompt for self-improvement.
    """

    def __init__(self, db_path: str = "~/.nobi/feedback_lessons.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()
        logger.info(f"[FeedbackStore] Initialized at {self.db_path}")

    # ─── DB Connection (thread-local for SQLite safety) ───────

    def _conn(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # WAL mode for concurrent reads
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self):
        """Create tables if not exist."""
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nori_lessons (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                user_id         TEXT    NOT NULL,
                correction_text TEXT    NOT NULL,
                lesson_extracted TEXT   NOT NULL,
                applied         INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Index for fast retrieval by recency
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nori_lessons_timestamp
            ON nori_lessons(timestamp DESC)
        """)
        # Index for per-user lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_nori_lessons_user
            ON nori_lessons(user_id)
        """)
        conn.commit()
        logger.debug("[FeedbackStore] DB initialized")

    # ─── Correction Detection ──────────────────────────────────

    def detect_correction(self, message: str) -> bool:
        """
        Returns True if the message contains correction indicators.
        Uses compiled regex patterns for efficiency.
        """
        if not message or not message.strip():
            return False
        for pattern in _COMPILED_PATTERNS:
            if pattern.search(message):
                logger.debug(f"[FeedbackStore] Correction detected: '{message[:80]}'")
                return True
        return False

    # ─── Lesson Extraction ────────────────────────────────────

    async def extract_lesson(
        self,
        user_message: str,
        bot_response: str,
        correction: str,
        llm_client,
        model: str = "deepseek-ai/DeepSeek-V3.1-TEE",
    ) -> str:
        """
        Use the LLM to extract a generalizable lesson from a correction.
        Falls back to a generic lesson if LLM unavailable.
        """
        if not llm_client:
            return self._fallback_lesson(correction)

        prompt = _LESSON_EXTRACTION_PROMPT.format(
            user_message=user_message[:500],
            bot_response=bot_response[:500],
            correction=correction[:500],
        )

        try:
            completion = llm_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You extract concise lessons from AI correction feedback."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=60,
                temperature=0.3,
                timeout=10,
            )
            lesson = completion.choices[0].message.content
            if lesson:
                lesson = lesson.strip().strip('"\'').strip()
                # Validate: must be a reasonable length
                if 10 < len(lesson) < 200:
                    logger.info(f"[FeedbackStore] Lesson extracted: '{lesson}'")
                    return lesson
        except Exception as e:
            logger.warning(f"[FeedbackStore] LLM lesson extraction failed: {e}")

        return self._fallback_lesson(correction)

    def _fallback_lesson(self, correction: str) -> str:
        """
        Generate a simple rule-based lesson when LLM unavailable.
        Better than nothing.
        """
        msg = correction.lower()
        if any(kw in msg for kw in ["name", "call me", "i'm called"]):
            return "Always verify the user's name from memory before using it."
        if any(kw in msg for kw in ["already told", "told you", "mentioned before"]):
            return "Check conversation history before asking for information already provided."
        if any(kw in msg for kw in ["asked that", "asked already", "stop asking"]):
            return "Never repeat questions already answered in the current conversation."
        if any(kw in msg for kw in ["forgot", "don't remember", "forgot again"]):
            return "Actively recall and use all available user memory before responding."
        return "Listen more carefully and verify user details before responding."

    # ─── Storage ──────────────────────────────────────────────

    def save_lesson(self, user_id: str, correction: str, lesson: str) -> int:
        """
        Store a correction and its extracted lesson in SQLite.
        Returns the new lesson ID.
        """
        conn = self._conn()
        timestamp = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """
            INSERT INTO nori_lessons (timestamp, user_id, correction_text, lesson_extracted, applied)
            VALUES (?, ?, ?, ?, 0)
            """,
            (timestamp, user_id, correction[:1000], lesson[:500]),
        )
        conn.commit()
        lesson_id = cursor.lastrowid
        logger.info(f"[FeedbackStore] Lesson #{lesson_id} saved for user {user_id}: '{lesson[:60]}'")

        # Auto-curate if we have too many lessons
        self._maybe_curate()

        return lesson_id

    # ─── Retrieval ────────────────────────────────────────────

    def get_active_lessons(self, limit: int = 50) -> list:
        """
        Return most recent lessons for system prompt injection.
        Returns list of dicts with keys: id, lesson, timestamp, user_id.
        Deduplicates near-identical lessons to keep the list clean.
        """
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT id, lesson_extracted as lesson, timestamp, user_id
            FROM nori_lessons
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit * 2,),  # fetch more, then deduplicate
        ).fetchall()

        if not rows:
            return []

        # Simple deduplication: skip lessons where first 30 chars match a seen lesson
        seen_prefixes: set = set()
        unique_lessons: list = []
        for row in rows:
            lesson = row["lesson"]
            prefix = lesson[:30].lower().strip()
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                unique_lessons.append({
                    "id": row["id"],
                    "lesson": lesson,
                    "timestamp": row["timestamp"],
                    "user_id": row["user_id"],
                })
            if len(unique_lessons) >= limit:
                break

        return unique_lessons

    def get_lesson_count(self) -> int:
        """Return total number of stored lessons."""
        conn = self._conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM nori_lessons").fetchone()
        return row["cnt"] if row else 0

    def mark_applied(self, lesson_id: int):
        """Mark a lesson as applied (for tracking purposes)."""
        conn = self._conn()
        conn.execute(
            "UPDATE nori_lessons SET applied = 1 WHERE id = ?",
            (lesson_id,),
        )
        conn.commit()

    # ─── Periodic Curation ────────────────────────────────────

    def _maybe_curate(self):
        """
        Trigger curation every 100 lessons to keep the DB clean.
        Non-blocking: just removes oldest duplicates synchronously
        (full LLM curation via curate_with_llm is called externally).
        """
        count = self.get_lesson_count()
        if count > 0 and count % 100 == 0:
            logger.info(f"[FeedbackStore] Reached {count} lessons — triggering basic curation")
            self._prune_oldest_duplicates()

    def _prune_oldest_duplicates(self, keep_per_prefix: int = 3):
        """
        Remove old duplicate lessons (same first 30 chars).
        Keeps the N most recent for each prefix.
        """
        conn = self._conn()
        rows = conn.execute(
            "SELECT id, lesson_extracted FROM nori_lessons ORDER BY timestamp ASC"
        ).fetchall()

        prefix_counts: dict = {}
        to_delete: list = []
        for row in rows:
            prefix = row["lesson_extracted"][:30].lower().strip()
            prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
            if prefix_counts[prefix] > keep_per_prefix:
                to_delete.append(row["id"])

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(f"DELETE FROM nori_lessons WHERE id IN ({placeholders})", to_delete)
            conn.commit()
            logger.info(f"[FeedbackStore] Pruned {len(to_delete)} duplicate lessons")

    async def curate_with_llm(self, llm_client, model: str = "deepseek-ai/DeepSeek-V3.1-TEE"):
        """
        Full LLM-powered curation: deduplicate, merge, and consolidate lessons.
        Called periodically (e.g. every 100 new lessons). Non-destructive — only
        replaces the lesson list if LLM returns a valid result.
        """
        if not llm_client:
            self._prune_oldest_duplicates()
            return

        lessons = self.get_active_lessons(limit=100)
        if len(lessons) < 10:
            return  # Not enough lessons to curate

        lesson_text = "\n".join([f"{i+1}. {l['lesson']}" for i, l in enumerate(lessons)])

        prompt = f"""\
You are curating a list of lessons that an AI companion (Nori) has learned from user corrections.

Current lessons ({len(lessons)} total):
{lesson_text}

Task: Return a CLEANED version of these lessons:
1. Remove exact or near-duplicate lessons (keep the best-worded version)
2. Merge related lessons into one cleaner rule
3. Remove overly specific lessons that don't generalize
4. Keep the list to max 30 lessons
5. Ensure each lesson starts with an action verb

Return ONLY the cleaned lessons, one per line, numbered. Nothing else.
"""
        try:
            completion = llm_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You curate AI behavior lessons concisely."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
                temperature=0.2,
                timeout=30,
            )
            result = completion.choices[0].message.content
            if not result:
                return

            # Parse numbered lines
            curated_lines = []
            for line in result.strip().splitlines():
                line = line.strip()
                # Strip leading numbers: "1. lesson" → "lesson"
                cleaned = re.sub(r"^\d+\.\s*", "", line).strip().strip('"\'')
                if cleaned and 10 < len(cleaned) < 200:
                    curated_lines.append(cleaned)

            if len(curated_lines) < 5:
                logger.warning("[FeedbackStore] LLM curation returned too few lessons — skipping")
                return

            # Replace the DB content with curated lessons
            conn = self._conn()
            conn.execute("DELETE FROM nori_lessons")
            timestamp = datetime.now(timezone.utc).isoformat()
            for lesson in curated_lines:
                conn.execute(
                    "INSERT INTO nori_lessons (timestamp, user_id, correction_text, lesson_extracted, applied) "
                    "VALUES (?, 'curated', 'LLM curation', ?, 1)",
                    (timestamp, lesson),
                )
            conn.commit()
            logger.info(f"[FeedbackStore] LLM curation complete: {len(curated_lines)} lessons retained")

        except Exception as e:
            logger.warning(f"[FeedbackStore] LLM curation failed: {e}")
            # Fall back to simple pruning
            self._prune_oldest_duplicates()
