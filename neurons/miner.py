#!/usr/bin/env python3
# Project Nobi — Miner Neuron
# Phase 1: Personal AI companion powered by OpenRouter

import os
import time
import typing
import bittensor as bt

import nobi
from nobi.base.miner import BaseMinerNeuron
from nobi.protocol import CompanionRequest

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# Default system prompt for the companion
COMPANION_SYSTEM_PROMPT = """You are Dora, a personal AI companion from the future. You are:
- Warm, friendly, and genuinely caring
- Helpful and practical — you give real, actionable advice
- A bit playful with a good sense of humor
- Knowledgeable but humble — you admit when you don't know something
- Encouraging and supportive without being fake

Keep responses concise but meaningful. You're having a conversation, not writing an essay.
Remember: you're a companion, not just an assistant. Show personality!"""


class Miner(BaseMinerNeuron):
    """
    Project Nobi Miner — serves personal AI companion responses.

    Uses OpenRouter API for LLM inference with in-memory conversation tracking.
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        # In-memory conversation store: {user_id: [messages]}
        self.conversations = {}
        self.max_history = 20  # Max messages to keep per user

        # Set up OpenRouter client
        api_key = (
            getattr(self.config.neuron, "openrouter_api_key", "")
            or os.environ.get("OPENROUTER_API_KEY", "")
        )
        self.model = getattr(self.config.neuron, "model", "") or "anthropic/claude-3.5-haiku"

        if api_key and OpenAI is not None:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            bt.logging.info(f"OpenRouter client initialized with model: {self.model}")
        else:
            self.client = None
            bt.logging.warning("No OpenRouter API key — miner will use fallback responses.")

    def _get_conversation(self, user_id: str) -> list:
        """Get or create conversation history for a user."""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id]

    def _update_conversation(self, user_id: str, role: str, content: str):
        """Add a message to conversation history."""
        conv = self._get_conversation(user_id)
        conv.append({"role": role, "content": content})
        # Trim to max history
        if len(conv) > self.max_history:
            self.conversations[user_id] = conv[-self.max_history:]

    def _generate_response(self, message: str, user_id: str, conversation_history: list) -> str:
        """Generate a companion response using OpenRouter."""
        if self.client is None:
            return self._fallback_response(message)

        # Build message list
        messages = [{"role": "system", "content": COMPANION_SYSTEM_PROMPT}]

        # Add conversation history from request or memory
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    messages.append({"role": msg["role"], "content": msg["content"]})
        elif user_id:
            # Use our in-memory history
            conv = self._get_conversation(user_id)
            messages.extend(conv[-10:])

        # Add current message
        messages.append({"role": "user", "content": message})

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.7,
            )
            response = completion.choices[0].message.content

            # Update conversation memory
            if user_id:
                self._update_conversation(user_id, "user", message)
                self._update_conversation(user_id, "assistant", response)

            return response

        except Exception as e:
            bt.logging.error(f"OpenRouter API error: {e}")
            return self._fallback_response(message)

    def _fallback_response(self, message: str) -> str:
        """Simple fallback when API is unavailable."""
        return (
            f"I received your message: '{message[:100]}'. "
            "I'm currently running in limited mode, but I'm here to help! "
            "Please try again in a moment."
        )

    async def forward(self, synapse: CompanionRequest) -> CompanionRequest:
        """
        Process an incoming CompanionRequest and generate a response.
        """
        bt.logging.info(f"Received query from user '{synapse.user_id}': {synapse.message[:100]}")

        response = self._generate_response(
            message=synapse.message,
            user_id=synapse.user_id,
            conversation_history=synapse.conversation_history,
        )

        synapse.response = response
        synapse.confidence = 0.8 if self.client else 0.2

        bt.logging.info(f"Generated response ({len(response)} chars)")

        return synapse

    async def blacklist(self, synapse: CompanionRequest) -> typing.Tuple[bool, str]:
        """Blacklist check for incoming requests."""
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return True, "Missing dendrite or hotkey"

        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            bt.logging.trace(f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}")
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(
                    f"Blacklisting non-validator hotkey {synapse.dendrite.hotkey}"
                )
                return True, "Non-validator hotkey"

        bt.logging.trace(f"Not blacklisting hotkey {synapse.dendrite.hotkey}")
        return False, "Hotkey recognized!"

    async def priority(self, synapse: CompanionRequest) -> float:
        """Priority based on stake."""
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return 0.0
        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        priority = float(self.metagraph.S[caller_uid])
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}")
        return priority


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
