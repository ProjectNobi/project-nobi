"""
Project Nobi — Cross-Miner Memory Sync
========================================
Ensures all miners have consistent memory for each user.
The validator acts as memory coordinator, syncing memories
to all miners after multi-turn tests.
"""

import asyncio
import logging
from typing import List, Optional

try:
    import bittensor as bt
    from nobi.protocol import MemoryStore
except ImportError:
    bt = None

logger = logging.getLogger("nobi-memory-sync")


async def sync_memories_to_miners(
    dendrite,
    metagraph,
    user_id: str,
    memories: List[dict],
    timeout: float = 10.0,
) -> int:
    """
    Sync a user's memories to ALL active miners.
    Called by the validator after multi-turn tests to ensure consistency.

    Args:
        dendrite: Bittensor dendrite for sending synapses
        metagraph: Current metagraph with miner axons
        user_id: The user whose memories to sync
        memories: List of memory dicts with content, type, importance, tags
        timeout: Timeout per sync call

    Returns:
        Number of miners that successfully stored the memories.
    """
    if bt is None or not dendrite or not metagraph:
        logger.warning("[Sync] Bittensor not available, skipping sync")
        return 0

    if not memories:
        return 0

    # Find all active miners
    try:
        active_axons = []
        active_uids = []
        for uid in range(metagraph.n.item()):
            axon = metagraph.axons[uid]
            if axon.ip != "0.0.0.0" and axon.port > 0:
                active_axons.append(axon)
                active_uids.append(uid)

        if not active_axons:
            logger.debug("[Sync] No active miners to sync to")
            return 0
    except Exception as e:
        logger.warning(f"[Sync] Error getting active miners: {e}")
        return 0

    synced_count = 0

    # Send each memory to all miners (batch per memory to reduce calls)
    for mem in memories[:10]:  # Cap at 10 memories per sync
        try:
            content = mem.get("content", "")
            if not content:
                continue

            synapse = MemoryStore(
                user_id=user_id,
                content=content,
                memory_type=mem.get("type", "fact"),
                importance=float(mem.get("importance", 0.5)),
                tags=mem.get("tags", []),
            )

            responses = await dendrite(
                axons=active_axons,
                synapse=synapse,
                deserialize=False,
                timeout=timeout,
            )

            stored = sum(
                1 for r in (responses or [])
                if r and getattr(r, "stored", False)
            )
            if stored > 0:
                synced_count += 1

        except Exception as e:
            logger.debug(f"[Sync] Error syncing memory: {e}")
            continue

    if synced_count > 0:
        logger.info(
            f"[Sync] Synced {synced_count}/{len(memories)} memories for {user_id} "
            f"to {len(active_axons)} miners"
        )

    return synced_count
