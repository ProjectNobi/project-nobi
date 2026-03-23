"""
Project Nobi — TEE Attestation Module
======================================
Verify that miners are ACTUALLY running inside a Trusted Execution Environment
(not just claiming to). Attestation reports are signed by the hardware vendor's
root of trust and include a measurement of the running code — you can't fake one
without the private key held by AMD or NVIDIA.

Supported TEE types
-------------------
* AMD SEV-SNP  — AMD EPYC processors (Milan, Genoa). Recommended for miners.
  Targon (SN4) already uses this on Bittensor — proven to work.
* NVIDIA CC    — NVIDIA H100/A100 Confidential Computing mode.

MVP scope
---------
Full cryptographic chain-of-trust verification (AMD KDS VCEK certificate fetch,
ECDSA-P384 signature check) is complex and requires network access to AMD.
This module provides:
  - The correct report structure / field parser for AMD SNP attestation reports
  - A structural validity check (magic bytes, version, length)
  - Measurement extraction so validators can pin expected code hashes
  - A pluggable `_verify_amd_signature_stub` ready for full VCEK integration
  - Caching of attestation status per miner UID
  - NVIDIA CC framework (structural only — no GPU in CI)

Wire transport
--------------
Attestation reports are base64-encoded in CompanionRequest.tee_attestation.
The verifier is called by the validator before scoring.
"""

import base64
import hashlib
import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger("nobi-tee-attestation")

# ─── AMD SEV-SNP report layout ────────────────────────────────────────────────
# Reference: AMD SEV-SNP ABI Specification, Revision 1.55
# https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/
#   specifications/56860.pdf
#
# The attestation report is 1184 bytes total:
#   Offset 0   (4 bytes)  : version  (must be 2 for SNP)
#   Offset 4   (4 bytes)  : guest SVN
#   Offset 8   (8 bytes)  : policy
#   Offset 16  (16 bytes) : family ID
#   Offset 32  (16 bytes) : image ID
#   Offset 48  (4 bytes)  : VMPL
#   Offset 52  (4 bytes)  : signature algorithm (1 = ECDSA-P384-SHA384)
#   Offset 56  (8 bytes)  : current TCB version
#   Offset 64  (8 bytes)  : platform info
#   Offset 72  (4 bytes)  : author key enabled flag
#   Offset 76  (4 bytes)  : reserved
#   Offset 80  (64 bytes) : report data (user-supplied nonce / public key hash)
#   Offset 144 (48 bytes) : MEASUREMENT (SHA-384 of guest code — key field)
#   Offset 192 (32 bytes) : host data
#   Offset 224 (48 bytes) : ID key digest
#   Offset 272 (48 bytes) : author key digest
#   Offset 320 (32 bytes) : report ID
#   Offset 352 (32 bytes) : report ID MA
#   Offset 384 (8 bytes)  : reported TCB
#   Offset 392 (24 bytes) : reserved
#   Offset 416 (512 bytes): VCEK certificate (optional, can be 0-padded)
#   Offset 928 (128 bytes): reserved
#   Offset 1056 (128 bytes): signature (ECDSA-P384, r+s each 72 bytes padded)
#   Total = 1184 bytes

AMD_SNP_REPORT_SIZE = 1184
AMD_SNP_VERSION_OFFSET = 0
AMD_SNP_POLICY_OFFSET = 8
AMD_SNP_REPORT_DATA_OFFSET = 80
AMD_SNP_MEASUREMENT_OFFSET = 144
AMD_SNP_MEASUREMENT_SIZE = 48    # SHA-384 = 48 bytes
AMD_SNP_SIGNATURE_OFFSET = 1056
AMD_SNP_SIGNATURE_SIZE = 128
AMD_SNP_EXPECTED_VERSION = 2

# Minimum "mock" report size for testing (header + measurement region)
AMD_SNP_MIN_REPORT_SIZE = AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE  # 192 bytes

# NVIDIA CC PPCIE report magic
NVIDIA_CC_MAGIC = b"NVRM"

# Attestation cache TTL (seconds) — re-verify every 10 minutes
ATTESTATION_CACHE_TTL = 600


@dataclass
class SNPReportFields:
    """Parsed fields from an AMD SEV-SNP attestation report."""
    version: int = 0
    guest_svn: int = 0
    policy: int = 0
    vmpl: int = 0
    signature_algo: int = 0
    measurement: bytes = field(default_factory=bytes)
    report_data: bytes = field(default_factory=bytes)
    host_data: bytes = field(default_factory=bytes)
    reported_tcb: int = 0
    # Whether the signature field was present and non-zero
    has_signature: bool = False

    @property
    def measurement_hex(self) -> str:
        return self.measurement.hex()

    def __repr__(self) -> str:
        return (
            f"SNPReport(version={self.version}, policy=0x{self.policy:x}, "
            f"measurement={self.measurement_hex[:16]}…)"
        )


@dataclass
class AttestationResult:
    """Result of an attestation verification attempt."""
    valid: bool
    tee_type: str          # "amd-sev-snp" | "nvidia-cc" | "none"
    measurement: str = ""  # hex measurement (code hash)
    error: str = ""
    verified_at: float = field(default_factory=time.time)
    # Full VCEK chain verification (requires network access to AMD KDS)
    chain_verified: bool = False

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "tee_type": self.tee_type,
            "measurement": self.measurement,
            "error": self.error,
            "verified_at": self.verified_at,
            "chain_verified": self.chain_verified,
        }


class TEEAttestationVerifier:
    """
    Verify miner TEE attestation reports.

    Validators call this on each miner response to determine whether
    the miner is running inside a genuine TEE enclave.

    Usage::

        verifier = TEEAttestationVerifier()
        result = verifier.verify_amd_sev_snp(report_bytes)
        if result.valid:
            # Apply TEE bonus to miner score
            ...

    Pinning expected measurements::

        verifier.expected_measurements.add(
            "expected_sha384_hex_goes_here"
        )
    """

    def __init__(
        self,
        expected_measurements: Optional[set] = None,
        strict_measurement_check: bool = False,
    ):
        """
        Args:
            expected_measurements: Set of hex SHA-384 hashes of approved miner
                binaries. If non-empty and strict_measurement_check=True, any
                report whose measurement is not in this set is rejected.
            strict_measurement_check: If True, reject reports whose measurement
                is not in expected_measurements. Default False (log warning only).
        """
        # Approved binary measurements (SHA-384 hex strings)
        self.expected_measurements: set = expected_measurements or set()
        self.strict_measurement_check = strict_measurement_check

        # Cache: miner_uid → (AttestationResult, timestamp)
        self._cache: Dict[int, Tuple[AttestationResult, float]] = {}

    # ─── Public API ──────────────────────────────────────────────────────────

    def verify_amd_sev_snp(self, attestation_report: bytes) -> AttestationResult:
        """
        Verify an AMD SEV-SNP attestation report.

        Steps:
        1. Parse report structure (magic bytes, version, size)
        2. Extract measurement (SHA-384 of guest code)
        3. Check measurement against expected_measurements (if configured)
        4. Stub for VCEK signature verification (requires AMD KDS network call)

        Args:
            attestation_report: Raw bytes of the AMD SNP attestation report,
                as returned by ``/dev/sev-guest`` ioctl GUEST_REPORT.

        Returns:
            AttestationResult with valid=True if the report passes all checks.
        """
        if not attestation_report:
            return AttestationResult(
                valid=False, tee_type="amd-sev-snp",
                error="empty attestation report"
            )

        # 1. Size check
        if len(attestation_report) < AMD_SNP_MIN_REPORT_SIZE:
            return AttestationResult(
                valid=False, tee_type="amd-sev-snp",
                error=f"report too short: {len(attestation_report)} < {AMD_SNP_MIN_REPORT_SIZE}"
            )

        # 2. Parse fields
        try:
            parsed = _parse_snp_report(attestation_report)
        except Exception as e:
            return AttestationResult(
                valid=False, tee_type="amd-sev-snp",
                error=f"parse error: {e}"
            )

        # 3. Version check
        if parsed.version != AMD_SNP_EXPECTED_VERSION:
            return AttestationResult(
                valid=False, tee_type="amd-sev-snp",
                error=f"unexpected SNP version {parsed.version} (expected {AMD_SNP_EXPECTED_VERSION})"
            )

        # 4. Measurement check
        measurement_hex = parsed.measurement_hex
        measurement_ok = True
        if self.expected_measurements:
            if measurement_hex not in self.expected_measurements:
                msg = f"measurement {measurement_hex[:16]}… not in approved set"
                if self.strict_measurement_check:
                    return AttestationResult(
                        valid=False, tee_type="amd-sev-snp",
                        error=msg, measurement=measurement_hex
                    )
                else:
                    logger.warning("[TEE] %s — allowing (strict_measurement_check=False)", msg)
                    measurement_ok = False

        # 5. Signature verification stub
        # Full verification requires fetching VCEK cert from AMD KDS:
        #   https://kdsintf.amd.com/vcek/v1/{product}/{hwid}?blSPL=...&teeSPL=...
        # Then verifying ECDSA-P384 signature over the first 672 bytes of report.
        # We stub this out for MVP — chain_verified=False signals to callers.
        chain_verified, sig_error = _verify_amd_signature_stub(attestation_report, parsed)

        return AttestationResult(
            valid=True,
            tee_type="amd-sev-snp",
            measurement=measurement_hex,
            chain_verified=chain_verified,
            error=sig_error if sig_error else ("measurement_mismatch" if not measurement_ok else ""),
        )

    def verify_nvidia_cc(self, attestation_report: bytes) -> AttestationResult:
        """
        Verify an NVIDIA Confidential Computing attestation report.

        NVIDIA CC attestation is produced by the PPCIE library via:
            nv-attestation-sdk / nv-cc-attestation

        The report includes:
        - RIM (Reference Integrity Manifest) measurements
        - OCSP-validated certificate chain from NVIDIA
        - GPC (GPU-signed attestation certificate)

        MVP: structural check on report magic bytes and minimum size.
        Full OCSP chain verification requires the nv-attestation-sdk library.

        Args:
            attestation_report: Raw bytes from NVIDIA attestation service.

        Returns:
            AttestationResult with valid=True on structural validity.
        """
        if not attestation_report:
            return AttestationResult(
                valid=False, tee_type="nvidia-cc",
                error="empty attestation report"
            )

        if len(attestation_report) < len(NVIDIA_CC_MAGIC):
            return AttestationResult(
                valid=False, tee_type="nvidia-cc",
                error=f"report too short: {len(attestation_report)} bytes"
            )

        # Magic bytes check
        if attestation_report[:len(NVIDIA_CC_MAGIC)] != NVIDIA_CC_MAGIC:
            return AttestationResult(
                valid=False, tee_type="nvidia-cc",
                error="invalid magic bytes — not an NVIDIA CC report"
            )

        # Structural validity: report must be JSON or binary blob with minimum size
        min_size = 64  # At minimum: magic + header
        if len(attestation_report) < min_size:
            return AttestationResult(
                valid=False, tee_type="nvidia-cc",
                error=f"report too short: {len(attestation_report)} < {min_size}"
            )

        # Extract measurement hash if present (bytes 4..52 in simplified format)
        measurement = ""
        if len(attestation_report) >= 52:
            measurement = attestation_report[4:52].hex()

        logger.info("[TEE] NVIDIA CC report structurally valid (full OCSP chain not verified in MVP)")

        return AttestationResult(
            valid=True,
            tee_type="nvidia-cc",
            measurement=measurement,
            chain_verified=False,  # Full OCSP chain verification not yet implemented
        )

    def verify_from_base64(self, tee_type: str, attestation_b64: str) -> AttestationResult:
        """
        Verify an attestation report from its base64-encoded wire representation.

        This is the main entry point used by the validator — it receives
        CompanionRequest.tee_type and CompanionRequest.tee_attestation and
        calls this method.

        Args:
            tee_type: "amd-sev-snp" | "nvidia-cc" | "none"
            attestation_b64: Base64-encoded attestation report bytes

        Returns:
            AttestationResult
        """
        if tee_type == "none" or not attestation_b64:
            return AttestationResult(valid=False, tee_type="none", error="no TEE claimed")

        try:
            report_bytes = base64.b64decode(attestation_b64)
        except Exception as e:
            return AttestationResult(
                valid=False, tee_type=tee_type,
                error=f"base64 decode failed: {e}"
            )

        if tee_type == "amd-sev-snp":
            return self.verify_amd_sev_snp(report_bytes)
        elif tee_type == "nvidia-cc":
            return self.verify_nvidia_cc(report_bytes)
        else:
            return AttestationResult(
                valid=False, tee_type=tee_type,
                error=f"unknown tee_type: {tee_type!r}"
            )

    def get_attestation_status(self, miner_uid: int) -> dict:
        """
        Return cached attestation status for a miner UID.

        The validator calls this after processing a miner's response.
        Returns the last known attestation result, with cache TTL enforcement.

        Args:
            miner_uid: The miner's UID on the subnet.

        Returns:
            dict with keys: valid, tee_type, measurement, chain_verified,
            verified_at, error, cache_age_seconds
        """
        cached = self._cache.get(miner_uid)
        now = time.time()

        if cached is None:
            return {
                "valid": False,
                "tee_type": "none",
                "measurement": "",
                "chain_verified": False,
                "verified_at": None,
                "error": "not_verified",
                "cache_age_seconds": None,
            }

        result, ts = cached
        age = now - ts
        data = result.to_dict()
        data["cache_age_seconds"] = age
        data["cache_expired"] = age > ATTESTATION_CACHE_TTL
        return data

    def record_attestation(self, miner_uid: int, result: AttestationResult) -> None:
        """
        Store an attestation result in the cache for miner_uid.

        Called by the validator after verifying a miner's attestation report.
        """
        self._cache[miner_uid] = (result, time.time())
        logger.info(
            "[TEE] miner_uid=%d tee_type=%s valid=%s chain_verified=%s measurement=%s",
            miner_uid, result.tee_type, result.valid, result.chain_verified,
            result.measurement[:16] + "…" if result.measurement else "none"
        )

    def clear_cache(self, miner_uid: Optional[int] = None) -> None:
        """Clear attestation cache. Pass miner_uid to clear one entry, or None to clear all."""
        if miner_uid is not None:
            self._cache.pop(miner_uid, None)
        else:
            self._cache.clear()

    def is_tee_verified(self, miner_uid: int) -> bool:
        """
        Quick check: is this miner currently verified as running in a TEE?

        Returns True only if cached result is valid AND cache is not expired.
        """
        status = self.get_attestation_status(miner_uid)
        return bool(
            status["valid"]
            and not status.get("cache_expired", True)
        )


# ─── Internals ───────────────────────────────────────────────────────────────

def _parse_snp_report(data: bytes) -> SNPReportFields:
    """
    Parse an AMD SEV-SNP attestation report into structured fields.

    Raises:
        struct.error: If data is too short to parse.
        ValueError: If parsed values are out of expected range.
    """
    fields = SNPReportFields()

    # version (u32) at offset 0
    fields.version = struct.unpack_from("<I", data, 0)[0]
    # guest_svn (u32) at offset 4
    fields.guest_svn = struct.unpack_from("<I", data, 4)[0]
    # policy (u64) at offset 8
    fields.policy = struct.unpack_from("<Q", data, 8)[0]
    # VMPL (u32) at offset 48
    if len(data) >= 52:
        fields.vmpl = struct.unpack_from("<I", data, 48)[0]
    # signature algorithm (u32) at offset 52
    if len(data) >= 56:
        fields.signature_algo = struct.unpack_from("<I", data, 52)[0]

    # report_data (64 bytes) at offset 80
    if len(data) >= AMD_SNP_REPORT_DATA_OFFSET + 64:
        fields.report_data = data[AMD_SNP_REPORT_DATA_OFFSET:AMD_SNP_REPORT_DATA_OFFSET + 64]

    # measurement (48 bytes) at offset 144
    if len(data) >= AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE:
        fields.measurement = data[AMD_SNP_MEASUREMENT_OFFSET:AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE]

    # host_data (32 bytes) at offset 192
    if len(data) >= 224:
        fields.host_data = data[192:224]

    # reported_tcb (u64) at offset 384 (only if full report present)
    if len(data) >= 392:
        fields.reported_tcb = struct.unpack_from("<Q", data, 384)[0]

    # Signature presence (non-zero check at offset 1056)
    if len(data) >= AMD_SNP_SIGNATURE_OFFSET + AMD_SNP_SIGNATURE_SIZE:
        sig_bytes = data[AMD_SNP_SIGNATURE_OFFSET:AMD_SNP_SIGNATURE_OFFSET + AMD_SNP_SIGNATURE_SIZE]
        fields.has_signature = any(b != 0 for b in sig_bytes)

    return fields


def _verify_amd_signature_stub(
    report: bytes, parsed: SNPReportFields
) -> Tuple[bool, str]:
    """
    Stub for AMD VCEK signature verification.

    Full implementation requires:
    1. Extract VCEK certificate from report (or fetch from AMD KDS API)
    2. Build cert chain: VCEK → ASK → ARK (AMD root of trust)
    3. Verify ECDSA-P384 signature over first 672 bytes of report
       using the VCEK public key
    4. Validate cert chain expiry and CRL

    AMD KDS endpoint:
        https://kdsintf.amd.com/vcek/v1/{product_name}/{hwid}
        ?blSPL={bl_spl}&teeSPL={tee_spl}&snpSPL={snp_spl}&ucodeSPL={ucode_spl}

    Hardware IDs and TCB version fields are in the report body.

    Returns:
        (chain_verified: bool, error_message: str)
    """
    # In the MVP, we return chain_verified=False with an informational note.
    # When cryptography library is available and network access is enabled,
    # this should be replaced with full VCEK verification.
    if parsed.has_signature:
        logger.debug(
            "[TEE] AMD SNP signature present but VCEK chain verification not yet "
            "implemented (MVP). chain_verified=False. "
            "Production validators should implement AMD KDS VCEK fetch + ECDSA-P384 verify."
        )
        return False, "vcek_chain_not_verified_mvp"
    else:
        logger.debug("[TEE] AMD SNP report has no signature bytes (test/mock report)")
        return False, "no_signature_in_report"


def generate_mock_snp_report(
    measurement: Optional[bytes] = None,
    report_data: Optional[bytes] = None,
    version: int = 2,
) -> bytes:
    """
    Generate a mock AMD SEV-SNP attestation report for testing.

    The mock report has the correct structure and version but no real
    VCEK signature. It is only for unit tests and development.

    Args:
        measurement: 48-byte measurement value. Random if not provided.
        report_data: 64-byte report_data field. Zeros if not provided.
        version: SNP report version (default 2).

    Returns:
        bytes: AMD_SNP_REPORT_SIZE (1184) bytes of mock report data.
    """
    import os as _os
    report = bytearray(AMD_SNP_REPORT_SIZE)

    # Version at offset 0
    struct.pack_into("<I", report, 0, version)
    # guest_svn at offset 4
    struct.pack_into("<I", report, 4, 1)
    # policy at offset 8 (0x30000 = standard SNP policy: SMT allowed, debug off)
    struct.pack_into("<Q", report, 8, 0x30000)
    # VMPL at offset 48
    struct.pack_into("<I", report, 48, 0)
    # signature_algo at offset 52 (1 = ECDSA-P384-SHA384)
    struct.pack_into("<I", report, 52, 1)

    # report_data at offset 80 (64 bytes)
    rd = report_data if report_data else bytes(64)
    report[AMD_SNP_REPORT_DATA_OFFSET:AMD_SNP_REPORT_DATA_OFFSET + 64] = rd[:64]

    # measurement at offset 144 (48 bytes)
    m = measurement if measurement else _os.urandom(AMD_SNP_MEASUREMENT_SIZE)
    report[AMD_SNP_MEASUREMENT_OFFSET:AMD_SNP_MEASUREMENT_OFFSET + AMD_SNP_MEASUREMENT_SIZE] = m[:AMD_SNP_MEASUREMENT_SIZE]

    return bytes(report)


def generate_mock_nvidia_cc_report(measurement: Optional[bytes] = None) -> bytes:
    """
    Generate a mock NVIDIA CC attestation report for testing.

    Args:
        measurement: 48-byte measurement. Random if not provided.

    Returns:
        bytes: Minimal mock NVIDIA CC report with correct magic.
    """
    import os as _os
    header = NVIDIA_CC_MAGIC  # 4 bytes magic
    m = measurement if measurement else _os.urandom(48)
    padding = bytes(12)  # pad to 64 bytes
    return header + m[:48] + padding
