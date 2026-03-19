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

# Track forward step count for periodic memory testing
_step_counter = 0


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
    global _step_counter
    _step_counter += 1

    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)

    if len(miner_uids) == 0:
        bt.logging.warning("No miners available to query.")
        time.sleep(10)
        return

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
            deserialize=True,
            timeout=timeout,
        )
        latency = time.monotonic() - t_start
        response = responses[0] if responses else ""
        if not isinstance(response, str) or not response:
            response = ""
        return response, latency
    except Exception as e:
        latency = time.monotonic() - t_start
        bt.logging.debug(f"Miner query failed: {e}")
        return "", latency


async def _forward_single_turn(self, miner_uids):
    """Single-turn query with dynamically generated question and per-miner latency."""
    query = generate_single_turn_query()
    # Include a fake user_id so miners can't distinguish test from real user
    fake_user_id = f"user_{random.randint(100000, 999999)}"

    bt.logging.info(f"[Single-turn] Querying {len(miner_uids)} miners: '{query[:80]}'")

    # Task 1: Per-miner latency — query all miners in parallel, track individual timing
    synapse = CompanionRequest(message=query, user_id=fake_user_id)
    tasks = [
        _query_single_miner(
            self.dendrite,
            self.metagraph.axons[uid],
            synapse,
            self.config.neuron.timeout,
        )
        for uid in miner_uids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    latencies = []
    for r in results:
        if isinstance(r, Exception):
            processed.append("")
            latencies.append(self.config.neuron.timeout)
        else:
            processed.append(r[0])
            latencies.append(r[1])

    rewards = get_rewards(
        self, query=query, responses=processed,
        test_type="single", latencies=latencies,
    )
    bt.logging.info(f"Scored responses: {rewards}")
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
    bt.logging.info(f"[Multi-turn] Test query to {len(active_uids)} active miners "
                   f"({len(failed_uids)} failed): '{scenario['test_query']}'")

    synapse = CompanionRequest(
        message=scenario["test_query"],
        user_id=test_user_id,
    )
    tasks = [
        _query_single_miner(
            self.dendrite,
            self.metagraph.axons[uid],
            synapse,
            self.config.neuron.timeout,
        )
        for uid in active_uids
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
                   f"failed_uids: {failed_uids})")
    self.update_scores(rewards, miner_uids)


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
