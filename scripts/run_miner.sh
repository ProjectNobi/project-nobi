#!/bin/bash
# Project Nobi — Run Miner via PM2

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -z "${CHUTES_API_KEY:-}" ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
    echo "⚠️  No LLM API key set. Set CHUTES_API_KEY or OPENROUTER_API_KEY."
    echo "   Get a key from chutes.ai or openrouter.ai"
fi

WALLET_NAME="${WALLET_NAME:-my_wallet}"
WALLET_HOTKEY="${WALLET_HOTKEY:-nobi-miner}"
NETUID="${NETUID:-267}"
NETWORK="${NETWORK:-test}"
AXON_PORT="${AXON_PORT:-8091}"
EXTERNAL_IP="${EXTERNAL_IP:-}"

pm2 delete nobi-miner 2>/dev/null || true

cd "$PROJECT_DIR"

ARGS=(
    "$PROJECT_DIR/neurons/miner.py"
    --wallet.name "$WALLET_NAME"
    --wallet.hotkey "$WALLET_HOTKEY"
    --subtensor.network "$NETWORK"
    --netuid "$NETUID"
    --axon.port "$AXON_PORT"
    --blacklist.allow_non_registered
    --logging.debug
)

if [ -n "$EXTERNAL_IP" ]; then
    ARGS+=(--axon.external_ip "$EXTERNAL_IP" --axon.external_port "$AXON_PORT")
fi

pm2 start python3 --name nobi-miner -- "${ARGS[@]}"
pm2 save

echo "✅ Nobi Miner started via PM2"
echo "   View logs: pm2 logs nobi-miner"
echo "   Stop:      pm2 stop nobi-miner"
