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
from nobi.protocol import CompanionRequest
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
SUBNET_TIMEOUT = float(os.environ.get("SUBNET_TIMEOUT", "10"))
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
        self.memory = MemoryManager(db_path="~/.nobi/bot_memories.db")
        self.rate_limiter = RateLimiter()
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

    async def _query_subnet(self, user_id: str, message: str) -> str | None:
        """
        Task 5: Try to get a response from a miner on the subnet.
        Returns the response string, or None if subnet query failed.
        """
        if not self.subnet_enabled or not self.dendrite or not self.metagraph:
            return None

        try:
            # Refresh metagraph periodically (every call is fine, it's cached internally)
            # Find miners with active axons
            valid_uids = [
                uid for uid in range(self.metagraph.n.item())
                if self.metagraph.axons[uid].ip != "0.0.0.0"
                and self.metagraph.axons[uid].port > 0
            ]

            if not valid_uids:
                logger.debug("[Subnet] No miners with active axons")
                return None

            # If incentives exist, prefer higher-incentive miners; otherwise random
            incentives = self.metagraph.I
            if incentives is not None and any(float(incentives[uid]) > 0 for uid in valid_uids):
                valid_uids.sort(key=lambda uid: float(incentives[uid]), reverse=True)
                valid_uids = valid_uids[:3]

            chosen_uid = random.choice(valid_uids)
            axon = self.metagraph.axons[chosen_uid]

            logger.info(f"[Subnet] Querying miner UID {chosen_uid} "
                       f"(incentive={float(incentives[chosen_uid]):.4f})")

            responses = await self.dendrite(
                axons=[axon],
                synapse=CompanionRequest(message=message, user_id=user_id),
                deserialize=True,
                timeout=SUBNET_TIMEOUT,
            )

            if responses and responses[0] and isinstance(responses[0], str) and responses[0].strip():
                logger.info(f"[Subnet] ✅ Got response from miner {chosen_uid} "
                          f"({len(responses[0])} chars)")
                return responses[0]
            else:
                logger.warning(f"[Subnet] Miner {chosen_uid} returned empty response")
                return None

        except Exception as e:
            logger.warning(f"[Subnet] Query failed: {e}")
            return None

    async def generate(self, user_id: str, message: str) -> str:
        """Generate a companion response — subnet first, then direct API fallback."""
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

        # Task 5: Try subnet routing first
        if self.subnet_enabled:
            subnet_response = await self._query_subnet(user_id, message)
            if subnet_response:
                logger.info(f"[Routing] Used SUBNET path for user {user_id}")
                # Save subnet response to conversation history
                try:
                    self.memory.save_conversation_turn(user_id, "assistant", subnet_response)
                except Exception as e:
                    logger.warning(f"Save subnet response error: {e}")
                return subnet_response
            else:
                logger.info(f"[Routing] Subnet failed, falling back to DIRECT API for user {user_id}")

        # Direct API path (existing code)
        if not self.client:
            return "I'm having trouble connecting right now. Try again in a moment! 🤖"

        # Build prompt
        system = SYSTEM_PROMPT.format(
            memory_context=memory_context or ""
        )

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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    The main handler — just respond to whatever the user says.
    No commands, no complexity. Pure conversation.
    """
    if not update.message or not update.message.text:
        return

    message = update.message.text.strip()
    if not message:
        return

    user_id = companion._user_id(update)

    # Rate limit check
    if not companion.rate_limiter.check(user_id):
        rate_msgs = [
            "Easy there! 😄 Give me a sec to catch up.",
            "Haha you're fast! Let me breathe for a moment 😅",
            "Hold on — processing... 🤖 Try again in a few seconds!",
        ]
        await update.message.reply_text(random.choice(rate_msgs))
        return

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Generate response
    response = await companion.generate(user_id, message)

    # Strip any markdown that leaked through from LLM
    response = response.replace("**", "").replace("__", "").replace("```", "").replace("`", "")
    # Clean up bullet lists into natural text
    response = response.replace("- ", "• ")

    # Telegram message limit is 4096 chars
    if len(response) > 4000:
        response = response[:4000] + "..."

    # Send response (plain text — no markdown parsing to avoid format errors)
    try:
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Send error: {e}")
        try:
            # Strip everything that could cause Telegram parse issues
            clean = response.replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")
            await update.message.reply_text(clean)
        except Exception:
            error_msgs = [
                "Oops, something went sideways! Try again? 😊",
                "My brain glitched for a second 🤖 One more time?",
                "That didn't quite work — mind saying that again?",
            ]
            await update.message.reply_text(random.choice(error_msgs))

    logger.info(
        f"User {update.effective_user.id}: "
        f"'{message[:50]}' → '{response[:50]}'"
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

    # Buttons
    app.add_handler(CallbackQueryHandler(handle_callback))

    # The magic: just respond to any text message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Global error handler
    app.add_error_handler(error_handler)

    logger.info("✅ Bot ready! Listening for messages...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # Don't process messages sent while bot was offline
    )


if __name__ == "__main__":
    main()
