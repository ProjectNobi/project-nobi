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
import threading
from typing import List, Dict, Optional
from datetime import datetime, timezone


class MemoryManager:
    """Manages persistent user memories with SQLite backend."""

    def __init__(self, db_path: str = "~/.nobi/memories.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

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
                total_messages INTEGER DEFAULT 0
            );
        """)
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
        """Store a memory. Returns the memory ID."""
        memory_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        self._conn.execute(
            """INSERT INTO memories (id, user_id, memory_type, content, importance,
               tags, created_at, updated_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_id,
                user_id,
                memory_type,
                content,
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
                "content": row["content"],
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
        """Save a conversation message."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO conversations (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, now),
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
        """Get recent conversation history for a user."""
        rows = self._conn.execute(
            """SELECT role, content, created_at FROM conversations
               WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()

        return [
            {"role": row["role"], "content": row["content"]}
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
