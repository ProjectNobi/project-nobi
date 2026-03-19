"""
Phase 4 Tests — Voice, Image, Miner Specialization, Protocol Updates.
"""

import pytest
import sys
import os
from collections import defaultdict
from unittest.mock import patch, MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─── Miner Specialization Tests ─────────────────────────────────────────────

class TestQueryClassification:
    """Test query classification into specialization categories."""

    def test_advice_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("Should I change my career?") == "advice"
        assert classify_query("I'm feeling stressed about work") == "advice"
        assert classify_query("Help me decide between two options") == "advice"

    def test_creative_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("Write me a short story about space") == "creative"
        assert classify_query("Help me brainstorm ideas for a novel") == "creative"

    def test_technical_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("How do I fix this Python bug?") == "technical"
        assert classify_query("Explain the algorithm for binary search") == "technical"

    def test_social_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("Hey, how are you doing today?") == "social"
        assert classify_query("Tell me a joke") == "social"

    def test_knowledge_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("What is quantum computing?") == "knowledge"
        assert classify_query("Explain the history of Rome") == "knowledge"

    def test_general_query(self):
        from nobi.mining.specialization import classify_query
        assert classify_query("ok") == "general"
        assert classify_query("") == "general"
        assert classify_query("   ") == "general"


class TestMinerProfile:
    """Test MinerProfile scoring and data tracking."""

    def test_create_profile(self):
        from nobi.mining.specialization import MinerProfile
        profile = MinerProfile(uid=1, hotkey="test_hotkey", specialization="advice")
        assert profile.uid == 1
        assert profile.specialization == "advice"
        assert profile.total_queries == 0

    def test_add_score(self):
        from nobi.mining.specialization import MinerProfile
        profile = MinerProfile(uid=1, hotkey="test")
        profile.add_score("advice", 0.8)
        profile.add_score("advice", 0.9)
        assert profile.total_queries == 2
        assert abs(profile.get_category_score("advice") - 0.85) < 0.01

    def test_effective_score_with_bonus(self):
        from nobi.mining.specialization import MinerProfile, SPECIALIZATION_BONUS
        profile = MinerProfile(uid=1, hotkey="test", specialization="technical")
        profile.add_score("technical", 0.8)
        effective = profile.get_effective_score("technical")
        expected = 0.8 * (1.0 + SPECIALIZATION_BONUS)
        assert abs(effective - expected) < 0.01

    def test_no_bonus_for_general(self):
        from nobi.mining.specialization import MinerProfile
        profile = MinerProfile(uid=1, hotkey="test", specialization="general")
        profile.add_score("general", 0.8)
        assert abs(profile.get_effective_score("general") - 0.8) < 0.01

    def test_to_dict(self):
        from nobi.mining.specialization import MinerProfile
        profile = MinerProfile(uid=42, hotkey="abc123", specialization="creative")
        d = profile.to_dict()
        assert d["uid"] == 42
        assert d["hotkey"] == "abc123"
        assert d["specialization"] == "creative"


class TestMinerRouter:
    """Test the MinerRouter for query routing."""

    def test_register_miner(self):
        from nobi.mining.specialization import MinerRouter
        router = MinerRouter()
        profile = router.register_miner(uid=1, hotkey="h1", specialization="advice")
        assert profile.specialization == "advice"
        assert len(router.miners) == 1

    def test_route_query(self):
        from nobi.mining.specialization import MinerRouter
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="h1", specialization="advice")
        router.register_miner(uid=2, hotkey="h2", specialization="technical")

        query_type, selected = router.route_query("Should I quit my job?")
        assert query_type == "advice"
        assert len(selected) > 0

    def test_get_stats(self):
        from nobi.mining.specialization import MinerRouter
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="h1", specialization="advice")
        router.register_miner(uid=2, hotkey="h2", specialization="advice")
        router.register_miner(uid=3, hotkey="h3", specialization="technical")

        stats = router.get_stats()
        assert stats["total_miners"] == 3
        assert stats["specialization_distribution"]["advice"] == 2
        assert stats["specialization_distribution"]["technical"] == 1

    def test_invalid_specialization_defaults_to_general(self):
        from nobi.mining.specialization import MinerRouter
        router = MinerRouter()
        profile = router.register_miner(uid=1, hotkey="h1", specialization="invalid_type")
        assert profile.specialization == "general"

    def test_select_best_miner_with_scores(self):
        from nobi.mining.specialization import MinerRouter, MIN_SAMPLES_FOR_ROUTING
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="h1", specialization="advice")
        router.register_miner(uid=2, hotkey="h2", specialization="advice")

        # Add enough scores
        for _ in range(MIN_SAMPLES_FOR_ROUTING + 1):
            router.record_score(uid=1, query_type="advice", score=0.9)
            router.record_score(uid=2, query_type="advice", score=0.5)

        _, selected = router.route_query("I need some advice", top_k=1)
        assert len(selected) == 1
        assert selected[0].uid == 1  # Higher scorer


class TestSelectBestMiner:
    """Test the select_best_miner function."""

    def test_empty_miners(self):
        from nobi.mining.specialization import select_best_miner
        result = select_best_miner("advice", [])
        assert result == []

    def test_fewer_than_top_k(self):
        from nobi.mining.specialization import select_best_miner, MinerProfile
        miners = [MinerProfile(uid=1, hotkey="h1")]
        result = select_best_miner("advice", miners, top_k=3)
        assert len(result) == 1


# ─── Image Handler Tests ─────────────────────────────────────────────────────

class TestImageHandler:
    """Test image analysis response parsing."""

    def test_parse_vision_response(self):
        from nobi.vision.image_handler import _parse_vision_response

        raw = (
            "DESCRIPTION: A fluffy orange cat sleeping on a couch\n"
            "RESPONSE: What a cute cat! What's their name? 🐱\n"
            "MEMORIES: User has an orange cat, cat sleeps on couch"
        )
        desc, resp, mems = _parse_vision_response(raw)
        assert "orange cat" in desc
        assert "cute cat" in resp
        assert len(mems) == 2

    def test_parse_no_memories(self):
        from nobi.vision.image_handler import _parse_vision_response

        raw = (
            "DESCRIPTION: A sunset over the ocean\n"
            "RESPONSE: Beautiful sunset! 🌅\n"
            "MEMORIES: none"
        )
        _, _, mems = _parse_vision_response(raw)
        assert mems == []

    def test_parse_fallback(self):
        from nobi.vision.image_handler import _parse_vision_response

        raw = "Just a plain text response without structure."
        desc, resp, mems = _parse_vision_response(raw)
        assert resp == raw.strip()
        assert mems == []

    def test_sync_fallback(self):
        from nobi.vision.image_handler import analyze_image_sync

        result = analyze_image_sync(b"fake_image_data")
        assert result["success"] is False
        assert "response" in result


# ─── Voice Tests (Mock) ──────────────────────────────────────────────────────

class TestVoiceTTS:
    """Test TTS functionality."""

    def test_cache_key_generation(self):
        from nobi.voice.tts import _get_cache_key
        key1 = _get_cache_key("hello", "voice1")
        key2 = _get_cache_key("hello", "voice2")
        key3 = _get_cache_key("hello", "voice1")
        assert key1 != key2
        assert key1 == key3

    def test_base64_generation_without_gtts(self):
        from nobi.voice.tts import generate_speech_base64
        # Will return None if gTTS is not installed
        result = generate_speech_base64("test")
        # Just verify it doesn't crash
        assert result is None or isinstance(result, str)


class TestVoiceSTT:
    """Test STT functionality."""

    def test_base64_transcription_without_whisper(self):
        import base64
        from nobi.voice.stt import transcribe_base64
        # Will return None if whisper is not installed
        fake_audio = base64.b64encode(b"fake audio data").decode()
        result = transcribe_base64(fake_audio)
        assert result is None or isinstance(result, str)


# ─── Protocol Tests ──────────────────────────────────────────────────────────

class TestProtocolUpdates:
    """Test that protocol classes are properly defined."""

    def test_companion_request_has_query_type(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="test")
        assert hasattr(req, "query_type")
        assert req.query_type == "general"

    def test_companion_request_has_miner_specialization(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="test")
        assert hasattr(req, "miner_specialization")
        assert req.miner_specialization == ""

    def test_voice_request_synapse(self):
        from nobi.protocol import VoiceRequest
        req = VoiceRequest()
        assert req.audio_data == ""
        assert req.audio_format == "wav"
        assert req.language == "en"
        assert req.transcription == ""
        assert req.response_text == ""
        assert req.response_audio == ""

    def test_image_request_synapse(self):
        from nobi.protocol import ImageRequest
        req = ImageRequest()
        assert req.image_data == ""
        assert req.image_format == "jpg"
        assert req.caption == ""
        assert req.description == ""
        assert req.response == ""
        assert req.extracted_memories == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
