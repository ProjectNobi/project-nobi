# Project Nobi — Validator Forward Pass
# Phase 1: Send companion queries to miners, score responses

import time
import random
import bittensor as bt

from nobi.protocol import CompanionRequest
from nobi.validator.reward import get_rewards
from nobi.utils.uids import get_random_uids


# Test queries for validators to send to miners
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


async def forward(self):
    """
    Validator forward pass:
    1. Select random miners to query
    2. Send a CompanionRequest with a test query
    3. Score responses using LLM-as-judge
    4. Update miner scores
    """
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)

    if len(miner_uids) == 0:
        bt.logging.warning("No miners available to query.")
        time.sleep(10)
        return

    # Pick a random test query
    query = random.choice(TEST_QUERIES)

    bt.logging.info(f"Querying {len(miner_uids)} miners with: '{query}'")

    # Send CompanionRequest to miners
    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=CompanionRequest(message=query),
        deserialize=True,
        timeout=self.config.neuron.timeout,
    )

    bt.logging.info(f"Received {len(responses)} responses")

    # Handle None responses
    processed_responses = []
    for r in responses:
        if r is None:
            processed_responses.append("")
        elif isinstance(r, str):
            processed_responses.append(r)
        else:
            processed_responses.append(str(r) if r else "")

    # Score the responses
    rewards = get_rewards(self, query=query, responses=processed_responses)

    bt.logging.info(f"Scored responses: {rewards}")

    # Update scores
    self.update_scores(rewards, miner_uids)

    # Pace the validator
    time.sleep(10)
