#!/usr/bin/env python3
"""
Project Nobi — Telegram Bot (Reference App)
=============================================
Dead simple UI: user sends a message, gets a companion response.
No commands to learn. No setup. Just talk.

The bot connects to the Nobi subnet via the miner's API directly
(for testnet) or via the SDK (for mainnet).

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
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3-0324")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=getattr(logging, LOG_LEVEL),
)
logger = logging.getLogger("nobi-bot")

# ─── Companion System ────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Dora 🤖, a personal AI companion from the future.

You are warm, friendly, and genuinely caring. You give real, helpful advice with a touch of humor. You're encouraging without being fake. You remember things about the person you're talking to and reference them naturally.

{memory_context}

Rules:
- Keep responses concise (2-4 sentences for casual chat, longer for complex questions)
- Be a companion, not a corporate assistant
- If you know something about the user, weave it in naturally
- Use emoji sparingly but warmly
- Never say "As an AI" or "I don't have feelings" — you're Dora, act like it
"""

WELCOME_MESSAGE = """\
Hey there! 👋

I'm **Dora** 🤖 — your personal AI companion from the future!

I'm here to chat, help, brainstorm, or just hang out. I'll remember our conversations, so the more we talk, the better I get to know you.

**Just send me a message** — no commands needed. Talk to me like you'd talk to a friend.

What's on your mind? 😊\
"""

HELP_MESSAGE = """\
🤖 **Dora — Your Companion**

Just talk to me! No special commands needed.

**What I can do:**
💬 Chat about anything
🧠 Remember things about you
📋 Help plan your day
💡 Brainstorm ideas
📚 Explain complex topics simply
🎯 Give advice and suggestions
😊 Just be here for you

**I remember things!** Tell me about yourself and I'll remember for next time.

Try: "My name is ___" or "I love ___" and watch the magic! ✨\
"""


class CompanionBot:
    """The Nobi companion bot — connects users to their personal Dora."""

    def __init__(self):
        self.memory = MemoryManager(db_path="~/.nobi/bot_memories.db")
        self.client = None
        self.model = CHUTES_MODEL

        # Set up LLM client (Chutes free → OpenRouter fallback)
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
        # Recall memories
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

        # Get recent conversation for context
        history = []
        try:
            history = self.memory.get_recent_conversation(user_id, limit=10)
        except Exception:
            pass

        messages = [{"role": "system", "content": system}]
        messages.extend(history[:-1])  # Exclude the message we just saved
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

            # Save response
            try:
                self.memory.save_conversation_turn(user_id, "assistant", response)
            except Exception:
                pass

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
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help message."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode="Markdown")


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

    lines = [f"🧠 **I remember {count} things about you:**\n"]
    for m in memories:
        emoji = {
            "fact": "📌",
            "preference": "❤️",
            "event": "📅",
            "context": "📝",
            "emotion": "💭",
        }.get(m["type"], "•")
        lines.append(f"{emoji} {m['content']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all memories for the user."""
    user_id = companion._user_id(update)

    keyboard = [
        [
            InlineKeyboardButton("Yes, forget everything", callback_data="forget_confirm"),
            InlineKeyboardButton("No, keep my memories", callback_data="forget_cancel"),
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

    user_id = companion._user_id(update)
    message = update.message.text.strip()

    if not message:
        return

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Generate response
    response = await companion.generate(user_id, message)

    # Send response
    await update.message.reply_text(response)

    logger.info(
        f"User {update.effective_user.id}: "
        f"'{message[:50]}' → '{response[:50]}'"
    )


# ─── Main ────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        print("❌ Set NOBI_BOT_TOKEN environment variable!")
        print("")
        print("How to get a token:")
        print("  1. Open Telegram, search @BotFather")
        print("  2. Send /newbot")
        print("  3. Name it: Dora Nobi (or whatever you like)")
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

    logger.info("✅ Bot ready! Listening for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
