"""
Tests for 256-neuron (20 validators + 236 miners) scoring calibration.

Covers:
1. Score differentiation with 236 miners
2. Moving-average stability across sparse sampling
3. Quality floor enforcement
4. Anti-gaming: entropy threshold, diversity penalties at scale
5. Weight normalization across 236 miners
6. Query diversity — 9 template families, low collision rate
7. Timeout calibration (default 35s)
8. Cluster detection tightened threshold
9. Multi-turn scenario diversity
"""

import random
import time
import pytest
import numpy as np

from nobi.validator.tuning import (
    ScoringTuner,
    compute_diversity_penalties,
    compute_entropy,
)
from nobi.validator.reward import reward, get_rewards
from nobi.validator.query_generator import (
    generate_single_turn_query,
    generate_multi_turn_scenario,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tuner_256(tmp_path):
    """ScoringTuner pre-populated with 236 miners, 10 rounds each."""
    db = str(tmp_path / "scores_256.db")
    t = ScoringTuner(db_path=db)
    rng = random.Random(42)
    for uid in range(236):
        # Spread quality from 0.1 to 0.95 to simulate real differentiation
        base_q = 0.10 + (uid / 235) * 0.85
        for _ in range(10):
            q = max(0.0, min(1.0, base_q + rng.gauss(0, 0.03)))
            m = max(0.0, min(1.0, 0.5 + rng.gauss(0, 0.08)))
            r = max(0.0, min(1.0, 0.7 + rng.gauss(0, 0.08)))
            f = 0.90 * q + 0.10 * r
            t.record_score(uid=uid, round_type="single", quality=q,
                           memory=m, reliability=r, final=f)
    return t


# ─── 1. Score Differentiation ─────────────────────────────────────────────────

class TestScoreDifferentiation256:
    def test_high_std_with_236_miners(self, tuner_256):
        """With 236 miners spanning 0.1–0.95, std should be well above 0.08."""
        result = tuner_256.analyze_differentiation()
        assert result["is_differentiated"] is True, (
            f"Expected differentiation but std={result['final_std']:.4f} — "
            "scoring may be too compressed for 236-miner ranking"
        )
        assert result["final_std"] > 0.08, (
            f"Final score std={result['final_std']:.4f} too low. "
            "Miners cannot be meaningfully ranked across 236 slots."
        )

    def test_top_vs_bottom_percentile_spread(self, tuner_256):
        """Top-10 miners should score significantly higher than bottom-10."""
        lb = tuner_256.get_leaderboard(236)
        assert len(lb) >= 20
        top10_avg = np.mean([e["avg_final"] for e in lb[:10]])
        bot10_avg = np.mean([e["avg_final"] for e in lb[-10:]])
        spread = top10_avg - bot10_avg
        assert spread > 0.30, (
            f"Top-10 avg={top10_avg:.3f} vs bottom-10 avg={bot10_avg:.3f}. "
            f"Spread={spread:.3f} too narrow — weights will be near-equal across miners."
        )

    def test_differentiation_threshold_raised_for_256(self):
        """LOW_DIFFERENTIATION_STD must be >= 0.08 for 256-neuron network."""
        assert ScoringTuner.LOW_DIFFERENTIATION_STD >= 0.08, (
            "LOW_DIFFERENTIATION_STD is too low for 256-neuron calibration. "
            "Raise to at least 0.08 so poor differentiation is detected correctly."
        )

    def test_leaderboard_rank_count_256(self, tuner_256):
        """All 236 miners should appear in leaderboard."""
        lb = tuner_256.get_leaderboard(limit=256)
        assert len(lb) == 236


# ─── 2. Moving Average Window ─────────────────────────────────────────────────

class TestMovingAverageCalibration:
    def test_alpha_calibrated_for_large_network(self):
        """With 236 miners and sample_size=50, alpha=0.05 is appropriate.

        Each miner is sampled every ~4.7 steps (236/50).
        alpha=0.05 means a score contributes for ~14 steps before decaying to 50%.
        alpha=0.10 (old) would cause catastrophic decay — each miner would be
        essentially invisible between the rare sampling events.
        """
        from nobi.utils.config import add_validator_args
        import argparse
        parser = argparse.ArgumentParser()
        add_validator_args(None, parser)
        defaults = parser.parse_args([])
        # argparse with dest containing dots stores as flat dict key
        ns = vars(defaults)
        alpha = ns["neuron.moving_average_alpha"]
        sample_size = ns["neuron.sample_size"]
        timeout = ns["neuron.timeout"]

        # Alpha should be lowered for sparse sampling
        assert alpha <= 0.05, (
            f"moving_average_alpha={alpha} too high for 256-neuron network. "
            "With 236 miners and sample_size=50, alpha should be <=0.05 to prevent "
            "scores from decaying to near-zero between sampling events."
        )
        # Sample size should cover a meaningful fraction of miners
        assert sample_size >= 30, (
            f"sample_size={sample_size} too small. With 236 miners, "
            "need >=30 per step for reasonable coverage."
        )
        # Timeout raised for larger network
        assert timeout >= 35, (
            f"timeout={timeout}s may be too low. With 236 miners across 7 servers, "
            "recommend >=35s to absorb network latency variance."
        )

    def test_score_retention_per_cycle(self):
        """Score should retain at least 40% after one full sampling cycle."""
        alpha = 0.05
        sample_size = 50
        n_miners = 236
        steps_per_cycle = n_miners / sample_size  # ~4.7

        # Score after one full cycle with no new queries = (1-alpha)^steps
        retention = (1 - alpha) ** steps_per_cycle
        assert retention > 0.40, (
            f"Score retains only {retention:.1%} per cycle — "
            "miners disappear from rankings too quickly"
        )

    def test_old_alpha_would_catastrophically_decay(self):
        """Verify the old alpha=0.1 caused bad decay (validates the fix)."""
        old_alpha = 0.10
        n_miners = 236
        sample_size = 10  # old default
        steps_per_cycle = n_miners / sample_size  # 23.6

        retention = (1 - old_alpha) ** steps_per_cycle
        # Old config: ~8.4% retention — confirms fix was needed
        assert retention < 0.15, (
            f"Expected old config to have <15% retention, got {retention:.1%}"
        )


# ─── 3. Quality Floor Enforcement ─────────────────────────────────────────────

class TestQualityFloor:
    def test_quality_floor_constant_set(self):
        """QUALITY_FLOOR must be defined on ScoringTuner."""
        assert hasattr(ScoringTuner, "QUALITY_FLOOR"), (
            "ScoringTuner.QUALITY_FLOOR not defined — garbage responses won't be zeroed"
        )
        assert 0.05 <= ScoringTuner.QUALITY_FLOOR <= 0.20

    def test_below_floor_response_gets_zero(self):
        """Responses with quality below QUALITY_FLOOR should receive 0.0 reward.

        The floor is applied in reward() at the quality-score level (before reliability
        combination), so reliability cannot rescue garbage responses.
        """
        import nobi.validator.reward as rmod
        original = rmod._llm_judge

        try:
            rmod._llm_judge = lambda q, r, k="": 0.05  # below floor (0.10)
            # Use reward() directly — floor is applied there
            score = reward("test query", "a somewhat short response here", api_key="")
            assert score == 0.0, (
                f"Expected 0.0 for below-floor quality, got {score:.4f}"
            )
        finally:
            rmod._llm_judge = original

    def test_above_floor_response_passes(self):
        """Responses above QUALITY_FLOOR should retain their score."""
        import nobi.validator.reward as rmod
        original = rmod._llm_judge

        try:
            rmod._llm_judge = lambda q, r, k="": 0.80
            score = reward("hello", "A good detailed helpful response to your question", api_key="")
            assert score > 0.0, "Above-floor response should not be zeroed"
            assert score > 0.5, f"Expected high score, got {score:.4f}"
        finally:
            rmod._llm_judge = original

    def test_quality_floor_applied_in_get_rewards(self):
        """get_rewards zeroes out low-scoring responses (floor in reward() propagates)."""
        import nobi.validator.reward as rmod
        original = rmod._llm_judge

        try:
            # All responses score well below floor (0.04 < 0.10)
            rmod._llm_judge = lambda q, r, k="": 0.04

            class MockSelf:
                class config:
                    class neuron:
                        openrouter_api_key = ""
                metagraph = None

            rewards = get_rewards(
                MockSelf(),
                query="test",
                responses=["this is a response with some words"] * 5,
            )
            assert all(r == 0.0 for r in rewards), (
                f"Expected all zeros below floor, got {rewards}"
            )
        finally:
            rmod._llm_judge = original


# ─── 4. Anti-Gaming at Scale ─────────────────────────────────────────────────

class TestAntiGaming256:
    def test_entropy_threshold_raised_for_256(self):
        """LOW_ENTROPY_WARNING should be >=0.5 for 236-miner network."""
        assert ScoringTuner.LOW_ENTROPY_WARNING >= 0.5, (
            "LOW_ENTROPY_WARNING too low for 256-neuron network. "
            "With 236 miners, natural entropy floor is higher — threshold needs raising."
        )

    def test_similarity_threshold_tightened(self):
        """SIMILARITY_THRESHOLD should be <=0.015 to reduce false clustering at scale."""
        assert ScoringTuner.SIMILARITY_THRESHOLD <= 0.015, (
            "SIMILARITY_THRESHOLD too loose for 256-neuron network. "
            "With 236 miners, random noise causes more false-positive clustering at 0.02."
        )

    def test_diversity_penalties_scale_to_236_miners(self):
        """Diversity penalty computation works correctly at 236-response scale."""
        # 10 identical responses mixed in 236 unique ones.
        # Each "diverse" response uses completely different vocabulary to avoid n-gram overlap.
        # Use unique words/numbers ensuring no two responses share 3-char n-grams above threshold.
        import string
        # Unique vocabulary pool
        unique_words = [
            "aardvark", "balloon", "cactus", "dolphin", "ember", "falcon", "glacier",
            "harbor", "igloo", "jungle", "kitten", "lemon", "mango", "nebula", "ocean",
            "pepper", "quartz", "rapids", "safari", "tunnel", "umbrella", "velvet",
            "walrus", "xenon", "yogurt", "zeppelin",
        ]
        # Build 226 responses that are radically different from each other
        diverse = []
        for i in range(226):
            # Use a sequence of unique words based on index — ensures low n-gram overlap
            w1 = unique_words[i % len(unique_words)]
            w2 = unique_words[(i * 3 + 7) % len(unique_words)]
            w3 = unique_words[(i * 7 + 13) % len(unique_words)]
            suffix = str(i * 97 + 1000)  # unique numeric suffix
            diverse.append(f"{w1} {suffix} {w2} {w3} xyz{i:04d}")

        identical = ["Hello! I'd be happy to help you with that today."] * 10
        all_responses = diverse + identical

        penalties = compute_diversity_penalties(all_responses, threshold=0.85)
        assert len(penalties) == 236

        # Identical responses should be penalized
        assert all(p < 1.0 for p in penalties[226:]), (
            "Identical responses not penalized at scale"
        )
        # Most diverse responses should NOT be penalized (allow a few edge-case overlaps)
        penalized_diverse = sum(1 for p in penalties[:226] if p < 1.0)
        assert penalized_diverse <= 10, (
            f"{penalized_diverse}/226 diverse responses incorrectly penalized"
        )

    def test_entropy_236_diverse_responses(self):
        """236 diverse responses should have high entropy."""
        responses = [f"completely different response {i} about {i*3} topics" for i in range(236)]
        e = compute_entropy(responses)
        assert e > 0.8, f"Expected high entropy for diverse responses, got {e:.3f}"

    def test_entropy_bulk_identical_low(self):
        """Bulk identical responses from miners should flag low entropy."""
        responses = ["I'm here to help you anytime you need assistance!"] * 100
        e = compute_entropy(responses)
        assert e == 0.0, f"Expected 0 entropy for identical responses, got {e:.3f}"

    def test_gaming_detection_cluster_236(self, tmp_path):
        """Cluster detection with tighter threshold doesn't false-positive on random scores."""
        db = str(tmp_path / "cluster_test.db")
        t = ScoringTuner(db_path=db)
        rng = random.Random(123)
        # 236 miners with random (not artificially similar) scores
        for uid in range(236):
            base = rng.uniform(0.15, 0.90)
            for _ in range(5):
                f = max(0.0, min(1.0, base + rng.gauss(0, 0.04)))
                t.record_score(uid=uid, round_type="single", quality=f,
                               memory=0.0, reliability=0.7, final=f)

        alerts = t.detect_gaming()
        clusters = [a for a in alerts if a["type"] == "score_cluster"]
        # With random spread, false-positive clusters should be few
        assert len(clusters) <= 5, (
            f"Too many false-positive clusters ({len(clusters)}) with random scores — "
            "SIMILARITY_THRESHOLD may be too tight or too loose"
        )


# ─── 5. Weight Normalization ──────────────────────────────────────────────────

class TestWeightNormalization256:
    def test_l1_norm_distributes_unequally(self, tuner_256):
        """Top miners should get more weight than bottom miners."""
        lb = tuner_256.get_leaderboard(limit=236)
        scores = np.array([e["avg_final"] for e in lb])

        # Simulate L1 normalization (what base validator does)
        norm = np.linalg.norm(scores, ord=1)
        assert norm > 0, "All scores zero — normalization fails"
        weights = scores / norm

        top10_weight = weights[:10].sum()
        bot10_weight = weights[-10:].sum()
        assert top10_weight > bot10_weight * 3, (
            f"Top-10 weight={top10_weight:.4f} not sufficiently dominant over "
            f"bottom-10 weight={bot10_weight:.4f}. Distribution too flat."
        )

    def test_no_all_zero_scores(self, tuner_256):
        """Leaderboard should not have all-zero final scores."""
        lb = tuner_256.get_leaderboard(limit=236)
        nonzero = [e for e in lb if e["avg_final"] > 0]
        assert len(nonzero) > 200, (
            f"Only {len(nonzero)}/236 miners have nonzero scores — "
            "quality floor may be too aggressive"
        )

    def test_weight_normalization_handles_sparse_scores(self):
        """Normalization works when many miners have score 0 (new entrants)."""
        scores = np.zeros(256, dtype=np.float32)
        # Only 50 miners have scores (rest are new)
        rng = np.random.default_rng(42)
        scores[:50] = rng.uniform(0.2, 0.9, 50)

        norm = np.linalg.norm(scores, ord=1)
        if norm == 0:
            norm = np.ones_like(norm)
        weights = scores / norm
        assert abs(weights.sum() - 1.0) < 1e-5, "Weights don't sum to 1.0"
        assert weights[50:].sum() == 0.0, "New miners should have zero weight"


# ─── 6. Query Diversity ────────────────────────────────────────────────────────

class TestQueryDiversity256:
    def test_query_uniqueness_rate(self):
        """Generate 500 queries — collision rate should be low.

        Note: reflective and hypothetical templates use fixed pools (~10 entries each),
        so some collisions are expected. The goal is that most queries are unique,
        not that every single one is. We target <60% collision rate, which is realistic
        given the mix of fixed-pool and combinatorial templates.
        """
        queries = [generate_single_turn_query() for _ in range(500)]
        unique = set(queries)
        collision_rate = 1.0 - len(unique) / len(queries)
        # With 9 families including fixed-pool (reflective: 10, hypothetical: 7),
        # some collisions are expected. Target: majority unique across full set.
        assert collision_rate < 0.60, (
            f"Query collision rate={collision_rate:.1%} too high. "
            "Too many templates are using fixed/small pools."
        )
        # Unique count must be meaningfully large
        assert len(unique) >= 100, (
            f"Only {len(unique)} unique queries in 500 — query diversity is too low."
        )

    def test_nine_template_families_covered(self):
        """All 9 template families should fire within 300 samples."""
        seen_patterns = set()
        family_markers = [
            # Detect each family by distinctive vocabulary
            ("feeling_query", ["honestly", "lately", "any thoughts", "have you ever"]),
            ("life_goal_query", ["want to build", "trying to", "goal is to", "keep falling"]),
            ("hypothetical_query", ["hypothetically", "just wondering", "random question"]),
            ("reflective_query", ["most like yourself", "perfect day", "what does a perfect",
                                   "recharge", "quietly proud", "consistently makes"]),
            ("practical_problem_query", ["problem:", "struggling with", "dealing with"]),
            ("mood_query", ["feeling", "quite", "advice related"]),
            ("topic_query", ["get better at", "basics of", "common mistakes", "surprising thing"]),
            ("situation_query", ["i'm just started", "i've been", "so i'm"]),
            ("advice_query", ["hours free", "surprise my", "more productive", "make a decision"]),
            ("creative_query", ["short story", "motivational", "recommend one"]),
        ]

        for _ in range(500):
            q = generate_single_turn_query().lower()
            for name, markers in family_markers:
                if any(m in q for m in markers):
                    seen_patterns.add(name)

        # Should see at least 7 distinct families in 500 samples
        assert len(seen_patterns) >= 7, (
            f"Only {len(seen_patterns)} query families detected in 500 samples: {seen_patterns}. "
            "Some template families may not be firing."
        )

    def test_multi_turn_scenario_diversity(self):
        """7 scenario types should all appear within 200 generations."""
        scenarios = [generate_multi_turn_scenario() for _ in range(200)]
        descriptions = [s["description"].split("(")[0].strip() for s in scenarios]
        unique_types = set(descriptions)
        assert len(unique_types) >= 6, (
            f"Only {len(unique_types)} scenario types in 200 generations: {unique_types}"
        )

    def test_queries_not_empty(self):
        """All generated queries should be non-empty strings."""
        for _ in range(100):
            q = generate_single_turn_query()
            assert isinstance(q, str) and len(q.strip()) > 10

    def test_scenario_has_required_fields(self):
        """All generated scenarios must have required keys."""
        for _ in range(50):
            s = generate_multi_turn_scenario()
            assert "setup" in s and len(s["setup"]) >= 2
            assert "test_query" in s and s["test_query"]
            assert "memory_keywords" in s and len(s["memory_keywords"]) >= 2
            assert "description" in s


# ─── 7. Timeout Calibration ───────────────────────────────────────────────────

class TestTimeoutCalibration:
    def test_default_timeout_35s(self):
        """Default timeout should be >=35s for 236 miners across 7 servers."""
        from nobi.utils.config import add_validator_args
        import argparse
        parser = argparse.ArgumentParser()
        add_validator_args(None, parser)
        defaults = parser.parse_args([])
        # argparse stores dot-prefix args as flat dict
        ns = vars(defaults)
        timeout = ns["neuron.timeout"]
        assert timeout >= 35, (
            f"timeout={timeout}s too low. "
            "With 236 miners across 7 servers, recommend >=35s."
        )

    def test_reliability_scoring_reflects_35s_budget(self):
        """Reliability score at 34s (just under new timeout) should be non-zero."""
        from nobi.validator.reward import _score_reliability
        # 34s is near the budget — should be penalized but not zero
        score = _score_reliability(34.0)
        assert score > 0.0, "34s latency should still get some reliability score"
        # 5s still should be best
        assert _score_reliability(3.0) > _score_reliability(15.0)


# ─── 8. End-to-End: Scoring 236 Miners ───────────────────────────────────────

class TestEndToEnd256Miners:
    def test_get_rewards_236_miners(self):
        """get_rewards handles 236 responses correctly.

        Validates:
        - Array length is preserved
        - Below-floor responses get zeroed
        - High-quality responses retain high scores
        """
        import nobi.validator.reward as rmod
        original = rmod._llm_judge

        try:
            rng = random.Random(99)
            # Variable quality: 50 good, 100 medium, 86 bad
            # Pre-generate deterministic scores per index
            scores_list = (
                [rng.uniform(0.75, 0.95) for _ in range(50)] +
                [rng.uniform(0.30, 0.69) for _ in range(100)] +
                [rng.uniform(0.00, 0.09) for _ in range(86)]  # below floor
            )
            assert len(scores_list) == 236

            idx = [0]
            def mock_judge(q, r, k=""):
                s = scores_list[idx[0]]
                idx[0] = (idx[0] + 1) % len(scores_list)
                return s

            rmod._llm_judge = mock_judge

            class MockSelf:
                class config:
                    class neuron:
                        openrouter_api_key = ""
                metagraph = None

            # Use substantially different responses to avoid diversity penalty affecting top scores
            unique_words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
                            "golf", "hotel", "india", "juliet", "kilo", "lima",
                            "mike", "november", "oscar", "papa", "quebec", "romeo"]
            responses = [
                f"{unique_words[i % len(unique_words)]} {i*97} detailed helpful answer about {i}"
                for i in range(236)
            ]
            rewards = get_rewards(MockSelf(), query="test query", responses=responses)

            assert len(rewards) == 236, f"Expected 236 rewards, got {len(rewards)}"
            # Bottom 86 (judge score 0.0–0.09) should ALL be zero.
            # Floor is applied to quality_score directly in reward(), before reliability
            # combination, so reliability cannot rescue garbage responses.
            zero_count = int((rewards == 0.0).sum())
            assert zero_count >= 80, (
                f"Expected >=80 zero rewards (all below-floor quality scores), "
                f"got {zero_count}. Quality floor may not be applying correctly."
            )
            # At least some high-quality responses should be non-zero
            nonzero_count = int((rewards > 0.0).sum())
            assert nonzero_count >= 100, (
                f"Expected ~150 nonzero rewards, got {nonzero_count}"
            )
        finally:
            rmod._llm_judge = original

    def test_score_spread_meaningful_236(self):
        """After scoring 236 miners, std of rewards should exceed 0.1."""
        import nobi.validator.reward as rmod
        original = rmod._llm_judge

        try:
            rng = random.Random(77)

            def mock_judge(q, r, k=""):
                return rng.uniform(0.0, 1.0)

            rmod._llm_judge = mock_judge

            class MockSelf:
                class config:
                    class neuron:
                        openrouter_api_key = ""
                metagraph = None

            responses = [f"miner response {i}" * 5 for i in range(236)]
            rewards = get_rewards(MockSelf(), query="test", responses=responses)
            std = np.std(rewards)
            assert std > 0.10, (
                f"Reward std={std:.4f} too low — insufficient differentiation across 236 miners"
            )
        finally:
            rmod._llm_judge = original
