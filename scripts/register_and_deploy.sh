#!/bin/bash
# Project Nobi — Register & Deploy (Testnet SN272)
# Run this once we have testnet TAO funded

set -e

NETUID=272
NETWORK="test"
WALLET="${WALLET_NAME:-my_wallet}"
OPENROUTER_KEY="${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY environment variable}"
LOG_DIR="/var/log/nobi"
REPO="/root/project-nobi"

mkdir -p $LOG_DIR
cd $REPO

echo "=============================================="
echo "  Project Nobi — Testnet Deployment SN$NETUID"
echo "=============================================="

# 1. Register miner
echo ""
echo "[1/4] Registering nobi-miner on SN$NETUID..."
python3 -c "
import bittensor as bt
sub = bt.Subtensor(network='$NETWORK')
w = bt.Wallet(name='$WALLET', hotkey='nobi-miner')
print(f'Miner hotkey: {w.hotkey.ss58_address}')
if sub.is_hotkey_registered(netuid=$NETUID, hotkey_ss58=w.hotkey.ss58_address):
    print('Already registered!')
else:
    result = sub.burned_register(wallet=w, netuid=$NETUID)
    print(f'Result: {result.success} — {result.message}')
"

# 2. Register validator
echo ""
echo "[2/4] Registering nobi-validator on SN$NETUID..."
python3 -c "
import bittensor as bt
sub = bt.Subtensor(network='$NETWORK')
w = bt.Wallet(name='$WALLET', hotkey='nobi-validator')
print(f'Validator hotkey: {w.hotkey.ss58_address}')
if sub.is_hotkey_registered(netuid=$NETUID, hotkey_ss58=w.hotkey.ss58_address):
    print('Already registered!')
else:
    result = sub.burned_register(wallet=w, netuid=$NETUID)
    print(f'Result: {result.success} — {result.message}')
"

# 3. Launch miner via PM2
echo ""
echo "[3/4] Starting miner (PM2)..."
pm2 delete nobi-miner 2>/dev/null || true
pm2 start python3 --name nobi-miner -- \
    $REPO/neurons/miner.py \
    --wallet.name $WALLET \
    --wallet.hotkey nobi-miner \
    --subtensor.network $NETWORK \
    --netuid $NETUID \
    --axon.port 8091 \
    --neuron.openrouter_api_key $OPENROUTER_KEY \
    --neuron.model anthropic/claude-3.5-haiku \
    --blacklist.allow_non_registered \
    --logging.debug

# 4. Launch validator via PM2
echo ""
echo "[4/4] Starting validator (PM2)..."
pm2 delete nobi-validator 2>/dev/null || true
pm2 start python3 --name nobi-validator -- \
    $REPO/neurons/validator.py \
    --wallet.name $WALLET \
    --wallet.hotkey nobi-validator \
    --subtensor.network $NETWORK \
    --netuid $NETUID \
    --neuron.openrouter_api_key $OPENROUTER_KEY \
    --neuron.sample_size 5 \
    --neuron.axon_off \
    --logging.debug

pm2 save

echo ""
echo "=============================================="
echo "  ✅ Deployment complete!"
echo "  Monitor: pm2 logs nobi-miner"
echo "           pm2 logs nobi-validator"
echo "  Metagraph: python3 -c \"import bittensor as bt; sub=bt.Subtensor(network='test'); mg=sub.metagraph($NETUID); print(mg)\""
echo "=============================================="
