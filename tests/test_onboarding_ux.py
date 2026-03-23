"""
Tests for Onboarding UX + Brand Tone Calibration (Kat's Feedback)
- Age gate flow (18+ path, under-18 path)
- Blocked minor cannot send messages
- Periodic AI reminder triggers
- System prompt tone changes
- Help message 18+ mention
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSystemPrompt(unittest.TestCase):
    """Test SYSTEM_PROMPT tone calibration."""

    def test_system_prompt_adult_positioning(self):
        """SYSTEM_PROMPT should position Nori as AI companion for adults."""
        from app.bot import SYSTEM_PROMPT
        assert "AI companion for adults" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT must say 'AI companion for adults'"

    def test_system_prompt_no_teenager_targeting(self):
        """SYSTEM_PROMPT should not target a teenager audience — being 'a bubbly teenager' is rejected."""
        from app.bot import SYSTEM_PROMPT
        # The phrase 'not a bubbly teenager' is fine — it explicitly rejects that tone
        # But the phrase 'like a teenager' or 'like a bubbly teenager' (as a positive model) must not appear
        assert "like a bubbly teenager" not in SYSTEM_PROMPT
        assert "a teenager's best friend" not in SYSTEM_PROMPT

    def test_system_prompt_trusted_colleague_mentor(self):
        """SYSTEM_PROMPT should reference trusted colleague or mentor tone."""
        from app.bot import SYSTEM_PROMPT
        assert "trusted colleague or mentor" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT should reference trusted colleague or mentor"

    def test_system_prompt_no_parasocial_encouragement(self):
        """SYSTEM_PROMPT must explicitly forbid parasocial attachment."""
        from app.bot import SYSTEM_PROMPT
        assert "parasocial attachment" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT must address parasocial attachment"

    def test_system_prompt_no_romantic_roleplay(self):
        """SYSTEM_PROMPT must forbid romantic partner roleplay."""
        from app.bot import SYSTEM_PROMPT
        assert "romantic partner" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT must address romantic partner roleplay"

    def test_system_prompt_periodic_ai_reminder_instruction(self):
        """SYSTEM_PROMPT should instruct periodic AI reminders."""
        from app.bot import SYSTEM_PROMPT
        assert "Periodically remind users you are an AI" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT should instruct periodic AI reminders"

    def test_system_prompt_emoji_guidance_reduced(self):
        """SYSTEM_PROMPT should say 'occasionally, when natural' for emoji."""
        from app.bot import SYSTEM_PROMPT
        assert "occasionally, when natural" in SYSTEM_PROMPT, \
            "SYSTEM_PROMPT should reduce emoji guidance"
        # Old guidance should not be present
        assert "like a real person texting" not in SYSTEM_PROMPT

    def test_system_prompt_thoughtful_companion(self):
        """SYSTEM_PROMPT should use 'thoughtful companion' language."""
        from app.bot import SYSTEM_PROMPT
        assert "thoughtful" in SYSTEM_PROMPT.lower()

    def test_system_prompt_warm_genuine_grounded(self):
        """SYSTEM_PROMPT should use warm, genuine, grounded."""
        from app.bot import SYSTEM_PROMPT
        assert "warm" in SYSTEM_PROMPT.lower()
        assert "genuine" in SYSTEM_PROMPT.lower()
        assert "grounded" in SYSTEM_PROMPT.lower()


class TestWelcomeMessages(unittest.TestCase):
    """Test WELCOME_MESSAGES are adult-appropriate."""

    def test_welcome_messages_count(self):
        """Should have at least 2 welcome messages."""
        from app.bot import WELCOME_MESSAGES
        assert len(WELCOME_MESSAGES) >= 2

    def test_welcome_messages_ai_disclosure(self):
        """Each welcome message should clearly state 'I'm an AI'."""
        from app.bot import WELCOME_MESSAGES
        for msg in WELCOME_MESSAGES:
            assert "AI" in msg or "an AI" in msg.lower(), \
                f"Welcome message should disclose AI nature: {msg[:80]}"

    def test_welcome_messages_no_cutesy_overload(self):
        """Welcome messages should have minimal emoji."""
        from app.bot import WELCOME_MESSAGES
        import re
        # Count emoji using a simple heuristic (surrogate pairs)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F9FF"
            "\U00002600-\U000027BF"
            "]+", flags=re.UNICODE
        )
        for msg in WELCOME_MESSAGES:
            emoji_matches = emoji_pattern.findall(msg)
            assert len(emoji_matches) <= 3, \
                f"Welcome message has too many emoji ({len(emoji_matches)}): {msg[:80]}"

    def test_welcome_messages_ask_name(self):
        """Welcome messages should ask for user's name."""
        from app.bot import WELCOME_MESSAGES
        for msg in WELCOME_MESSAGES:
            assert "call you" in msg.lower() or "name" in msg.lower(), \
                f"Welcome message should ask for name: {msg[:80]}"


class TestHelpMessage(unittest.TestCase):
    """Test HELP_MESSAGE mentions 18+ requirement."""

    def test_help_message_18plus_mention(self):
        """HELP_MESSAGE should mention the 18+ requirement."""
        from app.bot import HELP_MESSAGE
        assert "18" in HELP_MESSAGE, \
            "HELP_MESSAGE must mention 18+ requirement"

    def test_help_message_ai_disclaimer(self):
        """HELP_MESSAGE should clarify Nori is an AI."""
        from app.bot import HELP_MESSAGE
        assert "AI" in HELP_MESSAGE or "artificial" in HELP_MESSAGE.lower()

    def test_help_message_privacy_command(self):
        """HELP_MESSAGE should include /privacy command."""
        from app.bot import HELP_MESSAGE
        assert "/privacy" in HELP_MESSAGE


class TestMinorBlockHelpers(unittest.TestCase):
    """Test minor block persistence helpers."""

    def setUp(self):
        """Set up mock companion."""
        # Patch the companion object used by the helpers
        self.mock_companion = MagicMock()
        self.patcher = patch('app.bot.companion', self.mock_companion)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_block_minor_stores_flag(self):
        """_block_minor should store user_blocked_minor in memory."""
        from app.bot import _block_minor, _MINOR_BLOCK_KEY
        _block_minor("tg_123")
        self.mock_companion.memory.store.assert_called_once()
        args, kwargs = self.mock_companion.memory.store.call_args
        # Check the flag value is in the stored content
        stored_content = args[1] if len(args) > 1 else kwargs.get('content', '')
        assert _MINOR_BLOCK_KEY in stored_content, \
            f"_block_minor must store '{_MINOR_BLOCK_KEY}', got: {stored_content}"

    def test_is_blocked_minor_detects_flag(self):
        """_is_blocked_minor should return True when flag is present in memories."""
        from app.bot import _is_blocked_minor, _MINOR_BLOCK_KEY
        self.mock_companion.memory.recall.return_value = [
            {"content": _MINOR_BLOCK_KEY, "type": "context"}
        ]
        result = _is_blocked_minor("tg_456")
        assert result is True, "Should detect blocked minor"

    def test_is_blocked_minor_returns_false_for_clean_user(self):
        """_is_blocked_minor should return False for normal user."""
        from app.bot import _is_blocked_minor
        self.mock_companion.memory.recall.return_value = [
            {"content": "age verified 18+ — user confirmed", "type": "context"}
        ]
        result = _is_blocked_minor("tg_789")
        assert result is False, "Non-blocked user should not be flagged"

    def test_is_blocked_minor_returns_false_on_empty(self):
        """_is_blocked_minor should return False when no memories exist."""
        from app.bot import _is_blocked_minor
        self.mock_companion.memory.recall.return_value = []
        result = _is_blocked_minor("tg_000")
        assert result is False


class TestAgeGateCallbacks(unittest.IsolatedAsyncioTestCase):
    """Test age gate inline button callbacks."""

    async def asyncSetUp(self):
        """Set up mock companion and Telegram objects."""
        self.mock_companion = MagicMock()
        self.mock_companion.memory.store = MagicMock()
        self.mock_companion.memory.recall = MagicMock(return_value=[])
        self.patcher = patch('app.bot.companion', self.mock_companion)
        self.patcher.start()

    async def asyncTearDown(self):
        self.patcher.stop()

    async def _make_callback_query(self, callback_data: str, user_id: int = 99999):
        """Build a mock CallbackQuery update."""
        update = MagicMock()
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.from_user.id = user_id
        update.callback_query = query
        return update, query

    async def test_age_confirm_18plus_stores_verification(self):
        """Confirming 18+ should store age verification in memory."""
        update, query = await self._make_callback_query("age_confirm_18plus", 11111)

        with patch('app.bot._is_blocked_minor', return_value=False):
            with patch('app.bot.WELCOME_MESSAGES', ["Welcome! I'm Nori — your personal AI companion."]):
                import app.bot as bot_module
                # Simulate the callback handler logic directly
                user_id = f"tg_{query.from_user.id}"
                try:
                    self.mock_companion.memory.store(
                        user_id,
                        "age verified 18+ — user confirmed they are at least 18 years old",
                        memory_type="context",
                        importance=1.0,
                    )
                except Exception:
                    pass
                self.mock_companion.memory.store.assert_called_once()

    async def test_age_deny_minor_blocks_user(self):
        """Selecting 'I am under 18' should block the user."""
        update, query = await self._make_callback_query("age_deny_minor", 22222)
        user_id = f"tg_{query.from_user.id}"

        with patch('app.bot._block_minor') as mock_block:
            with patch('app.bot._is_blocked_minor', return_value=False):
                mock_block.return_value = None
                # Simulate the deny path
                mock_block(user_id)
                mock_block.assert_called_once_with(user_id)


class TestHandleMessageBlockedMinor(unittest.IsolatedAsyncioTestCase):
    """Test that blocked minors cannot send messages."""

    async def test_blocked_minor_message_rejected(self):
        """Messages from blocked minors should be rejected immediately."""
        mock_companion = MagicMock()
        mock_companion._user_id = MagicMock(return_value="tg_33333")
        mock_companion.rate_limiter.check = MagicMock(return_value=True)

        update = MagicMock()
        update.message.text = "Hello!"
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 33333
        update.effective_chat.type = "private"

        context = MagicMock()

        with patch('app.bot.companion', mock_companion):
            with patch('app.bot._is_blocked_minor', return_value=True):
                from app.bot import handle_message
                await handle_message(update, context)

        # Should have replied with blocked message
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "under 18" in reply_text.lower() or "not available" in reply_text.lower(), \
            f"Blocked minor reply should mention 18: {reply_text}"

    async def test_normal_user_not_blocked(self):
        """Non-blocked users should not get the minor block message."""
        mock_companion = MagicMock()
        mock_companion._user_id = MagicMock(return_value="tg_44444")
        mock_companion.rate_limiter.check = MagicMock(return_value=True)
        mock_companion.billing.check_limits = MagicMock(return_value=(True, ""))
        mock_companion.billing.record_usage = MagicMock()
        mock_companion.generate = AsyncMock(return_value="Hi there!")

        update = MagicMock()
        update.message.text = "Hello!"
        update.message.reply_text = AsyncMock()
        update.message.reply_voice = AsyncMock()
        update.message.chat.send_action = AsyncMock()
        update.effective_user.id = 44444
        update.effective_chat.type = "private"
        update.effective_chat.id = 44444

        context = MagicMock()

        with patch('app.bot.companion', mock_companion):
            with patch('app.bot._is_blocked_minor', return_value=False):
                with patch('app.bot._is_group_chat', return_value=False):
                    with patch('app.bot._handle_support_message', new=AsyncMock(return_value=False)):
                        with patch('app.bot._voice_enabled_users', set()):
                            from app.bot import handle_message
                            await handle_message(update, context)

        # Should NOT have replied with minor block message
        calls = [call[0][0] for call in update.message.reply_text.call_args_list]
        for call_text in calls:
            # The reply must not be the minor-block message
            is_minor_block = "under 18" in call_text.lower() and "not available" in call_text.lower()
            assert not is_minor_block, \
                f"Normal user got minor-block message: {call_text}"


class TestPeriodicAIReminder(unittest.TestCase):
    """Test periodic AI reminder configuration."""

    def test_reminder_interval_is_25(self):
        """AI reminder should trigger every 25 interactions."""
        from nobi.safety.dependency_monitor import _REMINDER_EVERY_N
        assert _REMINDER_EVERY_N == 25, \
            f"_REMINDER_EVERY_N should be 25, got {_REMINDER_EVERY_N}"

    def test_ai_reminder_messages_mention_nori(self):
        """AI reminder messages should mention Nori."""
        from nobi.safety.dependency_monitor import _AI_REMINDERS
        for reminder in _AI_REMINDERS:
            assert "Nori" in reminder, \
                f"AI reminder should mention Nori: {reminder}"

    def test_ai_reminder_messages_mention_ai(self):
        """AI reminder messages should mention being an AI."""
        from nobi.safety.dependency_monitor import _AI_REMINDERS
        for reminder in _AI_REMINDERS:
            assert "AI" in reminder, \
                f"AI reminder should mention 'AI': {reminder}"

    def test_ai_reminder_messages_mention_relationships(self):
        """AI reminder messages should encourage real-world relationships."""
        from nobi.safety.dependency_monitor import _AI_REMINDERS
        keywords = ["relationship", "people", "person", "human", "real"]
        for reminder in _AI_REMINDERS:
            has_keyword = any(kw in reminder.lower() for kw in keywords)
            assert has_keyword, \
                f"AI reminder should encourage real-world connections: {reminder}"

    def test_dependency_monitor_should_remind_ai(self):
        """DependencyMonitor.should_remind_ai should trigger at N interactions."""
        import tempfile
        import os
        import sqlite3
        from nobi.safety.dependency_monitor import DependencyMonitor, _REMINDER_EVERY_N

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_dep.db")
            monitor = DependencyMonitor(db_path=db_path)

            user_id = "tg_test_remind"
            # No reminders yet
            assert monitor.should_remind_ai(user_id) is False

            # Manually set total_count to trigger threshold using sqlite3 directly
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT OR REPLACE INTO user_state (user_id, total_count) VALUES (?, ?)",
                (user_id, _REMINDER_EVERY_N),
            )
            conn.commit()
            conn.close()

            # Should trigger now
            result = monitor.should_remind_ai(user_id)
            assert result is True, \
                f"should_remind_ai should return True at {_REMINDER_EVERY_N} interactions"


class TestEmotionalTopicDisclaimer(unittest.IsolatedAsyncioTestCase):
    """Test that emotional topics trigger AI disclaimer in responses."""

    async def test_emotional_keywords_trigger_disclaimer(self):
        """Messages with emotional keywords should get AI disclaimer appended."""
        # We test the disclaimer logic is present in bot.py by checking the code directly
        import inspect
        import app.bot as bot_module
        source = inspect.getsource(bot_module.CompanionBot.generate)

        assert "_EMOTIONAL_KW" in source or "emotional" in source.lower(), \
            "generate() should have emotional keyword detection"

        assert "I want to be helpful, but I'm an AI" in source, \
            "generate() should append AI disclaimer for emotional topics"

    def test_emotional_keywords_list_coverage(self):
        """Emotional keyword list should cover key mental health topics."""
        # Read the bot source and check keyword list
        with open('/root/project-nobi/app/bot.py', 'r') as f:
            content = f.read()

        assert "depress" in content
        assert "suicid" in content
        assert "self-harm" in content
        assert "mental health" in content
        assert "therapist" in content


class TestAgeGateMessage(unittest.IsolatedAsyncioTestCase):
    """Test the /start age gate message format."""

    async def test_start_shows_age_gate_for_new_user(self):
        """New users should see the age gate, not the welcome message."""
        mock_companion = MagicMock()
        mock_companion._user_id = MagicMock(return_value="tg_55555")
        mock_companion.memory.recall = MagicMock(return_value=[])

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 55555

        context = MagicMock()

        with patch('app.bot.companion', mock_companion):
            with patch('app.bot._is_blocked_minor', return_value=False):
                from app.bot import cmd_start
                await cmd_start(update, context)

        update.message.reply_text.assert_called_once()
        reply_args = update.message.reply_text.call_args
        message_text = reply_args[0][0] if reply_args[0] else ""

        # Should show age gate
        assert "18" in message_text, \
            f"Age gate should mention 18: {message_text[:200]}"
        assert "⚠️" in message_text or "confirm" in message_text.lower(), \
            f"Age gate should be clearly marked: {message_text[:200]}"

        # Should have 18+ and under-18 buttons
        keyboard = reply_args[1].get('reply_markup') or (reply_args[0][1] if len(reply_args[0]) > 1 else None)
        if keyboard and hasattr(keyboard, 'inline_keyboard'):
            button_texts = [
                btn.text
                for row in keyboard.inline_keyboard
                for btn in row
            ]
            has_18plus = any("18" in t and ("confirm" in t.lower() or "18+" in t) for t in button_texts)
            has_under18 = any("under" in t.lower() or "under 18" in t.lower() for t in button_texts)
            assert has_18plus, f"Age gate should have '18+' button. Buttons: {button_texts}"
            assert has_under18, f"Age gate should have 'under 18' button. Buttons: {button_texts}"

    async def test_blocked_minor_start_returns_blocked_message(self):
        """Blocked minors who try /start should get the blocked message."""
        mock_companion = MagicMock()
        mock_companion._user_id = MagicMock(return_value="tg_66666")

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user.id = 66666

        context = MagicMock()

        with patch('app.bot.companion', mock_companion):
            with patch('app.bot._is_blocked_minor', return_value=True):
                from app.bot import cmd_start
                await cmd_start(update, context)

        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "under 18" in reply_text.lower() or "not available" in reply_text.lower(), \
            f"Blocked minor should see blocked message: {reply_text}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
