"""
ACT-R Forgetting Formula for Nori memories.
Biological memory decay: recency + frequency + importance.

Formula: A(i) = ln(Σ tₖ⁻ᵈ) where tₖ = time since recall k, d = decay parameter
Simplified: activation = base_level + recency_boost + frequency_component

References:
  Anderson & Lebiere (1998) — The Atomic Components of Thought
  Standard ACT-R decay parameter d = 0.5
"""

import json
import math
import logging
import os
import sqlite3
import time
from typing import List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("nobi-forgetting")

# Standard ACT-R decay parameter
DECAY_PARAMETER: float = 0.5

# Default activation threshold below which a memory is soft-deleted
DEFAULT_THRESHOLD: float = -2.0

# Tags that indicate high-importance memories (decay slower)
IMPORTANT_TAGS = frozenset({"name", "identity", "emotion", "date", "birthday", "anniversary",
                             "relationship", "family", "career", "location", "health", "pet"})

# Importance multiplier for protected memories
IMPORTANCE_DECAY_MULTIPLIER: float = 0.5  # lower d → slower decay


async def compute_activation(
    memory_id: str,
    access_times: List[float],
    importance: float = 1.0,
    decay: float = DECAY_PARAMETER,
) -> float:
    """
    Compute ACT-R activation score for a memory.

    Args:
        memory_id: Memory identifier (for logging).
        access_times: List of Unix timestamps when memory was last accessed.
                      If empty, uses [created_at] = now (single access at creation).
        importance: Importance multiplier [0.0, 1.0]. Higher = decays slower.
        decay: ACT-R decay parameter d. Default 0.5. Reduce to slow decay.

    Returns:
        Activation score (float). Typical range: -5.0 to +2.0.
        Scores below DEFAULT_THRESHOLD (-2.0) indicate forgettable memories.
    """
    if not access_times:
        # No access history — single access at "now" (just created/encountered)
        access_times = [time.time()]

    now = time.time()

    # Adjust decay based on importance
    # High importance → lower effective decay → slower forgetting
    effective_decay = decay * (1.0 - (importance * IMPORTANCE_DECAY_MULTIPLIER))
    effective_decay = max(0.05, min(1.0, effective_decay))

    total = 0.0
    for t_access in access_times:
        t_delta = now - t_access
        if t_delta <= 0:
            t_delta = 0.001  # avoid division by zero / log(0)
        # Convert to hours for more stable range
        t_hours = t_delta / 3600.0
        total += (t_hours ** -effective_decay)

    if total <= 0:
        return DEFAULT_THRESHOLD - 1.0

    activation = math.log(total)
    logger.debug(f"[ACT-R] memory={memory_id} activation={activation:.3f} "
                 f"accesses={len(access_times)} decay={effective_decay:.3f}")
    return activation


async def apply_forgetting(
    user_id: str,
    threshold: float = DEFAULT_THRESHOLD,
    db_path: str = "~/.nobi/bot_memories.db",
    lazy: bool = False,
) -> int:
    """
    Apply ACT-R forgetting to all memories for a user.

    Memories with activation below `threshold` are soft-deleted (marked inactive).
    Does NOT hard-delete — memories remain in DB with is_active=False.

    Args:
        user_id: The user to process.
        threshold: Activation threshold. Default -2.0.
        db_path: Path to SQLite database.
        lazy: If True, only process memories with access_count > 0.

    Returns:
        Count of memories soft-deleted.
    """
    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        logger.warning(f"[ACT-R] DB not found at {db_path}, skipping forgetting pass")
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Ensure is_active column exists (migration)
        try:
            conn.execute("SELECT is_active FROM memories LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE memories ADD COLUMN is_active INTEGER DEFAULT 1")
            conn.commit()
            logger.info("[ACT-R] Migrated: added is_active column to memories")

        # Fetch active memories for this user
        query = """
            SELECT id, importance, tags, created_at, last_accessed, access_count
            FROM memories
            WHERE user_id = ? AND (is_active IS NULL OR is_active = 1)
        """
        params = [user_id]
        if lazy:
            query += " AND access_count > 0"

        rows = conn.execute(query, params).fetchall()

        forgotten_count = 0
        now = time.time()

        for row in rows:
            # Build access_times from created_at + last_accessed
            access_times = []

            try:
                created_ts = datetime.fromisoformat(row["created_at"]).timestamp()
                access_times.append(created_ts)
            except (ValueError, TypeError):
                access_times.append(now - 86400)  # fallback: 1 day ago

            if row["last_accessed"]:
                try:
                    last_ts = datetime.fromisoformat(row["last_accessed"]).timestamp()
                    if last_ts > access_times[0]:
                        access_times.append(last_ts)
                except (ValueError, TypeError):
                    pass

            # Add synthetic access times based on access_count
            access_count = row["access_count"] or 0
            if access_count > 1:
                # Distribute accesses linearly between created_at and last_accessed
                if len(access_times) >= 2:
                    span = access_times[-1] - access_times[0]
                    for i in range(1, min(access_count - 1, 5)):  # cap at 5 for perf
                        t = access_times[0] + (span * i / access_count)
                        access_times.insert(-1, t)

            # Parse tags to determine importance multiplier
            try:
                tags = set(json.loads(row["tags"] or "[]"))
            except (json.JSONDecodeError, TypeError):
                tags = set()

            importance = float(row["importance"] or 0.5)

            # Boost importance if tagged as important
            if tags & IMPORTANT_TAGS:
                importance = min(1.0, importance * 1.3)

            # Compute activation
            activation = await compute_activation(
                memory_id=row["id"],
                access_times=access_times,
                importance=importance,
                decay=DECAY_PARAMETER,
            )

            if activation < threshold:
                conn.execute(
                    "UPDATE memories SET is_active = 0, updated_at = ? WHERE id = ?",
                    [datetime.now(timezone.utc).isoformat(), row["id"]]
                )
                forgotten_count += 1
                logger.debug(f"[ACT-R] Soft-deleted memory {row['id']} (activation={activation:.3f})")

        conn.commit()
        logger.info(f"[ACT-R] Forgetting pass for user={user_id}: "
                    f"{forgotten_count}/{len(rows)} memories soft-deleted")
        return forgotten_count

    except Exception as e:
        logger.error(f"[ACT-R] Error in apply_forgetting: {e}", exc_info=True)
        conn.rollback()
        return 0
    finally:
        conn.close()


async def run_forgetting_cron(
    db_path: str = "~/.nobi/bot_memories.db",
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """
    Run forgetting pass for ALL users in the database.
    Designed for nightly/weekly cron job execution.

    Returns:
        Dict with {total_users, total_forgotten, errors}
    """
    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        return {"total_users": 0, "total_forgotten": 0, "errors": ["DB not found"]}

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT user_id FROM memories").fetchall()
        user_ids = [r[0] for r in rows]
    finally:
        conn.close()

    total_forgotten = 0
    errors = []
    for uid in user_ids:
        try:
            count = await apply_forgetting(uid, threshold=threshold, db_path=db_path)
            total_forgotten += count
        except Exception as e:
            errors.append(f"user={uid}: {e}")

    result = {
        "total_users": len(user_ids),
        "total_forgotten": total_forgotten,
        "errors": errors,
    }
    logger.info(f"[ACT-R] Cron complete: {result}")
    return result
