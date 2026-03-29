"""
Tests for Project Nobi — TEE Attestation Module and Protocol Integration.

Covers:
- AMD SEV-SNP report parsing (valid, short, wrong version, bad size)
- NVIDIA CC report verification (valid, bad magic, too short)
- verify_from_base64 dispatch + base64 decode errors
- Attestation cache (record, get, expiry, clear)
- TEE scoring bonus (apply_tee_bonus, reward() with tee_verified)
- get_rewards() with tee_verified_flags
- Protocol fields on CompanionRequest
"""

import base64
import os
import struct
import time

import pytest
from unittest.mock import patch

# ─── Import TEE attestation module ───────────────────────────────────────────
from nobi.privacy.tee_attestation import (
    AMD_SNP_MEASUREMENT_OFFSET,
    AMD_SNP_MEASUREMENT_SIZE,
    AMD_SNP_MIN_REPORT_SIZE,
    AMD_SNP_REPORT_SIZE,
    ATTESTATION_CACHE_TTL,
    NVIDIA_CC_MAGIC,
    AttestationResult,
    SNPReportFields,
    TEEAttestationVerifier,
    _parse_snp_report,
    generate_mock_nvidia_cc_report,
    generate_mock_snp_report,
)

# ─── Import reward functions ──────────────────────────────────────────────────
from nobi.validator.reward import (
    TEE_BONUS_CHAIN_VERIFIED,
    TEE_BONUS_STRUCTURAL,
    TEE_MAX_FINAL_SCORE,
    apply_tee_bonus,
    reward,
)

# ─── Import protocol ─────────────────────────────────────────────────────────
from nobi.protocol import CompanionRequest


# ══════════════════════════════════════════════════════════════════════════════
# Mock Report Generators
# ══════════════════════════════════════════════════════════════════════════════

def make_snp_report(
    measurement: bytes = None,
    version: int = 2,
    size: int = AMD_SNP_REPORT_SIZE,
) -> bytes:
    """Create a mock SNP report of given size."""
    full = bytearray(generate_mock_snp_report(measurement=measurement, version=version))
    if size < len(full):
        return bytes(full[:size])
    return bytes(full)


# ══════════════════════════════════════════════════════════════════════════════
# Part 1: AMD SEV-SNP Report Parsing
# ══════════════════════════════════════════════════════════════════════════════

class TestSNPReportParsing:
    def test_parse_valid_report(self):
        """Full mock report should parse all fields correctly."""
        m = os.urandom(48)
        report = generate_mock_snp_report(measurement=m)
        parsed = _parse_snp_report(report)

        assert parsed.version == 2
        assert parsed.guest_svn == 1
        assert parsed.policy == 0x30000
        assert parsed.vmpl == 0
        assert parsed.signature_algo == 1
        assert parsed.measurement == m
        assert len(parsed.report_data) == 64
        assert len(parsed.host_data) == 32

    def test_measurement_hex_property(self):
        m = bytes(range(48))
        report = generate_mock_snp_report(measurement=m)
        parsed = _parse_snp_report(report)
        assert parsed.measurement_hex == m.hex()

    def test_parse_short_report(self):
        """Parsing a report at minimum size should succeed (partial fields)."""
        short = make_snp_report(size=AMD_SNP_MIN_REPORT_SIZE)
        parsed = _parse_snp_report(short)
        assert parsed.version == 2
        # measurement must be extracted (offset 144, size 48, total 192 = AMD_SNP_MIN_REPORT_SIZE)
        assert len(parsed.measurement) == 48

    def test_parse_custom_measurement(self):
        m = b"\xde\xad\xbe\xef" * 12
        report = generate_mock_snp_report(measurement=m)
        parsed = _parse_snp_report(report)
        assert parsed.measurement == m

    def test_repr(self):
        report = generate_mock_snp_report()
        parsed = _parse_snp_report(report)
        r = repr(parsed)
        assert "SNPReport" in r
        assert "version=2" in r


# ══════════════════════════════════════════════════════════════════════════════
# Part 2: AMD SEV-SNP Verification
# ══════════════════════════════════════════════════════════════════════════════

class TestAMDSEVSNPVerification:
    def setup_method(self):
        self.verifier = TEEAttestationVerifier()

    def test_valid_mock_report(self):
        report = generate_mock_snp_report()
        result = self.verifier.verify_amd_sev_snp(report)
        assert result.valid is True
        assert result.tee_type == "amd-sev-snp"
        assert len(result.measurement) == 96  # 48 bytes hex-encoded

    def test_empty_report(self):
        result = self.verifier.verify_amd_sev_snp(b"")
        assert result.valid is False
        assert "empty" in result.error

    def test_none_report(self):
        result = self.verifier.verify_amd_sev_snp(None)
        assert result.valid is False

    def test_too_short_report(self):
        result = self.verifier.verify_amd_sev_snp(bytes(100))
        assert result.valid is False
        assert "too short" in result.error

    def test_wrong_version(self):
        bad_report = generate_mock_snp_report(version=99)
        result = self.verifier.verify_amd_sev_snp(bad_report)
        assert result.valid is False
        assert "version" in result.error.lower()

    def test_version_1_rejected(self):
        """Version 1 reports (old format) should be rejected."""
        v1_report = generate_mock_snp_report(version=1)
        result = self.verifier.verify_amd_sev_snp(v1_report)
        assert result.valid is False

    def test_measurement_extracted(self):
        m = bytes(range(48))
        report = generate_mock_snp_report(measurement=m)
        result = self.verifier.verify_amd_sev_snp(report)
        assert result.valid is True
        assert result.measurement == m.hex()

    def test_chain_not_verified_in_mvp(self):
        """MVP: chain_verified should always be False (VCEK not yet implemented)."""
        report = generate_mock_snp_report()
        result = self.verifier.verify_amd_sev_snp(report)
        assert result.chain_verified is False

    def test_measurement_pinning_match(self):
        m = os.urandom(48)
        verifier = TEEAttestationVerifier(
            expected_measurements={m.hex()},
            strict_measurement_check=True,
        )
        report = generate_mock_snp_report(measurement=m)
        result = verifier.verify_amd_sev_snp(report)
        assert result.valid is True

    def test_measurement_pinning_mismatch_strict(self):
        """Strict mode: wrong measurement → valid=False."""
        verifier = TEEAttestationVerifier(
            expected_measurements={"a" * 96},  # 48 bytes hex = 96 chars
            strict_measurement_check=True,
        )
        report = generate_mock_snp_report(measurement=b"\x00" * 48)
        result = verifier.verify_amd_sev_snp(report)
        assert result.valid is False
        assert "approved set" in result.error

    def test_measurement_pinning_mismatch_permissive(self):
        """Permissive mode (default): wrong measurement → still valid but with error note."""
        verifier = TEEAttestationVerifier(
            expected_measurements={"a" * 96},
            strict_measurement_check=False,
        )
        report = generate_mock_snp_report(measurement=b"\x00" * 48)
        result = verifier.verify_amd_sev_snp(report)
        assert result.valid is True  # Permissive: allowed with warning
        assert result.error != ""    # But error is noted

    def test_result_to_dict(self):
        report = generate_mock_snp_report()
        result = self.verifier.verify_amd_sev_snp(report)
        d = result.to_dict()
        assert "valid" in d
        assert "tee_type" in d
        assert "measurement" in d
        assert "chain_verified" in d
        assert "error" in d
        assert "verified_at" in d


# ══════════════════════════════════════════════════════════════════════════════
# Part 3: NVIDIA CC Verification
# ══════════════════════════════════════════════════════════════════════════════

class TestNvidiaCCVerification:
    def setup_method(self):
        self.verifier = TEEAttestationVerifier()

    def test_valid_mock_report(self):
        report = generate_mock_nvidia_cc_report()
        result = self.verifier.verify_nvidia_cc(report)
        assert result.valid is True
        assert result.tee_type == "nvidia-cc"

    def test_empty_report(self):
        result = self.verifier.verify_nvidia_cc(b"")
        assert result.valid is False
        assert "empty" in result.error

    def test_wrong_magic(self):
        bad = b"XXXM" + bytes(60)
        result = self.verifier.verify_nvidia_cc(bad)
        assert result.valid is False
        assert "magic" in result.error

    def test_too_short(self):
        result = self.verifier.verify_nvidia_cc(b"NVRM")
        assert result.valid is False
        assert "too short" in result.error

    def test_measurement_extracted(self):
        m = bytes(range(48))
        report = generate_mock_nvidia_cc_report(measurement=m)
        result = self.verifier.verify_nvidia_cc(report)
        assert result.valid is True
        assert result.measurement == m.hex()

    def test_chain_not_verified_in_mvp(self):
        report = generate_mock_nvidia_cc_report()
        result = self.verifier.verify_nvidia_cc(report)
        assert result.chain_verified is False


# ══════════════════════════════════════════════════════════════════════════════
# Part 4: verify_from_base64 dispatch
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifyFromBase64:
    def setup_method(self):
        self.verifier = TEEAttestationVerifier()

    def test_amd_sev_snp_dispatch(self):
        report = generate_mock_snp_report()
        b64 = base64.b64encode(report).decode()
        result = self.verifier.verify_from_base64("amd-sev-snp", b64)
        assert result.valid is True
        assert result.tee_type == "amd-sev-snp"

    def test_nvidia_cc_dispatch(self):
        report = generate_mock_nvidia_cc_report()
        b64 = base64.b64encode(report).decode()
        result = self.verifier.verify_from_base64("nvidia-cc", b64)
        assert result.valid is True
        assert result.tee_type == "nvidia-cc"

    def test_none_type(self):
        result = self.verifier.verify_from_base64("none", "")
        assert result.valid is False
        assert result.tee_type == "none"

    def test_empty_attestation_string(self):
        result = self.verifier.verify_from_base64("amd-sev-snp", "")
        assert result.valid is False

    def test_invalid_base64(self):
        result = self.verifier.verify_from_base64("amd-sev-snp", "not-valid-base64!!!")
        assert result.valid is False
        assert "base64" in result.error.lower()

    def test_unknown_tee_type(self):
        b64 = base64.b64encode(b"test").decode()
        result = self.verifier.verify_from_base64("quantum-enclave", b64)
        assert result.valid is False
        assert "unknown tee_type" in result.error


# ══════════════════════════════════════════════════════════════════════════════
# Part 5: Attestation Cache
# ══════════════════════════════════════════════════════════════════════════════

class TestAttestationCache:
    def setup_method(self):
        self.verifier = TEEAttestationVerifier()

    def test_unknown_miner_returns_not_verified(self):
        status = self.verifier.get_attestation_status(999)
        assert status["valid"] is False
        assert status["tee_type"] == "none"
        assert status["error"] == "not_verified"
        assert status["verified_at"] is None

    def test_record_and_retrieve(self):
        result = AttestationResult(
            valid=True, tee_type="amd-sev-snp", measurement="abc123"
        )
        self.verifier.record_attestation(42, result)
        status = self.verifier.get_attestation_status(42)
        assert status["valid"] is True
        assert status["tee_type"] == "amd-sev-snp"
        assert status["measurement"] == "abc123"
        assert status["cache_age_seconds"] >= 0

    def test_cache_expired_flag(self):
        """Simulate an old cache entry."""
        result = AttestationResult(valid=True, tee_type="amd-sev-snp")
        # Manually insert with old timestamp
        old_ts = time.time() - ATTESTATION_CACHE_TTL - 1
        self.verifier._cache[10] = (result, old_ts)
        status = self.verifier.get_attestation_status(10)
        assert status["cache_expired"] is True

    def test_cache_not_expired_fresh(self):
        result = AttestationResult(valid=True, tee_type="amd-sev-snp")
        self.verifier.record_attestation(11, result)
        status = self.verifier.get_attestation_status(11)
        assert status["cache_expired"] is False

    def test_clear_single_miner(self):
        result = AttestationResult(valid=True, tee_type="amd-sev-snp")
        self.verifier.record_attestation(5, result)
        self.verifier.clear_cache(5)
        status = self.verifier.get_attestation_status(5)
        assert status["error"] == "not_verified"

    def test_clear_all(self):
        for uid in [1, 2, 3]:
            r = AttestationResult(valid=True, tee_type="amd-sev-snp")
            self.verifier.record_attestation(uid, r)
        self.verifier.clear_cache()
        for uid in [1, 2, 3]:
            s = self.verifier.get_attestation_status(uid)
            assert s["valid"] is False

    def test_is_tee_verified_true(self):
        result = AttestationResult(valid=True, tee_type="amd-sev-snp")
        self.verifier.record_attestation(20, result)
        assert self.verifier.is_tee_verified(20) is True

    def test_is_tee_verified_false_not_recorded(self):
        assert self.verifier.is_tee_verified(999) is False

    def test_is_tee_verified_false_invalid(self):
        result = AttestationResult(valid=False, tee_type="amd-sev-snp", error="bad")
        self.verifier.record_attestation(21, result)
        assert self.verifier.is_tee_verified(21) is False

    def test_is_tee_verified_false_expired(self):
        result = AttestationResult(valid=True, tee_type="amd-sev-snp")
        old_ts = time.time() - ATTESTATION_CACHE_TTL - 10
        self.verifier._cache[22] = (result, old_ts)
        assert self.verifier.is_tee_verified(22) is False


# ══════════════════════════════════════════════════════════════════════════════
# Part 6: TEE Scoring Bonus
# ══════════════════════════════════════════════════════════════════════════════

class TestTEEScoringBonus:
    def test_no_tee_no_change(self):
        score = apply_tee_bonus(0.80, tee_verified=False)
        assert score == pytest.approx(0.80)

    def test_structural_bonus(self):
        score = apply_tee_bonus(0.80, tee_verified=True, chain_verified=False)
        expected = min(1.0, 0.80 * (1.0 + TEE_BONUS_STRUCTURAL))
        assert score == pytest.approx(expected)

    def test_chain_verified_bonus(self):
        score = apply_tee_bonus(0.80, tee_verified=True, chain_verified=True)
        expected = min(1.0, 0.80 * (1.0 + TEE_BONUS_CHAIN_VERIFIED))
        assert score == pytest.approx(expected)

    def test_chain_bonus_larger_than_structural(self):
        structural = apply_tee_bonus(0.80, tee_verified=True, chain_verified=False)
        chain = apply_tee_bonus(0.80, tee_verified=True, chain_verified=True)
        assert chain > structural

    def test_bonus_capped_at_1(self):
        """Bonus should never push score above 1.0."""
        score = apply_tee_bonus(0.99, tee_verified=True, chain_verified=True)
        assert score <= TEE_MAX_FINAL_SCORE
        assert score == pytest.approx(TEE_MAX_FINAL_SCORE)

    def test_zero_score_stays_zero(self):
        score = apply_tee_bonus(0.0, tee_verified=True, chain_verified=True)
        assert score == pytest.approx(0.0)

    def test_bonus_constants_reasonable(self):
        """Sanity check on bonus constants."""
        assert 0.0 < TEE_BONUS_STRUCTURAL <= 0.15
        assert 0.0 < TEE_BONUS_CHAIN_VERIFIED <= 0.20
        assert TEE_BONUS_CHAIN_VERIFIED >= TEE_BONUS_STRUCTURAL

    def test_tee_bonus_in_reward_single_turn(self):
        """reward() should apply TEE bonus for single-turn scoring."""
        base = reward("hello", "Hello there! How can I help you today?", latency=1.0)
        with_tee = reward(
            "hello", "Hello there! How can I help you today?",
            latency=1.0,
            tee_verified=True,
            tee_chain_verified=False,
        )
        # TEE-verified miner should score at least as high
        assert with_tee >= base

    def test_tee_bonus_in_reward_multi_turn(self):
        """reward() should apply TEE bonus for multi-turn scoring.
        
        Patched _llm_judge for determinism — two live LLM calls are non-deterministic.
        """
        with patch("nobi.validator.reward._llm_judge", return_value=0.5):
            base = reward(
                "How's my cat?", "Your cat Felix is doing great!",
                test_type="multi_turn",
                memory_keywords=["Felix", "cat"],
                latency=1.0,
            )
            with_tee = reward(
                "How's my cat?", "Your cat Felix is doing great!",
                test_type="multi_turn",
                memory_keywords=["Felix", "cat"],
                latency=1.0,
                tee_verified=True,
            )
            assert with_tee >= base

    def test_no_tee_no_reward_change(self):
        """reward() without TEE flags should behave exactly as before.
        
        We patch _llm_judge to return a fixed value so this test is deterministic.
        Without mocking, two separate LLM calls could return different scores
        even at temperature=0 due to model non-determinism.
        """
        with patch("nobi.validator.reward._llm_judge", return_value=0.5):
            r1 = reward("hello", "Hi there!", latency=2.0, tee_verified=False)
            r2 = reward("hello", "Hi there!", latency=2.0)
            assert r1 == pytest.approx(r2)


# ══════════════════════════════════════════════════════════════════════════════
# Part 7: Protocol Fields
# ══════════════════════════════════════════════════════════════════════════════

class TestProtocolTEEFields:
    def test_companion_request_has_tee_type(self):
        req = CompanionRequest(message="hi")
        assert hasattr(req, "tee_type")
        assert req.tee_type == ""

    def test_companion_request_has_tee_attestation(self):
        req = CompanionRequest(message="hi")
        assert hasattr(req, "tee_attestation")
        assert req.tee_attestation == ""

    def test_companion_request_has_tee_verified(self):
        req = CompanionRequest(message="hi")
        assert hasattr(req, "tee_verified")
        assert req.tee_verified is False

    def test_tee_type_set_amd_sev_snp(self):
        report = generate_mock_snp_report()
        b64 = base64.b64encode(report).decode()
        req = CompanionRequest(
            message="hello",
            tee_type="amd-sev-snp",
            tee_attestation=b64,
        )
        assert req.tee_type == "amd-sev-snp"
        assert req.tee_attestation == b64
        assert req.tee_verified is False  # Default; validator sets this

    def test_tee_verified_can_be_set(self):
        req = CompanionRequest(message="hi")
        req.tee_verified = True
        assert req.tee_verified is True

    def test_backward_compatibility_no_tee_fields(self):
        """Requests without TEE fields should still work (defaults)."""
        req = CompanionRequest(message="test message")
        assert req.tee_type == ""
        assert req.tee_attestation == ""
        assert req.tee_verified is False
        assert req.message == "test message"

    def test_tee_type_nvidia_cc(self):
        report = generate_mock_nvidia_cc_report()
        b64 = base64.b64encode(report).decode()
        req = CompanionRequest(
            message="hello",
            tee_type="nvidia-cc",
            tee_attestation=b64,
        )
        assert req.tee_type == "nvidia-cc"

    def test_tee_none_type(self):
        req = CompanionRequest(message="hello", tee_type="none")
        assert req.tee_type == "none"

    def test_full_tee_workflow_integration(self):
        """
        Integration test: full workflow from miner advertisement to scoring.
        1. Miner sets tee_type + tee_attestation in request
        2. Validator verifies attestation
        3. Validator records result and sets tee_verified
        4. Scoring applies TEE bonus
        """
        # Miner side: set TEE fields
        report = generate_mock_snp_report()
        b64 = base64.b64encode(report).decode()
        req = CompanionRequest(
            message="What's the weather like?",
            tee_type="amd-sev-snp",
            tee_attestation=b64,
        )
        req.response = "I don't have real-time weather data, but I can help you check!"
        req.confidence = 0.9

        # Validator side: verify attestation
        verifier = TEEAttestationVerifier()
        attestation_result = verifier.verify_from_base64(req.tee_type, req.tee_attestation)
        assert attestation_result.valid is True

        # Validator marks miner as TEE-verified
        verifier.record_attestation(miner_uid=42, result=attestation_result)
        req.tee_verified = attestation_result.valid

        # Confirm cache
        assert verifier.is_tee_verified(42) is True

        # Scoring with TEE bonus — patch LLM judge for determinism
        with patch("nobi.validator.reward._llm_judge", return_value=0.5):
            base_score = reward(req.message, req.response, latency=1.0)
            tee_score = reward(
                req.message, req.response,
                latency=1.0,
                tee_verified=req.tee_verified,
                tee_chain_verified=attestation_result.chain_verified,
            )
        assert tee_score >= base_score
        assert tee_score <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Part 8: generate_mock helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestMockGenerators:
    def test_mock_snp_correct_size(self):
        report = generate_mock_snp_report()
        assert len(report) == AMD_SNP_REPORT_SIZE

    def test_mock_snp_custom_measurement(self):
        m = b"\x01" * 48
        report = generate_mock_snp_report(measurement=m)
        assert report[AMD_SNP_MEASUREMENT_OFFSET:AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE] == m

    def test_mock_snp_random_measurement(self):
        r1 = generate_mock_snp_report()
        r2 = generate_mock_snp_report()
        m1 = r1[AMD_SNP_MEASUREMENT_OFFSET:AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE]
        m2 = r2[AMD_SNP_MEASUREMENT_OFFSET:AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE]
        # Two random reports should have different measurements (with overwhelming probability)
        assert m1 != m2

    def test_mock_nvidia_correct_magic(self):
        report = generate_mock_nvidia_cc_report()
        assert report[:4] == NVIDIA_CC_MAGIC

    def test_mock_nvidia_minimum_size(self):
        report = generate_mock_nvidia_cc_report()
        assert len(report) >= 64

    def test_mock_nvidia_custom_measurement(self):
        m = b"\x02" * 48
        report = generate_mock_nvidia_cc_report(measurement=m)
        assert report[4:52] == m
