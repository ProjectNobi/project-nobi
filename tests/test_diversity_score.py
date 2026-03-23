"""
Tests for diversity_score() — miner diversity scoring.

Covers:
- Unique responses get neutral or bonus multiplier
- Near-duplicate responses are penalised
- High-similarity copies get maximum penalty
- Model fingerprint penalty (many miners with same length+vocab buckets)
- Diversity bonus for unique + substantive responses
- Edge cases: empty list, single response, all-empty strings
- Integration with get_rewards() (backward compat)
"""

import numpy as np
import pytest

from nobi.validator.reward import diversity_score


# ── Helpers ───────────────────────────────────────────────────────────────────

UNIQUE_RESPONSE_A = (
    "Sure! To make scrambled eggs, crack two eggs into a bowl, whisk them with "
    "a pinch of salt, then pour into a buttered pan on low heat. Stir gently "
    "until just set. Serve immediately for the best texture."
)

UNIQUE_RESPONSE_B = (
    "I'd suggest starting with a warm-up run of about 10 minutes, followed by "
    "interval sprints: 30 seconds at maximum effort, then 90 seconds recovery. "
    "Repeat 6 times, then cool down with 5 minutes of easy jogging."
)

UNIQUE_RESPONSE_C = (
    "Quantum entanglement occurs when particles interact in ways such that the "
    "quantum state of each particle cannot be described independently. Measuring "
    "one particle instantly affects its partner, regardless of distance."
)

DUPLICATE_RESPONSE = (
    "Sure! To make scrambled eggs, crack two eggs into a bowl, whisk them with "
    "a pinch of salt, then pour into a buttered pan on low heat. Stir gently "
    "until just set. Serve immediately for the best texture."
)  # Identical to UNIQUE_RESPONSE_A


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_list_returns_empty_array(self):
        result = diversity_score([])
        assert len(result) == 0
        assert isinstance(result, np.ndarray)

    def test_single_response_returns_one(self):
        result = diversity_score(["hello world"])
        assert len(result) == 1
        assert result[0] == pytest.approx(1.0)

    def test_all_empty_strings(self):
        result = diversity_score(["", "", ""])
        assert len(result) == 3
        # Empty strings are similar to each other (all empty sets); should be penalised
        assert all(isinstance(v, float) for v in result.tolist())

    def test_returns_float32_array(self):
        result = diversity_score([UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B])
        assert result.dtype == np.float32


# ── Unique responses ──────────────────────────────────────────────────────────

class TestUniqueResponses:
    def test_all_unique_responses_neutral_or_above(self):
        """Unique substantive responses should not be penalised."""
        responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B, UNIQUE_RESPONSE_C]
        result = diversity_score(responses)
        # All multipliers ≥ 1.0 (neutral or bonus)
        assert all(m >= 1.0 for m in result.tolist()), f"Got {result}"

    def test_unique_substantive_gets_bonus(self):
        """Unique responses with ≥ 20 words should receive diversity_bonus."""
        responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B, UNIQUE_RESPONSE_C]
        result = diversity_score(responses, diversity_bonus=0.05)
        assert all(m >= 1.05 - 1e-5 for m in result.tolist()), f"Got {result}"

    def test_unique_short_no_bonus(self):
        """Short responses (< 20 words) should not receive bonus."""
        short_a = "hello"
        short_b = "world"
        short_c = "testing"
        result = diversity_score([short_a, short_b, short_c], diversity_bonus=0.05)
        # Short: no bonus applied; multipliers ≤ 1.0
        assert all(m <= 1.0 + 1e-5 for m in result.tolist())


# ── Duplicate penalty ─────────────────────────────────────────────────────────

class TestDuplicatePenalty:
    def test_identical_responses_penalised(self):
        """Two identical responses should both be penalised."""
        responses = [UNIQUE_RESPONSE_A, DUPLICATE_RESPONSE]
        result = diversity_score(responses, similarity_threshold=0.85)
        # Both are penalised (multiplier < 1.0)
        assert all(m < 1.0 for m in result.tolist()), f"Got {result}"

    def test_identical_responses_multiplier_at_most_070(self):
        """A duplicate pair should receive a multiplier ≤ 0.70 (penalised)."""
        responses = [UNIQUE_RESPONSE_A, DUPLICATE_RESPONSE]
        result = diversity_score(responses, similarity_threshold=0.85)
        # Both should be penalised; exact value depends on whether they hit
        # the high_similarity_threshold (0.30) or regular threshold (0.70)
        assert all(m <= 0.70 + 1e-5 for m in result.tolist()), f"Got {result}"
        assert all(m >= 0.29 for m in result.tolist()), f"Got {result}"

    def test_high_similarity_max_penalty(self):
        """Near-exact copies above high_similarity_threshold → 0.30 multiplier."""
        # Use two copies of the same long string
        long_text = UNIQUE_RESPONSE_A * 3
        responses = [long_text, long_text]
        result = diversity_score(
            responses,
            similarity_threshold=0.80,
            high_similarity_threshold=0.95,
        )
        assert all(abs(m - 0.30) < 0.01 for m in result.tolist()), f"Got {result}"

    def test_multiple_copy_pairs_stronger_penalty(self):
        """A response involved in 2+ duplicate pairs → 0.50 multiplier."""
        # Miner 0 is identical to both miner 1 and miner 2
        r0 = UNIQUE_RESPONSE_A
        r1 = UNIQUE_RESPONSE_A  # copy 1
        r2 = UNIQUE_RESPONSE_A  # copy 2
        r3 = UNIQUE_RESPONSE_B  # unique
        result = diversity_score([r0, r1, r2, r3], similarity_threshold=0.85)
        # r0, r1, r2 each involved in 2 copy pairs → ≤ 0.50
        for i in [0, 1, 2]:
            assert result[i] <= 0.51, f"result[{i}]={result[i]}"
        # r3 unique → multiplier ≥ 1.0
        assert result[3] >= 1.0, f"result[3]={result[3]}"

    def test_unique_miner_not_penalised_in_mixed_set(self):
        """Unique miner in a set of duplicates should not be penalised."""
        responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B]
        result = diversity_score(responses, similarity_threshold=0.85)
        # Index 2 (unique) should have multiplier ≥ 1.0
        assert result[2] >= 1.0, f"result[2]={result[2]}"
        # Indices 0 and 1 (duplicates) should be penalised
        assert result[0] < 1.0
        assert result[1] < 1.0


# ── Model fingerprint penalty ─────────────────────────────────────────────────

class TestModelFingerprintPenalty:
    def test_many_same_fingerprint_triggers_penalty(self):
        """
        When ≥ n//2 responses share the same (length, vocab) bucket,
        all those miners should get the model-fingerprint penalty (≤ 0.80).
        """
        # Craft responses of almost identical length and vocab diversity
        template = "The weather today is nice and sunny outside in the park area nearby."
        responses = [template] * 6 + [UNIQUE_RESPONSE_B]
        result = diversity_score(responses, similarity_threshold=0.99)  # disable copy penalty
        # First 6 responses → same fp bucket, 6 >= 7//2=3 → penalised
        for i in range(6):
            assert result[i] <= 0.81, f"result[{i}]={result[i]}"

    def test_diverse_fingerprints_no_penalty(self):
        """
        Responses with very different lengths/vocab should not trigger model
        fingerprint penalty.
        """
        # Diverse lengths: 10 chars, 100 chars, 1000 chars
        responses = [
            "Hi there!",  # very short
            UNIQUE_RESPONSE_A,  # medium
            " ".join(["word"] * 200),  # long, repetitive vocab
        ]
        result = diversity_score(responses, similarity_threshold=0.99)
        # With 3 responses, threshold is max(3, 3//2)=3; only 1 per bucket → no penalty
        # So multipliers should be ≥ 1.0 (or bonus if substantive)
        assert all(m >= 0.99 for m in result.tolist()), f"Got {result}"


# ── Penalty bounds ────────────────────────────────────────────────────────────

class TestPenaltyBounds:
    def test_multipliers_in_valid_range(self):
        """All multipliers must be in [0.3, 1.0 + bonus]."""
        responses = [
            UNIQUE_RESPONSE_A,
            UNIQUE_RESPONSE_A,
            UNIQUE_RESPONSE_B,
            UNIQUE_RESPONSE_B,
            UNIQUE_RESPONSE_C,
        ]
        result = diversity_score(responses, diversity_bonus=0.05)
        assert all(0.29 <= m <= 1.06 for m in result.tolist()), f"Got {result}"

    def test_multipliers_are_floats(self):
        """Multipliers must be real numbers."""
        result = diversity_score([UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B])
        for m in result.tolist():
            assert isinstance(m, float)
            assert not np.isnan(m)
            assert not np.isinf(m)


# ── Custom thresholds ─────────────────────────────────────────────────────────

class TestCustomThresholds:
    def test_strict_threshold_catches_partial_copies(self):
        """Low similarity_threshold flags loosely similar responses."""
        # Slightly different but thematically similar
        r_a = "I love cats. They are fluffy and independent animals that make great pets."
        r_b = "I love cats. They are fluffy and independent animals that make excellent pets."
        result = diversity_score([r_a, r_b], similarity_threshold=0.70)
        # Very similar → penalised
        assert all(m < 1.0 for m in result.tolist()), f"Got {result}"

    def test_high_threshold_skips_partial_similarity(self):
        """High similarity_threshold only flags near-exact copies."""
        r_a = UNIQUE_RESPONSE_A
        r_b = "To make scrambled eggs, use two eggs, a bowl, and a pan with butter."
        result = diversity_score([r_a, r_b], similarity_threshold=0.98)
        # Not penalised at 98% threshold
        assert all(m >= 1.0 for m in result.tolist()), f"Got {result}"

    def test_no_bonus_when_bonus_zero(self):
        """diversity_bonus=0.0 → unique responses get exactly 1.0."""
        responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B, UNIQUE_RESPONSE_C]
        result = diversity_score(responses, diversity_bonus=0.0)
        assert all(abs(m - 1.0) < 1e-5 for m in result.tolist()), f"Got {result}"


# ── Integration with reward pipeline ─────────────────────────────────────────

class TestIntegrationWithRewards:
    def test_diversity_score_importable_from_reward(self):
        from nobi.validator.reward import diversity_score as ds
        assert ds is not None

    def test_get_rewards_returns_correct_length(self):
        """get_rewards with mock self should return array of correct length."""

        class MockNeuron:
            class config:
                class neuron:
                    openrouter_api_key = ""

        from nobi.validator.reward import get_rewards
        responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B, UNIQUE_RESPONSE_C]
        result = get_rewards(
            MockNeuron(),
            query="How are you?",
            responses=responses,
        )
        assert len(result) == 3
        assert isinstance(result, np.ndarray)

    def test_get_rewards_penalises_identical_responses(self):
        """
        get_rewards should give lower scores to identical responses than
        it gives to unique responses (diversity_score integration).
        """

        class MockNeuron:
            class config:
                class neuron:
                    openrouter_api_key = ""

        from nobi.validator.reward import get_rewards

        query = "Tell me a joke."
        unique_responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_B, UNIQUE_RESPONSE_C]
        duplicate_responses = [UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_A, UNIQUE_RESPONSE_A]

        unique_scores = get_rewards(MockNeuron(), query=query, responses=unique_responses)
        dup_scores = get_rewards(MockNeuron(), query=query, responses=duplicate_responses)

        # Average score for unique set should be >= average for duplicate set
        assert unique_scores.mean() >= dup_scores.mean() - 1e-5, (
            f"unique_mean={unique_scores.mean():.4f} dup_mean={dup_scores.mean():.4f}"
        )
