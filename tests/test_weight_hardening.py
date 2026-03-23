"""
Tests for WeightHardening — weight commit-reveal hardening.

Covers:
- Fingerprinting (output differs from input, within epsilon)
- Obfuscation (two calls with same input produce different outputs)
- Commit hash verification (round-trip)
- Stale detection (N identical epochs triggers flag)
- Copied weight detection (identical commits flagged)
- Similarity detection (quantised Jaccard)
- Backward compatibility (process/convert functions unaffected)
"""

import hashlib
import os
import tempfile

import numpy as np
import pytest

from nobi.base.utils.weight_utils import WeightHardening


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_hardening(tmp_path):
    """WeightHardening instance backed by a temp file."""
    state_file = str(tmp_path / "wh_state.json")
    return WeightHardening(validator_hotkey="test_hotkey_abc123", state_path=state_file)


@pytest.fixture
def simple_weights():
    """Simple normalised weight vector."""
    w = np.array([0.5, 0.3, 0.2], dtype=np.float32)
    return w


@pytest.fixture
def uniform_weights():
    """Uniform weight vector over 10 miners."""
    w = np.ones(10, dtype=np.float32) / 10
    return w


# ── Fingerprinting ────────────────────────────────────────────────────────────

class TestFingerprinting:
    def test_output_differs_from_input(self, tmp_hardening, simple_weights):
        """Hardening should change the weights (fingerprint + salt)."""
        hardened, salt, commit = tmp_hardening.harden(simple_weights)
        assert not np.allclose(hardened, simple_weights, atol=0)

    def test_weights_still_sum_to_one(self, tmp_hardening, simple_weights):
        """Hardened weights must remain normalised."""
        hardened, _, _ = tmp_hardening.harden(simple_weights)
        assert abs(hardened.sum() - 1.0) < 1e-5, f"Sum = {hardened.sum()}"

    def test_weights_non_negative(self, tmp_hardening, uniform_weights):
        """No negative weights after hardening."""
        hardened, _, _ = tmp_hardening.harden(uniform_weights)
        assert np.all(hardened >= 0.0)

    def test_fingerprint_within_epsilon_plus_salt(self, tmp_hardening, uniform_weights):
        """
        Maximum per-element deviation should be bounded by fingerprint_epsilon +
        salt_amplitude (plus tiny renorm effect).
        """
        hardened, _, _ = tmp_hardening.harden(uniform_weights)
        max_delta = np.max(np.abs(hardened - uniform_weights))
        # Empirical bound: fingerprint_epsilon + salt_amplitude + renorm tolerance
        upper_bound = (
            tmp_hardening.fingerprint_epsilon
            + tmp_hardening.salt_amplitude
            + 1e-3  # renorm tolerance
        )
        assert max_delta < upper_bound, f"max_delta={max_delta} > {upper_bound}"

    def test_two_validators_produce_different_hardened(self, tmp_path, uniform_weights):
        """Different hotkeys → different fingerprints → different outputs."""
        wh1 = WeightHardening("hotkey_validator_1", state_path=str(tmp_path / "v1.json"))
        wh2 = WeightHardening("hotkey_validator_2", state_path=str(tmp_path / "v2.json"))

        h1, _, _ = wh1.harden(uniform_weights.copy())
        h2, _, _ = wh2.harden(uniform_weights.copy())

        # Different validators → different hardened outputs
        assert not np.allclose(h1, h2, atol=1e-7)


# ── Obfuscation ───────────────────────────────────────────────────────────────

class TestObfuscation:
    def test_two_harden_calls_produce_different_salts(self, tmp_hardening, simple_weights):
        """Each call uses a fresh random salt."""
        _, salt1, _ = tmp_hardening.harden(simple_weights.copy())
        _, salt2, _ = tmp_hardening.harden(simple_weights.copy())
        assert salt1 != salt2, "Salts should be different for each epoch"

    def test_two_harden_calls_produce_different_weights(self, tmp_hardening, simple_weights):
        """Each call should yield different on-chain weights (due to random salt)."""
        h1, _, _ = tmp_hardening.harden(simple_weights.copy())
        h2, _, _ = tmp_hardening.harden(simple_weights.copy())
        assert not np.allclose(h1, h2, atol=1e-7)

    def test_two_harden_calls_produce_different_commits(self, tmp_hardening, simple_weights):
        """Each epoch's commit hash should be unique (different salt)."""
        _, _, c1 = tmp_hardening.harden(simple_weights.copy())
        _, _, c2 = tmp_hardening.harden(simple_weights.copy())
        assert c1 != c2


# ── Commit hash ───────────────────────────────────────────────────────────────

class TestCommitHash:
    def test_verify_commit_round_trip(self, tmp_hardening, simple_weights):
        """verify_commit should pass for the weights that produced the hash.
        Note: harden() returns float32; verify_commit works on that same array."""
        hardened, salt, commit = tmp_hardening.harden(simple_weights)
        # hardened is already float32; pass it directly — types must match
        assert tmp_hardening.verify_commit(commit, salt, hardened.astype(np.float32))

    def test_verify_commit_fails_on_tampered_weights(self, tmp_hardening, simple_weights):
        """Tampered weights must not verify."""
        hardened, salt, commit = tmp_hardening.harden(simple_weights)
        tampered = hardened.copy()
        tampered[0] += 0.1
        tampered /= tampered.sum()
        assert not tmp_hardening.verify_commit(commit, salt, tampered)

    def test_verify_commit_fails_on_wrong_salt(self, tmp_hardening, simple_weights):
        """Wrong salt must not verify."""
        hardened, salt, commit = tmp_hardening.harden(simple_weights)
        wrong_salt = os.urandom(32)
        assert not tmp_hardening.verify_commit(commit, wrong_salt, hardened)

    def test_commit_is_hex_string(self, tmp_hardening, simple_weights):
        """Commit hash must be a hex string of expected length."""
        _, _, commit = tmp_hardening.harden(simple_weights)
        assert isinstance(commit, str)
        assert len(commit) == 64  # SHA-256 hex = 64 chars
        int(commit, 16)  # must be valid hex

    def test_identical_weights_same_salt_same_commit(self, tmp_path, simple_weights):
        """Deterministic: same weights + same salt → same commit hash."""
        wh = WeightHardening("fixed_hotkey", state_path=str(tmp_path / "fixed.json"))
        fixed_salt = b"\xde\xad\xbe\xef" * 8  # 32 bytes
        # Compute commit manually without full harden (bypass random salt)
        commit_a = wh._make_commit_hash(simple_weights, fixed_salt)
        commit_b = wh._make_commit_hash(simple_weights, fixed_salt)
        assert commit_a == commit_b


# ── Stale weight detection ────────────────────────────────────────────────────

class TestStaleDetection:
    def test_not_stale_initially(self, tmp_hardening, simple_weights):
        """No stale flag before threshold is reached."""
        assert not tmp_hardening.check_stale()

    def test_stale_after_threshold_identical_commits(self, tmp_hardening):
        """
        Manually inject identical commit hashes to trigger stale detection.
        """
        # Stuff the history with identical hashes
        fake_hash = "a" * 64
        for _ in range(tmp_hardening.stale_threshold):
            tmp_hardening._record_epoch(fake_hash)
        assert tmp_hardening.check_stale()

    def test_not_stale_with_varying_commits(self, tmp_hardening):
        """Different hashes per epoch → no stale flag."""
        for i in range(tmp_hardening.stale_threshold):
            tmp_hardening._record_epoch(f"hash_{i}" + "0" * 58)
        assert not tmp_hardening.check_stale()

    def test_stale_threshold_configurable(self, tmp_path):
        """Custom stale_threshold is respected."""
        wh = WeightHardening(state_path=str(tmp_path / "s.json"), stale_threshold=2)
        fake_hash = "b" * 64
        wh._record_epoch(fake_hash)
        assert not wh.check_stale()
        wh._record_epoch(fake_hash)
        assert wh.check_stale()

    def test_real_harden_doesnt_stale_with_different_weights(self, tmp_hardening):
        """
        Even same input weights produce different commits (random salt) so
        harden() alone should not trigger stale in normal operation.
        """
        w = np.ones(5, dtype=np.float32) / 5
        for _ in range(tmp_hardening.stale_threshold + 1):
            tmp_hardening.harden(w.copy())
        # With random salt, commits differ — should not be stale
        # (probabilistic, but astronomically unlikely to collide)
        assert not tmp_hardening.check_stale()


# ── Copied weight flagging ────────────────────────────────────────────────────

class TestCopyDetection:
    def test_flag_identical_commits(self, tmp_hardening):
        my_commit = "abc" + "0" * 61
        others = [my_commit, "def" + "0" * 61, "ghi" + "0" * 61]
        flagged = tmp_hardening.flag_copied_weights(my_commit, others)
        assert flagged == [my_commit]

    def test_no_flag_when_all_different(self, tmp_hardening):
        my_commit = "aaa" + "0" * 61
        others = ["bbb" + "0" * 61, "ccc" + "0" * 61]
        flagged = tmp_hardening.flag_copied_weights(my_commit, others)
        assert flagged == []

    def test_flag_multiple_copies(self, tmp_hardening):
        my_commit = "zzz" + "0" * 61
        others = [my_commit, my_commit, "xxx" + "0" * 61]
        flagged = tmp_hardening.flag_copied_weights(my_commit, others)
        assert len(flagged) == 2

    def test_empty_other_commits(self, tmp_hardening):
        flagged = tmp_hardening.flag_copied_weights("abc" + "0" * 61, [])
        assert flagged == []


# ── Similarity detection ──────────────────────────────────────────────────────

class TestSimilarityDetection:
    def test_identical_vectors_have_similarity_one(self, tmp_hardening):
        w = np.array([0.5, 0.3, 0.2], dtype=np.float32)
        sim = tmp_hardening.detect_similar_weights(w, w)
        assert sim == pytest.approx(1.0)

    def test_very_different_vectors_have_lower_similarity_than_identical(self, tmp_hardening):
        """Very different weight distributions score lower than identical ones."""
        identical_a = np.array([0.5, 0.3, 0.1, 0.1], dtype=np.float32)
        identical_b = np.array([0.5, 0.3, 0.1, 0.1], dtype=np.float32)
        different_a = np.array([0.9, 0.05, 0.03, 0.02], dtype=np.float32)
        different_b = np.array([0.02, 0.03, 0.05, 0.90], dtype=np.float32)
        sim_identical = tmp_hardening.detect_similar_weights(identical_a, identical_b)
        sim_different = tmp_hardening.detect_similar_weights(different_a, different_b)
        assert sim_identical > sim_different, (
            f"identical sim={sim_identical} should > different sim={sim_different}"
        )

    def test_similar_vectors_have_higher_similarity_than_different(self, tmp_hardening):
        """Near-identical weight vectors should score higher than very different ones."""
        near_a = np.array([0.50, 0.30, 0.15, 0.05], dtype=np.float32)
        near_b = np.array([0.50, 0.30, 0.15, 0.05], dtype=np.float32)  # identical
        far_a  = np.array([0.10, 0.10, 0.10, 0.70], dtype=np.float32)
        far_b  = np.array([0.70, 0.10, 0.10, 0.10], dtype=np.float32)
        sim_near = tmp_hardening.detect_similar_weights(near_a, near_b)
        sim_far  = tmp_hardening.detect_similar_weights(far_a, far_b)
        assert sim_near > sim_far, (
            f"near sim={sim_near} should > far sim={sim_far}"
        )

    def test_similarity_symmetric(self, tmp_hardening):
        a = np.array([0.6, 0.4], dtype=np.float32)
        b = np.array([0.5, 0.5], dtype=np.float32)
        assert tmp_hardening.detect_similar_weights(a, b) == pytest.approx(
            tmp_hardening.detect_similar_weights(b, a)
        )


# ── State persistence ─────────────────────────────────────────────────────────

class TestStatePersistence:
    def test_state_survives_reload(self, tmp_path, simple_weights):
        """Epoch counter and weight history should persist across instantiations."""
        state_file = str(tmp_path / "persist.json")
        wh1 = WeightHardening(validator_hotkey="hotkey_x", state_path=state_file)
        wh1.harden(simple_weights.copy())
        wh1.harden(simple_weights.copy())
        epoch_after = wh1._epoch

        # Reload from same state file
        wh2 = WeightHardening(validator_hotkey="hotkey_x", state_path=state_file)
        assert wh2._epoch == epoch_after
        assert len(wh2._weight_history) == len(wh1._weight_history)

    def test_corrupt_state_handled_gracefully(self, tmp_path):
        """Corrupt state file should not raise; fresh state used instead."""
        state_file = str(tmp_path / "corrupt.json")
        with open(state_file, "w") as f:
            f.write("{not valid json{{")
        # Should not raise
        wh = WeightHardening(state_path=state_file)
        assert wh._epoch == 0
        assert wh._weight_history == []


# ── Backward compatibility ────────────────────────────────────────────────────

class TestBackwardCompatibility:
    def test_process_weights_unaffected(self):
        """
        process_weights_for_netuid and convert_weights_and_uids_for_emit
        must still be importable and functional.
        """
        from nobi.base.utils.weight_utils import (
            process_weights_for_netuid,
            convert_weights_and_uids_for_emit,
            normalize_max_weight,
        )
        uids = np.array([0, 1, 2])
        weights = np.array([0.5, 0.3, 0.2], dtype=np.float32)
        result_uids, result_weights = convert_weights_and_uids_for_emit(uids, weights)
        assert len(result_uids) == len(result_weights)
        assert all(isinstance(w, int) for w in result_weights)

    def test_weight_hardening_importable(self):
        from nobi.base.utils.weight_utils import WeightHardening
        assert WeightHardening is not None
