#!/bin/bash
# Project Nobi — Run Validator via PM2

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "${CHUTES_API_KEY:-}" ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "⚠️  No LLM API key set. Set CHUTES_API_KEY or OPENROUTER_API_KEY for scoring."
fi

WALLET_NAME="${WALLET_NAME:-my_wallet}"
WALLET_HOTKEY="${WALLET_HOTKEY:-nobi-validator}"
NETUID="${NETUID:-267}"
NETWORK="${NETWORK:-test}"

pm2 delete nobi-validator 2>/dev/null || true

cd "$PROJECT_DIR"

pm2 start python3 --name nobi-validator -- \
    "$PROJECT_DIR/neurons/validator.py" \
    --wallet.name "$WALLET_NAME" \
    --wallet.hotkey "$WALLET_HOTKEY" \
    --subtensor.network "$NETWORK" \
    --netuid "$NETUID" \
    --neuron.sample_size 10 \
    --neuron.axon_off \
    --logging.debug

pm2 save

echo "✅ Nobi Validator started via PM2"
echo "   View logs: pm2 logs nobi-validator"
echo "   Stop:      pm2 stop nobi-validator"
