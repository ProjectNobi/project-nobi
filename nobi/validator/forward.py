# Project Nobi — Validator Forward Pass
# Phase 1: Send companion queries to miners, score responses
# Phase 2: Multi-turn memory testing with dynamic query generation
# Phase 3: Per-miner latency tracking, soft multi-turn fallback, memory synapse testing
#
# FAIRNESS DESIGN:
# - Queries are dynamically generated (not static) — can't pre-cache answers
# - All miners get same query in each round — fair comparison
# - Scores use LLM judge with heuristic fallback that caps at 0.5 (not 1.0)
# - Memory scoring checks natural integration, not just keyword presence
# - Single-turn queries include a fake user_id — miners can't detect test vs real
# - Per-miner latency: each miner gets individual timing, not batch average
# - Soft multi-turn fallback: failing miners get score 0, rest continue

import json
import os
import time
import random
import asyncio
import numpy as np
import bittensor as bt

from nobi.protocol import CompanionRequest, MemoryStore, MemoryRecall
from nobi.validator.reward import get_rewards
from nobi.validator.query_generator import (
    generate_single_turn_query,
    generate_multi_turn_scenario,
)
from nobi.utils.uids import get_random_uids
from nobi.memory.sync import sync_memories_to_miners
from nobi.mining.specialization import (
    MinerRouter,
    classify_query,
    select_best_miner,
    SPECIALIZATIONS,
)

# Track forward step count for periodic memory testing
_step_counter = 0
_turn_counter = 0  # Track conversation turns for periodic decay

# ─── Miner TEE Public Key Cache (Phase 2: HPKE key wrapping) ─────────────────
# Maps miner UID → base64url-encoded X25519 public key
# Populated when miners include tee_pubkey in their responses
_miner_pubkey_cache: dict = {}  # uid (int) → pubkey_b64 (str)


def cache_miner_pubkey(uid: int, tee_pubkey_b64: str) -> None:
    """
    Cache a miner's TEE public key for HPKE key wrapping.

    Called after receiving a response from the miner that includes tee_pubkey.

    Args:
        uid: Miner's UID on the metagraph
        tee_pubkey_b64: Base64url-encoded X25519 public key (44 chars)
    """
    import base64
    if not tee_pubkey_b64:
        return
    try:
        raw = base64.urlsafe_b64decode(tee_pubkey_b64.encode("ascii"))
        if len(raw) != 32:
            bt.logging.warning(
                f"[HPKE] Miner {uid} sent invalid tee_pubkey length {len(raw)}, ignoring"
            )
            return
        _miner_pubkey_cache[uid] = tee_pubkey_b64
        bt.logging.debug(f"[HPKE] Cached TEE pubkey for miner {uid}: {tee_pubkey_b64[:16]}...")
    except Exception as e:
        bt.logging.warning(f"[HPKE] Failed to cache pubkey for miner {uid}: {e}")


def get_miner_pubkey_bytes(uid: int) -> bytes | None:
    """
    Get cached miner TEE public key bytes for HPKE wrapping.

    Returns:
        32-byte X25519 public key, or None if not cached yet
    """
    import base64
    pubkey_b64 = _miner_pubkey_cache.get(uid)
    if not pubkey_b64:
        return None
    try:
        return base64.urlsafe_b64decode(pubkey_b64.encode("ascii"))
    except Exception:
        return None


# ─── Miner Router (persistent across forward calls) ─────────────────────────
_miner_router: MinerRouter | None = None
_ROUTER_STATE_PATH = os.path.expanduser("~/.nobi/miner_router_state.json")


def _get_router() -> MinerRouter:
    """Get or initialize the global MinerRouter, loading persisted state."""
    global _miner_router
    if _miner_router is None:
        _miner_router = MinerRouter()
        _load_router_state(_miner_router)
    return _miner_router


def _load_router_state(router: MinerRouter) -> None:
    """Load router state from disk."""
    try:
        if os.path.exists(_ROUTER_STATE_PATH):
            with open(_ROUTER_STATE_PATH, "r") as f:
                state = json.load(f)
            for uid_str, profile_data in state.get("miners", {}).items():
                uid = int(uid_str)
                profile = router.register_miner(
                    uid=uid,
                    hotkey=profile_data.get("hotkey", ""),
                    specialization=profile_data.get("specialization", "general"),
                )
                profile.total_queries = profile_data.get("total_queries", 0)
                profile.total_score = profile_data.get("total_score", 0.0)
                for cat, scores in profile_data.get("scores_by_category", {}).items():
                    profile.scores_by_category[cat] = scores
            bt.logging.info(
                f"[Router] Loaded state: {len(router.miners)} miners from {_ROUTER_STATE_PATH}"
            )
    except Exception as e:
        bt.logging.warning(f"[Router] Failed to load state (non-fatal): {e}")


def _save_router_state(router: MinerRouter) -> None:
    """Persist router state to disk (JSON)."""
    try:
        os.makedirs(os.path.dirname(_ROUTER_STATE_PATH), exist_ok=True)
        state = {"miners": {}}
        for uid, profile in router.miners.items():
            state["miners"][str(uid)] = {
                "hotkey": profile.hotkey,
                "specialization": profile.specialization,
                "total_queries": profile.total_queries,
                "total_score": profile.total_score,
                "scores_by_category": dict(profile.scores_by_category),
            }
        with open(_ROUTER_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        bt.logging.warning(f"[Router] Failed to save state: {e}")


async def forward(self):
    """
    Validator forward pass:
    1. Select random miners to query
    2. Run either single-turn or multi-turn test (dynamically generated)
    3. Score responses using LLM-as-judge
    4. Track per-miner response latency for reliability scoring
    5. Update miner scores
    6. Periodically test MemoryStore/MemoryRecall synapses (every 5th step)
    """
    global _step_counter, _turn_counter
    _step_counter += 1
    _turn_counter += 1

    # Run memory decay every 100 turns
    if _turn_counter % 100 == 0:
        try:
            from nobi.memory import MemoryManager
            mm = MemoryManager()
            mm.decay_old_memories()
            bt.logging.info("[Forward] Ran memory importance decay")
        except Exception as e:
            bt.logging.debug(f"[Forward] Decay error (non-fatal): {e}")

    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)

    if len(miner_uids) == 0:
        bt.logging.warning("No miners available to query.")
        time.sleep(10)
        return

    # Ensure all queried miners are registered in the router
    router = _get_router()
    for uid in miner_uids:
        if uid not in router.miners:
            hotkey = self.metagraph.hotkeys[uid] if uid < len(self.metagraph.hotkeys) else ""
            router.register_miner(uid=uid, hotkey=hotkey)

    # Every 5th step, test memory synapses
    if _step_counter % 5 == 0:
        try:
            await test_memory(self, miner_uids)
        except Exception as e:
            bt.logging.warning(f"[Memory test] Error (non-fatal): {e}")

    # 60% multi-turn, 40% single-turn
    use_multi_turn = random.random() < 0.6

    if use_multi_turn:
        await _forward_multi_turn(self, miner_uids)
    else:
        await _forward_single_turn(self, miner_uids)

    time.sleep(10)


async def _query_single_miner(dendrite, axon, synapse, timeout):
    """Query a single miner and measure its individual latency."""
    t_start = time.monotonic()
    try:
        responses = await dendrite(
            axons=[axon],
            synapse=synapse,
            deserialize=False,  # Get raw synapse to read tee_pubkey
            timeout=timeout,
        )
        latency = time.monotonic() - t_start
        raw = responses[0] if responses else None

        # Phase 2: Cache the miner's TEE public key if advertised
        if raw is not None:
            tee_pubkey = getattr(raw, "tee_pubkey", "")
            if tee_pubkey:
                # We don't have UID here, caller handles caching
                # Return tee_pubkey alongside response so caller can cache it
                response = raw.response if isinstance(getattr(raw, "response", None), str) else ""
                return response, latency, tee_pubkey

        response = raw.response if raw and isinstance(getattr(raw, "response", None), str) else ""
        return response, latency, ""
    except Exception as e:
        latency = time.monotonic() - t_start
        bt.logging.debug(f"Miner query failed: {e}")
        return "", latency, ""


def _build_synapse_for_miner(
    query: str,
    user_id: str,
    query_type: str,
    context: str = "",
    miner_uid: int = None,
) -> "CompanionRequest":
    """
    Build a CompanionRequest synapse, encrypting if TEE encryption is available.

    Phase 5: If the cryptography library is available, all validator queries
    are encrypted with AES-256-GCM before being sent over the wire.

    Phase 6 (HPKE): If the miner's TEE public key is cached, the session key
    is HPKE-wrapped so only the miner's TEE enclave can unwrap it.
    Falls back to Phase 1 (plaintext key_id) if no pubkey is cached yet.

    Args:
        query: The query text
        user_id: User identifier
        query_type: Query category
        context: Optional memory context to also encrypt
        miner_uid: Miner's UID for HPKE pubkey lookup (Phase 2)

    Returns:
        CompanionRequest with either plaintext or encrypted fields
    """
    try:
        from nobi.privacy.tee_encryption import encrypt_payload, is_available
        if is_available():
            # Phase 2: use cached miner pubkey for HPKE wrapping if available
            miner_pubkey = None
            if miner_uid is not None:
                miner_pubkey = get_miner_pubkey_bytes(miner_uid)

            payload = encrypt_payload(query, context, miner_pubkey=miner_pubkey)

            if miner_pubkey is not None:
                bt.logging.debug(
                    f"[HPKE] Built Phase 2 encrypted synapse for miner {miner_uid} "
                    f"(scheme={payload['encryption_scheme']})"
                )

            return CompanionRequest(
                message="[encrypted]",  # Plaintext field set to non-sensitive marker
                user_id=user_id,
                query_type=query_type,
                encrypted=payload["encrypted"],
                encryption_scheme=payload["encryption_scheme"],
                encrypted_message=payload["encrypted_message"],
                encrypted_context=payload["encrypted_context"],
                key_id=payload["key_id"],
            )
    except Exception as e:
        bt.logging.debug(f"[TEE] Encryption unavailable, falling back to plaintext: {e}")

    # Fallback: plaintext (backward compatible)
    return CompanionRequest(message=query, user_id=user_id, query_type=query_type)


async def _forward_single_turn(self, miner_uids):
    """Single-turn query with dynamically generated question and per-miner latency."""
    query = generate_single_turn_query()
    # Include a fake user_id so miners can't distinguish test from real user
    fake_user_id = f"user_{random.randint(100000, 999999)}"

    # Classify the query type for specialization routing
    router = _get_router()
    query_type = classify_query(query)

    bt.logging.info(
        f"[Single-turn] Querying {len(miner_uids)} miners, "
        f"query_type={query_type}: '{query[:80]}'"
    )

    # Task 1: Per-miner latency — query all miners in parallel, track individual timing
    # Phase 2: Build per-miner synapses (each may have different HPKE pubkey)
    synapses = [
        _build_synapse_for_miner(query, fake_user_id, query_type, miner_uid=int(uid))
        for uid in miner_uids
    ]
    # Log encryption scheme for first synapse (representative)
    if synapses:
        _sample = synapses[0]
        bt.logging.info(
            f"[TEE] Query encrypted={getattr(_sample, 'encrypted', False)}, "
            f"scheme='{getattr(_sample, 'encryption_scheme', '')}'"
        )
    tasks = [
        _query_single_miner(
            self.dendrite,
            self.metagraph.axons[uid],
            synapse,
            self.config.neuron.timeout,
        )
        for uid, synapse in zip(miner_uids, synapses)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    latencies = []
    for uid, r in zip(miner_uids, results):
        if isinstance(r, Exception):
            processed.append("")
            latencies.append(self.config.neuron.timeout)
        else:
            processed.append(r[0])
            latencies.append(r[1])
            # Phase 2: Cache miner TEE pubkey if advertised
            if r[2]:
                cache_miner_pubkey(int(uid), r[2])

    rewards = get_rewards(
        self, query=query, responses=processed,
        test_type="single", latencies=latencies,
    )
    bt.logging.info(f"Scored responses: {rewards}")

    # Update router with per-miner scores by query category
    for uid, score in zip(miner_uids, rewards):
        router.record_score(int(uid), query_type, float(score))

    # Persist router state every 10 steps
    if _step_counter % 10 == 0:
        _save_router_state(router)

    self.update_scores(rewards, miner_uids)


async def _forward_multi_turn(self, miner_uids):
    """
    Multi-turn memory test with dynamically generated scenario.
    Each test is unique — miners can't pre-cache answers.
    Task 2: Soft fallback — failing miners get score 0 but don't abort the round.
    """
    scenario = generate_multi_turn_scenario()
    test_user_id = f"test_{random.randint(100000, 999999)}"

    bt.logging.info(f"[Multi-turn] Testing: {scenario['description']} "
                   f"with {len(miner_uids)} miners")

    # Track which miners are still viable (Task 2: soft fallback)
    active_uids = list(miner_uids)
    failed_uids = set()

    # Step 1: Send setup messages — skip failing miners instead of aborting
    for i, setup_msg in enumerate(scenario["setup"]):
        if not active_uids:
            bt.logging.warning("[Multi-turn] All miners failed during setup")
            break

        try:
            setup_responses = await self.dendrite(
                axons=[self.metagraph.axons[uid] for uid in active_uids],
                synapse=CompanionRequest(
                    message=setup_msg["content"],
                    user_id=test_user_id,
                ),
                deserialize=False,
                timeout=self.config.neuron.timeout,
            )

            # Check per-miner responses and mark failures
            still_active = []
            for uid, resp in zip(active_uids, setup_responses or []):
                if resp and resp.response:
                    still_active.append(uid)
                else:
                    failed_uids.add(uid)
                    bt.logging.debug(f"[Multi-turn] Miner {uid} failed setup {i+1}")

            responded = len(still_active)
            bt.logging.debug(f"[Multi-turn] Setup {i+1}: {responded}/{len(active_uids)} responded")
            active_uids = still_active

        except Exception as e:
            bt.logging.warning(f"[Multi-turn] Setup message {i+1} failed globally: {e}")
            # Don't abort — keep whatever miners we have
            break

        await asyncio.sleep(3)

    # If no active miners left, fall back to single-turn with original UIDs
    if not active_uids:
        bt.logging.warning("[Multi-turn] No miners survived setup, falling back to single-turn")
        await _forward_single_turn(self, miner_uids)
        return

    # Step 2: Send test query to surviving miners with per-miner latency
    # Classify the test query for specialization routing
    router = _get_router()
    query_type = classify_query(scenario["test_query"])

    bt.logging.info(f"[Multi-turn] Test query to {len(active_uids)} active miners "
                   f"({len(failed_uids)} failed), query_type={query_type}: "
                   f"'{scenario['test_query']}'")

    # Phase 2: Build per-miner synapses with HPKE wrapping if pubkey is cached
    synapses_multi = [
        _build_synapse_for_miner(
            scenario["test_query"], test_user_id, query_type, miner_uid=int(uid)
        )
        for uid in active_uids
    ]
    tasks = [
        _query_single_miner(
            self.dendrite,
            self.metagraph.axons[uid],
            synapse,
            self.config.neuron.timeout,
        )
        for uid, synapse in zip(active_uids, synapses_multi)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Build full response and latency arrays for ALL original miner_uids
    all_responses = []
    all_latencies = []
    active_idx = 0
    for uid in miner_uids:
        if uid in failed_uids:
            # Failed miners get empty response (score 0)
            all_responses.append("")
            all_latencies.append(self.config.neuron.timeout)
        else:
            r = results[active_idx]
            active_idx += 1
            if isinstance(r, Exception):
                all_responses.append("")
                all_latencies.append(self.config.neuron.timeout)
            else:
                all_responses.append(r[0])
                all_latencies.append(r[1])
                # Phase 2: Cache miner TEE pubkey if advertised
                if r[2]:
                    cache_miner_pubkey(int(uid), r[2])

    # Step 3: Score with memory keywords
    rewards = get_rewards(
        self,
        query=scenario["test_query"],
        responses=all_responses,
        test_type="multi_turn",
        memory_keywords=scenario["memory_keywords"],
        latencies=all_latencies,
    )

    bt.logging.info(f"[Multi-turn] Scored: {rewards} (keywords: {scenario['memory_keywords']}, "
                   f"failed_uids: {failed_uids}, query_type: {query_type})")

    # Update router with per-miner scores by query category
    for uid, score in zip(miner_uids, rewards):
        router.record_score(int(uid), query_type, float(score))

    # Persist router state every 10 steps
    if _step_counter % 10 == 0:
        _save_router_state(router)

    self.update_scores(rewards, miner_uids)

    # Phase 2: Sync test user's memories to all miners for consistency
    try:
        test_memories = [
            {"content": msg["content"], "type": "context", "importance": 0.7, "tags": ["test_sync"]}
            for msg in scenario["setup"]
        ]
        await sync_memories_to_miners(
            self.dendrite, self.metagraph, test_user_id, test_memories, timeout=8.0
        )
    except Exception as e:
        bt.logging.debug(f"[Multi-turn] Sync error (non-fatal): {e}")


async def test_memory(self, miner_uids):
    """
    Task 4: Test MemoryStore/MemoryRecall synapses.
    Periodically sends test data via MemoryStore, then verifies recall.
    Factors memory accuracy into miner scores.
    """
    test_user_id = f"memtest_{random.randint(100000, 999999)}"
    test_content = random.choice([
        "My favorite color is turquoise and I work as a data scientist",
        "I have a golden retriever named Max and I live in Portland",
        "I'm studying quantum computing at MIT and I love jazz music",
        "My birthday is March 15th and I'm allergic to peanuts",
        "I'm training for a marathon and my favorite book is Dune",
    ])
    test_keywords = [w for w in test_content.lower().split() if len(w) > 4][:5]

    bt.logging.info(f"[Memory test] Testing {len(miner_uids)} miners with MemoryStore/Recall")

    # Step 1: Send MemoryStore to all miners
    try:
        store_responses = await self.dendrite(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=MemoryStore(
                user_id=test_user_id,
                content=test_content,
                memory_type="fact",
                importance=0.8,
                tags=["test", "memory_check"],
            ),
            deserialize=False,
            timeout=self.config.neuron.timeout,
        )
        stored_count = sum(
            1 for r in (store_responses or [])
            if r and getattr(r, 'stored', False)
        )
        bt.logging.info(f"[Memory test] MemoryStore: {stored_count}/{len(miner_uids)} stored")
    except Exception as e:
        bt.logging.warning(f"[Memory test] MemoryStore failed: {e}")
        return

    # Brief pause to let miners persist
    await asyncio.sleep(2)

    # Step 2: Send MemoryRecall for the same user
    try:
        recall_responses = await self.dendrite(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=MemoryRecall(
                user_id=test_user_id,
                query=f"What do you know about user {test_user_id}?",
                limit=5,
            ),
            deserialize=False,
            timeout=self.config.neuron.timeout,
        )
    except Exception as e:
        bt.logging.warning(f"[Memory test] MemoryRecall failed: {e}")
        return

    # Step 3: Score memory recall accuracy
    memory_scores = []
    for i, resp in enumerate(recall_responses or []):
        if not resp or not getattr(resp, 'memories', None):
            memory_scores.append(0.0)
            continue

        # Check if recalled memories contain original content keywords
        recalled_text = " ".join(
            m.get("content", "") for m in resp.memories if isinstance(m, dict)
        ).lower()

        matches = sum(1 for kw in test_keywords if kw in recalled_text)
        score = matches / max(len(test_keywords), 1)
        memory_scores.append(score)

    memory_rewards = np.array(memory_scores, dtype=np.float32)
    bt.logging.info(f"[Memory test] Recall scores: {memory_rewards}")

    # Factor memory scores into overall scores (weight: 0.15)
    # This is additive to existing scores, scaled down
    weighted_memory = memory_rewards * 0.15
    self.update_scores(weighted_memory, miner_uids)
