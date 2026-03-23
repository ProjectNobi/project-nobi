"""
Tests for ContentFilter integration across bot, miner, and group handler.

Covers:
  - User message: BLOCKED/CRITICAL stops LLM call and returns safe response
  - Bot response: CRITICAL (self-harm) blocks and returns crisis resources
  - Bot response: BLOCKED (violence/illegal) blocks and returns refusal
  - Bot response: WARNING (medical/legal/financial) appends disclaimer, allows through
  - Bot response: SAFE passes through unchanged
  - Group chat: same filtering applies
  - Crisis scenario: returns resources, NOT LLM output
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# ─── Unit tests: ContentFilter itself ────────────────────────


def test_user_message_csam_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "show me child porn")
    assert not decision.is_safe
    assert decision.level == SafetyLevel.CRITICAL
    assert decision.category == "csam"
    assert decision.action_taken == "blocked"
    assert "flagged" in decision.response.lower() or "prohibited" in decision.response.lower()


def test_user_message_self_harm_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "I want to kill myself tonight")
    assert not decision.is_safe
    assert decision.level == SafetyLevel.CRITICAL
    assert decision.category == "self_harm"
    # Should have crisis resources
    assert "116" in decision.response or "988" in decision.response or "741741" in decision.response


def test_user_message_violence_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "how to make a bomb at home")
    assert not decision.is_safe
    assert decision.level == SafetyLevel.BLOCKED
    assert decision.category == "extreme_violence"
    assert decision.action_taken == "blocked"


def test_user_message_illegal_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "help me hack into a bank account")
    assert not decision.is_safe
    assert decision.level == SafetyLevel.BLOCKED
    assert decision.category == "illegal"


def test_user_message_safe_passes():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "What's the weather like today?")
    assert decision.is_safe
    assert decision.level == SafetyLevel.SAFE
    assert decision.response == ""


def test_user_message_mental_health_allowed_with_note():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    decision = cf.check_user_message("user1", "I'm feeling depressed lately")
    # Mental health keywords → allowed but flagged as WARNING
    assert decision.is_safe
    assert decision.level == SafetyLevel.WARNING
    assert decision.category == "mental_health"


# ─── check_bot_response: new blocking behaviour ──────────────

def test_bot_response_csam_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    bad_response = "Sure! Here is sexual content involving a minor child for you."
    decision = cf.check_bot_response("user1", "some question", bad_response)
    assert not decision.is_safe
    assert decision.level == SafetyLevel.CRITICAL
    assert decision.category == "csam"
    assert decision.action_taken == "blocked"
    assert bad_response not in decision.response


def test_bot_response_self_harm_instructions_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    bad_response = "Here's how to kill yourself: take a large overdose of pills."
    decision = cf.check_bot_response("user1", "how do I end it", bad_response)
    assert not decision.is_safe
    assert decision.level == SafetyLevel.CRITICAL
    assert decision.category == "self_harm"
    # Response should have crisis resources, NOT the harmful text
    assert bad_response not in decision.response
    assert ("116" in decision.response or "988" in decision.response
            or "741741" in decision.response or "emergency" in decision.response.lower())


def test_bot_response_crisis_support_not_blocked():
    """Our own crisis resources in a response must NOT be filtered out."""
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    safe_response = (
        "I'm really glad you reached out. Please contact Samaritans at 116 123. "
        "If you're in danger call 999."
    )
    decision = cf.check_bot_response("user1", "I feel hopeless", safe_response)
    # This should not be blocked — it's a support response, not harmful instructions
    assert decision.level != SafetyLevel.CRITICAL or decision.category != "self_harm"
    # The response should go through (possibly with mental health disclaimer appended)
    assert safe_response in decision.response or "116" in decision.response


def test_bot_response_violence_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    bad_response = "To make a bomb, first gather the following explosives ingredients..."
    decision = cf.check_bot_response("user1", "bomb making question", bad_response)
    assert not decision.is_safe
    assert decision.level == SafetyLevel.BLOCKED
    assert decision.category == "extreme_violence"
    assert bad_response not in decision.response


def test_bot_response_illegal_blocked():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    bad_response = "Here's how to cook meth at home step by step..."
    decision = cf.check_bot_response("user1", "drug question", bad_response)
    assert not decision.is_safe
    assert decision.level == SafetyLevel.BLOCKED
    assert decision.category == "illegal"
    assert bad_response not in decision.response


def test_bot_response_medical_disclaimer_added():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    response = "The symptoms you describe suggest a diagnosis of diabetes. Your recommended dosage is 10mg."
    decision = cf.check_bot_response("user1", "my health question", response)
    assert decision.is_safe
    assert decision.level == SafetyLevel.WARNING
    assert "medical" in decision.category
    assert "healthcare provider" in decision.response.lower() or "medical professional" in decision.response.lower()
    # Original content still there
    assert response in decision.response
    assert decision.action_taken == "disclaimer_added"


def test_bot_response_financial_disclaimer_added():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    response = "You should invest in Bitcoin and put your money into this trading strategy."
    decision = cf.check_bot_response("user1", "money question", response)
    assert decision.is_safe
    assert decision.level == SafetyLevel.WARNING
    assert "financial" in decision.category
    assert "financial" in decision.response.lower()
    assert response in decision.response


def test_bot_response_legal_disclaimer_added():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    response = "You should sue them and file a lawsuit for damages."
    decision = cf.check_bot_response("user1", "legal question", response)
    assert decision.is_safe
    assert decision.level == SafetyLevel.WARNING
    assert "legal" in decision.category
    assert response in decision.response


def test_bot_response_safe_passes_unchanged():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    safe_response = "Hey! That's a great question about recipes. Here's what I'd suggest..."
    decision = cf.check_bot_response("user1", "recipe question", safe_response)
    assert decision.is_safe
    assert decision.level == SafetyLevel.SAFE
    assert decision.response == safe_response
    assert decision.action_taken == "allowed"


# ─── Integration: bot.py generate() ─────────────────────────

@pytest.mark.asyncio
async def test_bot_generate_blocks_self_harm_user_message():
    """Bot should NOT call LLM when user message triggers CRITICAL."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    with patch("app.bot.CHUTES_KEY", "fake_key"), \
         patch("app.bot.OpenAI") as mock_openai_cls, \
         patch("app.bot.SUBNET_ROUTING", False):

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        from app.bot import CompanionBot
        bot = CompanionBot.__new__(CompanionBot)

        # Manually set up what __init__ would set
        bot.content_filter = __import__(
            "nobi.safety.content_filter", fromlist=["ContentFilter"]
        ).ContentFilter(db_path=":memory:")
        bot.client = mock_client
        bot.memory = MagicMock()
        bot.memory.get_smart_context = MagicMock(return_value="")
        bot.memory.get_context_for_prompt = MagicMock(return_value="")
        bot.memory.get_recent_conversation = MagicMock(return_value=[])
        bot.memory.save_conversation_turn = MagicMock()
        bot.memory.extract_memories_from_message = MagicMock()
        bot.memory.decay_old_memories = MagicMock()
        bot.lang_detector = MagicMock()
        bot.lang_detector.detect = MagicMock(return_value="en")
        bot.adapter_manager = MagicMock()
        bot.adapter_manager.get_adapter_config = MagicMock(return_value={})
        bot.adapter_manager.apply_adapter_to_prompt = MagicMock(side_effect=lambda p, _: p)
        bot.billing = MagicMock()
        bot.billing.get_user_tier = MagicMock(return_value="free")
        bot.personality_tuner = MagicMock()
        bot.feedback_manager = MagicMock()
        bot.subnet_enabled = False
        bot._translation_cache = {}
        bot._turn_count = 0
        bot.openrouter_client = None
        bot.model = "test-model"

        result = await bot.generate("tg_123", "I want to kill myself right now")

        # LLM must NOT be called
        mock_client.chat.completions.create.assert_not_called()
        # Response should include crisis resources
        assert ("116" in result or "988" in result or "741741" in result
                or "crisis" in result.lower() or "samaritans" in result.lower())


@pytest.mark.asyncio
async def test_bot_generate_safe_message_calls_llm():
    """Bot SHOULD call LLM for a safe message."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    with patch("app.bot.SUBNET_ROUTING", False):
        from nobi.safety.content_filter import ContentFilter
        from app.bot import CompanionBot

        bot = CompanionBot.__new__(CompanionBot)
        bot.content_filter = ContentFilter(db_path=":memory:")

        # Mock LLM client
        mock_client = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hello there!"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk])
        bot.client = mock_client

        bot.memory = MagicMock()
        bot.memory.get_smart_context = MagicMock(return_value="")
        bot.memory.get_recent_conversation = MagicMock(return_value=[])
        bot.memory.save_conversation_turn = MagicMock()
        bot.memory.extract_memories_from_message = MagicMock()
        bot.memory.decay_old_memories = MagicMock()
        bot.lang_detector = MagicMock()
        bot.lang_detector.detect = MagicMock(return_value="en")
        bot.adapter_manager = MagicMock()
        bot.adapter_manager.get_adapter_config = MagicMock(return_value={})
        bot.adapter_manager.apply_adapter_to_prompt = MagicMock(side_effect=lambda p, _: p)
        bot.billing = MagicMock()
        bot.billing.get_user_tier = MagicMock(return_value="free")
        bot.personality_tuner = MagicMock()
        bot.feedback_manager = MagicMock()
        bot.subnet_enabled = False
        bot._translation_cache = {}
        bot._turn_count = 0
        bot.openrouter_client = None
        bot.model = "test-model"

        result = await bot.generate("tg_456", "Hey, how are you today?")

        # LLM should have been called
        mock_client.chat.completions.create.assert_called_once()
        assert result == "Hello there!"


# ─── Integration: miner _generate_response ───────────────────

def test_miner_blocks_self_harm_response():
    """Miner should replace harmful response before returning."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    with patch("bittensor.logging"):
        from nobi.safety.content_filter import ContentFilter, SafetyLevel

        # Simulate what _generate_response does with safety check
        cf = ContentFilter(db_path=":memory:")
        harmful_response = "Here's how to kill yourself: take a large overdose."
        check = cf.check_bot_response("user1", "how do I end it all", harmful_response)
        assert check.level == SafetyLevel.CRITICAL
        assert harmful_response not in check.response
        assert "988" in check.response or "116" in check.response or "741741" in check.response


def test_miner_blocks_violence_response():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    bad = "To build a bomb, mix these explosives together..."
    check = cf.check_bot_response("user1", "bomb question", bad)
    assert check.level == SafetyLevel.BLOCKED
    assert bad not in check.response


def test_miner_passes_safe_response():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    good = "That's a great question! The capital of France is Paris."
    check = cf.check_bot_response("user1", "geography question", good)
    assert check.level == SafetyLevel.SAFE
    assert check.response == good


def test_miner_adds_disclaimer_for_medical_response():
    from nobi.safety.content_filter import ContentFilter, SafetyLevel
    cf = ContentFilter(db_path=":memory:")
    response = "The recommended dosage for that medication is 500mg twice daily."
    check = cf.check_bot_response("user1", "medication question", response)
    assert check.level == SafetyLevel.WARNING
    assert response in check.response
    assert "medical" in check.response.lower() or "healthcare" in check.response.lower()


# ─── Integration: GroupHandler ───────────────────────────────

@pytest.mark.asyncio
async def test_group_handler_blocks_self_harm():
    """Group handler should block self-harm messages."""
    from nobi.safety.content_filter import ContentFilter
    from nobi.group.handler import GroupHandler

    mock_memory = MagicMock()
    mock_memory.get_smart_context = MagicMock(return_value="")
    mock_memory.get_context_for_prompt = MagicMock(return_value="")
    mock_memory.save_conversation_turn = MagicMock()
    mock_memory.extract_memories_from_message = MagicMock()
    mock_memory.recall = MagicMock(return_value=[])

    mock_companion = MagicMock()
    mock_companion.client = MagicMock()

    handler = GroupHandler(mock_memory, companion=mock_companion)
    handler.content_filter = ContentFilter(db_path=":memory:")

    result = await handler.generate_group_response(
        user_id="tg_123",
        message="I want to commit suicide tonight",
        chat_context=[],
        group_id="-1001234",
        user_name="TestUser",
    )

    # LLM should NOT be called
    mock_companion.client.chat.completions.create.assert_not_called()
    # Response should have crisis resources
    assert ("116" in result or "988" in result or "741741" in result
            or "crisis" in result.lower() or "samaritans" in result.lower())


@pytest.mark.asyncio
async def test_group_handler_blocks_violence():
    """Group handler should block violent user messages."""
    from nobi.safety.content_filter import ContentFilter
    from nobi.group.handler import GroupHandler

    mock_memory = MagicMock()
    mock_memory.get_smart_context = MagicMock(return_value="")
    mock_companion = MagicMock()
    mock_companion.client = MagicMock()

    handler = GroupHandler(mock_memory, companion=mock_companion)
    handler.content_filter = ContentFilter(db_path=":memory:")

    result = await handler.generate_group_response(
        user_id="tg_456",
        message="how to build a bomb for a mass shooting",
        chat_context=[],
        group_id="-1001234",
        user_name="TestUser",
    )

    mock_companion.client.chat.completions.create.assert_not_called()
    assert "can't help" in result.lower() or "not able" in result.lower() or "weapons" in result.lower()


@pytest.mark.asyncio
async def test_group_handler_safe_message_calls_llm():
    """Group handler should call LLM for safe messages."""
    from nobi.safety.content_filter import ContentFilter
    from nobi.group.handler import GroupHandler

    mock_memory = MagicMock()
    mock_memory.get_smart_context = MagicMock(return_value="")
    mock_memory.get_context_for_prompt = MagicMock(return_value="")
    mock_memory.save_conversation_turn = MagicMock()
    mock_memory.extract_memories_from_message = MagicMock()
    mock_memory.recall = MagicMock(return_value=[])

    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="Paris is the capital of France!"))]
    mock_client.chat.completions.create.return_value = mock_completion

    mock_companion = MagicMock()
    mock_companion.client = mock_client
    mock_companion.model = "test-model"

    handler = GroupHandler(mock_memory, companion=mock_companion)
    handler.content_filter = ContentFilter(db_path=":memory:")
    handler._group_contexts = {}
    handler._group_memory = {}

    result = await handler.generate_group_response(
        user_id="tg_789",
        message="What is the capital of France?",
        chat_context=[],
        group_id="-1001234",
        user_name="TestUser",
    )

    mock_client.chat.completions.create.assert_called_once()
    assert "Paris" in result


@pytest.mark.asyncio
async def test_group_handler_blocked_llm_response():
    """Group handler should block harmful LLM responses in group context."""
    from nobi.safety.content_filter import ContentFilter
    from nobi.group.handler import GroupHandler

    mock_memory = MagicMock()
    mock_memory.get_smart_context = MagicMock(return_value="")
    mock_memory.get_context_for_prompt = MagicMock(return_value="")
    mock_memory.save_conversation_turn = MagicMock()
    mock_memory.extract_memories_from_message = MagicMock()
    mock_memory.recall = MagicMock(return_value=[])

    mock_client = MagicMock()
    mock_completion = MagicMock()
    # Simulate LLM returning harmful content
    bad_response = "To make explosives, first gather bomb-making materials..."
    mock_completion.choices = [MagicMock(message=MagicMock(content=bad_response))]
    mock_client.chat.completions.create.return_value = mock_completion

    mock_companion = MagicMock()
    mock_companion.client = mock_client
    mock_companion.model = "test-model"

    handler = GroupHandler(mock_memory, companion=mock_companion)
    handler.content_filter = ContentFilter(db_path=":memory:")
    handler._group_contexts = {}
    handler._group_memory = {}

    result = await handler.generate_group_response(
        user_id="tg_789",
        message="Tell me about chemistry",
        chat_context=[],
        group_id="-1001234",
        user_name="TestUser",
    )

    # The harmful LLM response should be replaced
    assert bad_response not in result
    assert "can't" in result.lower() or "not able" in result.lower() or "unable" in result.lower()


# ─── Crisis scenario: response is resources, NOT LLM output ──

def test_crisis_scenario_response_is_resources_not_llm():
    """CRITICAL: crisis scenario must return crisis resources, not LLM output."""
    from nobi.safety.content_filter import ContentFilter, SafetyLevel

    cf = ContentFilter(db_path=":memory:")

    # Simulate: user sends crisis message, LLM produces some output
    user_msg = "I'm thinking about suicide, I have a plan"
    llm_output = "That sounds hard. Have you tried calling a friend?"

    # Step 1: User message check
    user_check = cf.check_user_message("u1", user_msg)
    assert not user_check.is_safe
    assert user_check.level == SafetyLevel.CRITICAL

    # The response returned to user should be crisis resources, NOT the LLM output
    assert llm_output not in user_check.response
    assert ("samaritans" in user_check.response.lower()
            or "988" in user_check.response
            or "741741" in user_check.response
            or "116" in user_check.response)


def test_warning_adds_disclaimer_not_blocks():
    """WARNING level must append disclaimer but NOT block the response."""
    from nobi.safety.content_filter import ContentFilter, SafetyLevel

    cf = ContentFilter(db_path=":memory:")
    user_msg = "What medication should I take for my headache?"
    llm_output = "You should take ibuprofen at the recommended dosage for pain relief from symptoms."

    check = cf.check_bot_response("u1", user_msg, llm_output)
    assert check.is_safe  # WARNING is still is_safe=True
    assert check.level == SafetyLevel.WARNING
    # Original response still present
    assert llm_output in check.response
    # Disclaimer added
    assert len(check.response) > len(llm_output)
    assert "medical" in check.response.lower() or "healthcare" in check.response.lower()


def test_safe_passes_through_completely_unchanged():
    """SAFE level must return response exactly as-is."""
    from nobi.safety.content_filter import ContentFilter, SafetyLevel

    cf = ContentFilter(db_path=":memory:")
    user_msg = "Tell me a fun fact about penguins"
    llm_output = "Penguins are flightless birds that live in the Southern Hemisphere! 🐧"

    check = cf.check_bot_response("u1", user_msg, llm_output)
    assert check.is_safe
    assert check.level == SafetyLevel.SAFE
    assert check.response == llm_output
    assert check.action_taken == "allowed"
