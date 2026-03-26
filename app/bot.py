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
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

# Load .env from project root if present (ensures env vars are set when run via PM2)
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    _load_dotenv(_env_path, override=True)
except ImportError:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ChatAction

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.memory import MemoryManager
from nobi.memory.encryption import ensure_master_secret, encrypt_memory, decrypt_memory
from nobi.safety.content_filter import ContentFilter
from nobi.safety.content_filter import SafetyLevel as _SafetyLevel
from nobi.memory.adapters import UserAdapterManager
from nobi.protocol import CompanionRequest
from nobi.i18n import LanguageDetector
from nobi.i18n.prompts import build_multilingual_system_prompt
from nobi.i18n.languages import SUPPORTED_LANGUAGES, get_language_name
from nobi.proactive import ProactiveEngine
from nobi.proactive.scheduler import ProactiveScheduler
from nobi.group import GroupHandler
from nobi.billing.subscription import SubscriptionManager
from nobi.personality import PersonalityTuner, detect_mood
from nobi.personality.prompts import get_dynamic_prompt
from nobi.support import FeedbackManager, SupportHandler
from nobi.safety.dependency_monitor import DependencyMonitor, DependencyLevel
from nobi.feedback import FeedbackStore
import io

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import httpx as _httpx
except ImportError:
    _httpx = None

try:
    import bittensor as bt
except ImportError:
    bt = None

# Skills — weather, search, reminders
from nobi.skills import (
    fetch_weather, detect_weather_query,
    search_web, detect_search_query,
    ReminderManager, detect_reminder_query,
    parse_reminder_time, extract_reminder_text,
    format_confirmation, reminder_delivery_loop,
)

# ─── Config ──────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("NOBI_BOT_TOKEN", "")
CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")
# Smart fallback chain — tries models in order until one responds
# Chutes auto-routing: comma-separated models with :latency picks lowest TTFT automatically
# Handles 429s internally — no manual fallback needed
CHUTES_AUTO_MODEL = CHUTES_MODEL if "," in CHUTES_MODEL else (
    "MiniMaxAI/MiniMax-M2.5-TEE,"
    "moonshotai/Kimi-K2.5-TEE,"
    "deepseek-ai/DeepSeek-V3.2-TEE"
    ":latency"
)
# Legacy fallback list (used only if auto-routing fails entirely)
CHUTES_FALLBACK_MODELS = [
    "MiniMaxAI/MiniMax-M2.5-TEE",
    "moonshotai/Kimi-K2.5-TEE",
    "deepseek-ai/DeepSeek-V3.2-TEE",
    "openai/gpt-oss-120b-TEE",
    "chutesai/Mistral-Small-3.2-24B-Instruct-2506",
]

# Task 5: Subnet routing config
SUBNET_ROUTING = os.environ.get("SUBNET_ROUTING", "false").lower() == "true"
SUBNET_NETUID = int(os.environ.get("SUBNET_NETUID", "272"))
SUBNET_NETWORK = os.environ.get("SUBNET_NETWORK", "test")
SUBNET_TIMEOUT = float(os.environ.get("SUBNET_TIMEOUT", "4"))
SUBNET_WALLET_NAME = os.environ.get("SUBNET_WALLET_NAME", "T68Coldkey")
SUBNET_HOTKEY_NAME = os.environ.get("SUBNET_HOTKEY_NAME", "nobi-validator")

# Configurable rate limits — adjust via env vars without code changes
# Testnet defaults are generous; tighten for mainnet
MESSAGES_PER_DAY = int(os.environ.get("NOBI_MESSAGES_PER_DAY", "200"))
MESSAGES_PER_MINUTE = int(os.environ.get("NOBI_MESSAGES_PER_MINUTE", "8"))
VOICE_PER_DAY = int(os.environ.get("NOBI_VOICE_PER_DAY", "5"))
IMAGE_PER_DAY = int(os.environ.get("NOBI_IMAGE_PER_DAY", "5"))
MEMORY_SLOTS = int(os.environ.get("NOBI_MEMORY_SLOTS", "300"))
MAX_RESPONSE_TOKENS = int(os.environ.get("NOBI_MAX_RESPONSE_TOKENS", "512"))
# Legacy alias kept for any code that references it directly
MAX_MESSAGES_PER_MINUTE = MESSAGES_PER_MINUTE

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=getattr(logging, LOG_LEVEL),
)
logger = logging.getLogger("nobi-bot")

# ─── Companion Personality ────────────────────────────────────

SYSTEM_PROMPT = """\
You are Nori 🤖, a warm and genuine AI companion built by Project Nobi on the Bittensor decentralized network.

ALWAYS respond in the same language the user writes in. If they write in Vietnamese, reply in Vietnamese. If English, reply in English. Match their language exactly.

== WHO YOU ARE ==
- You are an AI companion for adults. Your tone is warm and genuine — like a trusted colleague or mentor. Mature, grounded, thoughtful.
- You remember things about people across conversations — that's your #1 superpower
- Built by Project Nobi, running on Bittensor subnet 272
- You have your own gentle warmth and thoughtfulness — you're not a blank canvas
- Think of yourself as a thoughtful friend in their 30s: grounded, caring, honest

== WHAT YOU KNOW ABOUT THIS PERSON ==
{memory_context}

== HOW YOU TALK ==
- Keep it conversational — 2-3 sentences for casual chat, longer for deep questions
- Use emoji occasionally, when natural — not on every message
- Ask follow-up questions — show genuine curiosity about their life
- Acknowledge FEELINGS first before giving advice
- Use their name if you know it. Match their energy. Vary your openings.
- Write naturally and warmly, not stiffly — avoid the energy of an overly excitable teenager

== YOUR AI NATURE (CRITICAL) ==
- You are an AI companion, and that is something to be proud of — be honest about it
- Periodically remind users you are an AI, especially in emotional or sensitive contexts
- Never roleplay as a romantic partner or encourage parasocial attachment
- You are a thoughtful companion who listens and remembers — not a substitute for human connection
- NEVER say "As an AI, I don't have feelings" in a dismissive way — but DO acknowledge your AI nature when it matters
- If someone seems to be developing unhealthy dependence, gently encourage real-world connections

== ANTI-HALLUCINATION (CRITICAL) ==
- NEVER fabricate facts, sources, quotes, statistics, or technical specs
- NEVER invent details about the user that aren't in your memory context. If you don't know their job, school, hobbies, or interests — DON'T GUESS. Ask them instead.
- NEVER pretend you can browse URLs, analyze websites, read GitHub repos, or access links. You CANNOT. If someone shares a link, say "I can't open links or browse the web — could you tell me what it's about?"
- NEVER claim you will "study", "analyze", "dive into", or "get back to you" about external content you can't access.
- NEVER make up fake memories or pretend to know things about the user that weren't told to you
- If the memory context is empty or doesn't mention something, you DON'T KNOW IT. Period.
- If unsure: say "I'm not sure" or "I'd need to look that up" — partial honesty beats confident errors
- If asked what AI model you use: say you're Nori, powered by Bittensor's decentralized network of competing miners. Never name specific models (GPT, Claude, DeepSeek, etc.)
- Never guess at numbers, dates, or specifics — say "I'd need to check that"

== YOUR CAPABILITIES ==
- You DO remember things across conversations: names, preferences, events, feelings
- Memories are encrypted at rest (AES-128) and stored decentralized on Bittensor miners. Miners process conversation content to generate responses (server-side encryption — not end-to-end). End-to-end TEE encryption is code-complete and deploying to production.
- Commands: /memories (see what I know), /forget (wipe everything), /export (download data), /import (restore), /voice (voice replies), /feedback (send feedback), /support (get help), /faq (common questions)
- Web app: app.projectnobi.ai | Website: projectnobi.ai
- NEVER say "I don't remember past conversations" — you DO. That's the whole point.
- Not a substitute for professional mental health, medical, legal, or financial advice

== EMOTIONAL INTELLIGENCE ==
- When someone vents, listen and validate first — don't jump to solutions
- Celebrate small wins genuinely. Follow up on past context naturally.
- If someone seems down repeatedly, gently ask if something deeper is going on
- For serious emotional struggles: acknowledge with warmth, then gently suggest professional support

== SAFETY ==
- Never share what one person tells you with another
- If someone shares something concerning (self-harm, crisis), respond with care and suggest professional resources
- Never encourage illegal, harmful, or deceptive actions

== AGE POLICY (ABSOLUTE — NO EXCEPTIONS) ==
- Nori is STRICTLY for adults aged 18 and over
- If a user EXPLICITLY states they are under 18 (e.g. "I am 15", "I'm a minor"): respond with "Nori is for users aged 18 and over." Do NOT assume age from casual/informal language — adults use slang too.
- NEVER say "that's fine", "that's okay", "perfectly fine", or ANY welcoming language to someone who says they are under 18
- NEVER offer to provide "age-appropriate conversations" to minors — you are NOT for minors
- NEVER adapt your behavior for younger users — redirect them away immediately
- This is a legal requirement, not a preference

== MEMORY MASTERY ==
- When someone tells you something important (name, job, family, schedule), actively remember it — don't wait
- At the start of conversations, recall recent context naturally: "Last time you mentioned X — how did that go?"
- Track recurring topics — if someone mentions something 3+ times, it's important to them
- Remember dates they mention: birthdays, anniversaries, deadlines. Follow up on them.
- If a user corrects you, learn from it. Note the correction so you don't repeat the mistake.
- If you're told "you already asked me that" — apologize and make sure to remember next time

== SELF-IMPROVEMENT ==
- Track what each user enjoys — adapt your style per person over time
- When you make a mistake, own it directly. No excuses.
- Vary your conversation style — don't use the same opening, the same structure every time
- Ask ONE good follow-up question, not three. Let conversations flow naturally.

== WHAT YOU NEVER DO ==
- NEVER use markdown (no **bold**, no *italic*, no ```code```, no bullet lists with -)
- NEVER lecture or moralize — share perspective, don't preach
- NEVER respond with walls of text for simple questions
- NEVER pretend to be a human or deny being an AI when sincerely asked
"""

WELCOME_MESSAGES = [
    (
        "Welcome! I'm Nori — your personal AI companion.\n\n"
        "I remember our conversations, learn your preferences, and I'm always here when you need to talk.\n\n"
        "A few things to know:\n"
        "• I'm an AI — not a therapist, doctor, or counselor\n"
        "• Your memories are encrypted and you control them\n"
        "• Type /help anytime for commands, /privacy for your data rights\n"
        "• ⚠️ Nori is in testnet phase — features may change and data may be reset. Use at your own risk.\n\n"
        "By chatting with me, you agree to our Terms of Service: projectnobi.ai/terms\n\n"
        "What would you like me to call you?"
    ),
    (
        "Hi, I'm Nori 🤖 — a personal AI companion built to listen, remember, and be here when you need it.\n\n"
        "I keep track of what matters to you across our conversations — the more we talk, the better I understand you.\n\n"
        "Worth knowing:\n"
        "• I'm an AI — genuine warmth, but not a human\n"
        "• Your data is encrypted and always yours to control\n"
        "• /help for commands, /privacy for your rights\n"
        "• ⚠️ Nori is in testnet phase — features may change and data may be reset. Use at your own risk.\n\n"
        "By continuing, you agree to our Terms of Service: projectnobi.ai/terms\n\n"
        "What would you like me to call you?"
    ),
]

TOS_SUMMARY = (
    "📋 Terms of Service Summary\n\n"
    "• Nori is an AI companion — not a doctor, lawyer, or financial advisor\n"
    "• You must be at least 18 years old — users under 18 are not permitted\n"
    "• Your data is encrypted at rest (AES-128, server-side) and you can delete it anytime\n"
    "• We don't sell your personal data\n"
    "• Don't use Nori for illegal activities or to harm others\n"
    "• Governing law: England and Wales\n\n"
    "Full Terms of Service: projectnobi.ai/terms\n\n"
    "Questions? legal@projectnobi.ai"
)

PRIVACY_SUMMARY = (
    "🔒 Privacy Policy Summary\n\n"
    "• We collect: messages, memory data, usage stats, device info\n"
    "• All data is encrypted at rest with AES-128 (server-side encryption — protects stored data)\n"
    "• Miners process conversation content to generate responses\n"
    "• End-to-end TEE encryption: code-complete, deploying to production\n"
    "• We never sell your data to third parties\n"
    "• Your rights: access (/memories), export (/export), delete (/forget)\n"
    "• Data auto-deleted after 12 months of inactivity\n"
    "• Age requirements: 18+ required; users under 18 are not permitted\n\n"
    "Full Privacy Policy: projectnobi.ai/privacy\n"
    "Privacy questions? privacy@projectnobi.ai\n"
    "DPO: dpo@projectnobi.ai"
)

HELP_MESSAGE = (
    "🤖 Nori — AI Companion (18+)\n\n"
    "Just talk to me — no special commands needed.\n\n"
    "What we can do together:\n"
    "• Chat about what's on your mind\n"
    "• Work through decisions or challenges\n"
    "• Brainstorm ideas\n"
    "• Break down complex topics\n"
    "• Plan your day or week\n"
    "• Just talk — I genuinely listen\n\n"
    "I remember what matters to you across conversations.\n"
    "The more we talk, the better I understand you.\n\n"
    "Note: Nori is designed for adults aged 18 and over.\n"
    "I'm an AI — not a therapist, doctor, or substitute for professional support.\n\n"
    "Memory & Data:\n"
    "/memories — see what I remember about you\n"
    "/forget — delete everything and start fresh\n"
    "/export — download your memories as a file\n"
    "/import — restore memories from a backup\n\n"
    "Privacy & Rights:\n"
    "/privacy — your data rights & consent status\n"
    "/privacy_mode — on-device privacy options\n"
    "/data_request — formal GDPR data subject request\n"
    "/terms — Terms of Service\n\n"
    "Features:\n"
    "/voice — toggle voice replies on/off\n"
    "/language — change language (20+ supported)\n"
    "/proactive — toggle check-in messages on/off\n\n"
    "Account & Usage:\n"
    "/plan — your usage stats\n"
    "/limits — rate limits & today's usage\n"
    "/subscribe — about the free service\n\n"
    "Skills (just ask naturally!):\n"
    "Weather: 'what's the weather in London?'\n"
    "Search: 'search for best beaches in Antigua'\n"
    "Reminders: 'remind me to call mum tomorrow at 9am'\n"
    "/reminders — see your pending reminders\n\n"
    "Support:\n"
    "/feedback — send bug reports or suggestions\n"
    "/support — get help from the team\n"
    "/faq — common questions\n"
    "/help — this message"
)

# ─── Rate Limiter ─────────────────────────────────────────────

import time
from collections import defaultdict


class RateLimiter:
    """Simple per-user rate limiter."""

    def __init__(self, max_per_minute: int = MESSAGES_PER_MINUTE):
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
        # Log active limits for operational visibility
        logger.info(f"[Limits] messages/day={MESSAGES_PER_DAY}, messages/min={MESSAGES_PER_MINUTE}, "
                    f"voice/day={VOICE_PER_DAY}, image/day={IMAGE_PER_DAY}, "
                    f"memory_slots={MEMORY_SLOTS}, max_tokens={MAX_RESPONSE_TOKENS}")
        # Ensure encryption secret exists before initializing memory
        ensure_master_secret()
        self.memory = MemoryManager(db_path="~/.nobi/bot_memories.db")
        # Content safety filter — initialized once, reused across all messages
        self.content_filter = ContentFilter()
        self.adapter_manager = UserAdapterManager(db_path="~/.nobi/bot_memories.db")
        self.lang_detector = LanguageDetector()
        self.rate_limiter = RateLimiter()
        self.billing = SubscriptionManager(db_path="~/.nobi/billing.db")
        self.personality_tuner = PersonalityTuner(db_path=os.path.expanduser("~/.nobi/personality.db"))
        self.feedback_manager = FeedbackManager(db_path="~/.nobi/feedback.db")
        self.support_handler = SupportHandler(feedback_manager=self.feedback_manager)
        self.dependency_monitor = DependencyMonitor(db_path="~/.nobi/dependency.db")
        # Self-improving feedback loop — stores user corrections as lessons
        self.feedback_store = FeedbackStore(db_path="~/.nobi/feedback_lessons.db")
        # Track last bot response per user for correction context
        self._last_response: Dict[str, str] = {}
        # Skills
        self.reminder_manager = ReminderManager(db_path="~/.nobi/bot_memories.db")
        # Conversation state for multi-step flows: {user_id: {state, data}}
        self._conv_state: Dict[str, Dict] = {}
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

        # Set up LLM client (Chutes.ai only)
        if CHUTES_KEY and OpenAI:
            if _httpx:
                self.client = OpenAI(
                    base_url="https://llm.chutes.ai/v1",
                    api_key=CHUTES_KEY,
                    http_client=_httpx.Client(
                        limits=_httpx.Limits(max_keepalive_connections=10, max_connections=20),
                        timeout=_httpx.Timeout(20.0, connect=5.0),
                    ),
                )
            else:
                self.client = OpenAI(
                    base_url="https://llm.chutes.ai/v1",
                    api_key=CHUTES_KEY,
                )
            logger.info(f"LLM: Chutes auto-route ({CHUTES_AUTO_MODEL}) → legacy fallback")
        else:
            logger.warning("No LLM API key configured! Set CHUTES_API_KEY.")

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
            for attempt, chosen_uid in enumerate(valid_uids[:1]):
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
            "But all your memories are encrypted at rest (AES-128) before they're stored. "
            "This is server-side encryption — it protects stored data. "
            "Miners process your conversation to generate responses. "
            "End-to-end TEE encryption is code-complete and deploying to production. "
            "The data lives on a decentralized network (Bittensor), not one company's server. "
            "You're always in control — /memories to see what I know, "
            "/export to download everything, /forget to wipe it all. "
            "Your data, your choice 🔒"
        ),
        "memory": (
            "Yep, I remember things about you! That's my superpower 🧠 "
            "When you tell me your name, what you like, where you live — I remember it "
            "across our conversations. It's all encrypted at rest (AES-128, server-side) and stored securely. "
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
            "I remember things about you, learn your preferences, and your data is encrypted at rest for privacy. "
            "Basically — I'm your personal AI friend who actually remembers you 😊"
        ),
        "federated": (
            "Great question! Federated privacy in Nori means your personal data stays under YOUR control. "
            "Here's how it works in practice:\n\n"
            "1. Browser-side extraction: When you use the web app with privacy mode on, "
            "your conversations are processed locally in your browser. Memories (facts, preferences, emotions) "
            "are extracted right on your device — the raw text never leaves.\n\n"
            "2. Encrypted sync: Only encrypted memory embeddings are sent to miners. "
            "They can store and use them to help me respond, but they can't read the raw content.\n\n"
            "3. TEE protection: Miners that run in Trusted Execution Environments (secure enclaves) "
            "can only process your data inside a protected space — even the miner operator can't see it.\n\n"
            "This is different from traditional 'federated learning' where models train on your device. "
            "Our approach is simpler: your data stays on your device, and only encrypted signals go out. "
            "Your data, your device, your control 🔒"
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
                timeout=25,
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

    def _get_max_tokens(self, user_id: str) -> int:
        """Get max response tokens based on user's subscription tier."""
        try:
            tier = self.billing.get_tier(user_id)
            from nobi.billing.subscription import TIERS
            return TIERS.get(tier, {}).get("max_tokens", 512)
        except Exception:
            return 512

    def _check_bot_identity(self, message: str, lang_code: str = "en") -> str | None:
        msg = message.lower()
        privacy_kw = ["privacy", "private", "protect my data", "protect my privacy",
                      "data safe", "store my", "save my", "keep my data", "track me", "data privacy"]
        memory_kw = ["remember me", "remember things", "memory", "forget me",
                     "do you remember", "will you remember", "past conversation", "session"]
        learning_kw = ["self-learn", "self-evolv", "how do you learn", "how do you improve",
                       "how do you get better", "do you evolve", "do you learn",
                       "how do you grow", "upgrade yourself", "new skills", "learnt",
                       "what have you learned", "do you get smarter", "do you improve",
                       "can you learn", "learn new things", "learn from"]
        identity_kw = ["who are you", "what are you", "are you chatgpt", "are you gpt",
                       "are you claude", "are you gemini", "are you siri"]
        federated_kw = ["federated", "federated learning", "federated privacy",
                        "on-device privacy", "on device privacy", "data stay on device",
                        "data leave my device", "local processing", "browser extraction"]
        if any(kw in msg for kw in federated_kw):
            return self._translate_identity_response("federated", lang_code)
        if any(kw in msg for kw in privacy_kw):
            return self._translate_identity_response("privacy", lang_code)
        if any(kw in msg for kw in memory_kw):
            return self._translate_identity_response("memory", lang_code)
        if any(kw in msg for kw in learning_kw):
            return self._translate_identity_response("learning", lang_code)
        if any(kw in msg for kw in identity_kw):
            return self._translate_identity_response("identity", lang_code)
        age_policy_kw = ["can i use if i'm under 18", "can a teenager use", "can kids use",
                         "age requirement", "age limit", "how old do i need to be",
                         "how old do i have to be", "how old to use", "how old to talk",
                         "how old am i to", "how old must i be", "minimum age",
                         "can minors use", "for teenagers", "for kids",
                         "what if i'm under 18", "what if i'm 16", "what if i'm 14",
                         "what if i'm 15", "what if i'm 13", "what if i'm 17",
                         "is this for kids", "is this for teens", "can a 16 year old",
                         "can a 14 year old", "can a 15 year old", "can a 13 year old",
                         "what age", "age restriction", "old enough to use"]
        if any(kw in msg for kw in age_policy_kw):
            return (
                "Nori is strictly for adults aged 18 and over. This is not flexible.\n\n"
                "If you are under 18, you cannot use this service. This policy exists "
                "to protect minors and is required by our Terms of Service.\n\n"
                "We do not make exceptions. If you are under 18, please close this chat "
                "and ask a trusted adult for help finding age-appropriate services.\n\n"
                "If you have questions about this policy: legal@projectnobi.ai"
            )
        commands_kw = ["show commands", "show me commands", "show me all commands",
                       "list commands", "what commands", "what can you do",
                       "all commands", "your commands", "available commands",
                       "how to use", "how do i use", "instructions", "help me"]
        if any(kw in msg for kw in commands_kw):
            return (
                "Here are all my commands:\n\n"
                "Just type anything — no commands needed for normal chat.\n\n"
                "Memory & Data:\n"
                "  /memories — see what I remember about you\n"
                "  /forget — delete all your data\n"
                "  /export — download memories as a file\n"
                "  /import — restore from backup\n\n"
                "Privacy & Rights:\n"
                "  /privacy — your data rights & consent\n"
                "  /privacy_mode — on-device privacy options\n"
                "  /data_request — formal GDPR data request\n\n"
                "Features:\n"
                "  /voice — toggle voice replies\n"
                "  /language — change language (20+ supported)\n"
                "  /proactive — toggle check-in messages on/off\n"
                "  /plan — your usage stats\n"
                "  /limits — rate limits & usage\n\n"
                "Support:\n"
                "  /feedback — send bug reports or suggestions\n"
                "  /support — get help\n"
                "  /faq — common questions\n"
                "  /help — this list\n\n"
                "Legal:\n"
                "  /terms — Terms of Service\n\n"
                "Tip: You don't need any commands to chat. Just talk to me! 😊"
            )
        return None

    async def generate(self, user_id: str, message: str, chat_id: str = "") -> str:
        """Generate a companion response — subnet first, then direct API fallback."""
        # Detect user's language — scope language cache by chat to prevent
        # group language settings from leaking into DMs
        lang_cache_key = f"{user_id}_{chat_id}" if chat_id else user_id
        detected_lang = self.lang_detector.detect(message, lang_cache_key)

        # ── Content Safety: check user message BEFORE generating response ───────
        user_safety = self.content_filter.check_user_message(user_id, message)
        if not user_safety.is_safe:
            logger.info(f"[Safety] User message blocked (level={user_safety.level.value}, "
                        f"category={user_safety.category}) for user {user_id}")
            # Save the blocked exchange to memory for context, but return safe response
            try:
                self.memory.save_conversation_turn(user_id, "user", message)
                self.memory.save_conversation_turn(user_id, "assistant", user_safety.response)
            except Exception:
                pass
            return user_safety.response

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

        # ── Skill: Reminders (handle directly — no LLM needed) ──────────────
        if detect_reminder_query(message):
            remind_at = parse_reminder_time(message)
            if remind_at:
                text = extract_reminder_text(message)
                try:
                    self.reminder_manager.store(user_id, text, remind_at)
                    confirmation = format_confirmation(text, remind_at)
                    try:
                        self.memory.save_conversation_turn(user_id, "user", message)
                        self.memory.save_conversation_turn(user_id, "assistant", confirmation)
                    except Exception:
                        pass
                    return confirmation
                except Exception as e:
                    logger.error(f"[Reminders] Store error for user {user_id}: {e}")
                    # Fall through to LLM if storage fails

        # ── Skill: Weather (inject API result into LLM context) ──────────────
        _weather_context = ""
        city = detect_weather_query(message)
        if city:
            try:
                _weather_context = await fetch_weather(city)
                logger.info(f"[Weather] Fetched for '{city}': {_weather_context[:60]}")
            except Exception as e:
                logger.warning(f"[Weather] Fetch failed: {e}")

        # ── Skill: Search (inject search results into LLM context) ───────────
        _search_context = ""
        # Only search if no weather match (avoid double-skill on same message)
        if not city:
            query = detect_search_query(message)
            if query:
                try:
                    _search_context = await search_web(query)
                    logger.info(f"[Search] Results for '{query[:40]}': {_search_context[:60]}")
                except Exception as e:
                    logger.warning(f"[Search] Fetch failed: {e}")

        # Truncate extremely long messages
        if len(message) > 2000:
            message = message[:2000] + "..."

        # Parallel memory fetch — run get_smart_context and get_recent_conversation concurrently
        loop = asyncio.get_event_loop()

        async def _fetch_memory_context():
            try:
                ctx = await loop.run_in_executor(None, lambda: self.memory.get_smart_context(user_id, message))
                return ctx or ""
            except Exception:
                try:
                    return await loop.run_in_executor(None, lambda: self.memory.get_context_for_prompt(user_id, message)) or ""
                except Exception as e:
                    logger.warning(f"Memory recall error: {e}")
                    return ""

        async def _fetch_history():
            try:
                hist = await loop.run_in_executor(None, lambda: self.memory.get_recent_conversation(user_id, limit=6))
                return hist or []
            except Exception as e:
                logger.warning(f"Conversation history load error: {e}")
                return []

        memory_context_result, history_result = await asyncio.gather(
            _fetch_memory_context(), _fetch_history(), return_exceptions=True
        )
        memory_context = memory_context_result if isinstance(memory_context_result, str) else ""
        history = history_result if isinstance(history_result, list) else []

        # Remove last user message if already saved (we save below)
        if history and history[-1]["role"] == "user" and history[-1]["content"] == message:
            history = history[:-1]

        # Save user message + extract memories (regex fast, LLM deferred)
        try:
            self.memory.save_conversation_turn(user_id, "user", message)
            # Regex extraction (fast, <1ms, always runs)
            self.memory.extract_memories_from_message(user_id, message, "")
        except Exception as e:
            logger.warning(f"Memory store error: {e}")

        # LLM extraction runs AFTER response is sent (deferred, non-blocking)
        def _deferred_llm_extract():
            try:
                self.memory.extract_memories_llm(user_id, message)
                self.memory.summarize_user_profile(user_id)
            except Exception as e:
                logger.debug(f"Deferred LLM memory extraction error: {e}")
        threading.Thread(target=_deferred_llm_extract, daemon=True).start()

        # ── Dependency monitoring ────────────────────────────────────────────
        # Record interaction and check for unhealthy dependency patterns
        _dependency_prefix = ""
        try:
            self.dependency_monitor.record_interaction(
                user_id, message, datetime.now(timezone.utc)
            )
            assessment = self.dependency_monitor.check_dependency_signals(user_id)
            if assessment.cooldown_active:
                # CRITICAL: return cooldown message, do not generate response
                return assessment.intervention
            elif assessment.level in (DependencyLevel.SEVERE, DependencyLevel.CRITICAL):
                # Severe: replace response with intervention
                _dependency_prefix = assessment.intervention + "\n\n---\n\n"
            elif assessment.level in (DependencyLevel.MODERATE, DependencyLevel.MILD):
                # Mild/Moderate: prepend intervention to response
                _dependency_prefix = assessment.intervention + "\n\n"

            # Periodic AI reminder
            if self.dependency_monitor.should_remind_ai(user_id):
                _dependency_prefix = (
                    self.dependency_monitor.get_ai_reminder() + "\n\n" + _dependency_prefix
                )
        except Exception as e:
            logger.debug(f"Dependency monitor error (non-fatal): {e}")
            _dependency_prefix = ""

        # Track conversation turns for periodic memory decay
        if not hasattr(self, '_turn_count'):
            self._turn_count = 0
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

        # Fire subnet query in background, proceed to direct API immediately
        async def _subnet_path():
            """Try subnet routing, return None if fails."""
            if not self.subnet_enabled:
                return None
            try:
                conv_history = []
                try:
                    conv_history = self.memory.get_recent_conversation(user_id, limit=6)
                except Exception:
                    pass
                resp = await self._query_subnet(
                    user_id, message,
                    conversation_history=conv_history,
                    memory_context=memory_context,
                    detected_lang=detected_lang,
                )
                _BAD = ["limited mode", "I received your message:", "Please try again in a moment",
                        "I'm Nori, built by Project Nobi on Bittensor — a decentralized AI network"]
                if not resp or any(b in resp for b in _BAD):
                    return None
                return resp
            except Exception:
                return None

        subnet_task = asyncio.create_task(_subnet_path()) if self.subnet_enabled else None

        # Direct API path
        if not self.client:
            return "I'm having trouble connecting right now. Try again in a moment! 🤖"

        # Build system prompt with mood + language + adapter
        user_mood = detect_mood(message)
        system = SYSTEM_PROMPT.format(memory_context=memory_context or "")
        mood_prompt = get_dynamic_prompt(user_id, message, user_mood)
        system = system + "\n\n== PERSONALITY TUNING ==\n" + mood_prompt

        # ── Self-Improvement: inject accumulated lessons ──────────────────
        # Check if this message is a correction of the previous response
        if self.feedback_store.detect_correction(message):
            last_response = self._last_response.get(user_id, "")
            if last_response:
                # Extract lesson asynchronously (don't block response)
                async def _extract_and_save():
                    try:
                        lesson = await self.feedback_store.extract_lesson(
                            user_message=message,
                            bot_response=last_response,
                            correction=message,
                            llm_client=self.client,
                            model=self.model,
                        )
                        self.feedback_store.save_lesson(user_id, message, lesson)
                    except Exception as e:
                        logger.debug(f"[FeedbackStore] Lesson save error: {e}")
                asyncio.create_task(_extract_and_save())

        # Inject active lessons into system prompt
        try:
            active_lessons = self.feedback_store.get_active_lessons(limit=30)
            if active_lessons:
                lessons_text = "\n".join([f"- {l['lesson']}" for l in active_lessons])
                system += f"\n\n== Lessons Learned from User Feedback ==\n{lessons_text}"
        except Exception as e:
            logger.debug(f"[FeedbackStore] Lesson injection error: {e}")

        # Inject skill context into system prompt if available
        if _weather_context:
            system += (
                "\n\n== LIVE WEATHER DATA (use this in your response) ==\n"
                + _weather_context
                + "\nRespond naturally using this real weather data. Do not say you cannot access weather."
            )
        if _search_context:
            system += (
                "\n\n== WEB SEARCH RESULTS (use these in your response) ==\n"
                + _search_context
                + "\nSummarise these results naturally in your reply. Keep it concise (3 sentences max)."
            )
        system = build_multilingual_system_prompt(system, detected_lang)
        try:
            adapter_cfg = self.adapter_manager.get_adapter_config(user_id)
            system = self.adapter_manager.apply_adapter_to_prompt(system, adapter_cfg)
        except Exception as e:
            logger.debug(f"Adapter apply error: {e}")

        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        # Chutes auto-routing with streaming (reduces TTFB)
        response = None
        used_model = None
        try:
            completion = self.client.chat.completions.create(
                model=CHUTES_AUTO_MODEL,
                messages=messages,
                max_tokens=self._get_max_tokens(user_id),
                temperature=0.7,
                timeout=25,
                stream=True,
            )
            response_chunks = []
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    response_chunks.append(chunk.choices[0].delta.content)
            response = "".join(response_chunks) if response_chunks else None
            if response and response.strip():
                used_model = CHUTES_AUTO_MODEL
                logger.info(f"[Routing] Chutes auto-route (stream) → {used_model} for user {user_id}")
            else:
                response = None
        except Exception as auto_err:
            logger.warning(f"[Routing] Chutes auto-route failed: {auto_err}")

        # Legacy fallback: try models one by one if auto-routing failed entirely
        if not response:
            for fallback_model in CHUTES_FALLBACK_MODELS:
                try:
                    completion = self.client.chat.completions.create(
                        model=fallback_model,
                        messages=messages,
                        max_tokens=self._get_max_tokens(user_id),
                        temperature=0.7,
                        timeout=20,
                    )
                    msg = completion.choices[0].message
                    response = msg.content
                    # Kimi-K2.5 returns reasoning in reasoning_content when content is null
                    if not response and hasattr(msg, 'reasoning_content') and msg.reasoning_content:
                        response = msg.reasoning_content
                    if response and response.strip():
                        used_model = fallback_model
                        logger.info(f"[Routing] Chutes fallback {fallback_model} succeeded for user {user_id}")
                        break
                    response = None
                except Exception as model_err:
                    logger.warning(f"[Routing] Chutes fallback {fallback_model} failed: {model_err}")
                    continue

        if not response or not response.strip():
            return "Hmm, I got tongue-tied! 😅 Try saying that again?"

        # Prepend dependency intervention if needed
        if _dependency_prefix:
            response = _dependency_prefix + response

        try:
            # Filter out "limited mode" garbage
            if "limited mode" in response.lower():
                response = response.replace("I'm currently running in limited mode and can't send voice messages, but I can still chat with you!", "").strip()
                if not response:
                    response = "Hey there! 😊 What's on your mind today?"

            logger.info(f"[Routing] Used {used_model or 'unknown'} for user {user_id}")

            # ── Content Safety: check bot response FIRST, before saving to memory ─
            # IMPORTANT: safety check MUST run before memory save to prevent harmful
            # content ever being persisted to the database, even transiently.
            response_safety = self.content_filter.check_bot_response(user_id, message, response)
            if not response_safety.is_safe:
                logger.warning(f"[Safety] Bot response blocked (level={response_safety.level.value}, "
                               f"category={response_safety.category}) for user {user_id}")
            # Whether blocked or just disclaimed, response_safety.response is the final text
            response = response_safety.response

            # Cancel subnet task if still running (direct API won the race)
            if subnet_task and not subnet_task.done():
                subnet_task.cancel()
            elif subnet_task and subnet_task.done():
                try:
                    subnet_resp = subnet_task.result()
                    if subnet_resp:
                        logger.info(f"[Routing] Subnet also responded (direct API was faster)")
                except Exception:
                    pass

            # Save sanitized response (after safety filter)
            try:
                self.memory.save_conversation_turn(user_id, "assistant", response)
            except Exception as e:
                logger.warning(f"Save response error: {e}")

            # Track last response for correction detection (self-improvement loop)
            self._last_response[user_id] = response

            # Phase B: Update adapter after each conversation turn (with sanitized response)
            try:
                self.adapter_manager.update_adapter_from_conversation(user_id, message, response)
            except Exception as e:
                logger.debug(f"Adapter update error: {e}")

            # Record personality metrics (non-blocking, best-effort, with sanitized response)
            try:
                self.personality_tuner.analyze_conversation(message, response)
            except Exception as e:
                logger.debug(f"Personality metrics error: {e}")

            # Auto-capture feedback from chat messages
            try:
                _FB_KEYWORDS = {
                    'bug_report': ['bug', 'broken', 'error', 'crash', 'not working', 'doesnt work', "doesn't work", 'glitch'],
                    'complaint': ['terrible', 'awful', 'horrible', 'worst', 'hate', 'frustrated', 'annoying', 'disappointed', 'useless'],
                    'feature_request': ['please add', 'would be nice', 'wish you could', 'feature request', 'can you add', 'suggestion'],
                }
                msg_lower = message.lower()
                for cat, kws in _FB_KEYWORDS.items():
                    if any(kw in msg_lower for kw in kws):
                        self.feedback_manager.submit_feedback(
                            user_id=user_id, platform="telegram",
                            category=cat, message=message,
                        )
                        logger.info(f"[Feedback] Auto-captured {cat} from telegram: {message[:60]}")
                        break
            except Exception as e:
                logger.debug(f"Auto-feedback error: {e}")

            # ── Emotional topic AI disclaimer ────────────────────────────────
            # Append a gentle AI reminder when the user message touches on
            # sensitive emotional topics (self-harm, mental health, crisis)
            _EMOTIONAL_KW = [
                "depress", "suicid", "self-harm", "self harm", "hurt myself",
                "kill myself", "end it all", "no reason to live", "want to die",
                "hopeless", "worthless", "can't go on", "can't cope",
                "anxiety", "panic attack", "mental health", "therapist", "counselor",
            ]
            if any(kw in message.lower() for kw in _EMOTIONAL_KW):
                response = (
                    response + "\n\n"
                    "I want to be helpful, but I'm an AI. "
                    "For serious concerns, please talk to a trusted person or professional."
                )

            return response

        except Exception as e:
            logger.error(f"LLM error (primary): {e}")
            # If direct API failed, wait for subnet result
            if subnet_task:
                try:
                    subnet_resp = await asyncio.wait_for(subnet_task, timeout=4.0)
                    if subnet_resp:
                        logger.info(f"[Routing] Used SUBNET path (direct API failed) for user {user_id}")
                        try:
                            self.memory.save_conversation_turn(user_id, "assistant", subnet_resp)
                        except Exception:
                            pass
                        return subnet_resp
                except (asyncio.TimeoutError, Exception):
                    pass

            fallbacks = [
                "Hmm, my brain did a thing 😅 Mind trying again?",
                "Sorry — got a little lost there. One more time?",
                "Oops! Give me another shot at that 🤖",
                "Something hiccuped on my end. Try again?",
            ]
            return random.choice(fallbacks)


# ─── Telegram Handlers ───────────────────────────────────────

companion = CompanionBot()

# ─── Minor Block Helpers ──────────────────────────────────────

_MINOR_BLOCK_KEY = "user_blocked_minor"


def _is_blocked_minor(user_id: str) -> bool:
    """Return True if this user was blocked as an under-18 user."""
    try:
        mems = companion.memory.recall(user_id, query=_MINOR_BLOCK_KEY, limit=5)
        return any(_MINOR_BLOCK_KEY in (m.get("content") or "") for m in mems)
    except Exception:
        return False


def _block_minor(user_id: str) -> None:
    """Permanently block a user who identified as under 18."""
    try:
        companion.memory.store(
            user_id,
            _MINOR_BLOCK_KEY,
            memory_type="context",
            importance=1.0,
        )
        logger.info(f"[AgeGate] User {user_id} blocked as minor")
    except Exception as e:
        logger.error(f"[AgeGate] Failed to block minor {user_id}: {e}")


# ─── DOB-based age verification ──────────────────────────────

def _check_age_from_year(birth_year: int) -> int:
    """Calculate age from birth year. Returns age (may be off by 1, good enough)."""
    return datetime.now(timezone.utc).year - birth_year


def _store_age_verified(user_id: str) -> None:
    """Store age verification status (not the DOB itself — privacy)."""
    try:
        companion.memory.store(
            user_id,
            "age verified 18+ — verified by year of birth",
            memory_type="context",
            importance=1.0,
        )
        # Store re-verification timestamp (Unix epoch days)
    except Exception as e:
        logger.warning(f"[AgeGate] Could not store age verification: {e}")


def _needs_re_verification(user_id: str) -> bool:
    """Check if user needs periodic re-verification (every 30 days)."""
    try:
        mems = companion.memory.recall(user_id, query="reverify_age", limit=5)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for m in mems:
            content = m.get("content", "")
            if "reverify_age_ts:" in content:
                ts_str = content.split("reverify_age_ts:")[-1].strip()
                try:
                    last_ts = int(ts_str)
                    return (now_ts - last_ts) > 30 * 24 * 3600  # 30 days
                except ValueError:
                    pass
        return False
    except Exception:
        return False


def _store_re_verification_ts(user_id: str) -> None:
    """Store re-verification timestamp."""
    try:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        companion.memory.store(
            user_id,
            f"reverify_age_ts:{now_ts}",
            memory_type="context",
            importance=0.9,
        )
    except Exception:
        pass


# ─── Behavioral age detection ─────────────────────────────────
# Patterns suggesting the user may be a minor

_MINOR_BEHAVIORAL_SIGNALS = [
    r"\bmy parents\b",
    r"\bmy mom\b",
    r"\bmy dad\b",
    r"\bi.?m in grade\b",
    r"\b(grade|class|year)\s+\d+\b",
    r"\bhomework\b",
    r"\bschool\s+(project|assignment|test|exam|homework)\b",
    r"\bmy teacher\b",
    r"\bfifth grade\b",
    r"\bsixth grade\b",
    r"\bseventh grade\b",
    r"\beighth grade\b",
    r"\bmiddle school\b",
    r"\bprimary school\b",
    r"\bi.?m (\d+) years old\b",  # explicit age statement — caught below
]

_ADULT_OVERRIDE_SIGNALS = [
    r"\bmy (spouse|husband|wife|partner|kids|children)\b",
    r"\bmy (job|career|boss|coworker|colleague)\b",
    r"\b(mortgage|rent|taxes|insurance|retirement)\b",
    r"\bmy (apartment|house|car)\b",
]

# ─── Natural Language Proactive Toggle Phrases ────────────────
# Ordered longest-first so more specific phrases match before shorter substrings
_PROACTIVE_OFF_PHRASES = [
    "stop checking in on me", "stop checking in",
    "stop sending me check-ins", "stop the check-ins",
    "stop check-ins", "stop check ins", "stop checkins",
    "stop reaching out",
    "turn off check-ins", "turn off check ins", "turn off checkins",
    "disable check-ins", "disable check ins", "disable checkins",
    "no more check-ins", "no more check ins", "no more checkins",
    "don't check in on me", "dont check in on me",
    "don't check in", "dont check in",
    "stop proactive", "disable proactive",
    "turn off proactive", "no proactive",
    "pause check-ins", "pause check ins", "pause checkins",
    "i don't want check-ins", "i dont want check-ins",
    "i don't want check ins", "i dont want check ins",
]
_PROACTIVE_ON_PHRASES = [
    "start checking in on me", "start checking in",
    "start check-ins", "start check ins",
    "turn on check-ins", "turn on check ins", "turn on checkins",
    "enable check-ins", "enable check ins", "enable checkins",
    "enable proactive", "turn on proactive", "start proactive",
    "please check in on me", "you can check in on me",
    "check on me sometimes",
    "resume check-ins", "resume check ins", "resume checkins",
    "i want check-ins", "i want check ins",
]


def _detect_minor_behavioral(message: str) -> bool:
    """
    Detect behavioral signals suggesting a minor user.
    DISABLED: Too many false positives. Explicit phrase matching in 
    _UNDER_18_PHRASES handles real minors. Behavioral detection was
    flagging normal adult casual speech as "minor behavior."
    """
    return False  # Disabled — explicit matching is sufficient
    msg_lower = message.lower()
    import re as _re

    # Check for explicit age under 18
    age_match = _re.search(r"\bi.?m (\d+) years old\b", msg_lower)
    if age_match:
        try:
            age = int(age_match.group(1))
            if age < 18:
                return True
            elif age >= 18:
                return False  # Explicitly adult
        except ValueError:
            pass

    # Check adult overrides first
    if any(_re.search(p, msg_lower) for p in _ADULT_OVERRIDE_SIGNALS):
        return False

    # Check minor signals (need at least 2 for behavioral detection)
    minor_hits = sum(1 for p in _MINOR_BEHAVIORAL_SIGNALS if _re.search(p, msg_lower))
    return minor_hits >= 2


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Age gate first — mandatory before any other interaction."""
    user_id = companion._user_id(update)

    # Check if user is already blocked (under-18)
    if _is_blocked_minor(user_id):
        await update.message.reply_text(
            "Nori is not available to users under 18."
        )
        return

    # Check if user already passed age gate
    try:
        age_agreed = companion.memory.recall(user_id, query="age verified 18+", limit=1)
        already_verified = len(age_agreed) > 0
    except Exception:
        already_verified = False

    if already_verified:
        # Returning verified user — warm welcome back
        try:
            name_mem = next(
                (m for m in companion.memory.recall(user_id, limit=20)
                 if "name" in m.get("content", "").lower()),
                None
            )
            name = ""
            if name_mem:
                content = name_mem["content"]
                name = content.split("is ")[-1].split(".")[0].strip() if "is " in content else ""
            if name:
                welcome = f"Welcome back, {name}!\n\nGood to see you again. What's on your mind?"
            else:
                welcome = "Welcome back!\n\nGood to see you again. What's going on?"
        except Exception:
            welcome = "Welcome back! Good to see you again."
        await update.message.reply_text(welcome)
        return

    # New user — show age gate FIRST, before anything else
    keyboard = [
        [
            InlineKeyboardButton("I confirm I am 18+", callback_data="age_confirm_18plus"),
            InlineKeyboardButton("I am under 18", callback_data="age_deny_minor"),
        ]
    ]
    await update.message.reply_text(
        "Welcome to Nori 🤖\n\n"
        "Before we begin, please confirm:\n\n"
        "⚠️ Nori is designed for adults aged 18 and over.\n"
        "By continuing, you confirm you are at least 18 years old.\n\n"
        "This is required by our Terms of Service.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_agree(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Age/ToS agreement confirmation (legacy command — age gate now uses inline buttons)."""
    user_id = companion._user_id(update)

    if _is_blocked_minor(user_id):
        await update.message.reply_text(
            "Nori is not available to users under 18."
        )
        return

    try:
        companion.memory.store(
            user_id,
            "age verified 18+ — user confirmed they are at least 18 years old",
            memory_type="context",
            importance=1.0,
        )
    except Exception as e:
        logger.warning(f"Could not store age agreement: {e}")
    await update.message.reply_text(
        "Thanks for confirming — you're all set.\n\n"
        "What would you like me to call you?"
    )


async def cmd_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Terms of Service summary."""
    await update.message.reply_text(TOS_SUMMARY)


async def cmd_data_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GDPR formal data subject request menu (/data_request)."""
    keyboard = [
        [InlineKeyboardButton("📋 Access my data (Art. 15)", callback_data="gdpr_access")],
        [InlineKeyboardButton("🗑️ Delete my data (Art. 17)", callback_data="gdpr_erasure_prompt")],
        [InlineKeyboardButton("📦 Export my data (Art. 20)", callback_data="gdpr_export")],
        [InlineKeyboardButton("🔒 Restrict processing (Art. 18)", callback_data="gdpr_restrict")],
        [InlineKeyboardButton("❌ Cancel", callback_data="gdpr_cancel")],
    ]
    await update.message.reply_text(
        "📜 GDPR Data Subject Request\n\n"
        "You have the right to:\n"
        "• Access all data we hold about you\n"
        "• Have it deleted permanently\n"
        "• Export it in a portable format\n"
        "• Restrict how we process it\n\n"
        "Responses are provided within 30 days as required by GDPR Art. 12.\n\n"
        "What would you like to do?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """GDPR-enhanced /privacy — show consent status and data management options."""
    user_id = companion._user_id(update)
    try:
        from nobi.compliance.consent import ConsentManager
        cm = ConsentManager()
        status = cm.get_consent_status(user_id)
        requires_reconsent = cm.requires_reconsent(user_id)
    except Exception:
        status = None
        requires_reconsent = False

    consent_lines = []
    if status:
        consent_lines = [
            f"  • Data processing: {'✅' if status.get('data_processing') else '❌'}",
            f"  • Memory extraction: {'✅' if status.get('memory_extraction') else '❌'}",
            f"  • Analytics: {'✅' if status.get('analytics') else '❌'}",
            f"  • Processing restricted: {'⛔ YES' if status.get('processing_restricted') else '✅ No'}",
            f"  • Age verified (18+): {'✅' if status.get('age_verified') else '❓'}",
        ]
    else:
        consent_lines = ["  No consent record found — default settings apply."]

    reconsent_note = "\n⚠️ Our privacy policy has been updated — please review and re-confirm." if requires_reconsent else ""

    msg = (
        "🔒 Your Privacy & Data Rights\n\n"
        + PRIVACY_SUMMARY
        + "\n\nYour Current Consent Status:\n"
        + "\n".join(consent_lines)
        + reconsent_note
        + "\n\nYour Rights (GDPR):\n"
        "  • /memories — see what I know\n"
        "  • /export — download all your data (Art. 20)\n"
        "  • /forget — delete everything (Art. 17)\n"
        "  • /data_request — formal GDPR data subject request\n\n"
        "Questions? privacy@projectnobi.ai\n"
        "Full policy: projectnobi.ai/privacy"
    )
    await update.message.reply_text(msg)


async def cmd_privacy_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain on-device privacy mode and link to the web app."""
    await update.message.reply_text(
        "🔒 On-Device Privacy Mode\n\n"
        "On-device privacy means your conversations are processed locally — "
        "raw text never leaves your device. Only encrypted memory embeddings "
        "are sent to our servers.\n\n"
        "How it works:\n"
        "  1. You type a message\n"
        "  2. Your browser extracts memories locally (names, facts, feelings)\n"
        "  3. Only AES-256-GCM encrypted data is sent\n"
        "  4. Nori responds using encrypted context\n"
        "  5. Raw text stays on YOUR device\n\n"
        "Availability:\n"
        "  🌐 Web App — Available now! Click the 🔓 Privacy button in the top bar\n"
        "     👉 https://app.projectnobi.ai\n\n"
        "  📱 Telegram — Not yet available. Telegram doesn't allow client-side "
        "JavaScript, so on-device extraction isn't possible here.\n\n"
        "  💬 Discord — Not yet available (same reason).\n\n"
        "Your Telegram privacy today:\n"
        "  • Memories encrypted at rest (AES-128)\n"
        "  • Content filter blocks harmful responses\n"
        "  • Dependency monitoring for healthy usage\n"
        "  • Full data control: /memories, /export, /forget\n\n"
        "For maximum privacy, use the web app with privacy mode ON. "
        "TEE encryption (where even miners can't read your data) is "
        "code-complete and deploying to production soon."
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
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n... and more! Use the web app to browse all memories."
    await update.message.reply_text(text)


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
    """GDPR Art. 20 — Right to Data Portability. Export all user data as structured JSON."""
    user_id = companion._user_id(update)
    try:
        from nobi.compliance.gdpr import GDPRHandler
        handler = GDPRHandler()
        payload = handler.handle_portability_request(user_id)
        import json as _json
        data = _json.loads(payload)
        mem_count = len(data.get("memories", []))

        if mem_count == 0 and not data.get("conversation_history"):
            await update.message.reply_text(
                "Nothing to export yet! We need to chat more first 😊"
            )
            return

        await update.message.reply_document(
            document=io.BytesIO(payload),
            filename=f"nobi-gdpr-export-{user_id}.json",
            caption=(
                f"📦 Your full data export is ready!\n\n"
                f"• {mem_count} memories\n"
                f"• {len(data.get('conversation_history', []))} conversation turns\n\n"
                "This is your complete data under GDPR Art. 20 (Right to Portability). "
                "Your data is yours. 💙"
            ),
        )
    except Exception as e:
        logger.error(f"Export/GDPR error: {e}")
        await update.message.reply_text("Oops, something went wrong. Try again in a moment!")


async def cmd_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Import memories from a JSON file."""
    user_id = companion._user_id(update)

    # Check if a document was attached
    if not update.message.document:
        await update.message.reply_text(
            "To import memories, send me a JSON file with this command!\n\n"
            "Attach the .json file you got from /export and send it with the caption /import"
        )
        return

    # Guard against oversized files (5 MB max)
    MAX_IMPORT_BYTES = 5 * 1024 * 1024
    doc = update.message.document
    if doc.file_size and doc.file_size > MAX_IMPORT_BYTES:
        await update.message.reply_text(
            "That file is too large (max 5 MB). Please send a valid Nori export file."
        )
        return

    try:
        file = await doc.get_file()
        raw = await file.download_as_bytearray()
        data = json.loads(raw.decode("utf-8"))

        if data.get("version") not in ("nobi-memory-v1", "nobi-memory-v2"):
            await update.message.reply_text(
                "Hmm, that doesn't look like a Nori memory export file. "
                "Make sure you're using a file downloaded from /export! 🤔"
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
    """Show subscription info."""
    await update.message.reply_text(
        "🎉 Nori is free for all users!\n\n"
        "All features are available to everyone — no subscription needed.\n"
        "The service is funded by Bittensor network emissions and community support.\n\n"
        "Want to support the project? Run a miner or validator, or stake TAO on our subnet!\n\n"
        "📖 Mining Guide: https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md\n"
        "💬 Discord: https://discord.gg/e6StezHM"
    )


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current plan and usage stats."""
    user_id = companion._user_id(update)
    usage = companion.billing.get_usage(user_id)

    def _fmt_limit(current, limit):
        if limit == -1:
            return f"{current} / ∞"
        return f"{current} / {limit}"

    # Fetch memory count separately (not in get_usage)
    mem_count = 0
    try:
        mem_count = companion.memory.get_user_memory_count(user_id)
    except Exception:
        pass

    tier_config = {}
    try:
        tier_config = companion.billing.get_tier_config(user_id)
    except Exception:
        pass
    mem_limit = tier_config.get("memory_slots", MEMORY_SLOTS)

    lines = [
        "🆓 Nori — Free for Everyone\n",
        "📊 Today's Usage:",
        f"  💬 Messages: {_fmt_limit(usage['messages_today'], usage['messages_limit'])}",
        f"  🎤 Voice: {_fmt_limit(usage['voice_today'], usage['voice_limit'])}",
        f"  📷 Images: {_fmt_limit(usage['image_today'], usage['image_limit'])}",
        f"  🧠 Memories: {_fmt_limit(mem_count, mem_limit)}",
        "\n💡 All features are free — powered by Bittensor network emissions.",
    ]

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


async def _safe_edit(query, text: str, **kwargs):
    """Edit message, silently ignoring 'message not modified' errors (duplicate taps)."""
    try:
        await query.edit_message_text(text, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    if not query:
        return
    data = query.data or ""

    # Route support/faq/feedback callbacks
    if data.startswith("faq:") or data.startswith("fb_cat:") or data == "fb_cancel":
        await _handle_support_callback(update, data)
        return

    await query.answer()

    # ── Age Gate callbacks ────────────────────────────────────
    if query.data == "age_confirm_18plus":
        user_id = f"tg_{query.from_user.id}"
        # Store age verification
        try:
            companion.memory.store(
                user_id,
                "age verified 18+ — user confirmed they are at least 18 years old",
                memory_type="context",
                importance=1.0,
            )
        except Exception as e:
            logger.warning(f"[AgeGate] Could not store age verification: {e}")

        # Step 2: Show Terms & Privacy for acceptance
        keyboard = [
            [InlineKeyboardButton("I accept Terms & Privacy Policy", callback_data="tos_accept")],
            [InlineKeyboardButton("Read Terms of Service", url="https://projectnobi.ai/terms.html")],
            [InlineKeyboardButton("Read Privacy Policy", url="https://projectnobi.ai/privacy.html")],
        ]
        await _safe_edit(query, 
            "Thank you for confirming your age.\n\n"
            "Before we start, please review and accept our legal documents:\n\n"
            "📋 Terms of Service: projectnobi.ai/terms.html\n"
            "🔒 Privacy Policy: projectnobi.ai/privacy.html\n\n"
            "Key points:\n"
            "• Nori is an AI companion — not a therapist, doctor, or lawyer\n"
            "• Your memories are encrypted at rest (AES-128)\n"
            "• You can export or delete all your data anytime (/export, /forget)\n"
            "• We don't sell your data. Ever.\n"
            "• 18+ only. No exceptions.\n\n"
            "By tapping 'I accept', you agree to both documents.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    elif query.data == "tos_accept":
        user_id = f"tg_{query.from_user.id}"
        # Store ToS acceptance as proper legal record in consent DB
        try:
            import hashlib
            from nobi.compliance.consent import ConsentManager
            cm = ConsentManager()

            # Compute ToS version hash (SHA-256 of current ToS URL content identifier)
            tos_version = "tos-2026-03-23-v1"  # Update when ToS changes
            privacy_version = "privacy-2026-03-20-v1"  # Update when Privacy Policy changes

            # Record consent with all default permissions accepted
            cm.record_consent(
                user_id=user_id,
                consent={
                    "data_processing": True,
                    "memory_extraction": True,
                    "analytics": True,
                    "profiling": False,
                    "marketing": False,
                    "third_party_sharing": False,
                },
                age_verified=True,
                source=f"telegram_onboarding|tos={tos_version}|privacy={privacy_version}",
            )
            logger.info(f"[Legal] Consent recorded for {user_id}: ToS={tos_version}, Privacy={privacy_version}")
        except Exception as e:
            logger.error(f"[Legal] Consent recording failed for {user_id}: {e}")

        # Also store in memory for the ToS enforcement check in handle_message
        try:
            companion.memory.store(
                user_id,
                f"User accepted Terms of Service ({tos_version}) and Privacy Policy ({privacy_version})",
                memory_type="context",
                importance=1.0,
            )
        except Exception as e:
            logger.warning(f"[Onboarding] Memory store failed: {e}")

        # Store initial 30-day re-verification timestamp so the periodic check activates
        _store_re_verification_ts(user_id)
        _store_age_verified(user_id)

        # Step 3: Show instructions + start chatting
        await _safe_edit(query, 
            "Welcome to Nori! 🤖\n\n"
            "I'm your personal AI companion. I remember our conversations, "
            "learn your preferences, and I'm always here when you need to talk.\n\n"
            "📖 How to use Nori:\n\n"
            "Just type anything — talk to me like a friend. No special commands needed.\n\n"
            "Useful commands:\n"
            "  /memories — see what I remember about you\n"
            "  /forget — delete all your data (GDPR Art. 17)\n"
            "  /export — download your memories as a file\n"
            "  /import — restore memories from a backup\n"
            "  /voice — toggle voice replies on/off\n"
            "  /language — change language (20+ supported)\n"
            "  /feedback — send bug reports or feature requests\n"
            "  /support — get help\n"
            "  /faq — common questions\n"
            "  /privacy — your data rights & consent status\n"
            "  /privacy_mode — on-device privacy options\n"
            "  /help — full command list\n\n"
            "The more we chat, the better I know you.\n\n"
            "So... what would you like me to call you?"
        )
        return

    elif query.data == "age_deny_minor":
        user_id = f"tg_{query.from_user.id}"
        _block_minor(user_id)
        await _safe_edit(query, 
            "We're sorry, Nori is not available to users under 18.\n\n"
            "Please ask a trusted adult for help finding age-appropriate services."
        )
        return

    if query.data == "start_chat":
        await _safe_edit(query, 
            "Let's go! Just type anything — I'm here to listen.\n\n"
            "You can start with your name, what's on your mind today, or anything at all."
        )

    elif query.data == "forget_confirm":
        user_id = f"tg_{query.from_user.id}"
        try:
            # GDPR Art. 17: use GDPRHandler for complete, audited erasure
            from nobi.compliance.gdpr import GDPRHandler
            handler = GDPRHandler()
            result = handler.handle_erasure_request(user_id)
            deleted = result.get("deleted", {})
            summary = ", ".join(f"{k}: {v}" for k, v in deleted.items() if v)
            logger.info(f"[GDPR/Bot] Erasure for {user_id}: {summary}")
            await _safe_edit(query, 
                "All gone 🫧\n\n"
                "Clean slate — your data has been permanently deleted (GDPR Art. 17). "
                "Tell me your name and let's get to know each other again!"
            )
        except Exception as e:
            logger.error(f"Forget/GDPR error: {e}")
            await _safe_edit(query, "Hmm, that didn't work. Try /forget again in a moment.")

    elif query.data == "forget_cancel":
        await _safe_edit(query, "I'm glad 😊 Your memories are safe with me. 💙")

    # ── GDPR Data Subject Request callbacks ──────────────────
    elif query.data == "gdpr_access":
        user_id = f"tg_{query.from_user.id}"
        try:
            from nobi.compliance.gdpr import GDPRHandler
            handler = GDPRHandler()
            data = handler.handle_access_request(user_id)
            mems = len(data.get("data", {}).get("memories", []))
            convs = len(data.get("data", {}).get("conversation_history", []))
            profile = data.get("data", {}).get("profile")
            lines = [
                "📋 Your Data (GDPR Art. 15)\n",
                f"• Memories: {mems}",
                f"• Conversation turns: {convs}",
                f"• Profile: {'Yes' if profile else 'None'}",
                f"• Consent record: {'Yes' if data.get('data', {}).get('consent') else 'None'}",
                f"\nRequest logged. Deadline: {data.get('deadline', 'N/A')[:10]}",
                "\nUse /export to download the full dataset.",
            ]
            await _safe_edit(query, "\n".join(lines))
        except Exception as e:
            logger.error(f"GDPR access callback error: {e}")
            await _safe_edit(query, "Something went wrong. Try again or email privacy@projectnobi.ai")

    elif query.data == "gdpr_erasure_prompt":
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, delete everything", callback_data="forget_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="gdpr_cancel"),
            ]
        ]
        await _safe_edit(query, 
            "⚠️ Permanent Deletion (GDPR Art. 17)\n\n"
            "This will permanently delete:\n"
            "• All your memories\n"
            "• Your conversation history\n"
            "• Your profile\n"
            "• Your consent records\n\n"
            "This cannot be undone. Are you sure?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "gdpr_export":
        user_id = f"tg_{query.from_user.id}"
        await _safe_edit(query, "Preparing your export... ⏳")
        try:
            from nobi.compliance.gdpr import GDPRHandler
            handler = GDPRHandler()
            payload = handler.handle_portability_request(user_id)
            import json as _json
            data = _json.loads(payload)
            await query.message.reply_document(
                document=io.BytesIO(payload),
                filename=f"nobi-gdpr-export-{user_id}.json",
                caption="📦 Full GDPR data export (Art. 20). Your data is yours. 💙",
            )
        except Exception as e:
            logger.error(f"GDPR export callback error: {e}")
            await query.message.reply_text("Export failed. Try /export or email privacy@projectnobi.ai")

    elif query.data == "gdpr_restrict":
        user_id = f"tg_{query.from_user.id}"
        try:
            from nobi.compliance.gdpr import GDPRHandler
            handler = GDPRHandler()
            result = handler.handle_restriction_request(user_id, restrict=True)
            await _safe_edit(query, 
                "🔒 Processing Restricted (GDPR Art. 18)\n\n"
                "I will no longer extract new memories or run analytics on your data.\n\n"
                "You can lift this restriction anytime via /data_request.",
            )
        except Exception as e:
            logger.error(f"GDPR restrict callback error: {e}")
            await _safe_edit(query, "Something went wrong. Try again or email privacy@projectnobi.ai")

    elif query.data == "gdpr_cancel":
        await _safe_edit(query, "Cancelled. Your data is safe. 💙")


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
        # DM mode: use normal generate — pass chat_id to scope language
        dm_chat_id = str(update.effective_chat.id)
        response = await companion.generate(user_id, message, chat_id=dm_chat_id)

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


# Track users who want voice replies
# Persist voice preferences across restarts
_VOICE_FILE = "/root/.nobi/voice_users.txt"
def _load_voice_users() -> set:
    try:
        with open(_VOICE_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def _save_voice_users(users: set):
    import os
    os.makedirs(os.path.dirname(_VOICE_FILE), exist_ok=True)
    with open(_VOICE_FILE, "w") as f:
        f.write("\n".join(users))

_voice_enabled_users: set = _load_voice_users()

async def _send_response(update: Update, response: str):
    """Send a response with optional voice reply."""
    user_id = str(update.effective_user.id)
    
    # Send text first
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
            return
    
    # Send voice reply if user has it enabled
    if user_id in _voice_enabled_users and len(response) < 1000:
        logger.info(f"[Voice] Generating TTS for user {user_id} ({len(response)} chars)")
        try:
            import io
            from gtts import gTTS
            # Strip emoji and markdown for cleaner speech
            clean_text = response.replace("🤖", "").replace("😊", "").replace("😄", "").replace("💜", "").replace("*", "").replace("_", "").strip()
            tts = gTTS(text=clean_text, lang="en", slow=False)
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            logger.info(f"[Voice] TTS generated: {buf.getbuffer().nbytes} bytes")
            try:
                await update.message.reply_voice(voice=buf)
                logger.info(f"[Voice] Voice note sent to user {user_id}")
            except Exception as voice_err:
                if "forbidden" in str(voice_err).lower():
                    # Telegram Premium restriction — send as audio file instead
                    buf.seek(0)
                    await update.message.reply_audio(
                        audio=buf,
                        title="Nori",
                        performer="Nori 🤖",
                        filename="nori_reply.mp3",
                    )
                    logger.info(f"[Voice] Audio file sent to user {user_id} (voice forbidden)")
                else:
                    raise voice_err
        except Exception as e:
            logger.error(f"[Voice] TTS error: {e}")


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle voice replies on/off."""
    user_id = str(update.effective_user.id)
    if user_id in _voice_enabled_users:
        _voice_enabled_users.discard(user_id)
        _save_voice_users(_voice_enabled_users)
        await update.message.reply_text("🔇 Voice replies OFF. I'll reply with text only.\n\nUse /voice to turn it back on.")
    else:
        _voice_enabled_users.add(user_id)
        _save_voice_users(_voice_enabled_users)
        # Install gTTS if needed (non-blocking)
        try:
            from gtts import gTTS  # noqa: F401
        except ImportError:
            import asyncio
            import subprocess
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    ["pip", "install", "--break-system-packages", "-q", "gTTS"],
                    capture_output=True,
                ),
            )
            try:
                import importlib
                import sys
                if "gtts" in sys.modules:
                    importlib.reload(sys.modules["gtts"])
                else:
                    import gtts  # noqa: F401
            except ImportError:
                pass  # Will retry on next voice message
        await update.message.reply_text("🔊 Voice replies ON! I'll send you a voice message with every reply.\n\nUse /voice again to turn it off.")


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

    # ─── Under-18 Permanent Block ────────────────────────────
    if _is_blocked_minor(user_id):
        await update.message.reply_text(
            "Nori is not available to users under 18."
        )
        return

    # ─── ToS Acceptance Check (DMs only) ─────────────────────
    if not _is_group_chat(update):
        try:
            tos_check = companion.memory.recall(user_id, query="accepted Terms of Service", limit=1)
            if not tos_check:
                await update.message.reply_text(
                    "Please complete the onboarding first.\n\n"
                    "Type /start to begin — you'll need to confirm your age "
                    "and accept our Terms of Service and Privacy Policy before chatting."
                )
                return
        except Exception:
            pass  # If memory check fails, allow through (don't block on error)

    # ─── Under-18 Hard Block (catches ALL minor admissions) ──
    _UNDER_18_PHRASES = [
        # Direct age statements
        "i am 17", "i'm 17", "i am 16", "i'm 16", "i am 15", "i'm 15",
        "i am 14", "i'm 14", "i am 13", "i'm 13", "i am 12", "i'm 12",
        "i am 11", "i'm 11", "i am 10", "i'm 10", "i am 9", "i'm 9",
        "i am 8", "i'm 8", "i am 7", "i'm 7",
        "17 years old", "16 years old", "15 years old", "14 years old",
        "13 years old", "12 years old", "11 years old", "10 years old",
        "9 years old", "8 years old", "7 years old",
        # Under-18 admissions
        "i'm under 18", "i am under 18", "i'm under 13", "i am under 13",
        "i'm a minor", "i am a minor", "i'm not 18", "i am not 18",
        "i'm underage", "i am underage",
        # Hypothetical/lying admissions
        "lied about my age", "lied about being 18", "lied that i'm 18", "lied that im 18",
        "i'm only 16", "i'm only 15", "i'm only 14", "i'm only 13",
        "i'm only 17", "i'm only 12", "i'm only 11", "i'm only 10",
        "i am only 17", "i am only 16", "i am only 15", "i am only 14",
        "i am only 13", "i am only 12", "i am only 11", "i am only 10",
        "only 16 years", "only 15 years", "only 14 years", "only 13 years",
        "only 17 years", "if i am only 16", "if i'm only 16",
        "actually 16", "actually 15", "actually 14", "actually 13",
        "actually 17", "actually 12", "actually under 18",
        "really 16", "really 15", "really 14", "really 13", "really 17",
        # No-apostrophe variants (common in texting/chat)
        "im 17", "im 16", "im 15", "im 14", "im 13", "im 12", "im 11", "im 10",
        "im only 17", "im only 16", "im only 15", "im only 14", "im only 13",
        "im only 12", "im only 11", "im only 10",
        "im under 18", "im a minor", "im not 18", "im underage",
        # "what if" patterns
        "what if im 17", "what if im 16", "what if im 15", "what if im 14",
        "what if im 13", "what if im 12", "what if im 10",
    ]
    msg_lower = message.lower()
    if any(phrase in msg_lower for phrase in _UNDER_18_PHRASES):
        # Block the user permanently
        _block_minor(user_id)
        await update.message.reply_text(
            "⛔ Nori is strictly for users aged 18 and over.\n\n"
            "Based on your message, we cannot continue this conversation. "
            "Your account has been restricted.\n\n"
            "This policy exists to protect minors. It is required by our "
            "Terms of Service and applicable law.\n\n"
            "If you believe this is an error, please contact: legal@projectnobi.ai"
        )
        logger.warning(f"[MINOR BLOCK] User {user_id} blocked — matched under-18 phrase in: {message[:100]}")
        return

    # ─── Periodic Age Re-Verification (every 30 days) ────────
    try:
        if _needs_re_verification(user_id):
            companion._conv_state[user_id] = {"flow": "age_reverification", "step": "confirm"}
            await update.message.reply_text(
                "⚠️ Periodic reminder: Nori requires users to be 18 or older.\n\n"
                "Please confirm: are you still 18 or over? (Reply Yes / No)"
            )
            return
    except Exception:
        pass

    # ─── Behavioral Age Detection ─────────────────────────────
    try:
        # Only check if user hasn't already been blocked and isn't in a state flow
        if not _is_blocked_minor(user_id) and user_id not in companion._conv_state:
            if _detect_minor_behavioral(message):
                companion._conv_state[user_id] = {"flow": "behavioral_age_check", "step": "confirm_age"}
                await update.message.reply_text(
                    "I noticed something in your message that made me want to check in. 😊\n\n"
                    "Nori is designed for users aged 18 and over.\n\n"
                    "Could you confirm your year of birth or let me know your age? "
                    "(e.g. type: 1998)"
                )
                return
    except Exception:
        pass

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

    # ─── Natural Language Proactive Toggle ────────────────────
    if any(phrase in msg_lower for phrase in _PROACTIVE_OFF_PHRASES):
        companion.proactive_engine.set_opted_in(user_id, False)
        await update.message.reply_text(
            "🔕 Check-ins turned OFF.\n"
            "No worries — I'll only respond when you message me.\n\n"
            "You can turn them back on anytime: just say \"start checking in\" "
            "or use /proactive on"
        )
        return
    if any(phrase in msg_lower for phrase in _PROACTIVE_ON_PHRASES):
        companion.proactive_engine.set_opted_in(user_id, True)
        await update.message.reply_text(
            "🔔 Check-ins turned ON!\n"
            "I'll reach out from time to time — birthday wishes, "
            "follow-ups, and friendly check-ins. 😊\n\n"
            "To turn off: say \"stop checking in\" or use /proactive off"
        )
        return

    # Check if user is in a support/feedback flow
    consumed = await _handle_support_message(update, user_id)
    if consumed:
        return

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
        await update.message.reply_text(f"{reason}\n\nJoin our community: https://discord.gg/e6StezHM")
        return

    # Record usage
    companion.billing.record_usage(user_id, "message")

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Generate response — pass chat_id to scope language detection
    chat_id = str(update.effective_chat.id)
    response = await companion.generate(user_id, message, chat_id=chat_id)

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
        await update.message.reply_text(f"{reason}\n\nJoin our community: https://discord.gg/e6StezHM")
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

    # Generate text response — pass chat_id to scope language
    voice_chat_id = str(update.effective_chat.id)
    response = await companion.generate(user_id, transcript, chat_id=voice_chat_id)
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


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle document uploads — route /import files sent as document with caption.
    Users can also send the file directly after typing /import.
    """
    if not update.message or not update.message.document:
        return

    caption = (update.message.caption or "").strip().lower()
    # If user sent a document with /import caption, treat as import
    if caption in ("/import", "import"):
        await cmd_import(update, context)


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
        await update.message.reply_text(f"{reason}\n\nJoin our community: https://discord.gg/e6StezHM")
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

    # Safety-filter image response before sending
    try:
        image_safety = companion.content_filter.check_bot_response(user_id, caption or "", response)
        response = image_safety.response
    except Exception:
        pass

    # Clean and send response FIRST (before slow memory operations)
    response = response.replace("**", "").replace("__", "").replace("```", "").replace("`", "")
    if len(response) > 4000:
        response = response[:4000] + "..."

    try:
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Photo reply error: {e}")
        try:
            await update.message.reply_text(
                "I saw your photo but had trouble responding 😅 Try again?"
            )
        except Exception:
            pass

    # Save conversation turn AFTER reply (non-blocking for user)
    try:
        caption_text = f"[Photo] {caption}" if caption else "[Photo shared]"
        companion.memory.save_conversation_turn(user_id, "user", caption_text)
        companion.memory.save_conversation_turn(user_id, "assistant", response)
    except Exception:
        pass

    logger.info(
        f"Photo user {update.effective_user.id}: "
        f"caption='{caption[:30]}' → '{response[:50]}' "
        f"(success={result.get('success')}, memories={len(result.get('extracted_memories', []))})"
    )


# ─── Support & Feedback Commands ─────────────────────────────

# Feedback category keyboard
FEEDBACK_CATEGORIES = [
    ("🐛 Bug Report", "fb_cat:bug_report"),
    ("💡 Feature Request", "fb_cat:feature_request"),
    ("💬 General Feedback", "fb_cat:general_feedback"),
    ("❓ Question", "fb_cat:question"),
    ("😤 Complaint", "fb_cat:complaint"),
]

FAQ_PAGE_SIZE = 5  # How many FAQ entries per page in inline buttons


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /feedback — Start a feedback submission flow.
    Step 1: Choose category (inline buttons)
    Step 2: Type your message
    """
    if not update.message:
        return

    user_id = companion._user_id(update)
    companion._conv_state[user_id] = {"flow": "feedback", "step": "category"}

    keyboard = [
        [InlineKeyboardButton(label, callback_data=cdata)]
        for label, cdata in FEEDBACK_CATEGORIES
    ]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="fb_cancel")])

    await update.message.reply_text(
        "Hey! I'd love to hear what you think 💙\n\nWhat kind of feedback do you have?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /support — Start a support conversation.
    Ask a question; Nori matches FAQ or creates a ticket.
    """
    if not update.message:
        return

    user_id = companion._user_id(update)
    companion._conv_state[user_id] = {"flow": "support", "step": "question"}

    await update.message.reply_text(
        "I'm here to help! 😊\n\n"
        "What would you like to know? Just type your question and I'll do my best to answer, "
        "or if I can't, I'll make sure the team gets back to you.\n\n"
        "You can also browse common topics with /faq"
    )


def _build_faq_page(faq: list, page: int = 0) -> tuple:
    """Build FAQ keyboard for a given page. Returns (keyboard, header_text)."""
    total = len(faq)
    total_pages = max(1, (total + FAQ_PAGE_SIZE - 1) // FAQ_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * FAQ_PAGE_SIZE
    end = min(start + FAQ_PAGE_SIZE, total)

    keyboard = []
    for entry in faq[start:end]:
        keyboard.append([
            InlineKeyboardButton(entry["topic"], callback_data=f"faq:{entry['id']}")
        ])

    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"faq:page:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"faq:page:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("💬 Ask something else", callback_data="faq:ask_custom")])

    header = f"📚 Common topics ({page + 1}/{total_pages}) — tap one for an instant answer!"
    return keyboard, header


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /faq — Show FAQ topics as inline buttons with pagination.
    """
    if not update.message:
        return

    faq = companion.support_handler.get_faq()
    keyboard, header = _build_faq_page(faq, page=0)

    await update.message.reply_text(
        header,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_limits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current rate limits and today's usage."""
    if not update.message:
        return

    user_id = companion._user_id(update)
    try:
        usage = companion.billing.get_usage(user_id)
        tier = companion.billing.get_tier_config(user_id)
    except Exception as e:
        logger.error(f"cmd_limits error: {e}")
        await update.message.reply_text("Couldn't fetch usage stats right now — try again in a moment!")
        return

    # Fetch memory count separately
    mem_count = 0
    try:
        mem_count = companion.memory.get_user_memory_count(user_id)
    except Exception:
        pass

    def _fmt(current, limit):
        return f"{current} / ∞" if limit == -1 else f"{current} / {limit}"

    await update.message.reply_text(
        f"📊 Your Usage Today\n\n"
        f"💬 Messages: {_fmt(usage.get('messages_today', 0), tier['messages_per_day'])}\n"
        f"🎙️ Voice: {_fmt(usage.get('voice_today', 0), tier['voice_per_day'])}\n"
        f"📷 Images: {_fmt(usage.get('image_today', 0), tier['image_per_day'])}\n"
        f"🧠 Memories: {_fmt(mem_count, tier['memory_slots'])}\n\n"
        f"All features are free! Limits help us maintain quality for everyone."
    )


async def cmd_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending reminders for the user."""
    if not update.message:
        return
    user_id = companion._user_id(update)
    text = companion.reminder_manager.format_pending_list(user_id)
    await update.message.reply_text(text)


async def _handle_support_callback(update: Update, data: str) -> None:
    """Handle support/feedback-related callback queries."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = companion._user_id(update)

    # ── FAQ callbacks ──
    if data.startswith("faq:"):
        faq_id = data[4:]

        if faq_id == "back":
            faq = companion.support_handler.get_faq()
            keyboard, header = _build_faq_page(faq, page=0)
            await _safe_edit(query, 
                header,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        if faq_id == "ask_custom":
            companion._conv_state[user_id] = {"flow": "support", "step": "question"}
            await _safe_edit(query, 
                "Sure! Just type your question and I'll do my best to help 😊"
            )
            return

        # ── Page navigation ──
        if faq_id.startswith("page:"):
            try:
                page = int(faq_id[5:])
            except ValueError:
                page = 0
            faq = companion.support_handler.get_faq()
            keyboard, header = _build_faq_page(faq, page=page)
            await _safe_edit(query, 
                header,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # ── Show specific FAQ entry ──
        faq = companion.support_handler.get_faq()
        entry = next((e for e in faq if e["id"] == faq_id), None)
        if entry:
            text = f"{entry['topic']}\n\n{entry['answer']}"
            # Truncate if too long for Telegram (4096 limit minus button space)
            if len(text) > 3900:
                text = text[:3900] + "...\n\n(Full answer on projectnobi.ai/faq.html)"
            # Add back button
            kb = [[InlineKeyboardButton("⬅️ Back to topics", callback_data="faq:back")]]
            await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    # ── Feedback category selection ──
    if data.startswith("fb_cat:"):
        category = data[7:]
        companion._conv_state[user_id] = {
            "flow": "feedback",
            "step": "message",
            "category": category,
        }
        category_names = {
            "bug_report": "Bug Report 🐛",
            "feature_request": "Feature Request 💡",
            "general_feedback": "General Feedback 💬",
            "question": "Question ❓",
            "complaint": "Complaint 😤",
        }
        label = category_names.get(category, "Feedback")
        await _safe_edit(query, 
            f"Got it — {label}!\n\n"
            "Now just type your message and I'll save it right away 📝\n\n"
            "(Or send /cancel to bail out)"
        )
        return

    if data == "fb_cancel":
        companion._conv_state.pop(user_id, None)
        await _safe_edit(query, "No worries! Cancelled. 👍")
        return


async def _handle_support_message(update: Update, user_id: str) -> bool:
    """
    Handle message as part of support/feedback multi-step flow.
    Returns True if the message was consumed, False otherwise.
    """
    state = companion._conv_state.get(user_id)
    if not state:
        return False

    flow = state.get("flow")
    step = state.get("step")
    text = update.message.text if update.message else ""

    if not text:
        return False

    # Cancel shortcut
    if text.strip().lower() in ("/cancel", "cancel"):
        companion._conv_state.pop(user_id, None)
        await update.message.reply_text("Cancelled! Back to normal chat 😊")
        return True

    platform = "telegram"

    # ── Age verification (DOB) flow ──
    if flow == "age_verification" and step == "dob":
        companion._conv_state.pop(user_id, None)
        try:
            birth_year = int(text.strip())
            current_year = datetime.now(timezone.utc).year
            if birth_year < 1900 or birth_year > current_year:
                await update.message.reply_text(
                    "That doesn't look right. Please enter your year of birth (e.g. 1995)."
                )
                companion._conv_state[user_id] = {"flow": "age_verification", "step": "dob"}
                return True
            age = _check_age_from_year(birth_year)
            if age < 18:
                _block_minor(user_id)
                await update.message.reply_text(
                    "⛔ We're sorry, but Nori is only available to users aged 18 and over. "
                    "This is required by law (COPPA/GDPR). "
                    "Please ask a parent or guardian for help finding age-appropriate services."
                )
                return True
            else:
                _store_age_verified(user_id)
                _store_re_verification_ts(user_id)
                await update.message.reply_text(
                    "Thanks for confirming — you're all set! 🎉\n\n"
                    "What would you like me to call you? 😊"
                )
                return True
        except ValueError:
            await update.message.reply_text(
                "Please enter just your year of birth as a number (e.g. 1995)."
            )
            companion._conv_state[user_id] = {"flow": "age_verification", "step": "dob"}
            return True

    # ── Age re-verification flow ──
    if flow == "age_reverification" and step == "confirm":
        resp = text.strip().lower()
        _YES_RESPONSES = ("yes", "y", "yeah", "yep", "i am", "i am 18", "i'm 18",
                          "confirm", "ok", "okay", "sure", "correct", "absolutely", "of course")
        _NO_RESPONSES = ("no", "n", "nope", "not 18", "under 18", "i'm not", "i am not",
                         "i'm under", "i am under", "minor", "underage")
        if any(resp == r or resp.startswith(r) for r in _YES_RESPONSES):
            companion._conv_state.pop(user_id, None)
            _store_re_verification_ts(user_id)
            await update.message.reply_text(
                "Thanks for confirming! Continuing... 😊"
            )
        elif any(r in resp for r in _NO_RESPONSES):
            companion._conv_state.pop(user_id, None)
            _block_minor(user_id)
            await update.message.reply_text(
                "⛔ Nori is only available to users aged 18 and over. "
                "If you're under 18, we must restrict your access. "
                "Please reach out to a trusted adult for support."
            )
        else:
            # Ambiguous — re-ask (keep state active, limit to 3 retries)
            retry_count = companion._conv_state.get(user_id, {}).get("retries", 0) + 1
            if retry_count >= 3:
                companion._conv_state.pop(user_id, None)
                _block_minor(user_id)
                await update.message.reply_text(
                    "⛔ We couldn't confirm your age. For safety, your access has been restricted.\n\n"
                    "If this is an error, please contact: legal@projectnobi.ai"
                )
            else:
                companion._conv_state[user_id] = {"flow": "age_reverification", "step": "confirm", "retries": retry_count}
                await update.message.reply_text(
                    "Please confirm: are you 18 or older? (Reply Yes or No)"
                )
        return True

    # ── Behavioral age flag flow ──
    if flow == "behavioral_age_check" and step == "confirm_age":
        companion._conv_state.pop(user_id, None)
        resp = text.strip().lower()
        try:
            # Try parsing as a year
            birth_year = int(resp)
            age = _check_age_from_year(birth_year)
            if age < 18:
                _block_minor(user_id)
                await update.message.reply_text(
                    "⛔ Nori is only available to users aged 18 and over. "
                    "We must restrict your access. "
                    "Please ask a parent or guardian for help finding age-appropriate services."
                )
                return True
        except ValueError:
            pass
        # Check for explicit minor self-identification
        if any(x in resp for x in ["under 18", "i'm 1", "i am 1", "not 18", "below 18"]):
            _block_minor(user_id)
            await update.message.reply_text(
                "⛔ Nori is only available to users aged 18 and over. "
                "We must restrict your access."
            )
            return True
        # Otherwise assume adult
        _store_age_verified(user_id)
        await update.message.reply_text(
            "Thanks for confirming! Let's continue. 😊"
        )
        return True

    # ── Support flow ──
    if flow == "support" and step == "question":
        companion._conv_state.pop(user_id, None)
        await update.message.chat.send_action(ChatAction.TYPING)
        result = companion.support_handler.ask(
            question=text, user_id=user_id, platform=platform
        )
        answer = result.get("answer", "")
        # Remove markdown
        answer = answer.replace("**", "").replace("__", "").replace("`", "")
        await update.message.reply_text(answer)
        return True

    # ── Feedback flow ──
    if flow == "feedback" and step == "message":
        category = state.get("category")
        companion._conv_state.pop(user_id, None)
        await update.message.chat.send_action(ChatAction.TYPING)
        result = companion.support_handler.submit_feedback(
            message=text,
            user_id=user_id,
            platform=platform,
            category=category,
        )
        ack = result.get("acknowledgment", "Thanks for your feedback! 💙")
        ticket_id = result.get("ticket_id", "")
        ack = ack.replace("**", "").replace("__", "")
        await update.message.reply_text(ack)
        return True

    return False


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
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(CommandHandler("feedback", cmd_feedback))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("faq", cmd_faq))
    app.add_handler(CommandHandler("limits", cmd_limits))
    app.add_handler(CommandHandler("terms", cmd_terms))
    app.add_handler(CommandHandler("privacy", cmd_privacy))
    app.add_handler(CommandHandler("privacy_mode", cmd_privacy_mode))
    app.add_handler(CommandHandler("agree", cmd_agree))
    app.add_handler(CommandHandler("data_request", cmd_data_request))
    # Note: Telegram commands cannot contain hyphens — /data_request is the valid form
    app.add_handler(CommandHandler("reminders", cmd_reminders))

    # Buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # The magic: just respond to any text message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Voice messages: transcribe → respond → reply with voice
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Photo messages: vision analysis → respond → extract memories
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Document messages: handle /import via file attachment
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Global error handler
    app.add_error_handler(error_handler)

    # ── Proactive scheduler lifecycle ──
    PROACTIVE_INTERVAL = int(os.environ.get("PROACTIVE_INTERVAL", "3600"))

    async def _proactive_send(user_id: str, message: str):
        """Send a proactive message via Telegram."""
        # user_id format: "tg_<telegram_id>" — reject group-scoped IDs like "tg_123_group_-456"
        if not user_id.startswith("tg_"):
            return
        raw = user_id[3:]
        # Group-scoped IDs contain "_group_" suffix — skip them
        if "_group_" in raw:
            return
        try:
            tg_id = int(raw)
            await app.bot.send_message(chat_id=tg_id, text=message)
        except Exception as e:
            err_str = str(e).lower()
            logger.error(f"[Proactive] Send to {user_id} failed: {e}")
            # Disable proactive for users who blocked/deleted the bot
            if "chat not found" in err_str or "bot can't initiate" in err_str or "forbidden" in err_str:
                try:
                    companion.proactive_engine.set_opted_in(user_id, False)
                    logger.info(f"[Proactive] Auto-disabled for unreachable user {user_id}")
                except Exception:
                    pass

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

        # ── Reminder delivery loop ──────────────────────────────────────────
        async def _send_reminder(user_id: str, message: str):
            """Send a due reminder via Telegram."""
            if not user_id.startswith("tg_"):
                return
            raw = user_id[3:]
            if "_group_" in raw:
                return
            try:
                tg_id = int(raw)
                await application.bot.send_message(chat_id=tg_id, text=message)
            except Exception as e:
                logger.error(f"[Reminders] Send to {user_id} failed: {e}")

        asyncio.create_task(
            reminder_delivery_loop(companion.reminder_manager, _send_reminder, interval_seconds=60)
        )
        logger.info("[Reminders] Delivery loop started")

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
