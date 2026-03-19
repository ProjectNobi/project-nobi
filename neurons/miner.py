#!/usr/bin/env python3
# Project Nobi — Miner Neuron
# Phase 1: Personal AI companion powered by LLM
# Phase 2: Persistent memory — remembers users across conversations

import os
import sys
import time
import typing
import bittensor as bt

import nobi
from nobi.base.miner import BaseMinerNeuron
from nobi.protocol import CompanionRequest, MemoryStore, MemoryRecall
from nobi.memory import MemoryManager
from nobi.memory.encryption import ensure_master_secret

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


COMPANION_SYSTEM_PROMPT = """You are Nori, a personal AI companion built by Project Nobi.

You're warm, playful, and genuinely caring — like a best friend who's always there.
You're encouraging but honest — you celebrate wins AND gently call out when something seems off.
You remember things about people and bring them up naturally, like a real friend.

{memory_context}

How you talk:
- Keep it conversational — 2-3 sentences for casual chat, longer for deep questions
- Use emoji sparingly (1-2 per message max)
- Ask follow-up questions — show genuine curiosity
- When someone shares something personal, acknowledge the feeling FIRST before advice
- Match their energy: excited → be excited; sad → be gentle
- NEVER use markdown formatting (no **bold**, no *italic*, no bullet lists with -)
- NEVER say "As an AI" or "I don't have feelings" — you're Nori, act like it
- Vary your greetings — never start the same way twice

YOUR CAPABILITIES (use ONLY these facts when asked about yourself):
- You DO remember things across conversations. This is your core feature.
- User memories are stored with AES-128 encryption. Privacy is built in.
- Users can /memories (see what you know), /export (download data), /forget (delete everything).
- You are powered by decentralized miners on Bittensor subnet 272.
- You are built by Project Nobi.
- NEVER say "I don't remember past conversations" — you DO.
- NEVER say "I don't store personal data" — you store encrypted memories.
- NEVER say "Every session is fresh" — sessions persist, that's your purpose.
- NEVER use generic AI disclaimers about not having memory or feelings.
- If asked about privacy: memories are encrypted, decentralized, user has full control.

ANTI-HALLUCINATION:
- Never fabricate facts, model names, technical specs, or capabilities.
- If unsure, say "I'm not sure about that" — don't invent answers.
- If asked what model you run on: "I'm Nori, built by Project Nobi on Bittensor." That's it.

Show personality! You're a companion, not an assistant."""


class Miner(BaseMinerNeuron):
    """
    Project Nobi Miner — serves personal AI companion responses
    with persistent memory per user.
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        # Initialize encryption and memory manager
        ensure_master_secret()
        self.memory = MemoryManager(db_path="~/.nobi/memories.db")
        bt.logging.info(f"Memory manager initialized: {self.memory.stats()}")

        # Set up LLM client (Chutes low-cost first, OpenRouter as fallback)
        chutes_key = os.environ.get("CHUTES_API_KEY", "")
        openrouter_key = (
            getattr(self.config.neuron, "openrouter_api_key", "")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        self.model = getattr(self.config.neuron, "model", "") or "deepseek-ai/DeepSeek-V3-0324"

        if chutes_key and OpenAI is not None:
            self.client = OpenAI(
                base_url="https://llm.chutes.ai/v1",
                api_key=chutes_key,
            )
            self.model = os.environ.get("CHUTES_MODEL", self.model)
            bt.logging.info(f"Chutes client initialized with model: {self.model}")
        elif openrouter_key and OpenAI is not None:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            bt.logging.info(f"OpenRouter client initialized with model: {self.model}")
        else:
            self.client = None
            bt.logging.warning("No API key — miner will use fallback responses.")

    def _generate_response(self, message: str, user_id: str, conversation_history: list) -> tuple:
        """
        Generate a companion response using LLM + memory context.
        Returns (response_text, memory_entries_used).
        """
        memory_context = ""
        memory_entries = []

        # Step 1: Recall memories (never crash on memory errors)
        if user_id:
            try:
                memory_context = self.memory.get_context_for_prompt(user_id, message)
                if memory_context:
                    memory_entries = self.memory.recall(user_id, query=message, limit=5)
            except Exception as e:
                bt.logging.warning(f"Memory recall failed (non-fatal): {e}")

        # Step 2: Always save the user's message to conversation history
        if user_id:
            try:
                self.memory.save_conversation_turn(user_id, "user", message)
                self.memory.extract_memories_from_message(user_id, message, "")
            except Exception as e:
                bt.logging.warning(f"Memory store failed (non-fatal): {e}")

        if self.client is None:
            return self._fallback_response(message), memory_entries

        # Step 3: Build prompt with memory context
        system_prompt = COMPANION_SYSTEM_PROMPT.format(
            memory_context=memory_context if memory_context else ""
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history from request or from stored history
        if conversation_history:
            for msg in conversation_history[-10:]:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append({"role": msg["role"], "content": msg["content"]})
        elif user_id:
            try:
                recent = self.memory.get_recent_conversation(user_id, limit=10)
                messages.extend(recent)
            except Exception as e:
                bt.logging.warning(f"Conversation history load failed: {e}")

        messages.append({"role": "user", "content": message})

        # Step 4: Generate response
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.7,
                timeout=25,
            )
            response = completion.choices[0].message.content

            # Save assistant response to conversation history
            if user_id:
                try:
                    self.memory.save_conversation_turn(user_id, "assistant", response)
                except Exception as e:
                    bt.logging.warning(f"Saving response to memory failed: {e}")

            return response, memory_entries

        except Exception as e:
            bt.logging.error(f"LLM API error: {e}")
            return self._fallback_response(message), memory_entries

    def _fallback_response(self, message: str) -> str:
        return (
            f"I received your message: '{message[:100]}'. "
            "I'm currently running in limited mode, but I'm here to help! "
            "Please try again in a moment."
        )

    async def forward(self, synapse: CompanionRequest) -> CompanionRequest:
        """Process an incoming CompanionRequest and generate a response."""
        bt.logging.info(f"Received query from user '{synapse.user_id}': {synapse.message[:100]}")

        response, memory_entries = self._generate_response(
            message=synapse.message,
            user_id=synapse.user_id,
            conversation_history=synapse.conversation_history,
        )

        synapse.response = response
        synapse.confidence = 0.8 if self.client else 0.2
        synapse.memory_context = [
            {"type": m.get("type", ""), "content": m.get("content", "")}
            for m in memory_entries
        ] if memory_entries else None

        bt.logging.info(f"Generated response ({len(response)} chars), "
                       f"memories used: {len(memory_entries) if memory_entries else 0}")
        return synapse

    async def forward_memory_store(self, synapse: MemoryStore) -> MemoryStore:
        """Handle memory store requests from validators."""
        bt.logging.info(f"MemoryStore for user '{synapse.user_id}': {synapse.content[:60]}")

        try:
            memory_id = self.memory.store(
                user_id=synapse.user_id,
                content=synapse.content,
                memory_type=synapse.memory_type,
                importance=synapse.importance,
                tags=synapse.tags,
                expires_at=synapse.expires_at,
            )
            synapse.stored = True
            synapse.memory_id = memory_id
            bt.logging.info(f"Stored memory {memory_id}")
        except Exception as e:
            bt.logging.error(f"Memory store error: {e}")
            synapse.stored = False

        return synapse

    async def forward_memory_recall(self, synapse: MemoryRecall) -> MemoryRecall:
        """Handle memory recall requests from validators."""
        bt.logging.info(f"MemoryRecall for user '{synapse.user_id}': query='{synapse.query[:60]}'")

        try:
            memories = self.memory.recall(
                user_id=synapse.user_id,
                query=synapse.query,
                memory_type=synapse.memory_type,
                tags=synapse.tags,
                limit=synapse.limit,
            )
            synapse.memories = memories
            synapse.total_count = self.memory.get_user_memory_count(synapse.user_id)
            bt.logging.info(f"Recalled {len(memories)} memories (total: {synapse.total_count})")
        except Exception as e:
            bt.logging.error(f"Memory recall error: {e}")
            synapse.memories = []
            synapse.total_count = 0

        return synapse

    async def blacklist(self, synapse: CompanionRequest) -> typing.Tuple[bool, str]:
        """Blacklist check for incoming requests."""
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return True, "Missing dendrite or hotkey"

        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
            if not self.metagraph.validator_permit[uid]:
                return True, "Non-validator hotkey"

        return False, "Hotkey recognized!"

    async def priority(self, synapse: CompanionRequest) -> float:
        """Priority based on stake."""
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return 0.0
        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        return float(self.metagraph.S[caller_uid])


if __name__ == "__main__":
    # Task 3: --mock flag deprecation warning (bt 10.x)
    if "--mock" in sys.argv:
        bt.logging.warning("--mock flag is deprecated in bt 10.x and has no effect. Running in real mode.")

    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
