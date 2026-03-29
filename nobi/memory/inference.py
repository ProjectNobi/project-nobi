"""
Implicit Memory Inference — infer habits/preferences from behavior patterns.
Analyzes conversation history → extracts implicit knowledge user never stated.

Approach:
  - Takes last N conversation summaries for a user
  - Calls LLM with structured prompt
  - Extracts: habits, preferences, interests, routines, personality traits
  - Stores inferences as memory_type='implicit_inference'

Run mode:
  - On-demand via infer_implicit_memories()
  - Weekly cron via run_inference_cron()
"""

import os
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger("nobi-inference")

# Number of recent conversations to analyse
DEFAULT_CONV_LIMIT = 50

# Minimum conversations needed before inference is useful
MIN_CONV_THRESHOLD = 5

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

_INFERENCE_PROMPT = """You are an expert psychologist and behavioral analyst.
Based on the following conversation excerpts between an AI companion and a user, infer implicit knowledge about the user.

Look for:
- Daily habits and routines (sleep patterns, meal times, work schedule)
- Preferences (food, music, activities, communication style)
- Interests and hobbies
- Personality traits (introvert/extrovert, optimistic/pessimistic)
- Values and priorities
- Recurring concerns or worries
- Relationships and social patterns

Conversations:
---
{conversations}
---

Output ONLY a valid JSON array (no explanation, no markdown):
[
  {{"type": "habit|preference|interest|routine|personality|value|concern", "inference": "...", "confidence": 0.0-1.0, "evidence": "brief quote or pattern that supports this"}}
]

Rules:
- Only include inferences with confidence >= 0.5
- Maximum 10 inferences
- Be specific and actionable (e.g. "prefers late-night conversations" not "is active")
- If nothing can be inferred, return []
"""


def _get_llm_client() -> Optional[object]:
    """Get Chutes LLM client using project pattern."""
    if not _OPENAI_AVAILABLE:
        return None
    api_key = os.environ.get("CHUTES_API_KEY", "")
    if not api_key:
        return None
    base_url = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")
    return OpenAI(base_url=base_url, api_key=api_key)


def _get_model() -> str:
    return os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")


def _ensure_implicit_table(conn: sqlite3.Connection):
    """Create implicit_memories table if not exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS implicit_memories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            type TEXT NOT NULL,
            inference TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.5,
            evidence TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_implicit_user ON implicit_memories(user_id)")
    conn.commit()


async def infer_implicit_memories(
    user_id: str,
    conversation_summaries: List[str],
    db_path: str = "~/.nobi/bot_memories.db",
) -> List[Dict]:
    """
    Infer implicit memories from conversation history.

    Args:
        user_id: User identifier.
        conversation_summaries: List of conversation text snippets/summaries.
        db_path: SQLite database path.

    Returns:
        List of inference dicts with keys: type, inference, confidence, evidence.
    """
    if len(conversation_summaries) < MIN_CONV_THRESHOLD:
        logger.info(f"[Inference] Skipping user={user_id}: only {len(conversation_summaries)} "
                    f"conversations (need {MIN_CONV_THRESHOLD}+)")
        return []

    client = _get_llm_client()
    if not client:
        logger.warning("[Inference] No LLM client available — skipping inference")
        return []

    # Truncate conversations to avoid token overflow
    conversations_text = "\n---\n".join(c[:300] for c in conversation_summaries[:DEFAULT_CONV_LIMIT])

    prompt = _INFERENCE_PROMPT.format(conversations=conversations_text)

    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()

        # Parse JSON
        inferences = _parse_json_safely(raw)
        if not isinstance(inferences, list):
            logger.warning(f"[Inference] LLM returned non-list: {raw[:200]}")
            return []

        # Validate and clean
        cleaned = []
        for item in inferences:
            if not isinstance(item, dict):
                continue
            inference_text = str(item.get("inference", "")).strip()
            if not inference_text:
                continue
            conf = float(item.get("confidence", 0.5))
            if conf < 0.5:
                continue
            cleaned.append({
                "type": str(item.get("type", "preference")),
                "inference": inference_text,
                "confidence": min(1.0, max(0.0, conf)),
                "evidence": str(item.get("evidence", ""))[:500],
            })

        # Store in DB
        if cleaned:
            _store_inferences(user_id, cleaned, db_path)

        logger.info(f"[Inference] user={user_id}: extracted {len(cleaned)} inferences")
        return cleaned

    except Exception as e:
        logger.error(f"[Inference] LLM call failed: {e}", exc_info=True)
        return []


def _parse_json_safely(text: str) -> any:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


def _store_inferences(user_id: str, inferences: List[Dict], db_path: str):
    """Persist inferences to SQLite."""
    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        logger.warning(f"[Inference] DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        _ensure_implicit_table(conn)
        now = datetime.now(timezone.utc).isoformat()

        # Remove old inferences for this user (replace each run)
        # Keep only last batch to avoid stale data buildup
        conn.execute("DELETE FROM implicit_memories WHERE user_id = ?", [user_id])

        for inf in inferences:
            conn.execute(
                """INSERT INTO implicit_memories (id, user_id, type, inference, confidence, evidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [str(uuid.uuid4()), user_id, inf["type"], inf["inference"],
                 inf["confidence"], inf["evidence"], now, now]
            )
        conn.commit()
        logger.info(f"[Inference] Stored {len(inferences)} inferences for user={user_id}")
    except Exception as e:
        logger.error(f"[Inference] Store error: {e}", exc_info=True)
        conn.rollback()
    finally:
        conn.close()


def get_implicit_memories(user_id: str, db_path: str = "~/.nobi/bot_memories.db") -> List[Dict]:
    """Retrieve stored implicit inferences for a user."""
    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_implicit_table(conn)
        rows = conn.execute(
            "SELECT * FROM implicit_memories WHERE user_id = ? ORDER BY confidence DESC",
            [user_id]
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[Inference] Get error: {e}")
        return []
    finally:
        conn.close()


async def run_inference_cron(
    db_path: str = "~/.nobi/bot_memories.db",
    conv_limit: int = DEFAULT_CONV_LIMIT,
) -> Dict:
    """
    Run implicit memory inference for ALL users.
    Designed for weekly cron job execution.

    Returns:
        Dict with {total_users, total_inferences, errors}
    """
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return {"total_users": 0, "total_inferences": 0, "errors": ["DB not found"]}

    conn = sqlite3.connect(db_path_expanded)
    conn.row_factory = sqlite3.Row
    try:
        users = conn.execute("SELECT DISTINCT user_id FROM conversations").fetchall()
        user_ids = [r["user_id"] for r in users]
    finally:
        conn.close()

    total_inferences = 0
    errors = []

    for uid in user_ids:
        try:
            # Fetch recent conversations
            conn2 = sqlite3.connect(db_path_expanded)
            conn2.row_factory = sqlite3.Row
            try:
                rows = conn2.execute(
                    "SELECT content FROM conversations WHERE user_id = ? AND role = 'user' "
                    "ORDER BY created_at DESC LIMIT ?",
                    [uid, conv_limit]
                ).fetchall()
                summaries = [r["content"] for r in rows]
            finally:
                conn2.close()

            inferences = await infer_implicit_memories(uid, summaries, db_path=db_path)
            total_inferences += len(inferences)
        except Exception as e:
            errors.append(f"user={uid}: {e}")

    result = {
        "total_users": len(user_ids),
        "total_inferences": total_inferences,
        "errors": errors,
    }
    logger.info(f"[Inference] Cron complete: {result}")
    return result
