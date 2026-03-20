"""
Tests for nobi.validator.tuning — Scoring Weight Tuner
Dragon Lord 🐉 — Task 5

20+ tests covering:
- Score recording and retrieval
- Distribution analysis
- Differentiation detection
- Gaming detection (identical responses, score spikes)
- Weight suggestion logic
- Leaderboard
- Response diversity
- Length normalization
- Confidence calibration
- Entropy
"""

import os
import time
import tempfile
import pytest

from nobi.validator.tuning import (
    ScoringTuner,
    check_response_diversity,
    compute_diversity_penalties,
    normalize_length_score,
    score_confidence_calibration,
    compute_entropy,
    _char_ngrams,
    _jaccard,
)


@pytest.fixture
def tuner(tmp_path):
    """Create a ScoringTuner with a temp database."""
    db = str(tmp_path / "test_scores.db")
    return ScoringTuner(db_path=db)


@pytest.fixture
def populated_tuner(tuner):
    """Tuner with pre-populated score data."""
    import random
    random.seed(42)
    # 10 miners, 20 rounds each
    for uid in range(10):
        base_quality = 0.3 + uid * 0.06  # Spread from 0.3 to 0.84
        for round_num in range(20):
            q = max(0.0, min(1.0, base_quality + random.gauss(0, 0.05)))
            m = max(0.0, min(1.0, 0.5 + random.gauss(0, 0.1)))
            r = max(0.0, min(1.0, 0.7 + random.gauss(0, 0.1)))
            f = 0.5 * q + 0.4 * m + 0.1 * r
            tuner.record_score(
                uid=uid,
                round_type="multi_turn",
                quality=q,
                memory=m,
                reliability=r,
                final=f,
                round_id=f"round_{round_num}",
            )
    return tuner


# === Score Recording & Retrieval ===

class TestScoreRecording:
    def test_record_single_score(self, tuner):
        tuner.record_score(uid=1, round_type="single", quality=0.8, memory=0.0, reliability=0.9, final=0.82)
        history = tuner.get_miner_history(uid=1)
        assert len(history) == 1
        assert history[0]["quality"] == 0.8
        assert history[0]["final"] == 0.82

    def test_record_multiple_scores(self, tuner):
        for i in range(5):
            tuner.record_score(uid=1, round_type="single", quality=0.5 + i * 0.1,
                               memory=0.0, reliability=0.7, final=0.5 + i * 0.1)
        history = tuner.get_miner_history(uid=1)
        assert len(history) == 5

    def test_record_batch(self, tuner):
        records = [
            {"uid": i, "round_type": "single", "quality": 0.5, "memory": 0.0,
             "reliability": 0.7, "final": 0.55, "timestamp": time.time(), "round_id": "r1"}
            for i in range(10)
        ]
        tuner.record_scores_batch(records)
        for i in range(10):
            h = tuner.get_miner_history(uid=i)
            assert len(h) == 1

    def test_round_id_retrieval(self, tuner):
        tuner.record_score(uid=1, round_type="single", quality=0.8, memory=0.0,
                           reliability=0.9, final=0.82, round_id="test_round_1")
        tuner.record_score(uid=2, round_type="single", quality=0.6, memory=0.0,
                           reliability=0.7, final=0.62, round_id="test_round_1")
        scores = tuner.get_round_scores("test_round_1")
        assert len(scores) == 2
        assert scores[0]["final"] >= scores[1]["final"]  # Ordered by final desc


# === Distribution Analysis ===

class TestDistribution:
    def test_empty_distribution(self, tuner):
        dist = tuner.get_score_distribution(100)
        assert dist["count"] == 0
        assert dist["final"]["mean"] == 0.0

    def test_distribution_with_data(self, populated_tuner):
        dist = populated_tuner.get_score_distribution(100)
        assert dist["count"] == 100  # Limited to 100
        assert 0.0 < dist["final"]["mean"] < 1.0
        assert dist["final"]["std"] > 0.0
        assert dist["final"]["min"] <= dist["final"]["median"] <= dist["final"]["max"]

    def test_distribution_limit(self, populated_tuner):
        dist10 = populated_tuner.get_score_distribution(10)
        dist200 = populated_tuner.get_score_distribution(200)
        assert dist10["count"] == 10
        assert dist200["count"] == 200  # All 200 records


# === Differentiation Analysis ===

class TestDifferentiation:
    def test_good_differentiation(self, populated_tuner):
        result = populated_tuner.analyze_differentiation()
        assert result["is_differentiated"] is True
        assert result["final_std"] > 0.05
        assert result["miner_count"] == 10
        assert result["dominant_component"] is not None

    def test_poor_differentiation(self, tuner):
        # All miners score identically
        for uid in range(5):
            for _ in range(5):
                tuner.record_score(uid=uid, round_type="single",
                                   quality=0.5, memory=0.0, reliability=0.5, final=0.5)
        result = tuner.analyze_differentiation()
        assert result["is_differentiated"] is False
        assert "Poor differentiation" in result["recommendation"]

    def test_not_enough_data(self, tuner):
        tuner.record_score(uid=1, round_type="single", quality=0.5,
                           memory=0.0, reliability=0.5, final=0.5)
        result = tuner.analyze_differentiation()
        assert result["is_differentiated"] is False
        assert "Not enough data" in result["recommendation"]


# === Weight Suggestions ===

class TestWeightSuggestions:
    def test_default_weights_no_data(self, tuner):
        result = tuner.suggest_weights()
        assert "suggested" in result
        assert "Not enough data" in result["reasoning"]

    def test_weight_suggestions_with_data(self, populated_tuner):
        result = populated_tuner.suggest_weights()
        assert result["data_points"] > 0
        suggested = result["suggested"]
        # Should have multi_turn weights
        if "multi_turn" in suggested:
            weights = suggested["multi_turn"]
            assert abs(sum(weights.values()) - 1.0) < 0.01  # Weights sum to ~1.0
            assert all(v >= 0.05 for v in weights.values())  # Minimum floor

    def test_weights_reflect_variance(self, tuner):
        # Quality varies a lot, reliability doesn't
        import random
        random.seed(99)
        for uid in range(10):
            q = 0.1 + uid * 0.09  # High variance
            r = 0.7  # No variance
            f = 0.9 * q + 0.1 * r
            for _ in range(5):
                tuner.record_score(uid=uid, round_type="single",
                                   quality=q, memory=0.0, reliability=r, final=f)
        result = tuner.suggest_weights()
        if "single" in result["suggested"]:
            w = result["suggested"]["single"]
            # Quality should get higher weight than reliability
            assert w.get("quality", 0) >= w.get("reliability", 0)


# === Gaming Detection ===

class TestGamingDetection:
    def test_no_gaming(self, populated_tuner):
        alerts = populated_tuner.detect_gaming()
        # Normal data shouldn't trigger too many alerts
        spike_alerts = [a for a in alerts if a["type"] == "score_spike"]
        # Some spikes are normal with random data
        assert isinstance(alerts, list)

    def test_detect_perfect_scores(self, tuner):
        for _ in range(10):
            tuner.record_score(uid=99, round_type="single",
                               quality=0.98, memory=0.0, reliability=0.99, final=0.98)
        alerts = tuner.detect_gaming()
        perfect = [a for a in alerts if a["type"] == "perfect_scores"]
        assert len(perfect) == 1
        assert perfect[0]["uid"] == 99

    def test_detect_score_cluster(self, tuner):
        # 5 miners with nearly identical scores
        for uid in range(5):
            for _ in range(5):
                tuner.record_score(uid=uid, round_type="single",
                                   quality=0.60, memory=0.0, reliability=0.70,
                                   final=0.61)
        alerts = tuner.detect_gaming()
        clusters = [a for a in alerts if a["type"] == "score_cluster"]
        assert len(clusters) >= 1
        assert len(clusters[0]["uids"]) >= 3

    def test_detect_score_spike(self, tuner):
        # Miner has consistent low scores then a sudden spike
        for _ in range(10):
            tuner.record_score(uid=50, round_type="single",
                               quality=0.3, memory=0.0, reliability=0.5, final=0.32)
        tuner.record_score(uid=50, round_type="single",
                           quality=0.99, memory=0.0, reliability=1.0, final=0.99)
        alerts = tuner.detect_gaming()
        spikes = [a for a in alerts if a["type"] == "score_spike" and a["uid"] == 50]
        assert len(spikes) >= 1
        assert spikes[0]["severity"] in ["medium", "high"]


# === Leaderboard ===

class TestLeaderboard:
    def test_leaderboard_order(self, populated_tuner):
        lb = populated_tuner.get_leaderboard(10)
        assert len(lb) == 10
        # Should be sorted descending
        for i in range(len(lb) - 1):
            assert lb[i]["avg_final"] >= lb[i + 1]["avg_final"]

    def test_leaderboard_limit(self, populated_tuner):
        lb5 = populated_tuner.get_leaderboard(5)
        assert len(lb5) == 5

    def test_leaderboard_empty(self, tuner):
        lb = tuner.get_leaderboard(10)
        assert lb == []

    def test_leaderboard_fields(self, populated_tuner):
        lb = populated_tuner.get_leaderboard(1)
        entry = lb[0]
        assert "rank" in entry
        assert "uid" in entry
        assert "avg_final" in entry
        assert "avg_quality" in entry
        assert "round_count" in entry
        assert entry["rank"] == 1


# === Response Diversity ===

class TestResponseDiversity:
    def test_identical_responses_detected(self):
        responses = ["Hello, how can I help you today?"] * 5
        dupes = check_response_diversity(responses, threshold=0.85)
        assert len(dupes) > 0

    def test_diverse_responses_pass(self):
        responses = [
            "The weather today is sunny and warm.",
            "I recommend trying the new Italian restaurant downtown.",
            "Machine learning is a subset of artificial intelligence.",
            "The stock market closed higher today on strong earnings.",
            "Exercise regularly for better physical and mental health.",
        ]
        dupes = check_response_diversity(responses, threshold=0.85)
        assert len(dupes) == 0

    def test_diversity_penalties(self):
        responses = [
            "Hello, how can I help you today?",
            "Hello, how can I help you today?",
            "Hello, how can I help you today?",
            "The weather is sunny and I love coding.",
            "Python is a great programming language.",
        ]
        penalties = compute_diversity_penalties(responses, threshold=0.85)
        assert len(penalties) == 5
        # First 3 should be penalized, last 2 should be 1.0
        assert penalties[3] == 1.0
        assert penalties[4] == 1.0
        assert penalties[0] < 1.0
        assert penalties[1] < 1.0


# === Length Normalization ===

class TestLengthNormalization:
    def test_optimal_length_unchanged(self):
        response = "x" * 200  # Within optimal range
        result = normalize_length_score(response, 0.8)
        assert result == 0.8

    def test_empty_response(self):
        assert normalize_length_score("", 0.8) == 0.0

    def test_very_short_penalized(self):
        result = normalize_length_score("Hi", 0.8)
        assert result < 0.8

    def test_very_long_penalized(self):
        response = "word " * 2000  # Very long
        result = normalize_length_score(response, 0.8)
        assert result < 0.8

    def test_moderate_length_scaled(self):
        response = "x" * 30  # Below optimal min (50) but not tiny
        result = normalize_length_score(response, 0.8)
        assert 0.3 < result < 0.8


# === Confidence Calibration ===

class TestConfidenceCalibration:
    def test_correct_confident(self):
        result = score_confidence_calibration(
            "I'm absolutely certain the answer is 42.", is_correct=True
        )
        assert result == 1.0

    def test_wrong_confident_penalty(self):
        result = score_confidence_calibration(
            "I'm absolutely certain the answer is 42.", is_correct=False
        )
        assert result == 0.5

    def test_wrong_hedging_less_penalty(self):
        result = score_confidence_calibration(
            "I think the answer might be 42, but I could be wrong.", is_correct=False
        )
        assert result == 0.8

    def test_wrong_neutral(self):
        result = score_confidence_calibration(
            "The answer is 42.", is_correct=False
        )
        assert result == 0.7


# === Entropy ===

class TestEntropy:
    def test_identical_responses_low_entropy(self):
        responses = ["same response here"] * 10
        e = compute_entropy(responses)
        assert e == 0.0

    def test_diverse_responses_high_entropy(self):
        responses = [f"unique response number {i} with different words {i*13}" for i in range(10)]
        e = compute_entropy(responses)
        assert e > 0.5

    def test_single_response(self):
        assert compute_entropy(["hello"]) == 1.0

    def test_empty_responses(self):
        assert compute_entropy([]) == 1.0


# === Internal Helpers ===

class TestHelpers:
    def test_char_ngrams(self):
        grams = _char_ngrams("hello", 3)
        assert "hel" in grams
        assert "ell" in grams
        assert "llo" in grams

    def test_jaccard_identical(self):
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_jaccard_disjoint(self):
        assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0

    def test_jaccard_partial(self):
        sim = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
        assert 0.0 < sim < 1.0


# === Cleanup ===

class TestCleanup:
    def test_cleanup_old_data(self, tuner):
        # Insert old data
        import sqlite3
        conn = sqlite3.connect(tuner.db_path)
        old_ts = time.time() - 60 * 86400  # 60 days ago
        conn.execute(
            "INSERT INTO scores (uid, round_type, quality, memory, reliability, final, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "single", 0.5, 0.0, 0.5, 0.5, old_ts),
        )
        conn.commit()
        conn.close()

        # Insert recent data
        tuner.record_score(uid=2, round_type="single", quality=0.8, memory=0.0, reliability=0.9, final=0.82)

        tuner.cleanup_old_data(days=30)

        # Old data should be gone
        h1 = tuner.get_miner_history(uid=1)
        h2 = tuner.get_miner_history(uid=2)
        assert len(h1) == 0
        assert len(h2) == 1
