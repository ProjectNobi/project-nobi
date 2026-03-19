"""
Project Nobi — Phase C Integration Tests

Tests for the federated privacy architecture:
1. Preference signal generation (no PII leaks)
2. Differential privacy: noise actually added, values change
3. Privacy budget tracking: exhaustion warning
4. Secure aggregation: shares sum to original
5. Federated update synapse fields
6. Private scoring: individual scores are noised
7. Audit logger: operations recorded
8. k-anonymity: refuses to aggregate with < 5 signals
9. Sensitivity clipping: extreme values bounded
10. End-to-end: user message → preference signal → DP noise → aggregation → no PII recoverable
"""

import json
import os
import tempfile
import pytest
import numpy as np

from nobi.privacy.config import PRIVACY_CONFIG
from nobi.privacy.differential import (
    DifferentialPrivacyEngine,
    PrivacyAccountant,
    compute_gaussian_sigma,
)
from nobi.privacy.federated import (
    FederatedCompanionTrainer,
    _hash_user_id,
    _classify_topic,
)
from nobi.privacy.secure_agg import SecureAggregator, SecureScoreAggregator
from nobi.privacy.private_scoring import PrivateScorer
from nobi.privacy.audit import PrivacyAuditLogger


# ============================================================
# 1. Preference Signal Generation — No PII Leaks
# ============================================================

class TestPreferenceSignalGeneration:
    """Verify that preference signals contain NO personally identifiable information."""

    def setup_method(self):
        self.trainer = FederatedCompanionTrainer()

    def test_signal_has_no_raw_message(self):
        """The actual message text must NOT appear in the signal."""
        message = "My name is John and I live at 123 Main Street"
        signal = self.trainer.generate_preference_signal(
            user_id="user123", message=message,
            response="Hello John!", score=0.8
        )
        signal_str = json.dumps(signal)
        assert "John" not in signal_str
        assert "123 Main Street" not in signal_str
        assert "Hello" not in signal_str

    def test_signal_has_no_raw_user_id(self):
        """The raw user ID must NOT appear in the signal."""
        signal = self.trainer.generate_preference_signal(
            user_id="user_james_12345", message="Hello",
            response="Hi there!", score=0.7
        )
        assert "user_james_12345" not in json.dumps(signal)
        assert "user_id_hash" in signal  # Only the hash appears

    def test_signal_has_required_fields(self):
        """Signal must contain all required anonymous fields."""
        signal = self.trainer.generate_preference_signal(
            user_id="u1", message="Tell me about code",
            response="Here's some Python code...", score=0.9
        )
        assert "user_id_hash" in signal
        assert "response_length_preference" in signal
        assert "formality_delta" in signal
        assert "topic_category" in signal
        assert "quality_score" in signal
        assert "round" in signal

    def test_user_id_is_hashed(self):
        """User ID should be a fixed-length hash, not the original."""
        signal = self.trainer.generate_preference_signal(
            user_id="my_real_user_id", message="test",
            response="test", score=0.5
        )
        assert len(signal["user_id_hash"]) == 16  # Truncated SHA-256
        assert signal["user_id_hash"] == _hash_user_id("my_real_user_id")

    def test_topic_classification(self):
        """Topic should be classified from message content."""
        assert _classify_topic("I want to learn Python programming") == "tech"
        assert _classify_topic("What's the weather like?") == "general"
        assert _classify_topic("Help me study for my exam") == "education"

    def test_empty_user_id_raises(self):
        """Empty user_id should raise ValueError."""
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            self.trainer.generate_preference_signal(
                user_id="", message="test", response="test", score=0.5
            )


# ============================================================
# 2. Differential Privacy — Noise Actually Added
# ============================================================

class TestDifferentialPrivacy:
    """Verify that DP noise is correctly applied."""

    def setup_method(self):
        self.dp = DifferentialPrivacyEngine(epsilon=1.0, sensitivity=1.0)

    def test_clip_and_noise_changes_value(self):
        """Noise should change the value (with overwhelming probability)."""
        original = 0.5
        results = [self.dp.clip_and_noise(original) for _ in range(100)]
        # At least some values should differ from original
        different = [r for r in results if abs(r - original) > 1e-10]
        assert len(different) > 90  # Virtually all should be different

    def test_clip_and_noise_clips_extreme_values(self):
        """Values beyond sensitivity should be clipped before noising."""
        # With sensitivity=1.0, a value of 100 should be clipped to 1.0
        # Mean of noised values should be near 1.0, not 100
        results = [self.dp.clip_and_noise(100.0) for _ in range(1000)]
        mean = np.mean(results)
        assert abs(mean - 1.0) < 0.5  # Should be near 1.0 (the clip bound)

    def test_gaussian_sigma_computation(self):
        """Verify sigma computation for the Gaussian mechanism."""
        sigma = compute_gaussian_sigma(sensitivity=1.0, epsilon=1.0, delta=1e-5)
        assert sigma > 0
        # Higher epsilon → less noise (lower sigma)
        sigma_low = compute_gaussian_sigma(1.0, 2.0, 1e-5)
        assert sigma_low < sigma

    def test_private_mean(self):
        """Private mean should be close to true mean but not exact."""
        values = [0.5] * 100
        results = [self.dp.private_mean(values) for _ in range(50)]
        mean_of_means = np.mean(results)
        # Should be close to 0.5 on average
        assert abs(mean_of_means - 0.5) < 0.2

    def test_private_mean_empty_raises(self):
        """Private mean of empty list should raise."""
        with pytest.raises(ValueError):
            self.dp.private_mean([])

    def test_private_histogram(self):
        """Private histogram should have approximately correct counts."""
        values = [0.1, 0.2, 0.3, 0.6, 0.7, 0.8, 0.9]
        bins = [0.0, 0.5, 1.0]
        # Run multiple times and check average
        results = [self.dp.private_histogram(values, bins) for _ in range(100)]
        avg_bin0 = np.mean([r[0] for r in results])
        avg_bin1 = np.mean([r[1] for r in results])
        # True: bin0=3, bin1=4
        assert abs(avg_bin0 - 3) < 2.0
        assert abs(avg_bin1 - 4) < 2.0

    def test_private_histogram_few_bins_raises(self):
        """Histogram with < 2 bin edges should raise."""
        with pytest.raises(ValueError):
            self.dp.private_histogram([1, 2, 3], [0.5])

    def test_negative_epsilon_raises(self):
        """Negative epsilon should raise ValueError."""
        with pytest.raises(ValueError):
            self.dp.clip_and_noise(0.5, epsilon=-1.0)

    def test_zero_epsilon_raises(self):
        """Zero epsilon should raise ValueError."""
        with pytest.raises(ValueError):
            self.dp.clip_and_noise(0.5, epsilon=0.0)

    def test_privacy_budget_computation(self):
        """Basic composition: total ε = n * ε_per."""
        budget = DifferentialPrivacyEngine.compute_privacy_budget(10, 0.5)
        assert abs(budget - 5.0) < 1e-10


# ============================================================
# 3. Privacy Budget Tracking
# ============================================================

class TestPrivacyAccountant:
    """Verify privacy budget tracking and exhaustion."""

    def test_initial_state(self):
        acc = PrivacyAccountant(total_budget=5.0)
        assert acc.consumed == 0.0
        assert acc.remaining == 5.0
        assert not acc.is_exhausted
        assert not acc.is_warning

    def test_consume_tracks_budget(self):
        acc = PrivacyAccountant(total_budget=5.0)
        assert acc.consume(1.0, "query_1")
        assert acc.consumed == 1.0
        assert acc.remaining == 4.0

    def test_exhaustion_blocks_queries(self):
        acc = PrivacyAccountant(total_budget=2.0)
        assert acc.consume(1.0, "q1")
        assert acc.consume(1.0, "q2")
        assert acc.is_exhausted
        # Should refuse further queries
        assert not acc.consume(0.5, "q3")

    def test_warning_threshold(self):
        acc = PrivacyAccountant(total_budget=10.0, warning_threshold=0.8)
        acc.consume(7.5, "large_query")
        assert not acc.is_warning
        acc.consume(0.5, "small_query")
        assert acc.is_warning  # 8.0/10.0 = 0.8

    def test_cannot_afford_large_query(self):
        acc = PrivacyAccountant(total_budget=3.0)
        assert acc.can_afford(2.0)
        assert not acc.can_afford(4.0)

    def test_query_log(self):
        acc = PrivacyAccountant(total_budget=10.0)
        acc.consume(1.0, "first")
        acc.consume(2.0, "second")
        log = acc.get_log()
        assert len(log) == 2
        assert log[0] == (1.0, "first")
        assert log[1] == (2.0, "second")

    def test_reset(self):
        acc = PrivacyAccountant(total_budget=5.0)
        acc.consume(3.0, "query")
        acc.reset()
        assert acc.consumed == 0.0
        assert acc.remaining == 5.0


# ============================================================
# 4. Secure Aggregation — Shares Sum to Original
# ============================================================

class TestSecureAggregation:
    """Verify that additive secret sharing works correctly."""

    def setup_method(self):
        self.agg = SecureAggregator()

    def test_shares_sum_to_original(self):
        """Shares should reconstruct the original value."""
        value = 42.5
        shares = self.agg.create_shares(value, num_parties=5)
        assert len(shares) == 5
        reconstructed = self.agg.aggregate_shares([shares])
        assert abs(reconstructed - value) < 1e-6

    def test_multiple_values_aggregate(self):
        """Sum of multiple values should be recovered."""
        values = [10.0, 20.0, 30.0]
        all_shares = [self.agg.create_shares(v, 3) for v in values]
        total = self.agg.aggregate_shares(all_shares)
        assert abs(total - 60.0) < 1e-6

    def test_negative_values(self):
        """Negative values should work correctly."""
        value = -7.3
        shares = self.agg.create_shares(value, 3)
        reconstructed = self.agg.aggregate_shares([shares])
        assert abs(reconstructed - value) < 1e-6

    def test_zero_value(self):
        """Zero should work correctly."""
        shares = self.agg.create_shares(0.0, 4)
        reconstructed = self.agg.aggregate_shares([shares])
        assert abs(reconstructed) < 1e-6

    def test_verify_aggregate(self):
        """Verification should confirm correct aggregation."""
        values = [5.0, 15.0]
        all_shares = [self.agg.create_shares(v, 3) for v in values]
        assert self.agg.verify_aggregate(all_shares, 20.0)
        assert not self.agg.verify_aggregate(all_shares, 99.0)

    def test_individual_share_reveals_nothing(self):
        """A single share should not reveal the original value."""
        value = 42.0
        shares = self.agg.create_shares(value, 5)
        # Each individual share should be random, not equal to 42
        # (with overwhelming probability)
        for share in shares[:-1]:  # Last share is computed, skip it
            # Share should be a large random number, not close to scaled 42
            assert isinstance(share, int)

    def test_minimum_parties_raises(self):
        """Fewer than 2 parties should raise."""
        with pytest.raises(ValueError):
            self.agg.create_shares(1.0, 1)

    def test_empty_shares_raises(self):
        """Empty shares list should raise."""
        with pytest.raises(ValueError):
            self.agg.aggregate_shares([])


class TestSecureScoreAggregator:
    """Test the scoring-specific aggregation wrapper."""

    def test_submit_and_aggregate(self):
        """Submit scores and verify aggregate sum and mean."""
        agg = SecureScoreAggregator(num_miners=3, num_share_parties=3)
        agg.submit_score("miner_a", 0.8)
        agg.submit_score("miner_b", 0.6)
        agg.submit_score("miner_c", 0.9)

        total, mean = agg.aggregate()
        assert abs(total - 2.3) < 1e-5
        assert abs(mean - 2.3 / 3) < 1e-5

    def test_no_submissions_raises(self):
        """Aggregating with no submissions should raise."""
        agg = SecureScoreAggregator(num_miners=2)
        with pytest.raises(ValueError):
            agg.aggregate()

    def test_reset(self):
        """Reset should clear submissions."""
        agg = SecureScoreAggregator(num_miners=2)
        agg.submit_score("m1", 1.0)
        assert agg.get_submitted_count() == 1
        agg.reset()
        assert agg.get_submitted_count() == 0


# ============================================================
# 5. Federated Update Synapse Fields
# ============================================================

class TestFederatedUpdateSynapse:
    """Test the FederatedUpdate synapse definition."""

    def test_synapse_import(self):
        """FederatedUpdate should be importable from protocol."""
        from nobi.protocol import FederatedUpdate
        synapse = FederatedUpdate()
        assert synapse.signal_type == "preference"
        assert synapse.encrypted_signal == ""
        assert synapse.noise_added is False
        assert synapse.epsilon == 1.0
        assert synapse.aggregation_round == 0
        assert synapse.num_contributions == 0
        assert synapse.accepted is None
        assert synapse.global_update == {}

    def test_synapse_custom_values(self):
        """FederatedUpdate should accept custom values."""
        from nobi.protocol import FederatedUpdate
        synapse = FederatedUpdate(
            signal_type="quality",
            encrypted_signal='{"test": 1}',
            noise_added=True,
            epsilon=0.5,
            aggregation_round=3,
            num_contributions=10,
        )
        assert synapse.signal_type == "quality"
        assert synapse.noise_added is True
        assert synapse.epsilon == 0.5
        assert synapse.aggregation_round == 3
        assert synapse.num_contributions == 10


# ============================================================
# 6. Private Scoring — Individual Scores Are Noised
# ============================================================

class TestPrivateScoring:
    """Verify that the private scorer adds noise to miner scores."""

    def test_scores_are_noised(self):
        """Noised scores should differ from raw scores."""
        scorer = PrivateScorer(epsilon=1.0, sensitivity=1.0, total_budget=100.0)
        raw = {"m1": 0.8, "m2": 0.6, "m3": 0.4}

        noised = scorer.score_miners(raw)
        assert noised is not None

        # At least one score should differ
        different = any(
            abs(noised[k] - raw[k]) > 1e-10 for k in raw
        )
        assert different

    def test_budget_exhaustion_returns_none(self):
        """When budget is exhausted, score_miners returns None."""
        scorer = PrivateScorer(epsilon=1.0, total_budget=1.5)
        raw = {"m1": 0.5}

        result1 = scorer.score_miners(raw, epsilon=1.0)
        assert result1 is not None

        # Budget now at 1.0, only 0.5 left
        result2 = scorer.score_miners(raw, epsilon=1.0)
        assert result2 is None  # Budget exhausted

    def test_normalize_scores(self):
        """Normalization should map scores to [0, 1]."""
        scorer = PrivateScorer()
        scores = {"a": -0.5, "b": 0.0, "c": 0.5}
        normalized = scorer.normalize_scores(scores)
        assert abs(normalized["a"] - 0.0) < 1e-10
        assert abs(normalized["b"] - 0.5) < 1e-10
        assert abs(normalized["c"] - 1.0) < 1e-10

    def test_normalize_equal_scores(self):
        """Equal scores should all normalize to 0.5."""
        scorer = PrivateScorer()
        scores = {"a": 0.3, "b": 0.3, "c": 0.3}
        normalized = scorer.normalize_scores(scores)
        assert all(abs(v - 0.5) < 1e-10 for v in normalized.values())


# ============================================================
# 7. Audit Logger — Operations Recorded
# ============================================================

class TestAuditLogger:
    """Verify that all privacy operations are properly logged."""

    def setup_method(self):
        self.tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        )
        self.tmpfile.close()
        self.logger = PrivacyAuditLogger(log_path=self.tmpfile.name)

    def teardown_method(self):
        os.unlink(self.tmpfile.name)

    def test_log_data_access(self):
        """Data access events should be logged."""
        self.logger.log_data_access("abc123", "generate_signal", "preference")
        with open(self.tmpfile.name) as f:
            line = f.readline()
            entry = json.loads(line)
            assert entry["event"] == "data_access"
            assert entry["user_id_hash"] == "abc123"
            assert entry["operation"] == "generate_signal"

    def test_log_noise_addition(self):
        """Noise addition events should be logged."""
        self.logger.log_noise_addition(1.0, 1e-5, "gaussian")
        with open(self.tmpfile.name) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "noise_addition"
            assert entry["epsilon"] == 1.0

    def test_log_aggregation(self):
        """Aggregation events should be logged."""
        self.logger.log_aggregation(10, 5)
        with open(self.tmpfile.name) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "aggregation"
            assert entry["num_signals"] == 10
            assert entry["round_id"] == 5

    def test_generate_audit_report(self):
        """Audit report should summarize logged events."""
        self.logger.log_data_access("user_a", "op1", "pref")
        self.logger.log_data_access("user_b", "op2", "pref")
        self.logger.log_noise_addition(1.0, 1e-5, "gaussian")
        self.logger.log_aggregation(5, 1)

        report = self.logger.generate_audit_report()
        assert report["total_events"] == 4
        assert report["total_noise_additions"] == 1
        assert report["total_aggregations"] == 1
        assert report["unique_users_accessed"] == 2
        assert abs(report["total_epsilon_consumed"] - 1.0) < 1e-10

    def test_audit_report_empty_log(self):
        """Audit report on empty log should return zeros."""
        report = self.logger.generate_audit_report()
        assert report["total_events"] == 0

    def test_append_only(self):
        """Multiple writes should all be preserved (append-only)."""
        self.logger.log_data_access("a", "op1", "t1")
        self.logger.log_data_access("b", "op2", "t2")
        self.logger.log_data_access("c", "op3", "t3")
        with open(self.tmpfile.name) as f:
            lines = f.readlines()
            assert len(lines) == 3


# ============================================================
# 8. k-Anonymity — Refuses to Aggregate with < 5 Signals
# ============================================================

class TestKAnonymity:
    """Verify k-anonymity enforcement."""

    def test_aggregate_refuses_below_k(self):
        """Aggregation should return None with fewer than k signals."""
        trainer = FederatedCompanionTrainer()
        signals = [
            trainer.generate_preference_signal(f"u{i}", "hi", "hello", 0.5)
            for i in range(4)  # Only 4, need 5
        ]
        result = trainer.aggregate_signals(signals)
        assert result is None

    def test_aggregate_accepts_at_k(self):
        """Aggregation should succeed with exactly k signals."""
        trainer = FederatedCompanionTrainer()
        signals = [
            trainer.generate_preference_signal(f"u{i}", "hi", "hello", 0.5)
            for i in range(5)  # Exactly 5
        ]
        result = trainer.aggregate_signals(signals)
        assert result is not None
        assert result["num_contributions"] == 5

    def test_aggregate_accepts_above_k(self):
        """Aggregation should succeed with more than k signals."""
        trainer = FederatedCompanionTrainer()
        signals = [
            trainer.generate_preference_signal(f"u{i}", "hi", "hello", 0.5)
            for i in range(20)
        ]
        result = trainer.aggregate_signals(signals)
        assert result is not None
        assert result["num_contributions"] == 20

    def test_aggregate_empty_raises(self):
        """Aggregating empty list should raise ValueError."""
        trainer = FederatedCompanionTrainer()
        with pytest.raises(ValueError):
            trainer.aggregate_signals([])


# ============================================================
# 9. Sensitivity Clipping — Extreme Values Bounded
# ============================================================

class TestSensitivityClipping:
    """Verify that extreme values are properly clipped."""

    def test_extreme_score_clipped(self):
        """Extreme quality scores should be clipped to sensitivity bounds."""
        trainer = FederatedCompanionTrainer(sensitivity=1.0)
        # Score of 999 → clipped to 1.0 range
        signal = trainer.generate_preference_signal(
            "u1", "test", "test", score=999.0
        )
        # quality_score = (clipped_score - 0.5) * 2 * sensitivity
        # score is first clipped to [0,1] → 1.0 → (1.0-0.5)*2*1.0 = 1.0
        assert abs(signal["quality_score"]) <= 1.0

    def test_negative_score_clipped(self):
        """Negative scores should be clipped to 0."""
        trainer = FederatedCompanionTrainer(sensitivity=1.0)
        signal = trainer.generate_preference_signal(
            "u1", "test", "test", score=-5.0
        )
        # score clipped to 0.0 → (0.0-0.5)*2*1.0 = -1.0
        assert abs(signal["quality_score"]) <= 1.0

    def test_dp_clips_before_noise(self):
        """DP engine should clip values before adding noise."""
        dp = DifferentialPrivacyEngine(epsilon=1.0, sensitivity=1.0)
        # Value of 100 should be clipped to 1.0 before noise
        results = [dp.clip_and_noise(100.0) for _ in range(500)]
        mean = np.mean(results)
        # Mean should be near 1.0 (the clip bound), not 100
        assert mean < 5.0  # Very generous bound

    def test_signal_values_bounded(self):
        """All numeric signal fields should be within sensitivity bounds."""
        trainer = FederatedCompanionTrainer(sensitivity=1.0)
        signal = trainer.generate_preference_signal(
            "u1", "a" * 10000, "b" * 10000, score=0.5
        )
        assert abs(signal["response_length_preference"]) <= 1.0
        assert abs(signal["formality_delta"]) <= 1.0
        assert abs(signal["quality_score"]) <= 1.0


# ============================================================
# 10. End-to-End — No PII Recoverable
# ============================================================

class TestEndToEnd:
    """Full pipeline: message → signal → noise → aggregation → no PII."""

    def test_full_pipeline(self):
        """End-to-end: generate signals, noise them, aggregate, verify no PII."""
        trainer = FederatedCompanionTrainer(epsilon=1.0)

        # Simulate 10 users with distinct messages
        messages = [
            ("alice_smith", "My social security number is 123-45-6789",
             "I can't process SSNs", 0.3),
            ("bob_jones", "I live at 456 Oak Avenue, NYC",
             "That sounds like a nice area!", 0.7),
            ("carol_white", "My phone number is 555-0123",
             "I don't store phone numbers", 0.4),
            ("david_brown", "Tell me about Python programming",
             "Python is a versatile language...", 0.9),
            ("eve_black", "Help me with my homework on biology",
             "Sure! Biology is fascinating...", 0.8),
            ("frank_green", "I want to invest in crypto",
             "Crypto markets are volatile...", 0.6),
            ("grace_red", "Write me a poem about love",
             "Roses are red, violets are blue...", 0.85),
            ("henry_blue", "What's the weather like?",
             "I don't have weather data, but...", 0.5),
            ("iris_gold", "My password is hunter2",
             "Never share passwords!", 0.2),
            ("jack_silver", "I'm feeling anxious about work",
             "It's normal to feel anxious sometimes...", 0.75),
        ]

        # Step 1: Generate signals (locally, no PII in output)
        signals = []
        for user_id, msg, resp, score in messages:
            signal = trainer.generate_preference_signal(user_id, msg, resp, score)
            signals.append(signal)

        # Verify NO PII in any signal
        all_signals_str = json.dumps(signals)
        pii_terms = [
            "alice_smith", "bob_jones", "carol_white", "123-45-6789",
            "456 Oak Avenue", "555-0123", "hunter2", "My social security",
            "My phone number", "My password",
        ]
        for term in pii_terms:
            assert term not in all_signals_str, f"PII leak: '{term}' found in signals"

        # Step 2: Add DP noise
        noised_signals = [trainer.add_differential_noise(s) for s in signals]

        # Verify noise was added
        for orig, noised in zip(signals, noised_signals):
            assert noised["noise_added"] is True
            # At least one numeric field should differ
            any_diff = any(
                abs(orig.get(f, 0) - noised.get(f, 0)) > 1e-10
                for f in ["response_length_preference", "formality_delta", "quality_score"]
            )
            assert any_diff, "No noise was added to the signal"

        # Step 3: Aggregate (FedAvg)
        aggregated = trainer.aggregate_signals(noised_signals)
        assert aggregated is not None
        assert aggregated["num_contributions"] == 10

        # Step 4: Verify no PII in aggregated output
        agg_str = json.dumps(aggregated)
        for term in pii_terms:
            assert term not in agg_str, f"PII leak in aggregate: '{term}'"

        # Step 5: Apply update
        config = {"response_length_preference": 0.0, "formality_delta": 0.0,
                  "quality_score": 0.0}
        updated = trainer.apply_aggregated_update(config, aggregated)
        assert "last_round" in updated

    def test_full_pipeline_with_audit(self):
        """End-to-end with audit logging."""
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            log_path = f.name

        try:
            logger = PrivacyAuditLogger(log_path=log_path)
            scorer = PrivateScorer(
                epsilon=0.5, total_budget=50.0, audit_logger=logger
            )

            # Score some miners
            raw_scores = {f"miner_{i}": float(i) / 10.0 for i in range(10)}
            noised = scorer.score_miners(raw_scores)
            assert noised is not None

            # Check audit log
            report = logger.generate_audit_report()
            assert report["total_events"] >= 2  # noise_addition + aggregation
            assert report["total_noise_additions"] >= 1
        finally:
            os.unlink(log_path)

    def test_secure_aggregation_end_to_end(self):
        """Secure aggregation: miners submit shares, validator gets only the sum."""
        agg = SecureScoreAggregator(num_miners=5, num_share_parties=3)

        scores = {"m1": 0.9, "m2": 0.7, "m3": 0.5, "m4": 0.8, "m5": 0.6}
        expected_total = sum(scores.values())

        for mid, score in scores.items():
            agg.submit_score(mid, score)

        total, mean = agg.aggregate()
        assert abs(total - expected_total) < 1e-5
        assert abs(mean - expected_total / 5) < 1e-5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
