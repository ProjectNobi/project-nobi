# Project Nobi — Validator Forward Pass
# Phase 1: Send companion queries to miners, score responses
# Phase 2: Multi-turn memory testing with dynamic query generation
#
# FAIRNESS DESIGN:
# - Queries are dynamically generated (not static) — can't pre-cache answers
# - All miners get same query in each round — fair comparison
# - Scores use LLM judge with heuristic fallback that caps at 0.5 (not 1.0)
# - Memory scoring checks natural integration, not just keyword presence
# - Single-turn queries include a fake user_id — miners can't detect test vs real

import time
import random
import asyncio
import bittensor as bt

from nobi.protocol import CompanionRequest
from nobi.validator.reward import get_rewards
from nobi.validator.query_generator import (
    generate_single_turn_query,
    generate_multi_turn_scenario,
)
from nobi.utils.uids import get_random_uids


async def forward(self):
    """
    Validator forward pass:
    1. Select random miners to query
    2. Run either single-turn or multi-turn test (dynamically generated)
    3. Score responses using LLM-as-judge
    4. Track response latency for reliability scoring
    5. Update miner scores
    """
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)

    if len(miner_uids) == 0:
        bt.logging.warning("No miners available to query.")
        time.sleep(10)
        return

    # 60% multi-turn, 40% single-turn
    use_multi_turn = random.random() < 0.6

    if use_multi_turn:
        await _forward_multi_turn(self, miner_uids)
    else:
        await _forward_single_turn(self, miner_uids)

    time.sleep(10)


async def _forward_single_turn(self, miner_uids):
    """Single-turn query with dynamically generated question."""
    query = generate_single_turn_query()
    # Include a fake user_id so miners can't distinguish test from real user
    fake_user_id = f"user_{random.randint(100000, 999999)}"

    bt.logging.info(f"[Single-turn] Querying {len(miner_uids)} miners: '{query[:80]}'")

    t_start = time.monotonic()

    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=CompanionRequest(message=query, user_id=fake_user_id),
        deserialize=True,
        timeout=self.config.neuron.timeout,
    )

    latency = time.monotonic() - t_start

    processed = [
        r if isinstance(r, str) and r else ""
        for r in (responses if responses else [])
    ]

    # Track latency per miner for reliability scoring
    latencies = [latency / max(len(miner_uids), 1)] * len(miner_uids)

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
    """
    scenario = generate_multi_turn_scenario()
    test_user_id = f"test_{random.randint(100000, 999999)}"

    bt.logging.info(f"[Multi-turn] Testing: {scenario['description']} "
                   f"with {len(miner_uids)} miners")

    # Step 1: Send setup messages
    setup_ok = True
    for i, setup_msg in enumerate(scenario["setup"]):
        try:
            setup_responses = await self.dendrite(
                axons=[self.metagraph.axons[uid] for uid in miner_uids],
                synapse=CompanionRequest(
                    message=setup_msg["content"],
                    user_id=test_user_id,
                ),
                deserialize=False,
                timeout=self.config.neuron.timeout,
            )
            responded = sum(1 for r in setup_responses if r and r.response)
            bt.logging.debug(f"[Multi-turn] Setup {i+1}: {responded}/{len(miner_uids)} responded")
        except Exception as e:
            bt.logging.warning(f"[Multi-turn] Setup message {i+1} failed: {e}")
            setup_ok = False

        await asyncio.sleep(3)

    if not setup_ok:
        bt.logging.warning("[Multi-turn] Setup failed, falling back to single-turn")
        await _forward_single_turn(self, miner_uids)
        return

    # Step 2: Send test query
    bt.logging.info(f"[Multi-turn] Test query: '{scenario['test_query']}'")

    t_start = time.monotonic()

    try:
        test_responses = await self.dendrite(
            axons=[self.metagraph.axons[uid] for uid in miner_uids],
            synapse=CompanionRequest(
                message=scenario["test_query"],
                user_id=test_user_id,
            ),
            deserialize=True,
            timeout=self.config.neuron.timeout,
        )
    except Exception as e:
        bt.logging.error(f"[Multi-turn] Test query failed: {e}")
        return

    latency = time.monotonic() - t_start

    processed = [
        r if isinstance(r, str) and r else ""
        for r in (test_responses if test_responses else [])
    ]

    latencies = [latency / max(len(miner_uids), 1)] * len(miner_uids)

    # Step 3: Score with memory keywords
    rewards = get_rewards(
        self,
        query=scenario["test_query"],
        responses=processed,
        test_type="multi_turn",
        memory_keywords=scenario["memory_keywords"],
        latencies=latencies,
    )

    bt.logging.info(f"[Multi-turn] Scored: {rewards} (keywords: {scenario['memory_keywords']})")
    self.update_scores(rewards, miner_uids)
