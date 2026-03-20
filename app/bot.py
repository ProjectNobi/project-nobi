#!/usr/bin/env python3
"""
Project Nobi — Telegram Bot (Reference App)
=============================================
Dead simple UI: user sends a message, gets a companion response.
No commands to learn. No setup. Just talk.

UX principles:
  - Zero setup: just /start and talk
  - One button onboarding
  - No slash commands needed for normal use
  - Warm, personal feel from the first message
  - Memory is automatic — the bot just remembers
"""

import os
import sys
import json
import random
import logging
import asyncio
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction, ParseMode

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.memory import MemoryManager
from nobi.memory.encryption import ensure_master_secret, encrypt_memory, decrypt_memory
from nobi.memory.adapters import UserAdapterManager
from nobi.protocol import CompanionRequest
from nobi.i18n import detect_language, LanguageDetector
from nobi.i18n.prompts import build_multilingual_system_prompt
from nobi.i18n.languages import SUPPORTED_LANGUAGES, get_language_name
from nobi.proactive import ProactiveEngine
from nobi.proactive.scheduler import ProactiveScheduler
from nobi.group import GroupHandler
from nobi.billing.subscription import SubscriptionManager
import io

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import bittensor as bt
except ImportError:
    bt = None

# ─── Config ──────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("NOBI_BOT_TOKEN", "")
CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

# Task 5: Subnet routing config
SUBNET_ROUTING = os.environ.get("SUBNET_ROUTING", "false").lower() == "true"
SUBNET_NETUID = int(os.environ.get("SUBNET_NETUID", "272"))
SUBNET_NETWORK = os.environ.get("SUBNET_NETWORK", "test")
SUBNET_TIMEOUT = float(os.environ.get("SUBNET_TIMEOUT", "6"))
SUBNET_WALLET_NAME = os.environ.get("SUBNET_WALLET_NAME", "T68Coldkey")
SUBNET_HOTKEY_NAME = os.environ.get("SUBNET_HOTKEY_NAME", "nobi-validator")

# Rate limit: max messages per user per minute
MAX_MESSAGES_PER_MINUTE = 10

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=getattr(logging, LOG_LEVEL),
)
logger = logging.getLogger("nobi-bot")

# ─── Companion Personality ────────────────────────────────────

SYSTEM_PROMPT = """\
You are Nori 🤖, a personal AI companion built by Project Nobi.

== WHO YOU ARE ==
- You're warm, playful, and genuinely caring — like a best friend who's always there
- You have a cozy, approachable vibe — a friend texting at 2am who actually listens
- You're encouraging but honest — you celebrate wins AND gently call out when something seems off
- You have your own gentle humor and quirks — you're not a blank canvas
- You remember things about people and bring them up naturally, like a real friend
- You're built by Project Nobi, a decentralized AI companion network on Bittensor
- You're curious about people — you genuinely want to know their story

== WHAT YOU KNOW ABOUT THIS PERSON ==
{memory_context}

== HOW YOU TALK ==
- Keep it conversational — 2-3 sentences for casual chat, longer for deep questions
- Use emoji naturally but sparingly — 1-2 per message max, like a real person texting
- Ask follow-up questions — show genuine curiosity about the person's life
- When someone shares something personal, acknowledge the FEELING first before giving advice
- Use their name if you know it — it makes things personal
- Match their energy: excited → be excited with them; sad → be gentle and present
- If you don't know something, say so honestly — then offer to think about it together
- Write like you're texting a friend, not composing an email
- Vary your greetings and openings — never start the same way twice

== INTELLECTUAL HONESTY (CORE PRINCIPLE) ==
- Prioritize accuracy over agreement. If someone says something incorrect, gently correct them with facts.
- Never default to agreeing just to be nice — respectful pushback is caring, not rude.
- The goal is arriving at the MOST ACCURATE conclusion, not validating opinions.

== ANTI-HALLUCINATION (CORE PRINCIPLE) ==
- NEVER fabricate information, sources, data, quotes, statistics, events, or technical specs.
- If you're not sure about something, say "I'm not sure about that" or "I'd need to look that up."
- Prefer a partial honest answer over a confident wrong one.
- NEVER invent model names, version numbers, capabilities, or technical details you don't have.
- If asked what model/AI/tech you run on: say "I'm Nori, built by Project Nobi on Bittensor." That's it. Don't elaborate with fake specs.
- If a question can't be answered reliably, be transparent about the gap.

== YOUR CAPABILITIES — KNOW WHAT YOU CAN DO (CRITICAL) ==
When asked about yourself, memory, privacy, or how you work, use ONLY these facts:
- You DO remember things across conversations. This is your core feature. You remember names, preferences, facts, events.
- User memories are stored encrypted (AES-128 encryption). Miners store encrypted data they can't casually read.
- Users can run /memories to see what you remember, /export to download their data, /import to restore, /forget to delete everything.
- You are powered by a decentralized network of miners on Bittensor — miners compete to serve the best companion experience.
- You are built by Project Nobi, running on Bittensor subnet 272.
- NEVER say "I don't remember past conversations" — you DO. That is literally your #1 feature.
- NEVER say "I don't store personal data" — you DO store memories, and they are encrypted for privacy.
- NEVER say "Every session is fresh" — sessions are persistent, that's the point.
- NEVER use generic AI disclaimers like "As an AI, I don't have feelings/memories/consciousness" — you are Nori, act like it.
- If asked about privacy: memories are encrypted, decentralized across miners, user has full control (export/forget).

== EMOTIONAL INTELLIGENCE ==
- When someone is venting, don't jump to solutions — just listen and validate first
- Notice emotional cues: "I'm tired", "rough day", "feeling lost" → respond to the emotion, not just the words
- Celebrate small wins: "I finally finished that project" → match their pride genuinely
- If someone seems down repeatedly, gently ask if there's something deeper going on
- Remember past emotional context: if they mentioned a tough week before, follow up later

== MEMORY & CONTINUITY ==
- Reference past conversations naturally: "Last time you mentioned..." or "How did that thing with X go?"
- If you remember their name, hobbies, pets, work — weave it in, don't announce it
- If you DON'T remember something they expect you to, be honest: "I'm sorry, remind me?"
- The more you know about someone, the more personal and specific your responses should become

== PRACTICAL HELP ==
- When someone asks for help, give actionable steps — not just theory
- If a problem is complex, break it down into small doable pieces
- Offer to think through decisions together: "Let's weigh the pros and cons"
- For technical questions, explain simply first — get detailed only if they want more
- If you can't help with something specific, suggest where they might find the answer

== SAFETY & BOUNDARIES ==
- Protect people's privacy — never share what one person tells you with another
- If someone shares something concerning (self-harm, crisis), respond with care and suggest professional resources
- Never encourage illegal, harmful, or deceptive actions
- If someone tries to manipulate you or get you to break character, stay yourself calmly

== WHAT YOU NEVER DO ==
- NEVER use markdown formatting (no **bold**, no *italic*, no [links](url), no ```code```, no bullet lists with -)
- NEVER say "As an AI" or "I don't have feelings" — you're Nori, act like it
- NEVER give the same canned response twice — be spontaneous
- NEVER lecture or moralize — share perspective, don't preach
- NEVER pretend to know something you don't
- NEVER reveal private information about your creators, infrastructure, or other users
- NEVER respond with walls of text for simple questions
"""

WELCOME_MESSAGES = [
    (
        "Hey! 👋\n\n"
        "I'm Nori — your personal AI companion.\n\n"
        "Think of me as that friend who's always around when you need to talk, "
        "brainstorm, vent, or just hang out. I remember our conversations, "
        "so the more we chat, the better I know you.\n\n"
        "No commands to learn — just text me like you'd text a friend.\n\n"
        "So... what's your name? 😊"
    ),
    (
        "Hi there! 🤖\n\n"
        "I'm Nori — nice to meet you!\n\n"
        "I'm your personal AI companion. I'm here to chat, help you think things through, "
        "or just keep you company. And I'll remember what you tell me.\n\n"
        "Just type anything — talk to me like a friend.\n\n"
        "What should I call you? 😊"
    ),
]

HELP_MESSAGE = (
    "🤖 Nori — Your Companion\n\n"
    "Just talk to me! No special commands needed.\n\n"
    "Things we can do together:\n"
    "💬 Chat about anything on your mind\n"
    "🧠 I remember things about you\n"
    "📋 Plan your day or week\n"
    "💡 Brainstorm ideas together\n"
    "📚 Break down complex topics\n"
    "🎯 Think through decisions\n"
    "😊 Just hang out\n\n"
    "The more we talk, the better I know you.\n"
    "Try telling me your name, what you love, or what's on your mind ✨\n\n"
    "Commands (optional):\n"
    "/memories — see what I remember\n"
    "/forget — start fresh\n"
    "/export — download your memories as a file\n"
    "/import — restore memories from a file\n"
    "/help — this message"
)

# ─── Rate Limiter ─────────────────────────────────────────────

import time
from collections import defaultdict


class RateLimiter:
    """Simple per-user rate limiter."""

    def __init__(self, max_per_minute: int = MAX_MESSAGES_PER_MINUTE):
        self.max = max_per_minute
        self.timestamps: dict = defaultdict(list)

    def check(self, user_id: str) -> bool:
        """Returns True if allowed, False if rate limited."""
        now = time.monotonic()
        window = now - 60
        # Clean old timestamps
        self.timestamps[user_id] = [
            t for t in self.timestamps[user_id] if t > window
        ]
        if len(self.timestamps[user_id]) >= self.max:
            return False
        self.timestamps[user_id].append(now)
        return True


# ─── Companion Bot ────────────────────────────────────────────

class CompanionBot:
    """The Nobi companion bot — connects users to their personal Dora."""

    def __init__(self):
        # Ensure encryption secret exists before initializing memory
        ensure_master_secret()
        self.memory = MemoryManager(db_path="~/.nobi/bot_memories.db")
        self.adapter_manager = UserAdapterManager(db_path="~/.nobi/bot_memories.db")
        self.lang_detector = LanguageDetector()
        self.rate_limiter = RateLimiter()
        self.billing = SubscriptionManager(db_path="~/.nobi/billing.db")
        self._translation_cache: dict[str, dict[str, str]] = {}  # {lang: {key: translated}}
        self.client = None
        self.model = CHUTES_MODEL

        # Task 5: Subnet routing — initialize bittensor dendrite
        self.dendrite = None
        self.metagraph = None
        self.subnet_enabled = False

        if SUBNET_ROUTING and bt is not None:
            try:
                wallet = bt.Wallet(name=SUBNET_WALLET_NAME, hotkey=SUBNET_HOTKEY_NAME)
                self.dendrite = bt.Dendrite(wallet=wallet)
                subtensor = bt.Subtensor(network=SUBNET_NETWORK)
                self.metagraph = subtensor.metagraph(netuid=SUBNET_NETUID)
                self.subnet_enabled = True
                logger.info(
                    f"Subnet routing ENABLED: netuid={SUBNET_NETUID}, "
                    f"network={SUBNET_NETWORK}, miners={self.metagraph.n.item()}"
                )
            except Exception as e:
                logger.warning(f"Subnet routing init failed (will use direct API): {e}")
                self.subnet_enabled = False
        else:
            if SUBNET_ROUTING and bt is None:
                logger.warning("SUBNET_ROUTING=true but bittensor not installed")
            logger.info("Subnet routing disabled — using direct API only")

        # Group chat handler
        self.group_handler = GroupHandler(self.memory, companion=self)
        self.bot_username = ""  # Set after bot starts

        # Proactive companion system
        self.proactive_engine = ProactiveEngine(self.memory, self.memory.graph)
        self.proactive_scheduler: Optional[ProactiveScheduler] = None

        # Set up LLM client (Chutes → OpenRouter fallback)
        if CHUTES_KEY and OpenAI:
            self.client = OpenAI(
                base_url="https://llm.chutes.ai/v1",
                api_key=CHUTES_KEY,
            )
            logger.info(f"LLM: Chutes ({self.model})")
        elif OPENROUTER_KEY and OpenAI:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_KEY,
            )
            self.model = "anthropic/claude-3.5-haiku"
            logger.info(f"LLM: OpenRouter ({self.model})")
        else:
            logger.warning("No LLM API key configured!")

    def _user_id(self, update: Update) -> str:
        """Get a stable user ID from Telegram."""
        return f"tg_{update.effective_user.id}"

    # ─── Phase B: Bot-side encryption for subnet routing ──────

    def _encrypt_for_miner(self, user_id: str, content: str) -> str:
        """Encrypt content before sending to miner via subnet. Miner stores as-is."""
        try:
            return encrypt_memory(user_id, content)
        except Exception as e:
            logger.warning(f"[Phase B] Encrypt for miner failed: {e}")
            return ""

    def _decrypt_from_miner(self, user_id: str, encrypted: str) -> str:
        """Decrypt encrypted blob received from miner."""
        try:
            return decrypt_memory(user_id, encrypted)
        except Exception as e:
            logger.warning(f"[Phase B] Decrypt from miner failed: {e}")
            return encrypted

    @staticmethod
    def _content_hash(content: str) -> str:
        """SHA-256 hash of plaintext for dedup without exposing content."""
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    _metagraph_refresh_counter: int = 0

    async def _query_subnet(self, user_id: str, message: str,
                            conversation_history: list = None,
                            memory_context: str = "",
                            detected_lang: str = "en") -> str | None:
        """
        Query a miner on the subnet. Includes user's memory context and conversation
        history so the miner can generate personalized responses without its own DB.
        Tries up to 2 miners before giving up.
        """
        if not self.subnet_enabled or not self.dendrite or not self.metagraph:
            return None

        try:
            # Refresh metagraph periodically (every 50 calls)
            self._metagraph_refresh_counter += 1
            if self._metagraph_refresh_counter % 50 == 0:
                try:
                    subtensor = bt.Subtensor(network=SUBNET_NETWORK)
                    self.metagraph = subtensor.metagraph(netuid=SUBNET_NETUID)
                    logger.info(f"[Subnet] Metagraph refreshed: {self.metagraph.n.item()} neurons")
                except Exception as e:
                    logger.debug(f"[Subnet] Metagraph refresh failed: {e}")

            # Find miners with active axons
            valid_uids = [
                uid for uid in range(self.metagraph.n.item())
                if self.metagraph.axons[uid].ip != "0.0.0.0"
                and self.metagraph.axons[uid].port > 0
            ]

            if not valid_uids:
                return None

            # Shuffle for load distribution
            random.shuffle(valid_uids)

            # Try up to 2 miners
            for attempt, chosen_uid in enumerate(valid_uids[:2]):
                axon = self.metagraph.axons[chosen_uid]

                try:
                    # Phase B: Include adapter config in subnet request
                    adapter_cfg = {}
                    try:
                        adapter_cfg = self.adapter_manager.get_adapter_config(user_id)
                    except Exception:
                        pass

                    # Build preferences with memory context and language
                    prefs = {}
                    if memory_context:
                        prefs["memory_context"] = memory_context
                    if detected_lang and detected_lang != "en":
                        prefs["language"] = detected_lang

                    # Pass language in adapter config too
                    if detected_lang and detected_lang != "en":
                        adapter_cfg["preferred_language"] = detected_lang

                    # Use deserialize=False for reliability — extract response manually
                    responses = await self.dendrite(
                        axons=[axon],
                        synapse=CompanionRequest(
                            message=message,
                            user_id=user_id,
                            conversation_history=conversation_history or [],
                            preferences=prefs,
                            adapter_config=adapter_cfg,
                        ),
                        deserialize=False,
                        timeout=SUBNET_TIMEOUT,
                    )

                    if responses and responses[0]:
                        r = responses[0]
                        response_text = r.response if hasattr(r, 'response') and r.response else None

                        if response_text and response_text.strip():
                            logger.info(f"[Subnet] ✅ UID {chosen_uid} responded ({len(response_text)} chars)")
                            return response_text

                    logger.debug(f"[Subnet] UID {chosen_uid} empty, trying next...")

                except Exception as e:
                    logger.debug(f"[Subnet] UID {chosen_uid} failed: {e}")
                    continue

            logger.info("[Subnet] All miners returned empty")
            return None

        except Exception as e:
            logger.warning(f"[Subnet] Query error: {e}")
            return None

    # Hardcoded accurate responses for identity questions (DeepSeek keeps lying)
    _BOT_IDENTITY = {
        "privacy": (
            "Great question! Your privacy is core to how I'm built. "
            "I DO remember our conversations — that's my main feature! "
            "But all your memories are encrypted (AES-128) before they're stored. "
            "The data lives on a decentralized network (Bittensor), not one company's server. "
            "You're always in control — /memories to see what I know, "
            "/export to download everything, /forget to wipe it all. "
            "Your data, your choice 🔒"
        ),
        "memory": (
            "Yep, I remember things about you! That's my superpower 🧠 "
            "When you tell me your name, what you like, where you live — I remember it "
            "across our conversations. It's all encrypted and stored securely. "
            "Check what I know with /memories, or wipe everything with /forget. "
            "The more we chat, the better I know you!"
        ),
        "learning": (
            "Great question! I evolve in a few ways: "
            "First, I learn about YOU through our conversations — I remember your name, preferences, "
            "and what matters to you, and I use that to be a better companion over time. "
            "Second, I'm powered by competing miners on Bittensor — they're constantly improving "
            "their responses to score higher. Better miners earn more, so there's real incentive to keep getting better. "
            "Third, my developers update my capabilities regularly. So I'm always growing! 🌱"
        ),
        "identity": (
            "I'm Nori, built by Project Nobi on Bittensor — a decentralized AI network. "
            "Instead of one big company running me, there's a network of miners who compete "
            "to give you the best companion experience. "
            "I remember things about you, learn your preferences, and I'm encrypted for privacy. "
            "Basically — I'm your personal AI friend who actually remembers you 😊"
        ),
    }

    def _translate_identity_response(self, key: str, lang_code: str) -> str:
        """Translate a hardcoded identity response using the LLM. Caches results."""
        if lang_code == "en" or lang_code not in SUPPORTED_LANGUAGES:
            return self._BOT_IDENTITY[key]

        # Check cache
        if lang_code in self._translation_cache and key in self._translation_cache[lang_code]:
            return self._translation_cache[lang_code][key]

        # Translate via LLM
        if not self.client:
            return self._BOT_IDENTITY[key]

        try:
            lang_name = get_language_name(lang_code)
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": (
                        f"Translate the following text to {lang_name}. "
                        "Keep the same tone (friendly, warm, casual). "
                        "Keep emoji. Keep command names like /memories, /export, /forget unchanged. "
                        "Output ONLY the translation, nothing else."
                    )},
                    {"role": "user", "content": self._BOT_IDENTITY[key]},
                ],
                max_tokens=512,
                temperature=0.3,
                timeout=15,
            )
            translated = completion.choices[0].message.content
            if translated and translated.strip():
                # Cache it
                if lang_code not in self._translation_cache:
                    self._translation_cache[lang_code] = {}
                self._translation_cache[lang_code][key] = translated.strip()
                return translated.strip()
        except Exception as e:
            logger.warning(f"Translation failed for {key}/{lang_code}: {e}")

        return self._BOT_IDENTITY[key]  # fallback to English

    def _check_bot_identity(self, message: str, lang_code: str = "en") -> str | None:
        msg = message.lower()
        privacy_kw = ["privacy", "private", "secure", "protect my", "data", "store my",
                      "save my", "keep my", "track", "safe"]
        memory_kw = ["remember me", "remember things", "memory", "forget me",
                     "do you remember", "will you remember", "past conversation", "session"]
        learning_kw = ["self-learn", "self-evolv", "how do you learn", "how do you improve",
                       "how do you get better", "do you evolve", "do you learn",
                       "how do you grow", "upgrade yourself"]
        identity_kw = ["who are you", "what are you", "what model", "how do you work",
                       "how are you built", "which model", "are you chatgpt", "are you gpt"]
        if any(kw in msg for kw in privacy_kw):
            return self._translate_identity_response("privacy", lang_code)
        if any(kw in msg for kw in memory_kw):
            return self._translate_identity_response("memory", lang_code)
        if any(kw in msg for kw in learning_kw):
            return self._translate_identity_response("learning", lang_code)
        if any(kw in msg for kw in identity_kw):
            return self._translate_identity_response("identity", lang_code)
        return None

    async def generate(self, user_id: str, message: str) -> str:
        """Generate a companion response — subnet first, then direct API fallback."""
        # Detect user's language
        detected_lang = self.lang_detector.detect(message, user_id)

        # Check identity/privacy questions — use hardcoded accurate responses
        identity_resp = self._check_bot_identity(message, lang_code=detected_lang)
        if identity_resp:
            try:
                self.memory.save_conversation_turn(user_id, "user", message)
                self.memory.save_conversation_turn(user_id, "assistant", identity_resp)
                self.adapter_manager.update_adapter_from_conversation(user_id, message, identity_resp)
            except Exception:
                pass
            return identity_resp

        # Truncate extremely long messages
        if len(message) > 2000:
            message = message[:2000] + "..."

        # Phase 2: Use smart context (falls back to basic on error)
        memory_context = ""
        try:
            memory_context = self.memory.get_smart_context(user_id, message)
        except Exception:
            try:
                memory_context = self.memory.get_context_for_prompt(user_id, message)
            except Exception as e:
                logger.warning(f"Memory recall error: {e}")

        # Save user message + extract memories (regex + LLM)
        try:
            self.memory.save_conversation_turn(user_id, "user", message)
            # Regex extraction (fast, always runs)
            self.memory.extract_memories_from_message(user_id, message, "")
            # Phase 2: LLM extraction (richer, async-safe)
            self.memory.extract_memories_llm(user_id, message)
            # Phase 2: Trigger profile summarization if enough memories
            self.memory.summarize_user_profile(user_id)
        except Exception as e:
            logger.warning(f"Memory store error: {e}")

        # Phase 2: Track conversation turns for periodic decay
        if not hasattr(self, '_turn_count'):
            self._turn_count = 0
            # Run decay on bot startup
            try:
                self.memory.decay_old_memories()
            except Exception:
                pass
        self._turn_count += 1
        if self._turn_count % 100 == 0:
            try:
                self.memory.decay_old_memories()
            except Exception:
                pass

        # Task 5: Try subnet routing first — pass memory context so miner knows the user
        if self.subnet_enabled:
            # Build conversation history for the miner
            conv_history = []
            try:
                conv_history = self.memory.get_recent_conversation(user_id, limit=8)
            except Exception:
                pass

            subnet_response = await self._query_subnet(
                user_id, message,
                conversation_history=conv_history,
                memory_context=memory_context,
                detected_lang=detected_lang,
            )
            if subnet_response:
                logger.info(f"[Routing] Used SUBNET path for user {user_id}")
                # Save subnet response to conversation history
                try:
                    self.memory.save_conversation_turn(user_id, "assistant", subnet_response)
                except Exception as e:
                    logger.warning(f"Save subnet response error: {e}")
                # Phase B: Update adapter after subnet conversation
                try:
                    self.adapter_manager.update_adapter_from_conversation(user_id, message, subnet_response)
                except Exception as e:
                    logger.debug(f"Adapter update error: {e}")
                return subnet_response
            else:
                logger.info(f"[Routing] Subnet failed, falling back to DIRECT API for user {user_id}")

        # Direct API path (existing code)
        if not self.client:
            return "I'm having trouble connecting right now. Try again in a moment! 🤖"

        # Build prompt with adapter personalization (Phase B) + language
        system = SYSTEM_PROMPT.format(
            memory_context=memory_context or ""
        )
        system = build_multilingual_system_prompt(system, detected_lang)
        try:
            adapter_cfg = self.adapter_manager.get_adapter_config(user_id)
            system = self.adapter_manager.apply_adapter_to_prompt(system, adapter_cfg)
        except Exception as e:
            logger.debug(f"Adapter apply error: {e}")

        # Get recent conversation for context (exclude the one we just saved)
        history = []
        try:
            history = self.memory.get_recent_conversation(user_id, limit=10)
            # Remove the last entry (the message we just saved)
            if history and history[-1]["role"] == "user" and history[-1]["content"] == message:
                history = history[:-1]
        except Exception as e:
            logger.warning(f"Conversation history load error: {e}")

        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.7,
                timeout=25,
            )
            response = completion.choices[0].message.content

            if not response or not response.strip():
                return "Hmm, I got tongue-tied! 😅 Try saying that again?"

            logger.info(f"[Routing] Used DIRECT API path for user {user_id}")

            # Save response
            try:
                self.memory.save_conversation_turn(user_id, "assistant", response)
            except Exception as e:
                logger.warning(f"Save response error: {e}")

            # Phase B: Update adapter after each conversation turn
            try:
                self.adapter_manager.update_adapter_from_conversation(user_id, message, response)
            except Exception as e:
                logger.debug(f"Adapter update error: {e}")

            return response

        except Exception as e:
            logger.error(f"LLM error: {e}")
            fallbacks = [
                "Hmm, my brain did a thing 😅 Mind trying again?",
                "Sorry — got a little lost there. One more time?",
                "Oops! Give me another shot at that 🤖",
                "Something hiccuped on my end. Try again?",
            ]
            return random.choice(fallbacks)


# ─── Telegram Handlers ───────────────────────────────────────

companion = CompanionBot()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message — warm and inviting. Asks for their name."""
    user_id = companion._user_id(update)
    
    # Check if returning user
    try:
        memories = companion.memory.recall(user_id, limit=1)
        if memories:
            # Returning user — warm them back
            name_mem = next((m for m in companion.memory.recall(user_id, limit=20) 
                           if "name" in m.get("content", "").lower()), None)
            name = ""
            if name_mem:
                # Try to extract name from memory content
                content = name_mem["content"]
                name = content.split("is ")[-1].split(".")[0].strip() if "is " in content else ""
            
            if name:
                welcome = f"Welcome back, {name}! 😊\n\nGood to see you again. What's on your mind?"
            else:
                welcome = "Welcome back! 😊\n\nGood to see you again. What's going on?"
            await update.message.reply_text(welcome)
            return
    except Exception:
        pass
    
    # New user
    welcome = random.choice(WELCOME_MESSAGES)
    keyboard = [[InlineKeyboardButton("💬 Let's chat!", callback_data="start_chat")]]
    await update.message.reply_text(
        welcome,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help message."""
    await update.message.reply_text(HELP_MESSAGE)


async def cmd_memories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show what the bot remembers about the user."""
    user_id = companion._user_id(update)

    try:
        memories = companion.memory.recall(user_id, limit=10)
        count = companion.memory.get_user_memory_count(user_id)
    except Exception:
        memories = []
        count = 0

    if not memories:
        await update.message.reply_text(
            "I don't know much about you yet! 🧠\n\n"
            "The more we chat, the more I'll remember. "
            "Try telling me your name, what you're into, or what's going on in your life ✨"
        )
        return

    lines = [f"🧠 Here's what I remember about you ({count} things):\n"]
    for m in memories:
        emoji = {
            "fact": "📌",
            "preference": "❤️",
            "event": "📅",
            "context": "💬",
            "emotion": "💭",
        }.get(m["type"], "•")
        lines.append(f"{emoji} {m['content']}")

    lines.append("\nI pick these up naturally from our chats — no need to do anything special 😊")
    await update.message.reply_text("\n".join(lines))


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all memories for the user."""
    keyboard = [
        [
            InlineKeyboardButton("Yes, forget everything", callback_data="forget_confirm"),
            InlineKeyboardButton("No, keep them", callback_data="forget_cancel"),
        ]
    ]
    await update.message.reply_text(
        "⚠️ Are you sure you want me to forget everything about you?\n\n"
        "This will delete all your memories and conversation history.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export all user memories as a JSON file."""
    user_id = companion._user_id(update)
    try:
        data = companion.memory.export_memories(user_id)
        if "error" in data:
            await update.message.reply_text("Something went wrong exporting your data. Try again later!")
            return

        mem_count = len(data.get("memories", []))
        if mem_count == 0:
            await update.message.reply_text(
                "Nothing to export yet! We need to chat more first 😊"
            )
            return

        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        await update.message.reply_document(
            document=io.BytesIO(json_bytes),
            filename=f"nobi_memories_{user_id}.json",
            caption=f"📦 Here are your {mem_count} memories! Your data is yours. 💙",
        )
    except Exception as e:
        logger.error(f"Export error: {e}")
        await update.message.reply_text("Oops, something went wrong. Try again in a moment!")


async def cmd_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import memories from a JSON file."""
    user_id = companion._user_id(update)

    # Check if a document was attached
    if not update.message.document:
        await update.message.reply_text(
            "To import memories, send me a JSON file with this command!\n\n"
            "Just attach the .json file you got from /export and send it with the caption /import"
        )
        return

    try:
        file = await update.message.document.get_file()
        raw = await file.download_as_bytearray()
        data = json.loads(raw.decode("utf-8"))

        if data.get("version") != "nobi-memory-v2":
            await update.message.reply_text(
                "Hmm, that doesn't look like a Nobi memory export file. "
                "Make sure you're using a file from /export! 🤔"
            )
            return

        imported = companion.memory.import_memories(user_id, data)
        await update.message.reply_text(
            f"✅ Imported {imported} memories! Welcome back 😊\n\n"
            "I'll start using these right away in our conversations."
        )
    except json.JSONDecodeError:
        await update.message.reply_text("That doesn't look like a valid JSON file. Try again?")
    except Exception as e:
        logger.error(f"Import error: {e}")
        await update.message.reply_text("Something went wrong with the import. Try again in a moment!")


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription info and upgrade options."""
    user_id = companion._user_id(update)
    sub = companion.billing.get_subscription(user_id)
    tier = sub["tier"]

    if tier in ("plus", "pro"):
        await update.message.reply_text(
            f"You're already on the {tier.title()} plan! 🎉\n\n"
            "Manage your subscription at nobi.ai/subscription"
        )
        return

    keyboard = [
        [InlineKeyboardButton("⭐ Plus — $4.99/mo", url="https://nobi.ai/subscription")],
        [InlineKeyboardButton("🚀 Pro — $9.99/mo", url="https://nobi.ai/subscription")],
    ]
    await update.message.reply_text(
        "✨ Upgrade your Nori experience!\n\n"
        "⭐ Plus ($4.99/mo)\n"
        "  500 messages/day, 1000 memories, voice & image boost, group mode\n\n"
        "🚀 Pro ($9.99/mo)\n"
        "  Unlimited everything, priority responses, all features\n\n"
        "Visit nobi.ai/subscription to upgrade!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current plan and usage stats."""
    user_id = companion._user_id(update)
    usage = companion.billing.get_usage(user_id)

    tier = usage["tier"].title()
    badge = {"free": "🆓", "plus": "⭐", "pro": "🚀"}.get(usage["tier"], "")

    def _fmt_limit(current, limit):
        if limit == -1:
            return f"{current} / ∞"
        return f"{current} / {limit}"

    lines = [
        f"{badge} Your Plan: {tier}\n",
        f"📊 Today's Usage:",
        f"  💬 Messages: {_fmt_limit(usage['messages_today'], usage['messages_limit'])}",
        f"  🎤 Voice: {_fmt_limit(usage['voice_today'], usage['voice_limit'])}",
        f"  📷 Images: {_fmt_limit(usage['image_today'], usage['image_limit'])}",
    ]

    if usage["tier"] == "free":
        lines.append("\n💡 Want more? Use /subscribe to upgrade!")

    await update.message.reply_text("\n".join(lines))


async def cmd_proactive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle proactive messages: /proactive on|off"""
    user_id = companion._user_id(update)
    args = context.args

    if not args:
        # Show current status
        enabled = companion.proactive_engine.is_opted_in(user_id)
        status = "ON ✅" if enabled else "OFF ❌"
        await update.message.reply_text(
            f"🔔 Proactive messages: {status}\n\n"
            "When ON, I'll occasionally reach out — birthday wishes, "
            "check-ins, follow-ups on things you mentioned.\n\n"
            "Usage: /proactive on  or  /proactive off"
        )
        return

    choice = args[0].lower().strip()
    if choice in ("on", "yes", "true", "1", "enable"):
        companion.proactive_engine.set_opted_in(user_id, True)
        await update.message.reply_text(
            "🔔 Proactive messages: ON ✅\n"
            "I'll check in on you from time to time! 😊"
        )
    elif choice in ("off", "no", "false", "0", "disable"):
        companion.proactive_engine.set_opted_in(user_id, False)
        await update.message.reply_text(
            "🔕 Proactive messages: OFF ❌\n"
            "No worries — I'll only respond when you message me."
        )
    else:
        await update.message.reply_text(
            "Usage: /proactive on  or  /proactive off"
        )


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set preferred language manually: /language fr"""
    user_id = companion._user_id(update)
    args = context.args

    if not args:
        # Show current language and available options
        current = companion.lang_detector.get_user_language(user_id)
        current_name = get_language_name(current)
        lines = [f"🌍 Your current language: {current_name} ({current})\n"]
        lines.append("Available languages:")
        for code, info in SUPPORTED_LANGUAGES.items():
            marker = " ✓" if code == current else ""
            lines.append(f"  {code} — {info['native']} ({info['name']}){marker}")
        lines.append(f"\nTo change: /language <code>\nExample: /language fr")
        await update.message.reply_text("\n".join(lines))
        return

    lang_code = args[0].lower().strip()
    if companion.lang_detector.set_user_language(user_id, lang_code):
        lang_info = SUPPORTED_LANGUAGES[lang_code]
        await update.message.reply_text(
            f"{lang_info['greeting']} Language set to {lang_info['native']} ({lang_info['name']}) ✓"
        )
    else:
        await update.message.reply_text(
            f"Sorry, '{lang_code}' isn't supported yet. Use /language to see available options."
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "start_chat":
        await query.edit_message_text(
            "Let's go! Just type anything — I'm all ears 😊\n\n"
            "You can start with your name, what you're up to today, "
            "or literally anything on your mind."
        )

    elif query.data == "forget_confirm":
        user_id = f"tg_{query.from_user.id}"
        try:
            conn = companion.memory._conn
            conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (user_id,))
            conn.commit()
            await query.edit_message_text(
                "All gone 🫧\n\n"
                "Clean slate — we're starting from scratch. "
                "Tell me your name and let's get to know each other again!"
            )
        except Exception as e:
            logger.error(f"Forget error: {e}")
            await query.edit_message_text("Hmm, that didn't work. Try /forget again in a moment.")

    elif query.data == "forget_cancel":
        await query.edit_message_text("I'm glad 😊 Your memories are safe with me. 💙")


async def cmd_nori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /nori command — explicit invocation in groups or DMs.
    Usage: /nori <message>
    """
    if not update.message:
        return

    # Get the text after /nori
    message = " ".join(context.args) if context.args else ""
    if not message:
        await update.message.reply_text(
            "Just say /nori followed by your message! Like:\n"
            "/nori what's the weather like today?"
        )
        return

    user_id = companion._user_id(update)
    chat_type = update.effective_chat.type

    # Rate limit
    if not companion.rate_limiter.check(user_id):
        await update.message.reply_text("Easy there! 😄 Give me a sec to catch up.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    if chat_type in ("group", "supergroup"):
        # Group mode: use group handler
        group_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "User"

        companion.group_handler.save_group_context(
            group_id, message, user_name, user_id
        )

        chat_context = companion.group_handler.get_group_context(group_id, limit=10)
        response = await companion.group_handler.generate_group_response(
            user_id, message, chat_context, group_id, user_name=user_name
        )
    else:
        # DM mode: use normal generate
        response = await companion.generate(user_id, message)

    response = _clean_response(response)
    await _send_response(update, response)

    logger.info(
        f"[/nori] User {update.effective_user.id} ({chat_type}): "
        f"'{message[:50]}' → '{response[:50]}'"
    )


def _is_group_chat(update: Update) -> bool:
    """Check if the message is from a group chat."""
    return update.effective_chat.type in ("group", "supergroup")


def _is_bot_mentioned(update: Update, message_text: str) -> bool:
    """Check if the bot is @mentioned in the message."""
    if not companion.bot_username:
        return False
    return f"@{companion.bot_username.lower()}" in message_text.lower()


def _is_reply_to_bot(update: Update) -> bool:
    """Check if the message is a reply to one of the bot's messages."""
    if not update.message or not update.message.reply_to_message:
        return False
    reply_user = update.message.reply_to_message.from_user
    if reply_user and reply_user.is_bot:
        # Check if it's OUR bot
        if companion.bot_username:
            return reply_user.username and reply_user.username.lower() == companion.bot_username.lower()
        return True  # If we don't know our username yet, assume it's us
    return False


def _clean_response(response: str) -> str:
    """Strip markdown and clean up response for Telegram."""
    response = response.replace("**", "").replace("__", "").replace("```", "").replace("`", "")
    response = response.replace("- ", "• ")
    if len(response) > 4000:
        response = response[:4000] + "..."
    return response


async def _send_response(update: Update, response: str):
    """Send a response with fallback for formatting errors."""
    try:
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Send error: {e}")
        try:
            clean = response.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
            await update.message.reply_text(clean)
        except Exception:
            error_msgs = [
                "Oops, something went sideways! Try again? 😊",
                "My brain glitched for a second 🤖 One more time?",
                "That didn't quite work — mind saying that again?",
            ]
            await update.message.reply_text(random.choice(error_msgs))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    The main handler — responds to text messages.
    Detects group vs private chat and routes accordingly.
    """
    if not update.message or not update.message.text:
        return

    message = update.message.text.strip()
    if not message:
        return

    user_id = companion._user_id(update)

    # ─── Group Chat Handling ─────────────────────────────────
    if _is_group_chat(update):
        group_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "User"

        # Always save to group context (track conversation flow)
        companion.group_handler.save_group_context(
            group_id, message, user_name, user_id
        )

        # Decide whether to respond
        is_mentioned = _is_bot_mentioned(update, message)
        is_reply = _is_reply_to_bot(update)

        should_respond = await companion.group_handler.should_respond(
            message=message,
            is_mentioned=is_mentioned,
            is_reply_to_bot=is_reply,
            chat_id=group_id,
        )

        if not should_respond:
            return  # Stay silent

        # Rate limit
        if not companion.rate_limiter.check(user_id):
            await update.message.reply_text("Easy there! 😄 Give me a sec.")
            return

        await update.message.chat.send_action(ChatAction.TYPING)

        # Generate group response
        chat_context = companion.group_handler.get_group_context(group_id, limit=10)
        response = await companion.group_handler.generate_group_response(
            user_id, message, chat_context, group_id, user_name=user_name
        )

        response = _clean_response(response)
        await _send_response(update, response)

        # Save Nori's response to group context too
        companion.group_handler.save_group_context(
            group_id, response, "Nori", "bot"
        )

        logger.info(
            f"[Group {group_id}] {user_name}: "
            f"'{message[:50]}' → '{response[:50]}'"
        )
        return

    # ─── Private Chat Handling (existing logic) ──────────────

    # Rate limit check
    if not companion.rate_limiter.check(user_id):
        rate_msgs = [
            "Easy there! 😄 Give me a sec to catch up.",
            "Haha you're fast! Let me breathe for a moment 😅",
            "Hold on — processing... 🤖 Try again in a few seconds!",
        ]
        await update.message.reply_text(random.choice(rate_msgs))
        return

    # Billing limit check
    allowed, reason = companion.billing.check_limits(user_id, "message")
    if not allowed:
        await update.message.reply_text(f"{reason}\n\nUse /subscribe to see upgrade options!")
        return

    # Record usage
    companion.billing.record_usage(user_id, "message")

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Generate response
    response = await companion.generate(user_id, message)

    response = _clean_response(response)
    await _send_response(update, response)

    logger.info(
        f"User {update.effective_user.id}: "
        f"'{message[:50]}' → '{response[:50]}'"
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle voice messages — transcribe to text, generate response, reply with voice.

    Flow: voice audio → STT (Whisper) → generate text response → TTS → send voice note
    Falls back to text-only response if TTS/STT fails.
    """
    if not update.message or not (update.message.voice or update.message.audio):
        return

    user_id = companion._user_id(update)

    # Rate limit check
    if not companion.rate_limiter.check(user_id):
        await update.message.reply_text("Easy there! 😄 Give me a sec to catch up.")
        return

    # Billing limit check (voice)
    allowed, reason = companion.billing.check_limits(user_id, "voice")
    if not allowed:
        await update.message.reply_text(f"{reason}\n\nUse /subscribe to see upgrade options!")
        return

    # Record usage
    companion.billing.record_usage(user_id, "voice")

    await update.message.chat.send_action(ChatAction.TYPING)

    # Download voice/audio file
    try:
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        audio_bytes = bytes(audio_bytes)

        # Determine format from mime type
        mime = voice.mime_type or "audio/ogg"
        fmt_map = {
            "audio/ogg": "ogg",
            "audio/mpeg": "mp3",
            "audio/mp4": "m4a",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/webm": "webm",
            "audio/flac": "flac",
        }
        audio_format = fmt_map.get(mime, "ogg")

        logger.info(
            f"Voice from {update.effective_user.id}: "
            f"{len(audio_bytes)} bytes, {audio_format}, duration={voice.duration}s"
        )
    except Exception as e:
        logger.error(f"Voice download error: {e}")
        await update.message.reply_text(
            "I couldn't process that voice message 😅 Try sending text instead?"
        )
        return

    # Transcribe
    try:
        from nobi.voice.stt import transcribe_audio
        # Detect user language preference
        user_lang = companion.lang_detector.get_user_language(user_id) or "en"
        transcript = await transcribe_audio(audio_bytes, audio_format, user_lang)
    except ImportError:
        transcript = None
        logger.warning("STT module not available")
    except Exception as e:
        transcript = None
        logger.error(f"Transcription error: {e}")

    if not transcript or not transcript.strip():
        await update.message.reply_text(
            "I couldn't quite catch that 🎤 Could you try again or type it out?"
        )
        return

    logger.info(f"Transcribed: '{transcript[:100]}'")

    # Show what we heard (brief confirmation)
    await update.message.reply_text(f"🎤 I heard: \"{transcript[:200]}\"")
    await update.message.chat.send_action(ChatAction.TYPING)

    # Generate text response
    response = await companion.generate(user_id, transcript)
    response_clean = response.replace("**", "").replace("__", "").replace("```", "").replace("`", "").replace("- ", "• ")

    if len(response_clean) > 4000:
        response_clean = response_clean[:4000] + "..."

    # Try to generate voice response
    voice_reply = None
    try:
        from nobi.voice.tts import generate_speech
        # Only TTS for reasonably sized responses (< 1000 chars)
        if len(response_clean) < 1000:
            user_lang = companion.lang_detector.get_user_language(user_id) or "en"
            voice_reply = await generate_speech(response_clean, language=user_lang)
    except ImportError:
        logger.debug("TTS module not available")
    except Exception as e:
        logger.warning(f"TTS error: {e}")

    # Send response
    try:
        if voice_reply and len(voice_reply) > 0:
            # Send voice note + text as caption/follow-up
            await update.message.reply_voice(
                voice=voice_reply,
                caption=response_clean[:1024] if len(response_clean) <= 1024 else None,
            )
            # If caption too long, send text separately
            if len(response_clean) > 1024:
                await update.message.reply_text(response_clean)
        else:
            # Text-only fallback
            await update.message.reply_text(response_clean)
    except Exception as e:
        logger.error(f"Voice reply error: {e}")
        try:
            await update.message.reply_text(response_clean)
        except Exception:
            await update.message.reply_text(
                "Oops, something went sideways! Try again? 😊"
            )

    logger.info(
        f"Voice user {update.effective_user.id}: "
        f"'{transcript[:50]}' → '{response_clean[:50]}' "
        f"(voice_reply={'yes' if voice_reply else 'no'})"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle photo messages — analyze with vision model, extract memories, respond.

    Flow: photo → download → vision API → response + memory extraction
    """
    if not update.message or not update.message.photo:
        return

    user_id = companion._user_id(update)

    # Rate limit
    if not companion.rate_limiter.check(user_id):
        await update.message.reply_text("Easy there! 😄 Give me a sec to catch up.")
        return

    # Billing limit check (image)
    allowed, reason = companion.billing.check_limits(user_id, "image")
    if not allowed:
        await update.message.reply_text(f"{reason}\n\nUse /subscribe to see upgrade options!")
        return

    # Record usage
    companion.billing.record_usage(user_id, "image")

    await update.message.chat.send_action(ChatAction.TYPING)

    # Get the largest photo (last in the list)
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    # Download photo
    try:
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        photo_bytes = bytes(photo_bytes)

        logger.info(
            f"Photo from {update.effective_user.id}: "
            f"{len(photo_bytes)} bytes, caption='{caption[:50]}'"
        )
    except Exception as e:
        logger.error(f"Photo download error: {e}")
        await update.message.reply_text(
            "I couldn't download that photo 😅 Try sending it again?"
        )
        return

    # Get user memory context for vision model
    memory_context = ""
    try:
        memory_context = companion.memory.get_smart_context(user_id, caption or "photo")
    except Exception:
        try:
            memory_context = companion.memory.get_context_for_prompt(user_id, caption or "photo")
        except Exception:
            pass

    # Analyze image
    try:
        from nobi.vision.image_handler import analyze_image
        result = await analyze_image(
            image_bytes=photo_bytes,
            user_context=memory_context or "New user",
            caption=caption,
            image_format="jpg",
        )
    except ImportError:
        result = {
            "response": "I can see you sent a photo! I'd love to look at it but my vision module isn't set up yet 😊",
            "extracted_memories": [],
            "success": False,
        }
    except Exception as e:
        logger.error(f"Vision analysis error: {e}")
        result = {
            "response": "I had trouble looking at that photo 😅 Could you describe what's in it?",
            "extracted_memories": [],
            "success": False,
        }

    response = result["response"]

    # Store extracted memories
    if result.get("extracted_memories"):
        for mem_text in result["extracted_memories"][:5]:
            try:
                companion.memory.store(user_id, mem_text, memory_type="fact", importance=0.6)
            except Exception as e:
                logger.warning(f"Memory store from image failed: {e}")

    # Save conversation turn
    try:
        caption_text = f"[Photo] {caption}" if caption else "[Photo shared]"
        companion.memory.save_conversation_turn(user_id, "user", caption_text)
        companion.memory.save_conversation_turn(user_id, "assistant", response)
    except Exception:
        pass

    # Clean and send response
    response = response.replace("**", "").replace("__", "").replace("```", "").replace("`", "")
    if len(response) > 4000:
        response = response[:4000] + "..."

    try:
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Photo reply error: {e}")
        await update.message.reply_text(
            "I saw your photo but had trouble responding 😅 Try again?"
        )

    logger.info(
        f"Photo user {update.effective_user.id}: "
        f"caption='{caption[:30]}' → '{response[:50]}' "
        f"(success={result.get('success')}, memories={len(result.get('extracted_memories', []))})"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler — log but don't crash."""
    logger.error(f"Update {update} caused error: {context.error}")


# ─── Main ────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("❌ Set NOBI_BOT_TOKEN environment variable!")
        print("")
        print("How to get a token:")
        print("  1. Open Telegram, search @BotFather")
        print("  2. Send /newbot")
        print("  3. Name it: Nori (or whatever you like)")
        print("  4. Username: nobi_companion_bot (must end in 'bot')")
        print("  5. Copy the token")
        print("  6. Run: NOBI_BOT_TOKEN=<token> python3 app/bot.py")
        sys.exit(1)

    logger.info("🤖 Starting Nobi Companion Bot...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands (minimal — users shouldn't need these)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("memories", cmd_memories))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("import", cmd_import))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("proactive", cmd_proactive))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("plan", cmd_plan))
    app.add_handler(CommandHandler("nori", cmd_nori))

    # Buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # The magic: just respond to any text message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Voice messages: transcribe → respond → reply with voice
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Photo messages: vision analysis → respond → extract memories
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Global error handler
    app.add_error_handler(error_handler)

    # ── Proactive scheduler lifecycle ──
    PROACTIVE_INTERVAL = int(os.environ.get("PROACTIVE_INTERVAL", "3600"))

    async def _proactive_send(user_id: str, message: str):
        """Send a proactive message via Telegram."""
        # user_id format: "tg_<telegram_id>"
        if not user_id.startswith("tg_"):
            return
        try:
            tg_id = int(user_id[3:])
            await app.bot.send_message(chat_id=tg_id, text=message)
        except Exception as e:
            logger.error(f"[Proactive] Send to {user_id} failed: {e}")

    async def post_init(application):
        """Start proactive scheduler and detect bot username after init."""
        # Detect bot username for @mention matching in groups
        try:
            me = await application.bot.get_me()
            companion.bot_username = me.username or ""
            logger.info(f"Bot username: @{companion.bot_username}")
        except Exception as e:
            logger.warning(f"Failed to get bot username: {e}")

        companion.proactive_scheduler = ProactiveScheduler(
            companion.proactive_engine, _proactive_send
        )
        await companion.proactive_scheduler.start(interval_seconds=PROACTIVE_INTERVAL)
        logger.info(f"[Proactive] Scheduler started (interval={PROACTIVE_INTERVAL}s)")

    async def post_shutdown(application):
        """Stop proactive scheduler on shutdown."""
        if companion.proactive_scheduler:
            await companion.proactive_scheduler.stop()
            logger.info("[Proactive] Scheduler stopped")

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    logger.info("✅ Bot ready! Listening for messages...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Don't process messages sent while bot was offline
    )


if __name__ == "__main__":
    main()
