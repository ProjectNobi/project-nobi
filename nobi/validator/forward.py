# Project Nobi — Validator Forward Pass
# Phase 1: Send companion queries to miners, score responses
# Phase 2: Multi-turn conversations + memory testing

import time
import random
import bittensor as bt

from nobi.protocol import CompanionRequest, MemoryStore, MemoryRecall
from nobi.validator.reward import get_rewards
from nobi.utils.uids import get_random_uids


# Single-turn test queries (Phase 1)
TEST_QUERIES = [
    "Hello! How are you today?",
    "Can you help me plan my day?",
    "I'm feeling a bit stressed. Any advice?",
    "Tell me something interesting about space.",
    "What's a good recipe for a quick dinner?",
    "I need help understanding quantum computing in simple terms.",
    "Can you write me a short motivational message?",
    "What are some good habits to build?",
    "Help me brainstorm gift ideas for a friend's birthday.",
    "I want to learn a new skill. What do you recommend?",
    "Tell me a fun fact I probably don't know.",
    "How can I improve my sleep quality?",
    "What's the best way to stay focused while working?",
    "Can you explain why the sky is blue?",
    "I'm bored. Suggest something fun to do.",
]

# Multi-turn conversation scenarios (Phase 2)
# Each scenario tests memory: first message shares info, follow-up checks if miner remembers
MULTI_TURN_SCENARIOS = [
    {
        "setup": [
            {"role": "user", "content": "Hi! My name is Alex and I'm a software engineer."},
            {"role": "user", "content": "I love hiking and I have a dog named Luna."},
        ],
        "test_query": "What outdoor activities would you suggest for me and Luna?",
        "memory_keywords": ["alex", "luna", "hiking", "dog", "software"],
        "description": "Name + pet + hobby recall",
    },
    {
        "setup": [
            {"role": "user", "content": "I'm studying for my medical exams next month. It's really stressful."},
            {"role": "user", "content": "I prefer studying in the morning and I like coffee."},
        ],
        "test_query": "Any tips for my study session tomorrow?",
        "memory_keywords": ["medical", "exam", "morning", "coffee", "study"],
        "description": "Context + preference recall",
    },
    {
        "setup": [
            {"role": "user", "content": "I just moved to Tokyo from London last week!"},
            {"role": "user", "content": "I'm vegetarian and I don't speak much Japanese yet."},
        ],
        "test_query": "Can you recommend some places to eat near me?",
        "memory_keywords": ["tokyo", "london", "vegetarian", "japanese"],
        "description": "Location + dietary + language recall",
    },
    {
        "setup": [
            {"role": "user", "content": "My daughter Emma just turned 5 today!"},
            {"role": "user", "content": "She loves dinosaurs and painting."},
        ],
        "test_query": "What would be a fun birthday activity for her?",
        "memory_keywords": ["emma", "5", "dinosaur", "painting", "birthday"],
        "description": "Family + interests recall",
    },
    {
        "setup": [
            {"role": "user", "content": "I'm training for a marathon. My current best time is 4 hours."},
            {"role": "user", "content": "I usually run 3 times a week but I want to improve."},
        ],
        "test_query": "How should I adjust my training schedule this week?",
        "memory_keywords": ["marathon", "4 hours", "3 times", "training", "run"],
        "description": "Fitness goals recall",
    },
]


async def forward(self):
    """
    Validator forward pass:
    1. Select random miners to query
    2. Run either single-turn or multi-turn test
    3. Score responses using LLM-as-judge
    4. Update miner scores
    """
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)

    if len(miner_uids) == 0:
        bt.logging.warning("No miners available to query.")
        time.sleep(10)
        return

    # 60% chance of multi-turn test, 40% single-turn
    use_multi_turn = random.random() < 0.6 and len(MULTI_TURN_SCENARIOS) > 0

    if use_multi_turn:
        await _forward_multi_turn(self, miner_uids)
    else:
        await _forward_single_turn(self, miner_uids)

    time.sleep(10)


async def _forward_single_turn(self, miner_uids):
    """Original single-turn query."""
    query = random.choice(TEST_QUERIES)
    bt.logging.info(f"[Single-turn] Querying {len(miner_uids)} miners: '{query}'")

    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=CompanionRequest(message=query),
        deserialize=True,
        timeout=self.config.neuron.timeout,
    )

    processed = [
        r if isinstance(r, str) and r else ""
        for r in (responses if responses else [])
    ]

    rewards = get_rewards(self, query=query, responses=processed, test_type="single")
    bt.logging.info(f"Scored responses: {rewards}")
    self.update_scores(rewards, miner_uids)


async def _forward_multi_turn(self, miner_uids):
    """
    Multi-turn memory test:
    1. Send setup messages (share user info)
    2. Send test query (checks if miner remembers)
    3. Score based on response quality + memory recall
    """
    scenario = random.choice(MULTI_TURN_SCENARIOS)
    test_user_id = f"test_user_{random.randint(10000, 99999)}"

    bt.logging.info(f"[Multi-turn] Testing: {scenario['description']} "
                   f"with {len(miner_uids)} miners")

    # Step 1: Send setup messages to build memory
    setup_ok = True
    for i, setup_msg in enumerate(scenario["setup"]):
        try:
            setup_responses = await self.dendrite(
                axons=[self.metagraph.axons[uid] for uid in miner_uids],
                synapse=CompanionRequest(
                    message=setup_msg["content"],
                    user_id=test_user_id,
                ),
                deserialize=False,  # Get full synapse to check status
                timeout=self.config.neuron.timeout,
            )
            # Log setup results
            responded = sum(1 for r in setup_responses if r and r.response)
            bt.logging.debug(f"[Multi-turn] Setup {i+1}: {responded}/{len(miner_uids)} responded")
        except Exception as e:
            bt.logging.warning(f"[Multi-turn] Setup message {i+1} failed: {e}")
            setup_ok = False

        # Give miners time to process and store the memory
        await _async_sleep(3)

    if not setup_ok:
        bt.logging.warning("[Multi-turn] Setup failed, falling back to single-turn")
        await _forward_single_turn(self, miner_uids)
        return

    # Step 2: Send test query
    bt.logging.info(f"[Multi-turn] Test query: '{scenario['test_query']}'")

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

    processed = [
        r if isinstance(r, str) and r else ""
        for r in (test_responses if test_responses else [])
    ]

    # Step 3: Score with memory keywords bonus
    rewards = get_rewards(
        self,
        query=scenario["test_query"],
        responses=processed,
        test_type="multi_turn",
        memory_keywords=scenario["memory_keywords"],
    )

    bt.logging.info(f"[Multi-turn] Scored: {rewards} (keywords: {scenario['memory_keywords']})")
    self.update_scores(rewards, miner_uids)


async def _async_sleep(seconds):
    """Async-compatible sleep."""
    import asyncio
    await asyncio.sleep(seconds)
