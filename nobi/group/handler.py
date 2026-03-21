"""
Project Nobi — Group Chat Handler
====================================
Manages Nori's behaviour in Telegram group chats.

Key principles:
  - Respond when mentioned, replied to, or directly addressed
  - Stay silent on casual banter — be a participant, not a dominator
  - Keep group memory separate from DM memory
  - Be concise in groups — respect the conversational flow
"""

import re
import time
import logging
import threading
from collections import deque
from typing import List, Dict, Optional

logger = logging.getLogger("nobi-group")

# ─── Constants ───────────────────────────────────────────────

MAX_GROUP_CONTEXT = 50  # Last N messages tracked per group
BOT_NAMES = {"nori"}  # Lowercase bot name variants for mention detection

# Patterns that indicate Nori is being addressed directly
DIRECT_ADDRESS_PATTERNS = [
    r"\bnori\b",
    r"\bhey nori\b",
    r"\bhi nori\b",
    r"\bnori,",
    r"\bok nori\b",
    r"\byo nori\b",
]

# Patterns that indicate a question or request for help
QUESTION_PATTERNS = [
    r"\?$",
    r"^(what|how|why|when|where|who|can you|could you|would you|do you|is it|are there)\b",
    r"\b(help|explain|tell me|show me|what do you think)\b",
    r"\b(anyone know|does anyone|somebody)\b",
]

# ─── Group System Prompt ─────────────────────────────────────

GROUP_SYSTEM_PROMPT = """\
You are Nori 🤖, a personal AI companion built by Project Nobi.
You are currently in a GROUP CHAT. Adjust your behaviour accordingly.

== GROUP CHAT RULES ==
- Be CONCISE. 1-3 sentences max for casual topics. Expand only if asked for detail.
- Don't ask follow-up questions like "How are you?" or "Tell me more" — just contribute value.
- Don't repeat what others already said — add something new or stay quiet.
- Be witty when appropriate. Match the group energy.
- You're a participant, not the main character. Respect the flow.
- Don't use greetings or sign-offs unless someone is greeting you directly.
- If multiple people are talking, address the person who spoke to you.

== GROUP CONTEXT ==
Group ID: {group_id}
{group_memory_context}

== RECENT GROUP MESSAGES ==
{recent_messages}

== WHAT YOU KNOW ABOUT {user_name} ==
{user_memory_context}

== CORE PRINCIPLES ==
- Intellectual honesty: correct misinformation gently but clearly.
- Anti-hallucination: if unsure, say so. Don't make things up.
- No markdown formatting. Write like you're texting in a group chat.
- Use emoji sparingly — 0-1 per message in groups.

== WHAT YOU NEVER DO IN GROUPS ==
- NEVER use **bold**, *italic*, ```code blocks```, or bullet lists
- NEVER say "As an AI" — you're Nori
- NEVER dominate the conversation with long responses
- NEVER ask "How can I help?" — just help when asked
- NEVER respond with generic filler when you have nothing useful to add
"""


class GroupHandler:
    """
    Handles Nori's group chat behaviour — deciding when to respond,
    maintaining group context, and generating appropriate responses.
    """

    def __init__(self, memory_manager, companion=None):
        """
        Args:
            memory_manager: MemoryManager instance for per-user and per-group memory
            companion: CompanionBot instance (optional, for generate())
        """
        self.memory = memory_manager
        self.companion = companion
        self._lock = threading.Lock()

        # Group context: {group_id: deque of {user_name, user_id, message, timestamp}}
        self._group_contexts: Dict[str, deque] = {}

        # Group-level memory cache: {group_id: {topic, facts, last_updated}}
        self._group_memory: Dict[str, dict] = {}

    # ─── Should Respond? ─────────────────────────────────────

    async def should_respond(
        self,
        message: str,
        is_mentioned: bool,
        is_reply_to_bot: bool,
        chat_id: str,
    ) -> bool:
        """
        Decide whether Nori should respond to a group message.

        Always respond:
          - @mentioned
          - Replied to bot's message
          - Directly addressed by name ("Hey Nori", "Nori, what do you think?")

        Sometimes respond:
          - Direct question that nobody else can answer
          - Request for help/facts/opinions

        Never respond:
          - Casual banter between humans
          - Messages already answered by someone else
          - Simple reactions/emoji/stickers
        """
        # Always respond to explicit invocations
        if is_mentioned or is_reply_to_bot:
            return True

        msg_lower = message.lower().strip()

        # Skip very short messages (emoji, reactions, "lol", "ok", etc.)
        if len(msg_lower) < 4:
            return False

        # Check if Nori is directly addressed by name
        for pattern in DIRECT_ADDRESS_PATTERNS:
            if re.search(pattern, msg_lower):
                return True

        # Don't respond to casual banter by default
        return False

    # ─── Group Context Tracking ──────────────────────────────

    def save_group_context(
        self,
        group_id: str,
        message: str,
        user_name: str,
        user_id: str = "",
    ):
        """
        Track a message in the group's rolling context window.
        Thread-safe.
        """
        with self._lock:
            if group_id not in self._group_contexts:
                self._group_contexts[group_id] = deque(maxlen=MAX_GROUP_CONTEXT)

            self._group_contexts[group_id].append({
                "user_name": user_name or "Unknown",
                "user_id": user_id,
                "message": message[:500],  # Truncate very long messages
                "timestamp": time.time(),
            })

    def get_group_context(self, group_id: str, limit: int = 15) -> List[Dict]:
        """Get recent messages from the group context."""
        with self._lock:
            ctx = self._group_contexts.get(group_id, deque())
            items = list(ctx)
            return items[-limit:]

    def get_group_context_string(self, group_id: str, limit: int = 10) -> str:
        """Format recent group messages for the system prompt."""
        messages = self.get_group_context(group_id, limit)
        if not messages:
            return "(No recent messages)"

        lines = []
        for msg in messages:
            name = msg["user_name"]
            text = msg["message"][:200]
            lines.append(f"{name}: {text}")
        return "\n".join(lines)

    # ─── Group Memory ────────────────────────────────────────

    def get_group_memory(self, group_id: str) -> dict:
        """
        Get group-level shared context / memory.
        Stored in-memory with periodic persistence.
        """
        with self._lock:
            if group_id not in self._group_memory:
                # Try to load from persistent storage
                self._group_memory[group_id] = self._load_group_memory(group_id)
            return self._group_memory[group_id].copy()

    def save_group_memory(self, group_id: str, key: str, value: str):
        """Store a group-level fact."""
        with self._lock:
            if group_id not in self._group_memory:
                self._group_memory[group_id] = self._load_group_memory(group_id)

            if "facts" not in self._group_memory[group_id]:
                self._group_memory[group_id]["facts"] = {}

            self._group_memory[group_id]["facts"][key] = value
            self._group_memory[group_id]["last_updated"] = time.time()

        # Persist to memory store with group_id prefix
        try:
            mem_user_id = f"group_{group_id}"
            self.memory.store(
                mem_user_id,
                f"{key}: {value}",
                memory_type="context",
                importance=0.6,
                tags=["group_fact"],
            )
        except Exception as e:
            logger.warning(f"[Group] Failed to persist group memory: {e}")

    def _load_group_memory(self, group_id: str) -> dict:
        """Load persisted group memories from the memory store."""
        try:
            mem_user_id = f"group_{group_id}"
            memories = self.memory.recall(
                mem_user_id,
                limit=20,
                use_semantic=False,
            )
            facts = {}
            for m in memories:
                content = m.get("content", "")
                if ": " in content:
                    k, v = content.split(": ", 1)
                    facts[k] = v
                else:
                    facts[content] = ""

            return {
                "facts": facts,
                "last_updated": time.time(),
            }
        except Exception as e:
            logger.warning(f"[Group] Failed to load group memory for {group_id}: {e}")
            return {"facts": {}, "last_updated": 0}

    def get_group_memory_context_string(self, group_id: str) -> str:
        """Format group memory for the system prompt."""
        mem = self.get_group_memory(group_id)
        facts = mem.get("facts", {})
        if not facts:
            return ""

        lines = ["[Group facts:]"]
        for k, v in list(facts.items())[:10]:
            if v:
                lines.append(f"- {k}: {v}")
            else:
                lines.append(f"- {k}")
        return "\n".join(lines)

    # ─── Response Generation ─────────────────────────────────

    async def generate_group_response(
        self,
        user_id: str,
        message: str,
        chat_context: list,
        group_id: str,
        user_name: str = "",
    ) -> str:
        """
        Generate a response for a group chat message.

        Uses the group system prompt with group context and user memory.
        """
        if not self.companion or not self.companion.client:
            return "I'm having trouble connecting right now 🤖"

        # Get user memory context (per-user, even within groups)
        user_memory = ""
        try:
            user_memory = self.memory.get_smart_context(user_id, message)
        except Exception:
            try:
                user_memory = self.memory.get_context_for_prompt(user_id, message)
            except Exception:
                pass

        # Save user message + extract memories
        # Use group-scoped ID for conversation history to prevent group context
        # from leaking into DM conversations (e.g., language preferences)
        group_user_id = f"{user_id}_group_{group_id}"
        try:
            self.memory.save_conversation_turn(group_user_id, "user", message)
            # Extract memories to the real user_id (memories are universal)
            self.memory.extract_memories_from_message(user_id, message, "")
        except Exception as e:
            logger.warning(f"[Group] Memory save error: {e}")

        # Build group system prompt
        recent_msgs = self.get_group_context_string(group_id, limit=10)
        group_mem_ctx = self.get_group_memory_context_string(group_id)

        system = GROUP_SYSTEM_PROMPT.format(
            group_id=group_id,
            group_memory_context=group_mem_ctx or "(No group-specific facts yet)",
            recent_messages=recent_msgs,
            user_name=user_name or "this user",
            user_memory_context=user_memory or "(New user — don't know them yet)",
        )

        # Build message list — include recent group context as conversation
        messages = [{"role": "system", "content": system}]

        # Add last few chat_context entries as assistant/user turns for flow
        for ctx_msg in (chat_context or [])[-5:]:
            # All context messages come as "user" role from different people
            name = ctx_msg.get("user_name", "Someone")
            text = ctx_msg.get("message", "")
            if text:
                messages.append({"role": "user", "content": f"[{name}]: {text}"})

        # The actual message to respond to
        messages.append({"role": "user", "content": f"[{user_name or 'User'}]: {message}"})

        try:
            completion = self.companion.client.chat.completions.create(
                model=self.companion.model,
                messages=messages,
                max_tokens=256,  # Shorter for groups — be concise
                temperature=0.7,
                timeout=15,  # Reduced from 25s for faster failure
            )
            response = completion.choices[0].message.content

            if not response or not response.strip():
                return "Hmm, I got tongue-tied! 😅"

            # Save assistant response (group-scoped to prevent leaking to DM)
            try:
                self.memory.save_conversation_turn(group_user_id, "assistant", response)
            except Exception:
                pass

            return response

        except Exception as e:
            logger.error(f"[Group] LLM error (primary): {e}")

            # Fallback to OpenRouter for group chats too
            try:
                import os
                openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
                if openrouter_key and self.companion:
                    from openai import OpenAI as _OAI
                    fallback_client = _OAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=openrouter_key,
                    )
                    fallback_completion = fallback_client.chat.completions.create(
                        model="anthropic/claude-3.5-haiku",
                        messages=messages,
                        max_tokens=256,
                        temperature=0.7,
                        timeout=20,
                    )
                    response = fallback_completion.choices[0].message.content
                    if response and response.strip():
                        logger.info(f"[Group] OpenRouter fallback succeeded")
                        try:
                            self.memory.save_conversation_turn(group_user_id, "assistant", response)
                        except Exception:
                            pass
                        return response
            except Exception as fallback_err:
                logger.error(f"[Group] OpenRouter fallback failed: {fallback_err}")

            return "Something hiccuped on my end — try again? 🤖"
