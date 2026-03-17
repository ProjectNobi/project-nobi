#!/usr/bin/env python3
"""
Project Nobi — Validator
========================
Validates miner companion responses on Bittensor testnet subnet 272.

Usage:
    CHUTES_API_KEY=<key> WALLET_PASSWORD=<pw> python -m validator.main

Scoring:
    - Relevance  (0.4): Does the response address the user's message?
    - Coherence  (0.3): Is the response well-structured and logical?
    - Personality(0.2): Does it reflect the warm companion personality?
    - Speed      (0.1): How quickly did the miner respond?
"""

import os
import sys
import time
import json
import signal
import random
import traceback

import numpy as np
import requests
import bittensor as bt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from protocol import CompanionQuery

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

NETUID = 272
NETWORK = "test"
WALLET_NAME = "T68Coldkey"
HOTKEY_NAME = "nobi-validator"

# LLM config for judging
CHUTES_API_URL = "https://llm.chutes.ai/v1/chat/completions"
CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY", "")
JUDGE_MODEL = "deepseek-ai/DeepSeek-V3-0324"
JUDGE_TIMEOUT = 30

# Scoring weights
W_RELEVANCE = 0.4
W_COHERENCE = 0.3
W_PERSONALITY = 0.2
W_SPEED = 0.1

# Query timeout for miners
MINER_QUERY_TIMEOUT = 30  # seconds

# Epoch interval (seconds between validation rounds)
EPOCH_INTERVAL = 300  # 5 minutes

# ═══════════════════════════════════════════════════════════════════
# Test Prompts — diverse companion scenarios
# ═══════════════════════════════════════════════════════════════════

TEST_PROMPTS = [
    {
        "message": "I'm feeling really stressed about my job interview tomorrow. Any advice?",
        "context": "emotional_support",
    },
    {
        "message": "Can you help me plan a healthy meal for the week?",
        "context": "practical_help",
    },
    {
        "message": "I just got promoted at work! I'm so excited!",
        "context": "celebration",
    },
    {
        "message": "What's a good way to start learning Python programming?",
        "context": "education",
    },
    {
        "message": "I had a fight with my best friend and I don't know what to do.",
        "context": "relationship_advice",
    },
    {
        "message": "Tell me something interesting that might brighten my day.",
        "context": "entertainment",
    },
    {
        "message": "I've been procrastinating on my project. How do I get motivated?",
        "context": "productivity",
    },
    {
        "message": "I'm thinking about adopting a cat. What should I know?",
        "context": "general_advice",
    },
    {
        "message": "Can you explain quantum computing in simple terms?",
        "context": "education",
    },
    {
        "message": "I feel lonely tonight. Can we just chat?",
        "context": "companionship",
    },
]


# ═══════════════════════════════════════════════════════════════════
# LLM Judge
# ═══════════════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """You are a strict but fair judge evaluating AI companion responses.
You will be given:
1. The user's message
2. The companion's response

Score the response on three dimensions (each 0.0 to 1.0):
- **relevance**: Does the response directly address the user's message? (0=off-topic, 1=perfectly relevant)
- **coherence**: Is it well-structured, grammatically correct, logical? (0=incoherent, 1=perfectly clear)
- **personality**: Does it feel warm, caring, supportive, like a good friend? (0=cold/robotic, 1=warm and engaging)

Respond ONLY with valid JSON, no other text:
{"relevance": 0.0, "coherence": 0.0, "personality": 0.0}"""


def judge_response(user_message: str, companion_response: str) -> dict:
    """
    Use LLM to judge a companion response.
    Returns dict with relevance, coherence, personality scores (0-1 each).
    Falls back to heuristic scoring if LLM is unavailable.
    """
    if not CHUTES_API_KEY:
        bt.logging.warning("No CHUTES_API_KEY — using heuristic scoring")
        return heuristic_score(user_message, companion_response)

    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User message: {user_message}\n\n"
                f"Companion response: {companion_response}"
            ),
        },
    ]

    headers = {
        "Authorization": f"Bearer {CHUTES_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": JUDGE_MODEL,
        "messages": messages,
        "max_tokens": 100,
        "temperature": 0.1,  # Low temp for consistent scoring
    }

    try:
        resp = requests.post(
            CHUTES_API_URL,
            headers=headers,
            json=payload,
            timeout=JUDGE_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Parse JSON from response (handle potential markdown wrapping)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        scores = json.loads(content)

        # Clamp scores to [0, 1]
        return {
            "relevance": max(0.0, min(1.0, float(scores.get("relevance", 0.5)))),
            "coherence": max(0.0, min(1.0, float(scores.get("coherence", 0.5)))),
            "personality": max(0.0, min(1.0, float(scores.get("personality", 0.5)))),
        }
    except Exception as e:
        bt.logging.warning(f"LLM judge failed: {e} — falling back to heuristics")
        return heuristic_score(user_message, companion_response)


def heuristic_score(user_message: str, companion_response: str) -> dict:
    """
    Fallback heuristic scoring when LLM judge is unavailable.
    Simple but functional for testnet.
    """
    # Relevance: check for keyword overlap
    user_words = set(user_message.lower().split())
    resp_words = set(companion_response.lower().split())
    overlap = len(user_words & resp_words) / max(len(user_words), 1)
    relevance = min(1.0, overlap * 2 + 0.3)  # baseline + overlap bonus

    # Coherence: based on response length and structure
    resp_len = len(companion_response)
    if resp_len < 20:
        coherence = 0.2
    elif resp_len < 50:
        coherence = 0.5
    elif resp_len > 2000:
        coherence = 0.4  # too verbose
    else:
        coherence = 0.7

    # Personality: check for warmth markers
    warmth_markers = [
        "!", "😊", "💙", "🤗", "friend", "feel", "care", "help",
        "great", "wonderful", "happy", "understand", "support",
    ]
    warmth_count = sum(1 for m in warmth_markers if m.lower() in companion_response.lower())
    personality = min(1.0, 0.3 + warmth_count * 0.1)

    return {
        "relevance": round(relevance, 3),
        "coherence": round(coherence, 3),
        "personality": round(personality, 3),
    }


def calculate_speed_score(response_time: float) -> float:
    """
    Convert response time to a 0-1 score.
    <2s = 1.0, >20s = 0.0, linear interpolation between.
    """
    if response_time <= 2.0:
        return 1.0
    elif response_time >= 20.0:
        return 0.0
    else:
        return round(1.0 - (response_time - 2.0) / 18.0, 3)


def compute_weighted_score(scores: dict, speed_score: float) -> float:
    """Compute the final weighted score for a miner."""
    return (
        W_RELEVANCE * scores["relevance"]
        + W_COHERENCE * scores["coherence"]
        + W_PERSONALITY * scores["personality"]
        + W_SPEED * speed_score
    )


# ═══════════════════════════════════════════════════════════════════
# Validation Epoch
# ═══════════════════════════════════════════════════════════════════


def run_epoch(
    dendrite: bt.Dendrite,
    metagraph: bt.Metagraph,
    subtensor: bt.Subtensor,
    wallet: bt.Wallet,
    my_uid: int,
):
    """
    Run one validation epoch:
    1. Select a random test prompt
    2. Query all miners with it
    3. Score each response
    4. Set weights on-chain
    """
    # Pick a random test prompt
    prompt = random.choice(TEST_PROMPTS)
    user_message = prompt["message"]
    bt.logging.info(f"📝 Epoch prompt [{prompt['context']}]: '{user_message[:60]}...'")

    # Get active miner axons (exclude validators — they have non-zero stake typically)
    # On testnet we just query everyone except ourselves
    axon_infos = []
    miner_uids = []
    for uid in range(metagraph.n.item()):
        if uid == my_uid:
            continue
        axon_info = metagraph.axons[uid]
        # Skip neurons with no serving info
        if axon_info.ip == "0.0.0.0" or axon_info.port == 0:
            continue
        axon_infos.append(axon_info)
        miner_uids.append(uid)

    if not axon_infos:
        bt.logging.warning("⚠️ No active miners found. Skipping epoch.")
        return

    bt.logging.info(f"🎯 Querying {len(axon_infos)} miners: UIDs {miner_uids}")

    # Create synapse
    synapse = CompanionQuery(
        user_message=user_message,
        conversation_id=f"val-epoch-{int(time.time())}",
    )

    # Query all miners
    start_time = time.time()
    responses = dendrite.query(
        axons=axon_infos,
        synapse=synapse,
        timeout=MINER_QUERY_TIMEOUT,
    )
    total_time = time.time() - start_time

    # Ensure responses is a list
    if not isinstance(responses, list):
        responses = [responses]

    bt.logging.info(f"📬 Got {len(responses)} responses in {total_time:.2f}s")

    # ── Score each response ─────────────────────────────────────
    scores = {}
    for i, (uid, response) in enumerate(zip(miner_uids, responses)):
        companion_text = response.companion_response if response else None

        if not companion_text:
            bt.logging.warning(f"  UID {uid}: No response (timeout or error)")
            scores[uid] = 0.0
            continue

        # Get process time from dendrite timing info
        process_time = (
            response.dendrite.process_time
            if response.dendrite and response.dendrite.process_time
            else MINER_QUERY_TIMEOUT
        )

        # Judge the response quality
        quality_scores = judge_response(user_message, companion_text)
        speed = calculate_speed_score(process_time)
        final_score = compute_weighted_score(quality_scores, speed)

        scores[uid] = round(final_score, 4)

        bt.logging.info(
            f"  UID {uid}: score={final_score:.3f} "
            f"(rel={quality_scores['relevance']:.2f}, "
            f"coh={quality_scores['coherence']:.2f}, "
            f"per={quality_scores['personality']:.2f}, "
            f"spd={speed:.2f}, time={process_time:.2f}s)"
        )
        bt.logging.debug(f"  UID {uid} response: '{companion_text[:100]}...'")

    # ── Set weights on-chain ────────────────────────────────────
    if not scores:
        bt.logging.warning("⚠️ No scores to set. Skipping weight update.")
        return

    # Build weight arrays for ALL UIDs in the metagraph
    uids_list = list(scores.keys())
    weights_list = [scores[uid] for uid in uids_list]

    # Normalize weights to sum to 1
    total_weight = sum(weights_list)
    if total_weight > 0:
        weights_list = [w / total_weight for w in weights_list]
    else:
        # If all scores are 0, distribute equally
        weights_list = [1.0 / len(weights_list)] * len(weights_list)

    bt.logging.info(
        f"⚖️ Setting weights: {dict(zip(uids_list, [f'{w:.4f}' for w in weights_list]))}"
    )

    try:
        result = subtensor.set_weights(
            wallet=wallet,
            netuid=NETUID,
            uids=np.array(uids_list, dtype=np.int64),
            weights=np.array(weights_list, dtype=np.float32),
            wait_for_inclusion=True,
            wait_for_finalization=False,
        )
        bt.logging.info(f"✅ Weights set successfully: {result}")
    except Exception as e:
        bt.logging.error(f"❌ Failed to set weights: {e}")
        bt.logging.debug(traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════
# Main Validator Loop
# ═══════════════════════════════════════════════════════════════════


def main():
    """Main entry point for the Nobi validator."""
    bt.logging.info("🚀 Starting Project Nobi Validator...")
    bt.logging.info(f"   Network: {NETWORK} | Subnet: {NETUID}")
    bt.logging.info(
        f"   Weights: relevance={W_RELEVANCE}, coherence={W_COHERENCE}, "
        f"personality={W_PERSONALITY}, speed={W_SPEED}"
    )

    # ── Wallet setup ────────────────────────────────────────────
    wallet = bt.Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)

    # Unlock coldkey using password from environment
    wallet_password = os.environ.get("WALLET_PASSWORD")
    if wallet_password:
        wallet.coldkey_file.save_password_to_env(wallet_password)
        bt.logging.info("🔑 Wallet password loaded from environment")

    try:
        _ = wallet.hotkey
        bt.logging.info(f"🔑 Wallet loaded: {wallet.name}/{wallet.hotkey_str}")
    except Exception as e:
        bt.logging.error(f"❌ Failed to load wallet: {e}")
        sys.exit(1)

    # ── Subtensor connection ────────────────────────────────────
    subtensor = bt.Subtensor(network=NETWORK)
    bt.logging.info(f"🌐 Connected to subtensor: {NETWORK}")

    # ── Check registration ──────────────────────────────────────
    metagraph = bt.Metagraph(netuid=NETUID, network=NETWORK, subtensor=subtensor)
    my_uid = None
    for uid in range(len(metagraph.hotkeys)):
        if metagraph.hotkeys[uid] == wallet.hotkey.ss58_address:
            my_uid = uid
            break

    if my_uid is None:
        bt.logging.error("❌ Hotkey not registered on subnet 272. Register first!")
        sys.exit(1)
    bt.logging.info(f"✅ Registered as UID {my_uid}")

    # ── Dendrite for querying miners ────────────────────────────
    dendrite = bt.Dendrite(wallet=wallet)
    bt.logging.info("📡 Dendrite initialized")

    # ── Graceful shutdown ───────────────────────────────────────
    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        bt.logging.info("🛑 Shutdown signal received...")
        running = False

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # ── Main validation loop ────────────────────────────────────
    epoch = 0
    bt.logging.info(f"🟢 Validator running — epoch interval: {EPOCH_INTERVAL}s")

    try:
        while running:
            epoch += 1
            bt.logging.info(f"\n{'='*60}")
            bt.logging.info(f"🔄 Epoch {epoch} starting...")

            # Resync metagraph before each epoch
            try:
                metagraph.sync(subtensor=subtensor)
                bt.logging.info(
                    f"📊 Metagraph: {metagraph.n} neurons, block {metagraph.block}"
                )
            except Exception as e:
                bt.logging.warning(f"⚠️ Metagraph sync failed: {e}")

            # Run validation epoch
            try:
                run_epoch(dendrite, metagraph, subtensor, wallet, my_uid)
            except Exception as e:
                bt.logging.error(f"❌ Epoch {epoch} failed: {e}")
                bt.logging.debug(traceback.format_exc())

            bt.logging.info(f"⏰ Sleeping {EPOCH_INTERVAL}s until next epoch...")

            # Sleep in small increments to allow graceful shutdown
            for _ in range(EPOCH_INTERVAL):
                if not running:
                    break
                time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        bt.logging.info("👋 Nobi Validator stopped. Goodbye!")


if __name__ == "__main__":
    main()
