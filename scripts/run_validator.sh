#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Project Nobi — Run Validator via PM2
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Ensure required env vars
if [ -z "${CHUTES_API_KEY:-}" ]; then
    echo "⚠️  CHUTES_API_KEY not set. Validator will use heuristic scoring."
fi

if [ -z "${WALLET_PASSWORD:-}" ]; then
    echo "⚠️  WALLET_PASSWORD not set. Coldkey must be unencrypted or password set elsewhere."
fi

# Stop existing instance if running
pm2 delete nobi-validator 2>/dev/null || true

# Start validator with PM2 (env vars are inherited from current shell)
cd "$PROJECT_DIR"
CHUTES_API_KEY="${CHUTES_API_KEY:-}" \
WALLET_PASSWORD="${WALLET_PASSWORD:-}" \
pm2 start python3 \
    --name nobi-validator \
    --interpreter none \
    -- -m validator.main

echo "✅ Nobi Validator started via PM2"
echo "   View logs: pm2 logs nobi-validator"
echo "   Status:    pm2 status nobi-validator"
echo "   Stop:      pm2 stop nobi-validator"
