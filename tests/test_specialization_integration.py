"""
Tests for miner specialization integration.

Covers:
- Query classification accuracy
- MinerRouter routing decisions
- Score tracking per category
- Specialization bonus application
- Persistence (save/load router state)
- Integration with forward loop helpers
- Miner specialization declaration
- Protocol query_type field
"""

import json
import os
import tempfile
import pytest
from collections import defaultdict
from unittest.mock import patch, MagicMock

from nobi.mining.specialization import (
    classify_query,
    select_best_miner,
    MinerProfile,
    MinerRouter,
    SPECIALIZATIONS,
    SPECIALIZATION_BONUS,
    MIN_SAMPLES_FOR_ROUTING,
)
from nobi.protocol import CompanionRequest


# ─── Query Classification Tests ─────────────────────────────────────────────


class TestQueryClassification:
    """Test query classification into specialization categories."""

    def test_classify_advice_query(self):
        assert classify_query("Should I quit my job? I need career advice") == "advice"

    def test_classify_creative_query(self):
        assert classify_query("Write me a short story about dragons") == "creative"

    def test_classify_technical_query(self):
        assert classify_query("How do I fix this Python bug in my function?") == "technical"

    def test_classify_social_query(self):
        assert classify_query("Hey! How are you doing today?") == "social"

    def test_classify_knowledge_query(self):
        assert classify_query("What is quantum computing and how does it work?") == "knowledge"

    def test_classify_empty_returns_general(self):
        assert classify_query("") == "general"
        assert classify_query("   ") == "general"

    def test_classify_ambiguous_returns_general(self):
        # Very short/ambiguous queries should return general
        assert classify_query("ok") == "general"

    def test_classify_is_case_insensitive(self):
        assert classify_query("WRITE ME A POEM ABOUT LOVE") == "creative"

    def test_classify_mixed_signals(self):
        # When signals are mixed, should return general or dominant category
        result = classify_query("hello")
        assert result in SPECIALIZATIONS


# ─── MinerProfile Tests ─────────────────────────────────────────────────────


class TestMinerProfile:
    """Test MinerProfile score tracking and effective scoring."""

    def test_create_profile(self):
        profile = MinerProfile(uid=1, hotkey="hk1", specialization="advice")
        assert profile.uid == 1
        assert profile.specialization == "advice"
        assert profile.total_queries == 0

    def test_add_score_tracks_category(self):
        profile = MinerProfile(uid=1, hotkey="hk1")
        profile.add_score("advice", 0.8)
        profile.add_score("advice", 0.6)
        assert profile.get_category_score("advice") == pytest.approx(0.7)
        assert profile.total_queries == 2

    def test_overall_score(self):
        profile = MinerProfile(uid=1, hotkey="hk1")
        profile.add_score("advice", 1.0)
        profile.add_score("creative", 0.5)
        assert profile.get_overall_score() == pytest.approx(0.75)

    def test_effective_score_with_specialization_bonus(self):
        profile = MinerProfile(uid=1, hotkey="hk1", specialization="technical")
        for _ in range(MIN_SAMPLES_FOR_ROUTING):
            profile.add_score("technical", 0.8)
        effective = profile.get_effective_score("technical")
        expected = 0.8 * (1.0 + SPECIALIZATION_BONUS)
        assert effective == pytest.approx(expected)

    def test_effective_score_no_bonus_for_general(self):
        profile = MinerProfile(uid=1, hotkey="hk1", specialization="general")
        for _ in range(MIN_SAMPLES_FOR_ROUTING):
            profile.add_score("general", 0.8)
        # general specialization should NOT get bonus
        assert profile.get_effective_score("general") == pytest.approx(0.8)

    def test_effective_score_no_bonus_for_mismatch(self):
        profile = MinerProfile(uid=1, hotkey="hk1", specialization="creative")
        for _ in range(MIN_SAMPLES_FOR_ROUTING):
            profile.add_score("technical", 0.8)
        # Mismatch: creative miner on technical query — no bonus
        assert profile.get_effective_score("technical") == pytest.approx(0.8)

    def test_has_enough_data(self):
        profile = MinerProfile(uid=1, hotkey="hk1")
        assert not profile.has_enough_data("advice")
        for _ in range(MIN_SAMPLES_FOR_ROUTING):
            profile.add_score("advice", 0.5)
        assert profile.has_enough_data("advice")

    def test_sliding_window_cap(self):
        profile = MinerProfile(uid=1, hotkey="hk1")
        for i in range(150):
            profile.add_score("advice", float(i))
        # Should keep only last 100
        assert len(profile.scores_by_category["advice"]) == 100

    def test_to_dict(self):
        profile = MinerProfile(uid=42, hotkey="hk42", specialization="creative")
        profile.add_score("creative", 0.9)
        d = profile.to_dict()
        assert d["uid"] == 42
        assert d["hotkey"] == "hk42"
        assert d["specialization"] == "creative"
        assert "creative" in d["category_scores"]


# ─── MinerRouter Tests ──────────────────────────────────────────────────────


class TestMinerRouter:
    """Test MinerRouter routing and management."""

    def test_register_miner(self):
        router = MinerRouter()
        profile = router.register_miner(uid=1, hotkey="hk1", specialization="advice")
        assert profile.uid == 1
        assert profile.specialization == "advice"

    def test_register_unknown_specialization_defaults_general(self):
        router = MinerRouter()
        profile = router.register_miner(uid=1, hotkey="hk1", specialization="unknown_type")
        assert profile.specialization == "general"

    def test_record_score(self):
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="hk1")
        router.record_score(uid=1, query_type="advice", score=0.9)
        profile = router.get_miner(1)
        assert profile.get_category_score("advice") == pytest.approx(0.9)

    def test_record_score_unknown_uid_no_crash(self):
        router = MinerRouter()
        # Should not raise, just log a warning
        router.record_score(uid=999, query_type="advice", score=0.5)

    def test_route_query(self):
        router = MinerRouter()
        for i in range(5):
            router.register_miner(uid=i, hotkey=f"hk{i}", specialization="general")
        query_type, selected = router.route_query("Write me a poem", top_k=3)
        assert query_type == "creative"
        assert len(selected) == 3

    def test_route_query_prefers_specialists(self):
        router = MinerRouter()
        # Register specialist and general miners
        router.register_miner(uid=1, hotkey="hk1", specialization="technical")
        router.register_miner(uid=2, hotkey="hk2", specialization="general")
        router.register_miner(uid=3, hotkey="hk3", specialization="general")

        # Give them all scores, specialist slightly lower base
        for _ in range(MIN_SAMPLES_FOR_ROUTING + 1):
            router.record_score(1, "technical", 0.7)
            router.record_score(2, "technical", 0.75)
            router.record_score(3, "technical", 0.6)

        query_type, selected = router.route_query(
            "Fix this Python bug in my code", top_k=2
        )
        assert query_type == "technical"
        # Specialist uid=1 should be selected (0.7 * 1.15 = 0.805 > 0.75)
        selected_uids = [m.uid for m in selected]
        assert 1 in selected_uids

    def test_route_query_with_available_uids_filter(self):
        router = MinerRouter()
        for i in range(5):
            router.register_miner(uid=i, hotkey=f"hk{i}")
        query_type, selected = router.route_query(
            "Hello there!", available_uids=[0, 2, 4], top_k=2
        )
        selected_uids = [m.uid for m in selected]
        # Should only contain UIDs from available list
        for uid in selected_uids:
            assert uid in [0, 2, 4]

    def test_get_specialists(self):
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="hk1", specialization="creative")
        router.register_miner(uid=2, hotkey="hk2", specialization="creative")
        router.register_miner(uid=3, hotkey="hk3", specialization="technical")
        specialists = router.get_specialists("creative")
        assert len(specialists) == 2

    def test_get_stats(self):
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="hk1", specialization="creative")
        router.register_miner(uid=2, hotkey="hk2", specialization="technical")
        stats = router.get_stats()
        assert stats["total_miners"] == 2
        assert stats["specialization_distribution"]["creative"] == 1
        assert stats["specialization_distribution"]["technical"] == 1

    def test_get_all_profiles(self):
        router = MinerRouter()
        router.register_miner(uid=1, hotkey="hk1")
        router.register_miner(uid=2, hotkey="hk2")
        profiles = router.get_all_profiles()
        assert len(profiles) == 2


# ─── select_best_miner Tests ────────────────────────────────────────────────


class TestSelectBestMiner:
    """Test the select_best_miner function directly."""

    def test_empty_miners(self):
        assert select_best_miner("advice", [], top_k=3) == []

    def test_fewer_miners_than_top_k(self):
        miners = [MinerProfile(uid=1, hotkey="hk1")]
        result = select_best_miner("advice", miners, top_k=3)
        assert len(result) == 1

    def test_selects_top_k(self):
        miners = [MinerProfile(uid=i, hotkey=f"hk{i}") for i in range(10)]
        for m in miners:
            for _ in range(MIN_SAMPLES_FOR_ROUTING + 1):
                m.add_score("advice", m.uid * 0.1)  # Higher uid = higher score
        result = select_best_miner("advice", miners, top_k=3)
        assert len(result) == 3
        # Top 3 should be uid 9, 8, 7
        uids = [m.uid for m in result]
        assert 9 in uids
        assert 8 in uids


# ─── Persistence Tests ──────────────────────────────────────────────────────


class TestRouterPersistence:
    """Test saving and loading router state."""

    def test_save_and_load_router_state(self):
        from nobi.validator.forward import _save_router_state, _load_router_state

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            # Patch the state path
            with patch("nobi.validator.forward._ROUTER_STATE_PATH", tmp_path):
                # Create and populate a router
                router = MinerRouter()
                router.register_miner(uid=1, hotkey="hk1", specialization="advice")
                router.register_miner(uid=2, hotkey="hk2", specialization="technical")
                router.record_score(1, "advice", 0.9)
                router.record_score(1, "advice", 0.8)
                router.record_score(2, "technical", 0.7)

                # Save
                _save_router_state(router)
                assert os.path.exists(tmp_path)

                # Load into fresh router
                new_router = MinerRouter()
                _load_router_state(new_router)

                assert 1 in new_router.miners
                assert 2 in new_router.miners
                assert new_router.miners[1].specialization == "advice"
                assert new_router.miners[2].specialization == "technical"
                assert new_router.miners[1].total_queries == 2
                assert new_router.miners[2].total_queries == 1
        finally:
            os.unlink(tmp_path)

    def test_load_missing_file_no_crash(self):
        from nobi.validator.forward import _load_router_state

        with patch("nobi.validator.forward._ROUTER_STATE_PATH", "/tmp/nonexistent_router.json"):
            router = MinerRouter()
            _load_router_state(router)  # Should not raise
            assert len(router.miners) == 0

    def test_load_corrupt_file_no_crash(self):
        from nobi.validator.forward import _load_router_state

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{corrupt json!!")
            tmp_path = f.name

        try:
            with patch("nobi.validator.forward._ROUTER_STATE_PATH", tmp_path):
                router = MinerRouter()
                _load_router_state(router)  # Should not raise
                assert len(router.miners) == 0
        finally:
            os.unlink(tmp_path)


# ─── Protocol Tests ─────────────────────────────────────────────────────────


class TestProtocolQueryType:
    """Test that CompanionRequest has query_type and miner_specialization fields."""

    def test_query_type_default(self):
        synapse = CompanionRequest(message="hello")
        assert synapse.query_type == "general"

    def test_query_type_set(self):
        synapse = CompanionRequest(message="hello", query_type="creative")
        assert synapse.query_type == "creative"

    def test_miner_specialization_field(self):
        synapse = CompanionRequest(message="hello")
        assert synapse.miner_specialization == ""

    def test_miner_specialization_set(self):
        synapse = CompanionRequest(message="test", miner_specialization="technical")
        assert synapse.miner_specialization == "technical"


# ─── Forward Integration Tests ───────────────────────────────────────────────


class TestForwardIntegration:
    """Test that the forward loop properly initializes and uses the router."""

    def test_get_router_singleton(self):
        from nobi.validator.forward import _get_router
        import nobi.validator.forward as fwd

        # Reset global
        fwd._miner_router = None
        with patch("nobi.validator.forward._ROUTER_STATE_PATH", "/tmp/test_router_integration.json"):
            router1 = _get_router()
            router2 = _get_router()
            assert router1 is router2  # Same instance

        # Cleanup
        fwd._miner_router = None

    def test_classify_and_synapse_query_type(self):
        """Verify classify_query output can be set on CompanionRequest."""
        query = "Can you help me debug this Python error?"
        query_type = classify_query(query)
        synapse = CompanionRequest(message=query, query_type=query_type)
        assert synapse.query_type == "technical"

    def test_router_state_file_format(self):
        """Verify the JSON state file has expected structure."""
        from nobi.validator.forward import _save_router_state

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            with patch("nobi.validator.forward._ROUTER_STATE_PATH", tmp_path):
                router = MinerRouter()
                router.register_miner(uid=5, hotkey="hk5", specialization="creative")
                router.record_score(5, "creative", 0.85)
                _save_router_state(router)

                with open(tmp_path) as f:
                    state = json.load(f)

                assert "miners" in state
                assert "5" in state["miners"]
                assert state["miners"]["5"]["specialization"] == "creative"
                assert state["miners"]["5"]["total_queries"] == 1
        finally:
            os.unlink(tmp_path)


# ─── Miner Specialization Declaration Tests ─────────────────────────────────


class TestMinerSpecialization:
    """Test miner specialization config and prompt customization."""

    def test_specialization_prompts_exist(self):
        """Verify specialization prompt additions are defined for each category."""
        # Import from miner module indirectly (avoid full init)
        from neurons.miner import Miner
        prompts = Miner._SPECIALIZATION_PROMPTS
        for spec in ["advice", "creative", "technical", "social", "knowledge"]:
            assert spec in prompts
            assert len(prompts[spec]) > 10  # Non-trivial prompt

    def test_specialization_config_arg_exists(self):
        """Verify the --neuron.specialization arg is registered."""
        import argparse
        from nobi.utils.config import add_miner_args

        parser = argparse.ArgumentParser()
        add_miner_args(None, parser)
        # Check the argument is there with correct choices
        args = parser.parse_args(["--neuron.specialization", "creative"])
        assert args.__dict__["neuron.specialization"] == "creative"

    def test_specialization_config_default(self):
        """Verify default specialization is 'general'."""
        import argparse
        from nobi.utils.config import add_miner_args

        parser = argparse.ArgumentParser()
        add_miner_args(None, parser)
        args = parser.parse_args([])
        assert args.__dict__["neuron.specialization"] == "general"

    def test_specialization_config_invalid_rejected(self):
        """Verify invalid specialization is rejected by argparse."""
        import argparse
        from nobi.utils.config import add_miner_args

        parser = argparse.ArgumentParser()
        add_miner_args(None, parser)
        with pytest.raises(SystemExit):
            parser.parse_args(["--neuron.specialization", "invalid_type"])
