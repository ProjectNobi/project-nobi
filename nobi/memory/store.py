"""
Project Nobi — Memory Store
=============================
Persistent memory system for AI companions.

Each user gets their own memory space. Memories are:
  - Typed (fact, event, preference, context, emotion)
  - Tagged for retrieval
  - Scored by importance
  - Optionally time-limited
  - Searchable by natural language or structured queries

Storage: SQLite per-miner (lightweight, no external deps).
Future: Could shard across distributed storage for scale.
"""

import os
import json
import time
import uuid
import sqlite3
import logging
import threading
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

from nobi.memory.encryption import (
    encrypt_memory,
    decrypt_memory,
    is_encrypted,
    ensure_master_secret,
)

logger = logging.getLogger("nobi-memory")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class MemoryManager:
    """Manages persistent user memories with SQLite backend."""

    def __init__(self, db_path: str = "~/.nobi/memories.db", encryption_enabled: bool = True):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self.encryption_enabled = encryption_enabled
        if encryption_enabled:
            ensure_master_secret()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _encrypt(self, user_id: str, text: str) -> str:
        """Encrypt text if encryption is enabled."""
        if not self.encryption_enabled:
            return text
        return encrypt_memory(user_id, text)

    def _decrypt(self, user_id: str, text: str) -> str:
        """Decrypt text if it's encrypted. Backward-compatible with plaintext."""
        if not text:
            return text
        if is_encrypted(text):
            return decrypt_memory(user_id, text)
        return text

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(user_id, memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(user_id, importance DESC);

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);

            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                summary TEXT DEFAULT '',
                personality_notes TEXT DEFAULT '',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                total_messages INTEGER DEFAULT 0,
                memory_count_at_last_summary INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS archived_memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                archived_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_archived_user ON archived_memories(user_id);
        """)
        # Add memory_count_at_last_summary column if missing (migration)
        try:
            conn.execute("SELECT memory_count_at_last_summary FROM user_profiles LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE user_profiles ADD COLUMN memory_count_at_last_summary INTEGER DEFAULT 0")
        conn.commit()

    def store(
        self,
        user_id: str,
        content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        tags: List[str] = None,
        expires_at: Optional[str] = None,
    ) -> str:
        """Store a memory. Encrypts content before writing. Returns the memory ID."""
        memory_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        # Encrypt content before persisting
        encrypted_content = self._encrypt(user_id, content)

        self._conn.execute(
            """INSERT INTO memories (id, user_id, memory_type, content, importance,
               tags, created_at, updated_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_id,
                user_id,
                memory_type,
                encrypted_content,
                max(0.0, min(1.0, importance)),
                json.dumps(tags or []),
                now,
                now,
                expires_at,
            ),
        )
        self._conn.commit()
        return memory_id

    def recall(
        self,
        user_id: str,
        query: str = "",
        memory_type: Optional[str] = None,
        tags: List[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Recall memories for a user.

        Uses simple keyword matching + importance weighting.
        Future: semantic search with embeddings.
        """
        conn = self._conn
        now = datetime.now(timezone.utc).isoformat()

        # Build query
        conditions = ["user_id = ?"]
        params: list = [user_id]

        # Filter expired
        conditions.append("(expires_at IS NULL OR expires_at > ?)")
        params.append(now)

        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)

        if tags:
            # Match any tag
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            conditions.append(f"({' OR '.join(tag_conditions)})")

        where = " AND ".join(conditions)

        if query:
            # Keyword relevance scoring via LIKE matching (parameterized)
            # Sanitize keywords: strip punctuation, skip short words
            keywords = [
                w.lower().replace("'", "").replace('"', '')
                for w in query.split()
                if len(w) > 2
            ]
            if keywords:
                # CASE WHEN params go BEFORE WHERE params in the SQL
                # So we need separate param lists and merge in correct order
                case_parts = []
                kw_params = []
                for kw in keywords:
                    case_parts.append("(CASE WHEN LOWER(content) LIKE ? THEN 1 ELSE 0 END)")
                    kw_params.append(f"%{kw}%")
                relevance = " + ".join(case_parts)
                sql = f"""
                    SELECT *, ({relevance}) as relevance
                    FROM memories
                    WHERE {where}
                    ORDER BY relevance DESC, importance DESC, created_at DESC
                    LIMIT ?
                """
                # Params order: CASE WHEN params, then WHERE params, then LIMIT
                params = kw_params + params + [limit]
            else:
                sql = f"""
                    SELECT *, 0 as relevance FROM memories
                    WHERE {where}
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?
                """
                params.append(limit)
        else:
            sql = f"""
                SELECT *, 0 as relevance FROM memories
                WHERE {where}
                ORDER BY importance DESC, created_at DESC
                LIMIT ?
            """
            params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        # Update access counts
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE memories SET access_count = access_count + 1, "
                f"last_accessed = ? WHERE id IN ({placeholders})",
                [now] + ids,
            )
            conn.commit()

        return [
            {
                "id": row["id"],
                "type": row["memory_type"],
                "content": self._decrypt(user_id, row["content"]),
                "importance": row["importance"],
                "tags": json.loads(row["tags"]),
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
            }
            for row in rows
        ]

    def get_user_memory_count(self, user_id: str) -> int:
        """Get total memory count for a user."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def save_conversation_turn(
        self, user_id: str, role: str, content: str
    ):
        """Save a conversation message. Encrypts content before writing."""
        now = datetime.now(timezone.utc).isoformat()
        encrypted_content = self._encrypt(user_id, content)
        self._conn.execute(
            "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, encrypted_content, now),
        )

        # Update user profile
        self._conn.execute(
            """INSERT INTO user_profiles (user_id, first_seen, last_seen, total_messages)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE SET
               last_seen = excluded.last_seen,
               total_messages = total_messages + 1""",
            (user_id, now, now),
        )
        self._conn.commit()

    def get_recent_conversation(
        self, user_id: str, limit: int = 20
    ) -> List[Dict]:
        """Get recent conversation history for a user. Decrypts content."""
        rows = self._conn.execute(
            """SELECT role, content, created_at FROM conversations
               WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

        return [
            {"role": row["role"], "content": self._decrypt(user_id, row["content"])}
            for row in reversed(rows)
        ]

    def extract_memories_from_message(
        self, user_id: str, message: str, response: str
    ) -> List[str]:
        """
        Auto-extract memorable facts from a conversation turn.
        Uses regex patterns for accuracy. Future: LLM-based extraction.

        Returns list of memory IDs created.
        """
        import re
        created = []
        msg_lower = message.lower()

        # Name detection (regex for accuracy — avoids "I'm feeling" false positives)
        name_patterns = [
            r"(?:my name is|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, message)
            if match:
                name = match.group(1).strip()
                # Skip common false positives
                skip = {"sorry", "fine", "good", "okay", "well", "sure", "happy",
                        "feeling", "stressed", "tired", "excited", "worried"}
                if name.lower() not in skip and 1 < len(name) < 30:
                    mid = self.store(
                        user_id, f"User's name is {name}",
                        memory_type="fact", importance=0.9, tags=["name", "identity"],
                    )
                    created.append(mid)
                    break

        # Location detection (from Slumpz's patterns)
        location_patterns = [
            r"(?:I live in|I'm from|I moved to|I'm based in|I'm in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:from|in)\s+([A-Z][a-z]+)\s+(?:to|and|,|\.)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, message)
            if match:
                location = match.group(1).strip()
                if len(location) > 1:
                    mid = self.store(
                        user_id, f"User is from/lives in {location}",
                        memory_type="fact", importance=0.8, tags=["location"],
                    )
                    created.append(mid)
                    break

        # Occupation detection
        occupation_patterns = [
            r"I(?:'m| am) (?:a|an)\s+([\w\s]{3,30}?)(?:\.|,|!|\?|$| and| at| in| for)",
            r"I work (?:as|at|in|for)\s+(.+?)(?:\.|,|!|\?|$)",
        ]
        for pattern in occupation_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                occupation = match.group(1).strip()
                # Skip emotional states and common non-occupations
                skip_occ = {"feeling", "doing", "going", "trying", "looking",
                            "bit", "little", "very", "so", "really", "just",
                            "not", "also", "still", "currently", "vegetarian"}
                if occupation.split()[0].lower() not in skip_occ and len(occupation) > 2:
                    mid = self.store(
                        user_id, f"User works as/is: {occupation}",
                        memory_type="fact", importance=0.8, tags=["career", "occupation"],
                    )
                    created.append(mid)
                    break

        # Preference detection
        pref_patterns = [
            (r"I (?:love|like|enjoy|adore)\s+(.+?)(?:\.|,|!|\?|$)", "likes"),
            (r"I (?:hate|dislike|can't stand)\s+(.+?)(?:\.|,|!|\?|$)", "dislikes"),
            (r"I prefer\s+(.+?)(?:\.|,|!|\?|$)", "preference"),
            (r"my favorite (?:is |)\s*(.+?)(?:\.|,|!|\?|$)", "favorite"),
        ]
        for pattern, tag in pref_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                pref = match.group(1).strip()
                if 2 < len(pref) < 100:
                    mid = self.store(
                        user_id, f"User {tag}: {pref}",
                        memory_type="preference", importance=0.7, tags=[tag],
                    )
                    created.append(mid)

        # Life event detection
        event_signals = [
            "i just got ", "i recently ", "i'm starting ",
            "i moved to ", "i graduated ", "i got married",
            "i had a baby", "i got a new job", "i'm pregnant",
        ]
        for signal in event_signals:
            if signal in msg_lower:
                idx = msg_lower.index(signal)
                snippet = message[idx:idx + 120].split(".")[0].strip()
                if len(snippet) > len(signal) + 2:
                    mid = self.store(
                        user_id, snippet, memory_type="event",
                        importance=0.8, tags=["life_event"],
                    )
                    created.append(mid)

        # Emotion detection
        emotion_signals = [
            ("i'm feeling ", "emotion", 0.5, ["mood"]),
            ("i feel ", "emotion", 0.5, ["mood"]),
            ("i'm stressed", "emotion", 0.6, ["stress", "mood"]),
            ("i'm happy", "emotion", 0.5, ["happiness", "mood"]),
            ("i'm worried", "emotion", 0.6, ["worry", "mood"]),
            ("i'm excited", "emotion", 0.5, ["excitement", "mood"]),
        ]
        for signal, mtype, imp, tags in emotion_signals:
            if signal in msg_lower:
                idx = msg_lower.index(signal)
                snippet = message[idx:idx + 80].split(".")[0].strip()
                mid = self.store(
                    user_id, snippet, memory_type=mtype,
                    importance=imp, tags=tags,
                )
                created.append(mid)

        return created

    def get_context_for_prompt(
        self, user_id: str, current_message: str, max_memories: int = 5
    ) -> str:
        """
        Build a memory context string for the LLM prompt.
        Retrieves relevant memories and formats them.
        """
        memories = self.recall(
            user_id=user_id,
            query=current_message,
            limit=max_memories,
        )

        if not memories:
            return ""

        lines = ["[Memories about this user:]"]
        for m in memories:
            lines.append(f"- [{m['type']}] {m['content']}")

        return "\n".join(lines)

    # ─── Phase 2: LLM-Powered Memory Extraction ─────────────────

    def extract_memories_llm(self, user_id: str, message: str) -> List[str]:
        """
        Use LLM to extract nuanced memories from a message.
        Falls back to regex extraction if LLM is unavailable.
        Only calls LLM for messages > 20 chars.
        Returns list of memory IDs created.
        """
        if len(message.strip()) <= 20:
            return []

        api_key = os.environ.get("CHUTES_API_KEY", "")
        model = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

        if not api_key or OpenAI is None:
            logger.debug("[LLM Extract] No API key or openai lib, skipping")
            return []

        try:
            client = OpenAI(base_url="https://llm.chutes.ai/v1", api_key=api_key)
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "Extract key facts, preferences, events, and emotions from this user message. "
                        "Return a JSON array of objects with fields: "
                        '"content" (string, the memory), "type" (one of: fact, preference, event, emotion, context), '
                        '"importance" (float 0.0-1.0), "tags" (array of strings). '
                        "Only extract genuinely memorable information. Skip greetings and filler. "
                        "Return [] if nothing worth remembering. Return ONLY valid JSON, no explanation."
                    )},
                    {"role": "user", "content": message},
                ],
                max_tokens=300,
                temperature=0.1,
                timeout=5,
            )
            raw = completion.choices[0].message.content.strip()

            # Parse JSON — handle markdown code blocks
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            memories = json.loads(raw)

            if not isinstance(memories, list):
                return []

            created = []
            for mem in memories[:5]:  # Cap at 5 memories per message
                if not isinstance(mem, dict) or not mem.get("content"):
                    continue
                content = str(mem["content"])[:200]
                mtype = mem.get("type", "fact")
                if mtype not in ("fact", "preference", "event", "emotion", "context"):
                    mtype = "fact"
                importance = max(0.0, min(1.0, float(mem.get("importance", 0.5))))
                tags = mem.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                tags = [str(t) for t in tags[:5]]

                # Deduplicate: skip if very similar memory exists
                existing = self.recall(user_id, query=content, limit=3)
                if any(self._similar(content, e["content"]) for e in existing):
                    continue

                mid = self.store(user_id, content, memory_type=mtype,
                                 importance=importance, tags=tags)
                created.append(mid)

            logger.info(f"[LLM Extract] Created {len(created)} memories for {user_id}")
            return created

        except json.JSONDecodeError as e:
            logger.warning(f"[LLM Extract] JSON parse error: {e}")
            return []
        except Exception as e:
            logger.warning(f"[LLM Extract] Error: {e}")
            return []

    @staticmethod
    def _similar(a: str, b: str, threshold: float = 0.6) -> bool:
        """Simple word-overlap similarity check."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b)
        return overlap / min(len(words_a), len(words_b)) >= threshold

    # ─── Phase 2: Memory Importance Decay ──────────────────────

    def decay_old_memories(self):
        """
        Decay importance of old, unaccessed memories.
        - 30+ days, access_count=0: importance -= 0.1
        - Recently accessed: importance += 0.05 (cap 1.0)
        - 90+ days, never accessed: archive
        """
        try:
            conn = self._conn
            now = datetime.now(timezone.utc)
            thirty_days_ago = (now - timedelta(days=30)).isoformat()
            ninety_days_ago = (now - timedelta(days=90)).isoformat()
            seven_days_ago = (now - timedelta(days=7)).isoformat()

            # Archive very old never-accessed memories
            archived = conn.execute(
                """SELECT * FROM memories
                   WHERE created_at < ? AND access_count = 0""",
                (ninety_days_ago,),
            ).fetchall()

            if archived:
                archive_time = now.isoformat()
                for row in archived:
                    conn.execute(
                        """INSERT OR REPLACE INTO archived_memories
                           (id, user_id, memory_type, content, importance, tags,
                            created_at, updated_at, expires_at, access_count,
                            last_accessed, archived_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (row["id"], row["user_id"], row["memory_type"],
                         row["content"], row["importance"], row["tags"],
                         row["created_at"], row["updated_at"], row["expires_at"],
                         row["access_count"], row["last_accessed"], archive_time),
                    )
                conn.execute(
                    f"DELETE FROM memories WHERE created_at < ? AND access_count = 0 "
                    f"AND id IN ({','.join('?' * len(archived))})",
                    [ninety_days_ago] + [r["id"] for r in archived],
                )
                logger.info(f"[Decay] Archived {len(archived)} old memories")

            # Decay old unaccessed memories (30+ days, access_count=0)
            conn.execute(
                """UPDATE memories SET importance = MAX(0.05, importance - 0.1),
                   updated_at = ?
                   WHERE created_at < ? AND access_count = 0 AND importance > 0.05""",
                (now.isoformat(), thirty_days_ago),
            )

            # Boost recently accessed memories (accessed in last 7 days)
            conn.execute(
                """UPDATE memories SET importance = MIN(1.0, importance + 0.05),
                   updated_at = ?
                   WHERE last_accessed > ? AND last_accessed IS NOT NULL""",
                (now.isoformat(), seven_days_ago),
            )

            conn.commit()
            logger.info("[Decay] Memory importance decay completed")
        except Exception as e:
            logger.error(f"[Decay] Error: {e}")

    # ─── Phase 2: Smart Context Window ─────────────────────────

    def get_smart_context(
        self, user_id: str, current_message: str, max_tokens: int = 500
    ) -> str:
        """
        Intelligently select which memories to include in prompt context.
        Priority: user profile summary > recent memories > high-importance > frequently-accessed
        Fits within ~max_tokens (estimated at 4 chars/token).
        """
        max_chars = max_tokens * 4
        parts = []
        used_chars = 0

        # 1. User profile summary (most efficient)
        try:
            profile = self._conn.execute(
                "SELECT summary FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if profile and profile["summary"]:
                summary_line = f"[User Profile] {profile['summary']}"
                if len(summary_line) < max_chars * 0.4:  # Cap at 40% for summary
                    parts.append(summary_line)
                    used_chars += len(summary_line)
        except Exception:
            pass

        # 2. Last 5 conversation turns
        try:
            recent_conv = self.get_recent_conversation(user_id, limit=5)
            if recent_conv:
                conv_lines = []
                for turn in recent_conv[-5:]:
                    line = f"  {turn['role']}: {turn['content'][:100]}"
                    if used_chars + len(line) < max_chars * 0.6:
                        conv_lines.append(line)
                        used_chars += len(line)
                if conv_lines:
                    parts.append("[Recent conversation:]\n" + "\n".join(conv_lines))
        except Exception:
            pass

        # 3. Top 10 relevant memories (query-matched + high importance)
        remaining_chars = max_chars - used_chars
        if remaining_chars > 100:
            try:
                memories = self.recall(
                    user_id=user_id,
                    query=current_message,
                    limit=10,
                )
                if memories:
                    mem_lines = []
                    for m in memories:
                        line = f"- [{m['type']}] {m['content']}"
                        if used_chars + len(line) < max_chars:
                            mem_lines.append(line)
                            used_chars += len(line)
                    if mem_lines:
                        parts.append("[Memories about this user:]\n" + "\n".join(mem_lines))
            except Exception:
                pass

        return "\n\n".join(parts) if parts else ""

    # ─── Phase 2: Memory Summarization ─────────────────────────

    def summarize_user_profile(self, user_id: str) -> Optional[str]:
        """
        When a user has > 20 memories, create a concise LLM-generated profile summary.
        Re-summarizes every 50 new memories.
        Returns the summary or None on failure.
        """
        try:
            count = self.get_user_memory_count(user_id)
            if count < 20:
                return None

            # Check if we need to re-summarize
            profile = self._conn.execute(
                "SELECT summary, memory_count_at_last_summary FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            last_count = 0
            if profile:
                last_count = profile["memory_count_at_last_summary"] or 0
                if profile["summary"] and (count - last_count) < 50:
                    return profile["summary"]  # Still fresh enough

            api_key = os.environ.get("CHUTES_API_KEY", "")
            model = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

            if not api_key or OpenAI is None:
                return None

            # Get all memories for this user
            all_memories = self.recall(user_id, limit=50)
            if not all_memories:
                return None

            mem_text = "\n".join(f"- [{m['type']}] {m['content']}" for m in all_memories)

            client = OpenAI(base_url="https://llm.chutes.ai/v1", api_key=api_key)
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "Create a concise user profile summary (3-5 sentences) from these memories. "
                        "Include: name, location, occupation, key interests, personality traits, "
                        "and important life context. Be factual and concise. "
                        "Return ONLY the summary text, no labels or formatting."
                    )},
                    {"role": "user", "content": mem_text},
                ],
                max_tokens=200,
                temperature=0.3,
                timeout=5,
            )
            summary = completion.choices[0].message.content.strip()
            if not summary:
                return None

            # Store the summary
            now = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                """INSERT INTO user_profiles (user_id, summary, first_seen, last_seen, memory_count_at_last_summary)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   summary = excluded.summary,
                   memory_count_at_last_summary = excluded.memory_count_at_last_summary,
                   last_seen = excluded.last_seen""",
                (user_id, summary, now, now, count),
            )
            self._conn.commit()
            logger.info(f"[Summary] Updated profile for {user_id} ({count} memories)")
            return summary

        except Exception as e:
            logger.warning(f"[Summary] Error for {user_id}: {e}")
            return None

    # ─── Phase 2: Memory Export/Import ─────────────────────────

    def export_memories(self, user_id: str) -> Dict:
        """Export all memories for a user as a JSON-serializable dict."""
        try:
            memories = self._conn.execute(
                "SELECT * FROM memories WHERE user_id = ?",
                (user_id,),
            ).fetchall()

            profile = self._conn.execute(
                "SELECT * FROM user_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            return {
                "version": "nobi-memory-v2",
                "user_id": user_id,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "memories": [
                    {
                        "id": r["id"],
                        "type": r["memory_type"],
                        "content": self._decrypt(user_id, r["content"]),
                        "importance": r["importance"],
                        "tags": json.loads(r["tags"]),
                        "created_at": r["created_at"],
                        "access_count": r["access_count"],
                    }
                    for r in memories
                ],
                "profile": {
                    "summary": profile["summary"] if profile else "",
                    "personality_notes": profile["personality_notes"] if profile else "",
                    "total_messages": profile["total_messages"] if profile else 0,
                } if profile else None,
            }
        except Exception as e:
            logger.error(f"[Export] Error for {user_id}: {e}")
            return {"error": str(e)}

    def import_memories(self, user_id: str, data: Dict) -> int:
        """
        Import memories from an exported JSON dict.
        Returns number of memories imported.
        """
        try:
            if data.get("version") != "nobi-memory-v2":
                logger.warning(f"[Import] Unknown version: {data.get('version')}")
                return 0

            memories = data.get("memories", [])
            imported = 0
            for mem in memories:
                if not isinstance(mem, dict) or not mem.get("content"):
                    continue
                # Check for duplicates
                existing = self.recall(user_id, query=mem["content"], limit=3)
                if any(self._similar(mem["content"], e["content"]) for e in existing):
                    continue

                self.store(
                    user_id=user_id,
                    content=mem["content"],
                    memory_type=mem.get("type", "fact"),
                    importance=mem.get("importance", 0.5),
                    tags=mem.get("tags", []),
                )
                imported += 1

            # Restore profile summary if present
            profile = data.get("profile")
            if profile and profile.get("summary"):
                now = datetime.now(timezone.utc).isoformat()
                self._conn.execute(
                    """INSERT INTO user_profiles (user_id, summary, first_seen, last_seen)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET summary = excluded.summary""",
                    (user_id, profile["summary"], now, now),
                )
                self._conn.commit()

            logger.info(f"[Import] Imported {imported} memories for {user_id}")
            return imported

        except Exception as e:
            logger.error(f"[Import] Error for {user_id}: {e}")
            return 0

    def stats(self) -> Dict:
        """Get overall memory stats."""
        conn = self._conn
        total_memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        total_users = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM memories"
        ).fetchone()[0]
        total_conversations = conn.execute(
            "SELECT COUNT(*) FROM conversations"
        ).fetchone()[0]

        return {
            "total_memories": total_memories,
            "total_users": total_users,
            "total_conversation_turns": total_conversations,
        }
