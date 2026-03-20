"""
Tests for Group Chat Support (Task 4)
======================================
Tests GroupHandler, group memory, context tracking, should_respond logic,
and response generation for group chats.
"""

import os
import sys
import time
import asyncio
import threading
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.memory.store import MemoryManager
from nobi.group.handler import GroupHandler, GROUP_SYSTEM_PROMPT


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def memory():
    """Fresh in-memory MemoryManager for each test."""
    import tempfile
    db_path = os.path.join(tempfile.mkdtemp(), "test_group.db")
    mm = MemoryManager(db_path=db_path, encryption_enabled=False)
    yield mm


@pytest.fixture
def handler(memory):
    """GroupHandler with no companion (no LLM calls)."""
    return GroupHandler(memory_manager=memory, companion=None)


# ─── should_respond Tests ────────────────────────────────────

class TestShouldRespond:
    """Tests for the should_respond decision engine."""

    @pytest.mark.asyncio
    async def test_01_mentioned_always_responds(self, handler):
        """@mention → always respond."""
        result = await handler.should_respond(
            message="@nori_bot what do you think?",
            is_mentioned=True,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_02_reply_to_bot_always_responds(self, handler):
        """Reply to bot's message → always respond."""
        result = await handler.should_respond(
            message="That's interesting, tell me more",
            is_mentioned=False,
            is_reply_to_bot=True,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_03_hey_nori_responds(self, handler):
        """'Hey Nori' → respond."""
        result = await handler.should_respond(
            message="Hey Nori, what do you think about crypto?",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_04_nori_comma_responds(self, handler):
        """'Nori, ...' → respond."""
        result = await handler.should_respond(
            message="Nori, can you explain this?",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_05_hi_nori_responds(self, handler):
        """'Hi Nori' → respond."""
        result = await handler.should_respond(
            message="Hi Nori! How's it going?",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_06_random_banter_silent(self, handler):
        """Casual banter → stay silent."""
        result = await handler.should_respond(
            message="Yeah that movie was great honestly",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_07_short_message_silent(self, handler):
        """Very short messages (emoji, 'ok') → stay silent."""
        for msg in ["ok", "lol", "👍", "🔥"]:
            result = await handler.should_respond(
                message=msg,
                is_mentioned=False,
                is_reply_to_bot=False,
                chat_id="group_1",
            )
            assert result is False, f"Should be silent for '{msg}'"

    @pytest.mark.asyncio
    async def test_08_mentioned_plus_short_msg(self, handler):
        """@mention overrides even short messages."""
        result = await handler.should_respond(
            message="@nori ok",
            is_mentioned=True,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_09_ok_nori_responds(self, handler):
        """'ok nori' → respond (direct address)."""
        result = await handler.should_respond(
            message="ok nori tell me about bitcoin",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_10_nori_in_sentence_responds(self, handler):
        """Nori mentioned anywhere in message → respond."""
        result = await handler.should_respond(
            message="I think nori would know the answer",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_11_no_nori_no_mention_silent(self, handler):
        """No Nori name, no mention, no reply → silent."""
        result = await handler.should_respond(
            message="Has anyone been to Tokyo recently? I'm planning a trip.",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_12_yo_nori_responds(self, handler):
        """'yo nori' → respond."""
        result = await handler.should_respond(
            message="yo nori what's the latest news?",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id="group_1",
        )
        assert result is True


# ─── Group Context Tracking Tests ────────────────────────────

class TestGroupContext:
    """Tests for group message context tracking."""

    def test_13_save_and_retrieve_context(self, handler):
        """Save messages and retrieve them."""
        handler.save_group_context("g1", "Hello everyone!", "Alice", "u1")
        handler.save_group_context("g1", "Hey Alice!", "Bob", "u2")
        handler.save_group_context("g1", "What's up?", "Charlie", "u3")

        ctx = handler.get_group_context("g1")
        assert len(ctx) == 3
        assert ctx[0]["user_name"] == "Alice"
        assert ctx[1]["message"] == "Hey Alice!"
        assert ctx[2]["user_name"] == "Charlie"

    def test_14_context_limit(self, handler):
        """Context respects the limit parameter."""
        for i in range(20):
            handler.save_group_context("g1", f"Message {i}", f"User{i}", f"u{i}")

        ctx = handler.get_group_context("g1", limit=5)
        assert len(ctx) == 5
        # Should be the 5 most recent
        assert ctx[0]["message"] == "Message 15"

    def test_15_context_rolling_window(self, handler):
        """Context uses a rolling window (max 50 by default)."""
        from nobi.group.handler import MAX_GROUP_CONTEXT

        for i in range(MAX_GROUP_CONTEXT + 10):
            handler.save_group_context("g1", f"Msg {i}", "User", "u1")

        # Request all available (up to MAX_GROUP_CONTEXT)
        ctx = handler.get_group_context("g1", limit=MAX_GROUP_CONTEXT + 10)
        assert len(ctx) == MAX_GROUP_CONTEXT
        # Oldest should be gone (first 10 evicted)
        assert ctx[0]["message"] == "Msg 10"

    def test_16_context_per_group_isolation(self, handler):
        """Different groups have independent contexts."""
        handler.save_group_context("g1", "Group 1 message", "Alice", "u1")
        handler.save_group_context("g2", "Group 2 message", "Bob", "u2")

        ctx1 = handler.get_group_context("g1")
        ctx2 = handler.get_group_context("g2")

        assert len(ctx1) == 1
        assert len(ctx2) == 1
        assert ctx1[0]["user_name"] == "Alice"
        assert ctx2[0]["user_name"] == "Bob"

    def test_17_context_string_format(self, handler):
        """Context string is formatted for prompt injection."""
        handler.save_group_context("g1", "Hello!", "Alice", "u1")
        handler.save_group_context("g1", "Hi there!", "Bob", "u2")

        ctx_str = handler.get_group_context_string("g1")
        assert "Alice: Hello!" in ctx_str
        assert "Bob: Hi there!" in ctx_str

    def test_18_empty_context_string(self, handler):
        """Empty group returns placeholder string."""
        ctx_str = handler.get_group_context_string("nonexistent")
        assert "(No recent messages)" in ctx_str

    def test_19_context_truncates_long_messages(self, handler):
        """Very long messages get truncated in context."""
        long_msg = "A" * 1000
        handler.save_group_context("g1", long_msg, "Alice", "u1")

        ctx = handler.get_group_context("g1")
        assert len(ctx[0]["message"]) == 500  # Truncated


# ─── Group Memory Tests ─────────────────────────────────────

class TestGroupMemory:
    """Tests for group-level shared memory."""

    def test_20_group_memory_default_empty(self, handler):
        """New group has empty memory."""
        mem = handler.get_group_memory("new_group")
        assert isinstance(mem, dict)
        assert "facts" in mem

    def test_21_save_and_get_group_memory(self, handler):
        """Save and retrieve group-level facts."""
        handler.save_group_memory("g1", "topic", "crypto trading")
        mem = handler.get_group_memory("g1")
        assert mem["facts"]["topic"] == "crypto trading"

    def test_22_group_memory_isolation(self, handler):
        """Group memories are isolated per group."""
        handler.save_group_memory("g1", "topic", "crypto")
        handler.save_group_memory("g2", "topic", "cooking")

        mem1 = handler.get_group_memory("g1")
        mem2 = handler.get_group_memory("g2")
        assert mem1["facts"]["topic"] == "crypto"
        assert mem2["facts"]["topic"] == "cooking"

    def test_23_group_memory_persists_to_store(self, handler, memory):
        """Group memory is persisted to the memory store."""
        handler.save_group_memory("g1", "language", "English")

        # Check it was saved with group_ prefix
        memories = memory.recall("group_g1", limit=10, use_semantic=False)
        assert len(memories) > 0
        assert any("English" in m["content"] for m in memories)

    def test_24_group_memory_context_string(self, handler):
        """Group memory formats correctly for prompt."""
        handler.save_group_memory("g1", "topic", "AI research")
        handler.save_group_memory("g1", "vibe", "technical")

        ctx = handler.get_group_memory_context_string("g1")
        assert "topic: AI research" in ctx
        assert "vibe: technical" in ctx

    def test_25_group_memory_empty_context_string(self, handler):
        """Empty group memory returns empty string."""
        ctx = handler.get_group_memory_context_string("empty_group")
        assert ctx == ""

    def test_26_user_memory_in_groups(self, handler, memory):
        """Per-user memories still work within group context."""
        user_id = "tg_12345"
        memory.store(user_id, "User's name is Alice", memory_type="fact", importance=0.9)

        # User memories should be retrievable even in group context
        memories = memory.recall(user_id, limit=5)
        assert len(memories) > 0
        assert "Alice" in memories[0]["content"]


# ─── Thread Safety Tests ─────────────────────────────────────

class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_27_concurrent_context_writes(self, handler):
        """Multiple threads writing context simultaneously."""
        errors = []

        def write_context(thread_id):
            try:
                for i in range(50):
                    handler.save_group_context(
                        "g1", f"Thread {thread_id} msg {i}", f"User{thread_id}", f"u{thread_id}"
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_context, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Context should have messages from all threads (capped at MAX_GROUP_CONTEXT)
        ctx = handler.get_group_context("g1")
        assert len(ctx) > 0

    def test_28_concurrent_memory_writes(self, handler):
        """Multiple threads writing group memory simultaneously."""
        errors = []

        def write_memory(thread_id):
            try:
                for i in range(10):
                    handler.save_group_memory(
                        "g1", f"key_{thread_id}_{i}", f"value_{thread_id}_{i}"
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_memory, args=(t,)) for t in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"


# ─── Group System Prompt Tests ───────────────────────────────

class TestGroupSystemPrompt:
    """Tests for group-specific system prompt."""

    def test_29_prompt_has_concise_instruction(self):
        """Group prompt instructs concise responses."""
        assert "CONCISE" in GROUP_SYSTEM_PROMPT or "concise" in GROUP_SYSTEM_PROMPT.lower()

    def test_30_prompt_no_how_are_you(self):
        """Group prompt discourages 'How are you?' style questions."""
        assert "How are you" in GROUP_SYSTEM_PROMPT

    def test_31_prompt_no_domination(self):
        """Group prompt tells bot not to dominate."""
        lower = GROUP_SYSTEM_PROMPT.lower()
        assert "not the main character" in lower or "dominate" in lower or "participant" in lower

    def test_32_prompt_format_fields(self):
        """Group prompt has all required format fields."""
        assert "{group_id}" in GROUP_SYSTEM_PROMPT
        assert "{recent_messages}" in GROUP_SYSTEM_PROMPT
        assert "{user_memory_context}" in GROUP_SYSTEM_PROMPT
        assert "{group_memory_context}" in GROUP_SYSTEM_PROMPT

    def test_33_prompt_no_markdown(self):
        """Group prompt forbids markdown."""
        lower = GROUP_SYSTEM_PROMPT.lower()
        assert "no markdown" in lower or "never use **bold**" in lower.replace("\\*\\*", "**")


# ─── Response Generation Tests (no LLM) ─────────────────────

class TestResponseGeneration:
    """Tests for response generation (mocked — no LLM calls)."""

    @pytest.mark.asyncio
    async def test_34_no_companion_fallback(self, handler):
        """Without companion, returns fallback message."""
        response = await handler.generate_group_response(
            user_id="tg_123",
            message="Hello!",
            chat_context=[],
            group_id="g1",
            user_name="Alice",
        )
        assert "trouble connecting" in response.lower() or "🤖" in response

    @pytest.mark.asyncio
    async def test_35_context_passed_to_generation(self, handler):
        """Chat context is available during generation."""
        handler.save_group_context("g1", "Let's talk about AI", "Bob", "u2")
        handler.save_group_context("g1", "Sure, what about it?", "Charlie", "u3")

        ctx = handler.get_group_context("g1")
        assert len(ctx) == 2
        # Context should include both messages
        assert ctx[0]["message"] == "Let's talk about AI"


# ─── Integration Tests ───────────────────────────────────────

class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_36_full_group_flow(self, handler, memory):
        """Full flow: save context → check should_respond → (would generate)."""
        group_id = "g_test"
        user_id = "tg_999"

        # User sends messages
        handler.save_group_context(group_id, "anyone here?", "Alice", user_id)
        handler.save_group_context(group_id, "yeah I'm around", "Bob", "tg_888")

        # Alice mentions Nori
        handler.save_group_context(group_id, "Hey Nori, what's bitcoin?", "Alice", user_id)

        should = await handler.should_respond(
            message="Hey Nori, what's bitcoin?",
            is_mentioned=False,
            is_reply_to_bot=False,
            chat_id=group_id,
        )
        assert should is True

        # Context should have all 3 messages
        ctx = handler.get_group_context(group_id)
        assert len(ctx) == 3

    @pytest.mark.asyncio
    async def test_37_user_memory_and_group_memory_separate(self, handler, memory):
        """User memories and group memories use different ID spaces."""
        user_id = "tg_123"
        group_id = "g_456"

        # Store user memory
        memory.store(user_id, "User likes coffee", memory_type="preference")

        # Store group memory
        handler.save_group_memory(group_id, "topic", "programming")

        # User memories
        user_mems = memory.recall(user_id, limit=10, use_semantic=False)
        assert any("coffee" in m["content"] for m in user_mems)

        # Group memories (separate namespace)
        group_mems = memory.recall(f"group_{group_id}", limit=10, use_semantic=False)
        assert any("programming" in m["content"] for m in group_mems)

        # They don't cross-contaminate
        assert not any("programming" in m["content"] for m in user_mems)
        assert not any("coffee" in m["content"] for m in group_mems)

    @pytest.mark.asyncio
    async def test_38_multiple_groups_independent(self, handler):
        """Multiple groups maintain independent state."""
        for i in range(3):
            gid = f"g_{i}"
            handler.save_group_context(gid, f"Message in group {i}", f"User{i}", f"u{i}")
            handler.save_group_memory(gid, "name", f"Group {i}")

        for i in range(3):
            gid = f"g_{i}"
            ctx = handler.get_group_context(gid)
            assert len(ctx) == 1
            assert f"group {i}" in ctx[0]["message"]
            mem = handler.get_group_memory(gid)
            assert mem["facts"]["name"] == f"Group {i}"


# ─── Import/Init Tests ──────────────────────────────────────

class TestImports:
    """Tests that the module structure is correct."""

    def test_39_group_module_importable(self):
        """nobi.group imports correctly."""
        from nobi.group import GroupHandler
        assert GroupHandler is not None

    def test_40_handler_init_no_companion(self, memory):
        """GroupHandler works without a companion."""
        h = GroupHandler(memory_manager=memory)
        assert h.companion is None
        assert h.memory is memory

    def test_41_handler_init_with_companion(self, memory):
        """GroupHandler accepts a companion."""

        class FakeCompanion:
            client = None
            model = "test"

        h = GroupHandler(memory_manager=memory, companion=FakeCompanion())
        assert h.companion is not None
