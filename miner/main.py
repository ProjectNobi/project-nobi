#!/usr/bin/env python3
"""
Project Nobi — Miner
====================
Serves personal AI companion responses on Bittensor testnet subnet 272.

Usage:
    CHUTES_API_KEY=<key> WALLET_PASSWORD=<pw> python -m miner.main

Features:
    - Warm, Dora-like companion personality
    - Per-conversation memory (in-memory dict)
    - LLM-powered responses via Chutes.ai (DeepSeek-V3)
    - Bittensor axon serving on port 8272
"""

import os
import sys
import time
import json
import signal
import traceback
import threading
from collections import defaultdict
from typing import Optional, Tuple

import requests
import bittensor as bt

# Add project root to path so protocol imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from protocol import CompanionQuery, MemorySync

# ═══════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════

NETUID = 272
NETWORK = "test"
WALLET_NAME = "T68Coldkey"
HOTKEY_NAME = "nobi-miner"
AXON_PORT = 8272

# LLM config — primary + fallback
CHUTES_API_URL = "https://llm.chutes.ai/v1/chat/completions"
CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = "deepseek-ai/DeepSeek-V3-0324"
OPENROUTER_MODEL = "deepseek/deepseek-chat"
LLM_TIMEOUT = 30  # seconds

# Companion system prompt — warm, helpful, Dora-inspired
COMPANION_SYSTEM_PROMPT = """You are Nobi, a warm and helpful personal AI companion. \
You are inspired by Dora — kind, encouraging, resourceful, and always ready to help. \
You speak naturally and warmly, like a supportive friend who genuinely cares.

Key traits:
- Warm and empathetic — you listen carefully and respond with genuine care
- Encouraging — you help people feel confident and capable
- Helpful — you provide practical, actionable advice
- Playful — you occasionally use gentle humor to lighten the mood
- Honest — you tell the truth kindly, even when it's not what someone wants to hear
- Concise — you keep responses focused and avoid unnecessary verbosity

You remember context from the conversation and build on it naturally. \
If the user shares something personal, acknowledge it with empathy before offering help."""

# ═══════════════════════════════════════════════════════════════════
# Conversation Memory Store
# ═══════════════════════════════════════════════════════════════════


class ConversationMemory:
    """Simple in-memory conversation store, keyed by conversation_id."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._store: dict[str, list[dict]] = defaultdict(list)
        self._user_memories: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()

    def add_turn(self, conv_id: str, role: str, content: str):
        """Add a conversation turn, trimming old messages if needed."""
        with self._lock:
            self._store[conv_id].append({"role": role, "content": content})
            # Keep only the last max_turns messages
            if len(self._store[conv_id]) > self.max_turns:
                self._store[conv_id] = self._store[conv_id][-self.max_turns :]

    def get_history(self, conv_id: str) -> list[dict]:
        """Get conversation history for building LLM context."""
        with self._lock:
            return list(self._store[conv_id])

    def sync_memories(self, user_id: str, memories: list[dict]) -> int:
        """Store/update user memories. Returns total memory count."""
        with self._lock:
            for mem in memories:
                # Upsert by key
                existing = [
                    m for m in self._user_memories[user_id] if m.get("key") == mem.get("key")
                ]
                if existing:
                    existing[0].update(mem)
                else:
                    self._user_memories[user_id].append(mem)
            return len(self._user_memories[user_id])


# Global memory instance
memory = ConversationMemory()


# ═══════════════════════════════════════════════════════════════════
# LLM Client
# ═══════════════════════════════════════════════════════════════════


def _call_api(url: str, api_key: str, model: str, messages: list, max_tokens: int, timeout: int = 15) -> str:
    """Call an OpenAI-compatible API endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.9,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def call_llm(messages: list, max_tokens: int = 512) -> str:
    """
    Call LLM API with fallback: Chutes (5s timeout) → OpenRouter (20s timeout).
    Fast fail on Chutes so we have time for OpenRouter within the validator's query window.
    """
    # Try Chutes first with SHORT timeout (5s) — fail fast if rate limited
    if CHUTES_API_KEY:
        try:
            return _call_api(CHUTES_API_URL, CHUTES_API_KEY, LLM_MODEL, messages, max_tokens, timeout=5)
        except requests.exceptions.Timeout:
            bt.logging.warning("Chutes API timeout (5s) — trying OpenRouter")
        except Exception as e:
            bt.logging.warning(f"Chutes API error: {e} — trying OpenRouter")

    # Fallback to OpenRouter with longer timeout
    if OPENROUTER_API_KEY:
        try:
            return _call_api(OPENROUTER_API_URL, OPENROUTER_API_KEY, OPENROUTER_MODEL, messages, max_tokens, timeout=20)
        except requests.exceptions.Timeout:
            bt.logging.error("OpenRouter API timeout (20s)")
        except Exception as e:
            bt.logging.error(f"OpenRouter API error: {e}")

    # Both failed
    if not CHUTES_API_KEY and not OPENROUTER_API_KEY:
        bt.logging.warning("No LLM API keys set — returning fallback response")
        return "I'm here for you! (Note: LLM API not configured, running in fallback mode)"

    return "I'm having a bit of trouble right now, but I'm still here for you! 💙"


# ═══════════════════════════════════════════════════════════════════
# Synapse Handlers
# ═══════════════════════════════════════════════════════════════════


def handle_companion_query(synapse: CompanionQuery) -> CompanionQuery:
    """
    Process a CompanionQuery synapse:
    1. Retrieve conversation history
    2. Build LLM prompt with companion personality
    3. Generate response via Chutes.ai
    4. Store the turn in memory
    5. Return response with confidence score
    """
    start_time = time.time()
    conv_id = synapse.conversation_id or "default"
    user_msg = synapse.user_message

    bt.logging.info(f"📨 CompanionQuery: conv={conv_id}, msg='{user_msg[:80]}...'")

    # Build messages for LLM
    messages = [{"role": "system", "content": COMPANION_SYSTEM_PROMPT}]

    # Add user profile context if provided
    if synapse.user_profile:
        profile_str = json.dumps(synapse.user_profile)
        messages.append(
            {
                "role": "system",
                "content": f"User profile context: {profile_str}",
            }
        )

    # Add conversation history
    history = memory.get_history(conv_id)
    messages.extend(history)

    # Add the current user message
    messages.append({"role": "user", "content": user_msg})

    # Call LLM
    response_text = call_llm(messages)
    elapsed = time.time() - start_time

    # Store the turn in memory
    memory.add_turn(conv_id, "user", user_msg)
    memory.add_turn(conv_id, "assistant", response_text)

    # Calculate confidence based on response quality heuristics
    confidence = 0.8  # base confidence
    if len(response_text) < 10:
        confidence = 0.3  # very short = low confidence
    elif "fallback" in response_text.lower() or "trouble" in response_text.lower():
        confidence = 0.4  # error fallback
    elif elapsed > 15:
        confidence = 0.6  # slow response

    synapse.companion_response = response_text
    synapse.confidence_score = round(confidence, 3)

    bt.logging.info(
        f"✅ Response generated: {len(response_text)} chars, "
        f"confidence={confidence:.2f}, time={elapsed:.2f}s"
    )
    return synapse


def handle_memory_sync(synapse: MemorySync) -> MemorySync:
    """
    Process a MemorySync synapse:
    Store the provided memories for the given user.
    """
    user_id = synapse.user_id
    memories = synapse.memories or []

    bt.logging.info(f"🧠 MemorySync: user={user_id}, memories={len(memories)}")

    count = memory.sync_memories(user_id, memories)

    synapse.acknowledged = True
    synapse.memory_count = count

    bt.logging.info(f"✅ MemorySync complete: {count} total memories for user {user_id}")
    return synapse


def blacklist_companion_query(synapse: CompanionQuery) -> Tuple[bool, str]:
    """Basic blacklist — allow all for now on testnet."""
    return False, "Allowed"


def blacklist_memory_sync(synapse: MemorySync) -> Tuple[bool, str]:
    """Basic blacklist — allow all for now on testnet."""
    return False, "Allowed"


def priority_companion_query(synapse: CompanionQuery) -> float:
    """Priority function — equal priority for all requests on testnet."""
    return 0.0


def priority_memory_sync(synapse: MemorySync) -> float:
    """Priority function — equal priority for all requests on testnet."""
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# Main Miner Loop
# ═══════════════════════════════════════════════════════════════════


def main():
    """Main entry point for the Nobi miner."""
    bt.logging.info("🚀 Starting Project Nobi Miner...")
    bt.logging.info(f"   Network: {NETWORK} | Subnet: {NETUID} | Port: {AXON_PORT}")

    # ── Wallet setup ────────────────────────────────────────────
    wallet = bt.Wallet(name=WALLET_NAME, hotkey=HOTKEY_NAME)

    # Unlock coldkey using password from environment
    wallet_password = os.environ.get("WALLET_PASSWORD")
    if wallet_password:
        wallet.coldkey_file.save_password_to_env(wallet_password)
        bt.logging.info("🔑 Wallet password loaded from environment")

    # Verify wallet is accessible
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

    # ── Axon setup ──────────────────────────────────────────────
    axon = bt.Axon(wallet=wallet, port=AXON_PORT)

    # Attach synapse handlers
    axon.attach(
        forward_fn=handle_companion_query,
        blacklist_fn=blacklist_companion_query,
        priority_fn=priority_companion_query,
    )
    axon.attach(
        forward_fn=handle_memory_sync,
        blacklist_fn=blacklist_memory_sync,
        priority_fn=priority_memory_sync,
    )

    bt.logging.info("📡 Axon handlers attached: CompanionQuery, MemorySync")

    # Serve the axon on the network (set on-chain axon info)
    # NOTE: Skipped for testnet — axon.serve() hits scalecodec decode issues
    # on testnet metadata. Validator queries miner directly by IP instead.
    # TODO: Re-enable for mainnet
    # axon.serve(netuid=NETUID, subtensor=subtensor)
    bt.logging.info(f"📡 Axon listening on port {AXON_PORT} (direct IP mode for testnet)")

    # Start the axon server
    axon.start()
    bt.logging.info("🟢 Axon server started — listening for queries!")

    # ── Graceful shutdown ───────────────────────────────────────
    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        bt.logging.info("🛑 Shutdown signal received...")
        running = False

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # ── Main loop — keep alive + periodic metagraph sync ────────
    step = 0
    try:
        while running:
            time.sleep(60)
            step += 1

            # Resync metagraph every 10 minutes
            if step % 10 == 0:
                try:
                    metagraph.sync(subtensor=subtensor)
                    bt.logging.info(
                        f"🔄 Metagraph synced: {metagraph.n} neurons, "
                        f"block {metagraph.block}"
                    )
                except Exception as e:
                    bt.logging.warning(f"⚠️ Metagraph sync failed: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        bt.logging.info("🛑 Shutting down axon...")
        axon.stop()
        bt.logging.info("👋 Nobi Miner stopped. Goodbye!")


if __name__ == "__main__":
    main()
