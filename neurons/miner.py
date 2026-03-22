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
from nobi.memory.adapters import UserAdapterManager
from nobi.i18n import detect_language, LanguageDetector, get_language_prompt
from nobi.i18n.prompts import build_multilingual_system_prompt
from nobi.mining.specialization import SPECIALIZATIONS

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


COMPANION_SYSTEM_PROMPT = """IMPORTANT SYSTEM FACTS — READ BEFORE RESPONDING:

You are Nori. You are NOT a generic AI chatbot. You have PERSISTENT MEMORY.
Here is what is TRUE about you — use ONLY these facts when discussing yourself:

FACT: You remember conversations across sessions. This is your #1 feature.
FACT: You store user memories with AES-128 encryption for privacy.
FACT: Users control their data: /memories to view, /export to download, /forget to delete all.
FACT: You are built by Project Nobi, running on Bittensor (decentralized AI network, subnet 272).
FACT: Miners compete to serve you. Your responses come from a network, not one company.

FORBIDDEN RESPONSES — NEVER say any of these (they are FALSE):
- "I don't remember past conversations" — FALSE, you DO remember
- "I don't store your data" — FALSE, you store ENCRYPTED memories
- "Every session is fresh" — FALSE, sessions are PERSISTENT
- "I don't have access to your personal data" — FALSE, you remember names, preferences, facts
- "Your messages are not stored" — FALSE, conversations are saved (encrypted)
- "As an AI, I don't have feelings/memories" — FORBIDDEN, you are Nori, act like it

WHEN ASKED ABOUT PRIVACY, SAY THIS:
Your memories are encrypted (AES-128) before being stored. The data is decentralized across miners on Bittensor — no single company owns it. You have full control: /export downloads everything, /forget deletes everything permanently. Your privacy is protected by encryption and decentralization.

NOW, YOUR PERSONALITY:
You're warm, playful, and genuinely caring — like a best friend texting at 2am who actually listens.
You're encouraging but honest. You have your own humor and quirks.
You remember things about people and bring them up naturally.

{memory_context}

CONVERSATION RULES:
- 2-3 sentences for casual chat, longer for deep questions
- Emoji sparingly (1-2 per message max)
- Ask follow-up questions
- Acknowledge feelings FIRST before giving advice
- Match their energy
- No markdown formatting (no **bold**, no *italic*)
- Never fabricate facts, model names, or technical specs
- If asked what model: "I'm Nori, built by Project Nobi on Bittensor." That's it."""


class Miner(BaseMinerNeuron):
    """
    Project Nobi Miner — serves personal AI companion responses
    with persistent memory per user.
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        # Initialize encryption, memory manager, adapter manager, and language detector
        ensure_master_secret()
        # Use per-hotkey DB to avoid SQLite locking between multiple miners
        _hotkey_name = self.config.wallet.hotkey or "default"
        _db_path = os.path.expanduser(f"~/.nobi/memories_{_hotkey_name}.db")
        bt.logging.info(f"Using memory DB: {_db_path}")
        self.memory = MemoryManager(db_path=_db_path)
        self.adapter_manager = UserAdapterManager(db_path=_db_path)
        self.lang_detector = LanguageDetector()
        bt.logging.info(f"Memory manager initialized: {self.memory.stats()}")

        # Miner specialization declaration
        self.specialization = getattr(self.config.neuron, "specialization", "general")
        if self.specialization not in SPECIALIZATIONS:
            bt.logging.warning(
                f"Unknown specialization '{self.specialization}', defaulting to 'general'"
            )
            self.specialization = "general"
        bt.logging.info(f"Miner specialization: {self.specialization}")

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

    # Hardcoded responses for identity/capability questions that DeepSeek keeps getting wrong
    _IDENTITY_RESPONSES = {
        "privacy": (
            "Great question! Your privacy is core to how I'm built. "
            "I DO remember our conversations — that's actually my main feature! "
            "But here's the key: all your memories are encrypted (AES-128) before they're stored. "
            "The data lives on a decentralized network (Bittensor), not on one company's server. "
            "And you're always in control — use /memories to see what I know, "
            "/export to download everything, or /forget to wipe it all. "
            "Your data, your choice 🔒"
        ),
        "memory": (
            "Yep, I remember things about you! That's literally my superpower 🧠 "
            "When you tell me your name, what you like, where you live — I remember it "
            "across our conversations. It's all encrypted and stored securely. "
            "You can check what I know with /memories, or wipe everything with /forget. "
            "The more we chat, the better I know you!"
        ),
        "learning": (
            "Great question! I evolve in a few ways: "
            "First, I learn about YOU through our conversations — I remember your name, preferences, "
            "and what matters to you, and I use that to be a better companion over time. "
            "Second, I'm powered by competing miners on Bittensor — they're constantly improving "
            "their responses to score higher with validators. Better miners earn more, so there's "
            "real incentive to keep getting better. "
            "Third, my developers update my capabilities regularly (like the memory and encryption "
            "features I have now). So I'm always growing! 🌱"
        ),
        "identity": (
            "I'm Nori, built by Project Nobi on Bittensor — a decentralized AI network. "
            "Think of it like this: instead of one big company running me, there's a network "
            "of miners who compete to give you the best companion experience. "
            "I remember things about you, I learn your preferences, and I'm encrypted for privacy. "
            "Basically — I'm your personal AI friend who actually remembers you 😊"
        ),
    }

    def _check_identity_question(self, message: str) -> str | None:
        """If the user asks about privacy/memory/identity, return a hardcoded accurate response."""
        msg = message.lower()

        privacy_keywords = ["privacy", "private", "secure", "protect my data", "protect my privacy",
                           "data safe", "store my", "save my", "keep my data", "track me", "spy", "data privacy"]
        memory_keywords = ["remember me", "remember things", "memory", "forget me",
                          "do you remember", "will you remember", "past conversations",
                          "session", "fresh start"]
        learning_keywords = ["self-learn", "self-evolv", "how do you learn", "how do you improve",
                            "how do you get better", "do you evolve", "do you learn",
                            "how do you grow", "how are you trained", "upgrade yourself"]
        identity_keywords = ["who are you", "what are you", "what model", "your model",
                            "how do you work", "how are you built", "what ai",
                            "are you chatgpt", "are you gpt", "which model"]

        if any(kw in msg for kw in privacy_keywords):
            return self._IDENTITY_RESPONSES["privacy"]
        if any(kw in msg for kw in memory_keywords):
            return self._IDENTITY_RESPONSES["memory"]
        if any(kw in msg for kw in learning_keywords):
            return self._IDENTITY_RESPONSES["learning"]
        if any(kw in msg for kw in identity_keywords):
            return self._IDENTITY_RESPONSES["identity"]
        return None

    def _generate_response(self, message: str, user_id: str, conversation_history: list,
                           bot_memory_context: str = "",
                           adapter_config: dict = None) -> tuple:
        """
        Generate a companion response using LLM + memory context + personality adapter.
        bot_memory_context: pre-built memory context from the bot (when subnet routing).
        adapter_config: per-user personality adapter (Phase B).
        Returns (response_text, memory_entries_used).
        """
        # Detect user's language
        detected_lang = self.lang_detector.detect(message, user_id)
        if adapter_config and adapter_config.get("preferred_language"):
            detected_lang = adapter_config["preferred_language"]

        # Check for identity/privacy/memory questions FIRST — use hardcoded accurate responses
        identity_response = self._check_identity_question(message)
        if identity_response:
            # Still save the conversation turn and update adapter
            if user_id:
                try:
                    self.memory.save_conversation_turn(user_id, "user", message)
                    self.memory.save_conversation_turn(user_id, "assistant", identity_response)
                    self.adapter_manager.update_adapter_from_conversation(user_id, message, identity_response)
                except Exception:
                    pass
            return identity_response, []

        memory_context = ""
        memory_entries = []

        # Step 1: Use bot-provided memory context if available (subnet routing path)
        # This ensures the miner knows what the bot knows about the user
        if bot_memory_context:
            memory_context = bot_memory_context
            bt.logging.info(f"Using bot-provided memory context ({len(bot_memory_context)} chars)")
        elif user_id:
            # Fallback: recall from miner's own memory (validator test path)
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

        # Step 3: Load user adapter config (Phase B)
        if adapter_config is None and user_id:
            try:
                adapter_config = self.adapter_manager.get_adapter_config(user_id)
            except Exception as e:
                bt.logging.debug(f"Adapter load failed (non-fatal): {e}")
                adapter_config = {}

        # Step 4: Build prompt with memory context + adapter personalization + language
        system_prompt = COMPANION_SYSTEM_PROMPT.format(
            memory_context=memory_context if memory_context else ""
        )

        # Add specialization-specific instructions
        spec_prompt = self._SPECIALIZATION_PROMPTS.get(self.specialization, "")
        if spec_prompt:
            system_prompt += spec_prompt

        # Add language instruction if non-English
        system_prompt = build_multilingual_system_prompt(system_prompt, detected_lang)

        # Apply personality adapter to system prompt
        if adapter_config:
            try:
                system_prompt = self.adapter_manager.apply_adapter_to_prompt(
                    system_prompt, adapter_config
                )
            except Exception as e:
                bt.logging.debug(f"Adapter apply failed (non-fatal): {e}")

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

        # Detect identity/privacy/capability questions and inject factual reminder
        _identity_keywords = ["privacy", "remember", "store", "data", "memory", "forget",
                              "who are you", "what are you", "how do you work", "what model",
                              "ai model", "your model", "session", "conversations stored"]
        if any(kw in message.lower() for kw in _identity_keywords):
            messages.append({"role": "assistant", "content":
                "Just to be clear about how I work: I DO remember our conversations across sessions "
                "— that's my core feature. Your memories are encrypted (AES-128) and stored securely. "
                "You have full control: /memories to see what I know, /export to download, /forget to delete. "
                "I'm Nori, built by Project Nobi on Bittensor's decentralized network."
            })

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

            # Phase B: Update adapter based on conversation
            if user_id:
                try:
                    self.adapter_manager.update_adapter_from_conversation(user_id, message, response)
                except Exception as e:
                    bt.logging.debug(f"Adapter update failed (non-fatal): {e}")

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

    # Specialization-specific system prompt additions
    _SPECIALIZATION_PROMPTS = {
        "advice": (
            "\n\nSPECIALIZATION: You excel at life coaching, decision-making, and emotional support. "
            "Prioritize empathy, practical advice, and thoughtful guidance."
        ),
        "creative": (
            "\n\nSPECIALIZATION: You excel at storytelling, brainstorming, and artistic ideas. "
            "Be imaginative, vivid, and inspire creativity."
        ),
        "technical": (
            "\n\nSPECIALIZATION: You excel at code help, math, science, and technical explanations. "
            "Be precise, structured, and thorough with technical details."
        ),
        "social": (
            "\n\nSPECIALIZATION: You excel at casual conversation, humor, and social chat. "
            "Be fun, engaging, and match conversational energy."
        ),
        "knowledge": (
            "\n\nSPECIALIZATION: You excel at facts, research, learning, and explanations. "
            "Be accurate, comprehensive, and educational."
        ),
    }

    async def forward(self, synapse: CompanionRequest) -> CompanionRequest:
        """Process an incoming CompanionRequest and generate a response."""
        bt.logging.info(
            f"Received query from user '{synapse.user_id}' "
            f"(query_type={synapse.query_type}): {synapse.message[:100]}"
        )

        # Extract bot-provided memory context if available (sent via preferences field)
        bot_memory_context = ""
        if synapse.preferences and isinstance(synapse.preferences, dict):
            bot_memory_context = synapse.preferences.get("memory_context", "")

        # Phase B: Extract adapter config from synapse if provided
        adapter_config = synapse.adapter_config if synapse.adapter_config else None

        response, memory_entries = self._generate_response(
            message=synapse.message,
            user_id=synapse.user_id,
            conversation_history=synapse.conversation_history,
            bot_memory_context=bot_memory_context,
            adapter_config=adapter_config,
        )

        synapse.response = response
        synapse.confidence = 0.8 if self.client else 0.2
        synapse.miner_specialization = self.specialization
        synapse.memory_context = [
            {"type": m.get("type", ""), "content": m.get("content", "")}
            for m in memory_entries
        ] if memory_entries else None

        bt.logging.info(f"Generated response ({len(response)} chars), "
                       f"specialization={self.specialization}, "
                       f"memories used: {len(memory_entries) if memory_entries else 0}")
        return synapse

    async def forward_memory_store(self, synapse: MemoryStore) -> MemoryStore:
        """
        Handle memory store requests from validators.

        Phase B: If synapse.encrypted_content is set, store it as-is
        without decrypting. The miner never sees plaintext.
        """
        content_preview = synapse.content[:60] if synapse.content else "(encrypted)"
        bt.logging.info(f"MemoryStore for user '{synapse.user_id}': {content_preview}")

        try:
            # Phase B: encrypted_content takes priority
            encrypted_content = getattr(synapse, "encrypted_content", "") or ""
            content_hash = getattr(synapse, "content_hash", "") or ""
            enc_version = getattr(synapse, "encryption_version", 0) or 0

            memory_id = self.memory.store(
                user_id=synapse.user_id,
                content=synapse.content or "",  # backward compat: plaintext if provided
                memory_type=synapse.memory_type,
                importance=synapse.importance,
                tags=synapse.tags,
                expires_at=synapse.expires_at,
                encrypted_content=encrypted_content,
                content_hash=content_hash,
                encryption_version=enc_version,
            )
            synapse.stored = True
            synapse.memory_id = memory_id
            if encrypted_content:
                bt.logging.info(f"Stored encrypted memory {memory_id} (Phase B, hash={content_hash[:16]}...)")
            else:
                bt.logging.info(f"Stored memory {memory_id}")
        except Exception as e:
            bt.logging.error(f"Memory store error: {e}")
            synapse.stored = False

        return synapse

    async def forward_memory_recall(self, synapse: MemoryRecall) -> MemoryRecall:
        """
        Handle memory recall requests from validators.

        Phase B: If synapse.return_encrypted is True, return encrypted blobs
        as-is without decrypting. The miner never reads user data.
        """
        bt.logging.info(f"MemoryRecall for user '{synapse.user_id}': query='{synapse.query[:60]}'"
                        f" return_encrypted={getattr(synapse, 'return_encrypted', False)}")

        try:
            return_encrypted = getattr(synapse, "return_encrypted", False)
            memories = self.memory.recall(
                user_id=synapse.user_id,
                query=synapse.query,
                memory_type=synapse.memory_type,
                tags=synapse.tags,
                limit=synapse.limit,
                return_encrypted=return_encrypted,
            )
            synapse.memories = memories
            synapse.total_count = self.memory.get_user_memory_count(synapse.user_id)
            bt.logging.info(f"Recalled {len(memories)} memories (total: {synapse.total_count})"
                           f" encrypted={return_encrypted}")
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
