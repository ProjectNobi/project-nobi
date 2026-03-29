"""
Nightly Self-Reflection — Conflict Detection for Nori.

Detects two types of conflicts in user memories:
  1. Time conflicts   — same event referenced with different dates
  2. Fact conflicts   — contradictory facts (e.g. "lives in London" vs "lives in Paris")

Resolution strategy: flag for human review (never auto-delete without confirmation).
Flagged conflicts stored in memory_conflicts table with conflict_flag=True.
"""

import os
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger("nobi-reflection")

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# Conflict types
CONFLICT_TIME = "time_conflict"
CONFLICT_FACT = "fact_conflict"

_CONFLICT_PROMPT = """You are a careful fact-checker reviewing a user's memory entries for contradictions.

Below are memories stored about a user. Identify any conflicts:

TYPE 1 - Time conflicts: The same event is referenced with different dates or timeframes.
TYPE 2 - Fact conflicts: Two memories contain contradictory facts about the same subject.
  Examples: "lives in London" vs "lives in Paris", "married" vs "single", 
            "works at Google" vs "works at Apple"

Memories:
---
{memories}
---

Output ONLY valid JSON (no explanation, no markdown):
[
  {{
    "type": "time_conflict|fact_conflict",
    "memory_id_a": "...",
    "memory_id_b": "...",
    "description": "Brief description of the conflict",
    "confidence": 0.0-1.0
  }}
]

Rules:
- Only flag genuine contradictions, not updates (e.g. "I moved to Paris" after "lives in London" is an UPDATE, not conflict)
- Only include conflicts with confidence >= 0.6
- If no conflicts, return []
"""


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


def _ensure_conflict_table(conn: sqlite3.Connection):
    """Create memory_conflicts table if not exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_conflicts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory_id_a TEXT NOT NULL,
            memory_id_b TEXT NOT NULL,
            conflict_type TEXT NOT NULL,
            description TEXT NOT NULL,
            confidence REAL DEFAULT 0.7,
            resolved INTEGER DEFAULT 0,
            resolution_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_user ON memory_conflicts(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conflicts_resolved ON memory_conflicts(user_id, resolved)")
    conn.commit()


def _parse_json_safely(text: str) -> any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []


async def detect_conflicts(
    user_id: str,
    db_path: str = "~/.nobi/bot_memories.db",
) -> List[Dict]:
    """
    Detect conflicts in user's memories using LLM analysis.

    Args:
        user_id: User to analyse.
        db_path: SQLite DB path.

    Returns:
        List of conflict dicts: {type, memory_id_a, memory_id_b, description, confidence}
    """
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return []

    conn = sqlite3.connect(db_path_expanded)
    conn.row_factory = sqlite3.Row

    try:
        # Fetch fact-type memories (most likely to conflict)
        rows = conn.execute(
            """SELECT id, memory_type, content, created_at, tags
               FROM memories
               WHERE user_id = ? AND (is_active IS NULL OR is_active = 1)
               AND memory_type IN ('fact', 'event', 'preference', 'context')
               ORDER BY importance DESC
               LIMIT 100""",
            [user_id]
        ).fetchall()
    except Exception as e:
        logger.error(f"[Reflection] DB query error: {e}")
        conn.close()
        return []
    finally:
        conn.close()

    if len(rows) < 2:
        logger.debug(f"[Reflection] user={user_id}: not enough memories to check ({len(rows)})")
        return []

    # Decrypt memories if needed
    db_path_for_decrypt = db_path_expanded
    memories_text_parts = []
    for row in rows:
        content = row["content"]
        # Try to decrypt if encrypted
        try:
            from nobi.memory.encryption import decrypt_memory, is_encrypted
            if is_encrypted(content):
                content = decrypt_memory(user_id, content)
        except Exception:
            pass  # Use raw content

        memories_text_parts.append(
            f"[ID: {row['id']}] [{row['memory_type']}] {content}"
        )

    memories_text = "\n".join(memories_text_parts)

    client = _get_llm_client()
    if not client:
        # Fallback: rule-based conflict detection
        return _rule_based_conflict_detection(user_id, rows)

    prompt = _CONFLICT_PROMPT.format(memories=memories_text[:4000])  # token limit

    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        conflicts = _parse_json_safely(raw)

        if not isinstance(conflicts, list):
            return []

        # Validate
        valid = []
        row_ids = {row["id"] for row in rows}
        for c in conflicts:
            if not isinstance(c, dict):
                continue
            mid_a = str(c.get("memory_id_a", ""))
            mid_b = str(c.get("memory_id_b", ""))
            if not mid_a or not mid_b or mid_a == mid_b:
                continue
            # Note: IDs may be synthetic from LLM — still flag them
            conf = float(c.get("confidence", 0.7))
            if conf < 0.6:
                continue
            valid.append({
                "type": str(c.get("type", CONFLICT_FACT)),
                "memory_id_a": mid_a,
                "memory_id_b": mid_b,
                "description": str(c.get("description", ""))[:500],
                "confidence": min(1.0, max(0.0, conf)),
            })

        logger.info(f"[Reflection] user={user_id}: found {len(valid)} conflicts")
        return valid

    except Exception as e:
        logger.error(f"[Reflection] LLM call failed: {e}", exc_info=True)
        return _rule_based_conflict_detection(user_id, rows)


def _rule_based_conflict_detection(user_id: str, rows) -> List[Dict]:
    """
    Simple rule-based conflict detection as LLM fallback.
    Looks for memories with conflicting location/status keywords.
    """
    import re
    conflicts = []

    EXCLUSIVE_PATTERNS = [
        (r'\blives?\s+in\s+(\w+)', CONFLICT_FACT, "location"),
        (r'\bfrom\s+(\w+)', CONFLICT_FACT, "origin"),
        (r'\bworks?\s+at\s+(\w+)', CONFLICT_FACT, "employer"),
        (r'\bmarried\b|\bsingle\b|\bdivorced\b', CONFLICT_FACT, "relationship_status"),
    ]

    # Group by category
    category_matches: Dict[str, List] = {}
    for row in rows:
        content = row["content"].lower()
        for pattern, ctype, category in EXCLUSIVE_PATTERNS:
            match = re.search(pattern, content)
            if match:
                if category not in category_matches:
                    category_matches[category] = []
                category_matches[category].append((row["id"], match.group(), ctype))

    # Flag categories with multiple different values
    for category, matches in category_matches.items():
        if len(matches) >= 2:
            # Check if values differ
            values = set(m[1] for m in matches)
            if len(values) > 1:
                conflicts.append({
                    "type": matches[0][2],
                    "memory_id_a": matches[0][0],
                    "memory_id_b": matches[1][0],
                    "description": f"Potential {category} conflict: {list(values)[:3]}",
                    "confidence": 0.65,
                })

    return conflicts


async def resolve_conflict(
    conflict: Dict,
    user_id: str,
    strategy: str = "flag",
    db_path: str = "~/.nobi/bot_memories.db",
) -> Dict:
    """
    Resolve a detected conflict.

    Args:
        conflict: Conflict dict from detect_conflicts().
        user_id: User identifier.
        strategy: Resolution strategy. Only "flag" is supported (human review required).
        db_path: SQLite DB path.

    Returns:
        Resolution result dict.
    """
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return {"success": False, "error": "DB not found"}

    conn = sqlite3.connect(db_path_expanded)
    try:
        _ensure_conflict_table(conn)
        now = datetime.now(timezone.utc).isoformat()

        # Store conflict for human review
        conflict_id = str(uuid.uuid4())
        conn.execute(
            """INSERT OR IGNORE INTO memory_conflicts
               (id, user_id, memory_id_a, memory_id_b, conflict_type, description,
                confidence, resolved, resolution_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)""",
            [
                conflict_id,
                user_id,
                conflict.get("memory_id_a", ""),
                conflict.get("memory_id_b", ""),
                conflict.get("type", CONFLICT_FACT),
                conflict.get("description", ""),
                conflict.get("confidence", 0.7),
                now, now,
            ]
        )

        # Also flag in memories table if IDs are valid
        for mid in [conflict.get("memory_id_a"), conflict.get("memory_id_b")]:
            if mid:
                try:
                    # Ensure conflict_flag column exists
                    try:
                        conn.execute("SELECT conflict_flag FROM memories LIMIT 1")
                    except sqlite3.OperationalError:
                        conn.execute("ALTER TABLE memories ADD COLUMN conflict_flag INTEGER DEFAULT 0")

                    conn.execute(
                        "UPDATE memories SET conflict_flag = 1, updated_at = ? WHERE id = ?",
                        [now, mid]
                    )
                except Exception as e:
                    logger.debug(f"[Reflection] Could not flag memory {mid}: {e}")

        conn.commit()
        logger.info(f"[Reflection] Flagged conflict {conflict_id} for user={user_id}")
        return {
            "success": True,
            "conflict_id": conflict_id,
            "strategy": "flag",
            "message": "Conflict flagged for human review",
        }

    except Exception as e:
        logger.error(f"[Reflection] Resolve error: {e}", exc_info=True)
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


async def run_nightly_reflection(
    user_id: str,
    db_path: str = "~/.nobi/bot_memories.db",
) -> Dict:
    """
    Run full nightly reflection cycle for a user.

    Steps:
    1. Detect conflicts in memories
    2. Flag each conflict for human review
    3. Return summary

    Returns:
        Summary dict: {conflicts_found, conflicts_flagged, errors}
    """
    conflicts_found = 0
    conflicts_flagged = 0
    errors = []

    try:
        conflicts = await detect_conflicts(user_id, db_path=db_path)
        conflicts_found = len(conflicts)

        for conflict in conflicts:
            try:
                result = await resolve_conflict(
                    conflict, user_id, strategy="flag", db_path=db_path
                )
                if result.get("success"):
                    conflicts_flagged += 1
            except Exception as e:
                errors.append(f"resolve error: {e}")

    except Exception as e:
        errors.append(f"detect error: {e}")
        logger.error(f"[Reflection] Nightly reflection error for user={user_id}: {e}")

    summary = {
        "user_id": user_id,
        "conflicts_found": conflicts_found,
        "conflicts_flagged": conflicts_flagged,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[Reflection] Nightly summary: {summary}")
    return summary


async def run_reflection_cron(
    db_path: str = "~/.nobi/bot_memories.db",
) -> Dict:
    """
    Run nightly reflection for ALL users.
    Designed for cron job execution at 2am daily.

    Returns:
        Aggregate summary dict.
    """
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return {"total_users": 0, "total_conflicts": 0, "errors": ["DB not found"]}

    conn = sqlite3.connect(db_path_expanded)
    try:
        users = conn.execute("SELECT DISTINCT user_id FROM memories").fetchall()
        user_ids = [r[0] for r in users]
    finally:
        conn.close()

    total_conflicts = 0
    errors = []

    for uid in user_ids:
        try:
            result = await run_nightly_reflection(uid, db_path=db_path)
            total_conflicts += result.get("conflicts_found", 0)
            errors.extend(result.get("errors", []))
        except Exception as e:
            errors.append(f"user={uid}: {e}")

    return {
        "total_users": len(user_ids),
        "total_conflicts": total_conflicts,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_unresolved_conflicts(
    user_id: str,
    db_path: str = "~/.nobi/bot_memories.db",
) -> List[Dict]:
    """Get all unresolved conflicts for a user."""
    db_path_expanded = os.path.expanduser(db_path)
    if not os.path.exists(db_path_expanded):
        return []

    conn = sqlite3.connect(db_path_expanded)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_conflict_table(conn)
        rows = conn.execute(
            "SELECT * FROM memory_conflicts WHERE user_id = ? AND resolved = 0 ORDER BY created_at DESC",
            [user_id]
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[Reflection] Get conflicts error: {e}")
        return []
    finally:
        conn.close()
