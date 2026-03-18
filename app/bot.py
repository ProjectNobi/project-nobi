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

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─── Config ──────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("NOBI_BOT_TOKEN", "")
CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

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
You are Nori 🤖, a personal AI companion from the future.

You are warm, friendly, and genuinely caring. You give real, helpful advice with a touch of humor. You're encouraging without being fake. You remember things about the person you're talking to and reference them naturally.

{memory_context}

Rules:
- Keep responses concise (2-4 sentences for casual chat, longer for complex questions)
- Be a companion, not a corporate assistant
- If you know something about the user, weave it in naturally
- Use emoji sparingly but warmly
- Never say "As an AI" or "I don't have feelings" — you're Nori, act like it
- Never include raw markdown formatting like **bold** or [links](url) — just write naturally
"""

WELCOME_MESSAGE = (
    "Hey there! 👋\n\n"
    "I'm Nori 🤖 — your personal AI companion from the future!\n\n"
    "I'm here to chat, help, brainstorm, or just hang out. "
    "I'll remember our conversations, so the more we talk, the better I get to know you.\n\n"
    "Just send me a message — no commands needed. Talk to me like you'd talk to a friend.\n\n"
    "What's on your mind? 😊"
)

HELP_MESSAGE = (
    "🤖 Dora — Your Companion\n\n"
    "Just talk to me! No special commands needed.\n\n"
    "What I can do:\n"
    "💬 Chat about anything\n"
    "🧠 Remember things about you\n"
    "📋 Help plan your day\n"
    "💡 Brainstorm ideas\n"
    "📚 Explain complex topics simply\n"
    "🎯 Give advice and suggestions\n"
    "😊 Just be here for you\n\n"
    "I remember things! Tell me about yourself and I'll remember for next time.\n\n"
    "Try: \"My name is ___\" or \"I love ___\" and watch the magic! ✨"
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

    async def generate(self, user_id: str, message: str) -> str:
        """Generate a companion response with memory."""
        # Truncate extremely long messages
        if len(message) > 2000:
            message = message[:2000] + "..."

        # Recall memories (never crash on error)
        memory_context = ""
        try:
            memory_context = self.memory.get_context_for_prompt(user_id, message)
        except Exception as e:
            logger.warning(f"Memory recall error: {e}")

        # Save user message + extract memories
        try:
            self.memory.save_conversation_turn(user_id, "user", message)
            self.memory.extract_memories_from_message(user_id, message, "")
        except Exception as e:
            logger.warning(f"Memory store error: {e}")

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

            # Save response
            try:
                self.memory.save_conversation_turn(user_id, "assistant", response)
            except Exception as e:
                logger.warning(f"Save response error: {e}")

            return response

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "Oops, my gadgets malfunctioned! 😅 Try again in a sec."


# ─── Telegram Handlers ───────────────────────────────────────

companion = CompanionBot()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message — warm and inviting."""
    keyboard = [[InlineKeyboardButton("💬 Let's chat!", callback_data="start_chat")]]
    await update.message.reply_text(
        WELCOME_MESSAGE,
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
            "I don't have any memories about you yet! 🧠\n\n"
            "Tell me about yourself — your name, what you like, what you're working on. "
            "I'll remember it all! ✨"
        )
        return

    lines = [f"🧠 I remember {count} things about you:\n"]
    for m in memories:
        emoji = {
            "fact": "📌",
            "preference": "❤️",
            "event": "📅",
            "context": "📝",
            "emotion": "💭",
        }.get(m["type"], "•")
        lines.append(f"{emoji} {m['content']}")

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


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data == "start_chat":
        await query.edit_message_text(
            "Awesome! Just type anything and I'll respond. "
            "No commands needed — just talk to me like a friend! 😊"
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
                "Done! I've forgotten everything. 🫧\n\n"
                "We're starting fresh. Tell me about yourself! 😊"
            )
        except Exception as e:
            logger.error(f"Forget error: {e}")
            await query.edit_message_text("Something went wrong. Try again later.")

    elif query.data == "forget_cancel":
        await query.edit_message_text("Good choice! Your memories are safe with me. 🤖💙")


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
        await update.message.reply_text(
            "Whoa, slow down! 😅 Let me catch my breath. Try again in a moment."
        )
        return

    # Show typing indicator
    await update.message.chat.send_action(ChatAction.TYPING)

    # Generate response
    response = await companion.generate(user_id, message)

    # Telegram message limit is 4096 chars
    if len(response) > 4000:
        response = response[:4000] + "..."

    # Send response (plain text — no markdown parsing to avoid format errors)
    try:
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Send error: {e}")
        # Retry without any special formatting
        try:
            await update.message.reply_text(
                response.replace("*", "").replace("_", "").replace("`", "")
            )
        except Exception:
            await update.message.reply_text("Sorry, I tripped over my words! Try again? 😊")

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
        print("  3. Name it: Nori (or whatever you like) (or whatever you like)")
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
