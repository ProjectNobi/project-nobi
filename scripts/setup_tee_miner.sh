#!/usr/bin/env bash
# =============================================================================
# Project Nobi — TEE Miner Setup Script
# =============================================================================
# Detects AMD SEV-SNP or NVIDIA Confidential Computing hardware,
# configures your miner to advertise TEE capability, and verifies
# attestation works end-to-end.
#
# Usage:
#   bash scripts/setup_tee_miner.sh
#
# What it does:
#   1. Detect AMD SEV-SNP capability
#   2. Detect NVIDIA CC capability
#   3. Generate a TEE attestation report (real hardware) or mock (dev mode)
#   4. Configure miner environment variables
#   5. Verify everything works via Python attestation check
#
# Supported environments:
#   - Bare metal AMD EPYC Milan/Genoa with SEV-SNP enabled in BIOS
#   - Azure DCasv5 / AWS m6a instances (SEV-SNP pass-through VMs)
#   - NVIDIA H100/A100 with CC firmware
#   - Development mode (no hardware — uses mock attestation for testing)
#
# After running this script, add the following to your miner startup:
#   source ~/.nobi/tee_env.sh
# =============================================================================

set -euo pipefail

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── Config ───────────────────────────────────────────────────────────────────
NOBI_DIR="${HOME}/.nobi"
TEE_ENV_FILE="${NOBI_DIR}/tee_env.sh"
TEE_REPORT_FILE="${NOBI_DIR}/attestation_report.bin"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "${NOBI_DIR}"

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Project Nobi — TEE Miner Setup                    ║"
echo "║  Earn a +5–10% scoring bonus by running in a TEE enclave    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ─── Step 1: Detect AMD SEV-SNP ───────────────────────────────────────────────
log_info "Step 1/5: Detecting AMD SEV-SNP support..."

AMD_SEV_SNP=false
SEV_GUEST_DEV="/dev/sev-guest"

# Method 1: dmesg kernel log
if dmesg 2>/dev/null | grep -qi "sev-snp"; then
    log_ok "AMD SEV-SNP found in kernel log (dmesg)"
    AMD_SEV_SNP=true
fi

# Method 2: /dev/sev-guest device
if [[ -c "${SEV_GUEST_DEV}" ]]; then
    log_ok "/dev/sev-guest present — SEV-SNP device available"
    AMD_SEV_SNP=true
elif [[ "${AMD_SEV_SNP}" == "false" ]]; then
    log_warn "/dev/sev-guest not found"
fi

# Method 3: CPU model check
CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
if echo "${CPU_MODEL}" | grep -qi "EPYC"; then
    log_info "AMD EPYC CPU detected: ${CPU_MODEL}"
    log_info "  → Check BIOS: AMD EPYC Milan/Genoa supports SEV-SNP (enable in BIOS → CBS → CPU Common → SEV-SNP)"
fi

# Method 4: sevctl tool
if command -v sevctl &>/dev/null; then
    log_info "sevctl tool found — testing attestation..."
    if sevctl report "${TEE_REPORT_FILE}" 2>/dev/null; then
        REPORT_SIZE=$(wc -c < "${TEE_REPORT_FILE}")
        if [[ "${REPORT_SIZE}" -eq 1184 ]]; then
            log_ok "AMD SEV-SNP attestation report generated (${REPORT_SIZE} bytes)"
            AMD_SEV_SNP=true
        else
            log_warn "sevctl report generated but unexpected size: ${REPORT_SIZE} (expected 1184)"
        fi
    else
        log_warn "sevctl report failed — SEV-SNP may not be enabled in firmware"
    fi
fi

# ─── Step 2: Detect NVIDIA CC ─────────────────────────────────────────────────
log_info "Step 2/5: Detecting NVIDIA Confidential Computing support..."

NVIDIA_CC=false

if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "")
    if [[ -n "${GPU_NAME}" ]]; then
        log_info "NVIDIA GPU detected: ${GPU_NAME}"

        # Check CC mode
        CC_MODE=$(nvidia-smi --query-gpu=cc_mode.current --format=csv,noheader 2>/dev/null | head -1 || echo "N/A")
        if [[ "${CC_MODE}" != "N/A" && "${CC_MODE}" != "Off" && "${CC_MODE}" != "0" ]]; then
            log_ok "NVIDIA CC mode enabled: ${CC_MODE}"
            NVIDIA_CC=true
        else
            log_warn "NVIDIA GPU found but CC mode is: ${CC_MODE}"
            log_warn "  → To enable CC mode: sudo nvidia-smi --conf-compute-mode=CC_MODE_DEVTOOLS"
            log_warn "  → Requires H100 or A100, firmware 550+ and reboot"
        fi
    fi
else
    log_info "nvidia-smi not found — no NVIDIA GPU detected"
fi

# ─── Step 3: Determine TEE type ───────────────────────────────────────────────
log_info "Step 3/5: Determining TEE configuration..."

TEE_TYPE="none"
DEV_MODE=false

if [[ "${AMD_SEV_SNP}" == "true" ]]; then
    TEE_TYPE="amd-sev-snp"
    log_ok "Using AMD SEV-SNP as TEE type"
elif [[ "${NVIDIA_CC}" == "true" ]]; then
    TEE_TYPE="nvidia-cc"
    log_ok "Using NVIDIA CC as TEE type"
else
    log_warn "No TEE hardware detected."
    echo ""
    echo "Options:"
    echo "  1) Continue in development mode (mock attestation — no bonus, for testing only)"
    echo "  2) Exit and set up TEE hardware first"
    echo ""
    read -r -p "Continue in development mode? [y/N]: " CHOICE
    if [[ "${CHOICE}" =~ ^[Yy]$ ]]; then
        DEV_MODE=true
        TEE_TYPE="none"
        log_warn "Development mode — generating mock attestation for testing only"
    else
        log_info "Exiting. See docs/MINING_GUIDE.md for TEE hardware setup instructions."
        exit 0
    fi
fi

# ─── Step 4: Generate attestation report ──────────────────────────────────────
log_info "Step 4/5: Generating TEE attestation report..."

if [[ "${AMD_SEV_SNP}" == "true" && -c "${SEV_GUEST_DEV}" ]]; then
    # Real hardware: use sevctl if available, else raw ioctl via Python
    if command -v sevctl &>/dev/null && [[ ! -f "${TEE_REPORT_FILE}" ]]; then
        log_info "Generating AMD SNP attestation report via sevctl..."
        if sevctl report "${TEE_REPORT_FILE}"; then
            log_ok "Attestation report saved to ${TEE_REPORT_FILE}"
        else
            log_warn "sevctl report failed — will use Python fallback"
        fi
    fi

    # Python fallback: read from /dev/sev-guest directly
    if [[ ! -f "${TEE_REPORT_FILE}" ]]; then
        log_info "Generating attestation via /dev/sev-guest ioctl..."
        python3 - <<'EOF'
import os, struct, fcntl, base64, sys

SEV_GUEST_IOC_GET_REPORT = 0xc0185300  # _IOWR('S', 0x0, struct snp_report_req)
REPORT_FILE = os.path.expanduser("~/.nobi/attestation_report.bin")

# struct snp_report_req { uint8_t user_data[64]; uint32_t vmpl; uint8_t reserved[28]; }
req_data = struct.pack("64sI28s", bytes(64), 0, bytes(28))

try:
    with open("/dev/sev-guest", "rb") as f:
        buf = bytearray(2048)  # response buffer
        fcntl.ioctl(f, SEV_GUEST_IOC_GET_REPORT, buf)
        # Report is at offset 32 in response (skips ioctl header)
        report = bytes(buf[32:32+1184])
        with open(REPORT_FILE, "wb") as out:
            out.write(report)
        print(f"[OK] Report written: {len(report)} bytes")
except PermissionError:
    print("[WARN] Permission denied on /dev/sev-guest — try: sudo chmod 660 /dev/sev-guest")
    sys.exit(1)
except Exception as e:
    print(f"[WARN] ioctl failed: {e} — SEV-SNP may not be fully enabled")
    sys.exit(1)
EOF
    fi
elif [[ "${NVIDIA_CC}" == "true" ]]; then
    log_info "NVIDIA CC attestation generation (requires nv-attestation-sdk)"
    if python3 -c "import nv_attestation_sdk" 2>/dev/null; then
        python3 - <<'EOF'
import nv_attestation_sdk, os, base64

REPORT_FILE = os.path.expanduser("~/.nobi/attestation_report.bin")
try:
    client = nv_attestation_sdk.Attestation()
    report = client.get_attestation_report()
    with open(REPORT_FILE, "wb") as f:
        f.write(report)
    print(f"[OK] NVIDIA CC report written: {len(report)} bytes")
except Exception as e:
    print(f"[WARN] nv_attestation_sdk failed: {e}")
EOF
    else
        log_warn "nv-attestation-sdk not installed — install with: pip install nv-attestation-sdk"
        log_warn "Continuing without attestation report"
    fi
elif [[ "${DEV_MODE}" == "true" ]]; then
    log_info "Generating mock attestation report for development..."
    python3 - <<EOF
import sys
sys.path.insert(0, "${REPO_DIR}")
from nobi.privacy.tee_attestation import generate_mock_snp_report
import os, base64

REPORT_FILE = os.path.expanduser("~/.nobi/attestation_report.bin")
report = generate_mock_snp_report()
with open(REPORT_FILE, "wb") as f:
    f.write(report)
print(f"[OK] Mock AMD SNP report written: {len(report)} bytes (dev mode only)")
EOF
fi

# ─── Step 5: Write environment config ─────────────────────────────────────────
log_info "Step 5/5: Writing TEE environment configuration..."

ATTESTATION_B64=""
if [[ -f "${TEE_REPORT_FILE}" ]]; then
    ATTESTATION_B64=$(base64 -w 0 "${TEE_REPORT_FILE}")
    log_ok "Attestation report encoded (${#ATTESTATION_B64} base64 chars)"
fi

cat > "${TEE_ENV_FILE}" << ENVEOF
# Project Nobi — TEE Miner Environment
# Generated by scripts/setup_tee_miner.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
# Source this file before starting your miner: source ~/.nobi/tee_env.sh

# TEE hardware type: amd-sev-snp | nvidia-cc | none
export NOBI_TEE_TYPE="${TEE_TYPE}"

# Base64-encoded attestation report (rotated each startup for freshness)
# In production, this should be regenerated on each miner start.
export NOBI_TEE_ATTESTATION="${ATTESTATION_B64}"

# Development mode flag (do not set in production)
export NOBI_TEE_DEV_MODE="${DEV_MODE}"
ENVEOF

log_ok "TEE environment written to ${TEE_ENV_FILE}"

# ─── Verification ─────────────────────────────────────────────────────────────
echo ""
log_info "Running attestation verification check..."

python3 - <<EOF
import sys, os, base64
sys.path.insert(0, "${REPO_DIR}")
from nobi.privacy.tee_attestation import TEEAttestationVerifier

report_file = os.path.expanduser("~/.nobi/attestation_report.bin")
tee_type = "${TEE_TYPE}"

if not os.path.exists(report_file):
    print("[SKIP] No attestation report file found — skipping verification")
    sys.exit(0)

with open(report_file, "rb") as f:
    report_bytes = f.read()

b64 = base64.b64encode(report_bytes).decode()
verifier = TEEAttestationVerifier()

if tee_type == "none":
    print("[DEV] Dev mode — testing mock report parsing")
    result = verifier.verify_amd_sev_snp(report_bytes)
else:
    result = verifier.verify_from_base64(tee_type, b64)

print(f"  TEE type:       {result.tee_type}")
print(f"  Valid:          {result.valid}")
print(f"  Measurement:    {result.measurement[:32]}..." if result.measurement else "  Measurement:    (none)")
print(f"  Chain verified: {result.chain_verified}")
print(f"  Error:          {result.error or 'none'}")

if result.valid:
    print("")
    print("[OK] Attestation report is valid — TEE bonus will be applied by validators")
else:
    print("")
    print(f"[WARN] Attestation check failed: {result.error}")
    print("  The miner will still work but will not receive a TEE scoring bonus.")
EOF

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     Setup Complete                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if [[ "${TEE_TYPE}" != "none" ]]; then
    echo -e "  TEE type:   ${GREEN}${TEE_TYPE}${NC}"
    echo -e "  Bonus:      ${GREEN}+5% scoring bonus (structural verification)${NC}"
    echo -e "              ${GREEN}+10% when full chain verification lands${NC}"
else
    echo -e "  TEE type:   ${YELLOW}none (development mode)${NC}"
    echo -e "  Bonus:      ${YELLOW}none — hardware TEE required for scoring bonus${NC}"
fi

echo ""
echo "  Next steps:"
echo "  1. Add this to your miner startup script:"
echo "       source ~/.nobi/tee_env.sh"
echo ""
echo "  2. Restart your miner:"
echo "       pm2 restart YOUR_MINER_NAME"
echo ""
echo "  3. Verify TEE fields in logs:"
echo "       pm2 logs YOUR_MINER_NAME | grep -i tee"
echo ""
echo "  4. For AMD SEV-SNP fresh attestation on each start, add to run_miner.sh:"
echo "       sevctl report ~/.nobi/attestation_report.bin"
echo "       source ~/.nobi/tee_env.sh"
echo ""

if [[ "${AMD_SEV_SNP}" == "false" && "${NVIDIA_CC}" == "false" ]]; then
    echo "  ──────────────────────────────────────────────────"
    echo "  No TEE hardware found. See docs/MINING_GUIDE.md"
    echo "  for hardware options and expected cost impact."
    echo "  ──────────────────────────────────────────────────"
fi
