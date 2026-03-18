# Validating on Project Nobi

> Validators ensure companion quality by scoring miners. Stake TAO to earn dividends.

## Why Validate?

As a validator, you:
- Earn **dividends** proportional to your stake
- Help **improve companion quality** across the network
- Shape the **future of personal AI** — your weights determine who earns

## Requirements

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| CPU | 2 cores | Scoring uses LLM API, not local compute |
| RAM | 4 GB | |
| Disk | 5 GB | Logs + state |
| Stake | Top 64 by stake on subnet | Check current threshold with metagraph |
| LLM API Key | Required | For scoring miner responses (Chutes or OpenRouter) |
| Python | 3.10+ | |

## Step 1: Install

```bash
# Clone
git clone https://github.com/ProjectNobi/project-nobi.git
cd project-nobi

# (Recommended) Virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -e .
pip install bittensor-cli
```

**Note:** If `btcli` shows bittorrent commands, use `python3 -m bittensor_cli.cli` instead.

## Step 2: Create Wallet & Register

```bash
# Create wallet
btcli wallet new-coldkey --wallet.name my_validator_wallet
btcli wallet new-hotkey --wallet.name my_validator_wallet --wallet.hotkey nobi-validator

# Register on testnet
btcli subnets register \
    --netuid 272 \
    --wallet.name my_validator_wallet \
    --wallet.hotkey nobi-validator \
    --subtensor.network test
```

## Step 3: Stake TAO

You need enough stake to be in the **top 64 validators** by stake on the subnet. On testnet, even a small amount usually works since there are few validators.

```bash
# Stake TAO on your validator
btcli stake add \
    --wallet.name my_validator_wallet \
    --wallet.hotkey nobi-validator \
    --netuid 272 \
    --subtensor.network test

# Check if you have a validator permit
python -c "
import bittensor as bt
sub = bt.Subtensor(network='test')
mg = sub.metagraph(272)
w = bt.Wallet(name='my_validator_wallet', hotkey='nobi-validator')
hk = w.hotkey.ss58_address
if hk in mg.hotkeys:
    uid = mg.hotkeys.index(hk)
    print(f'UID: {uid}')
    print(f'Stake: {float(mg.S[uid]):.2f}')
    print(f'Validator permit: {bool(mg.validator_permit[uid])}')
else:
    print('Not registered yet')
"
```

## Step 4: Get an LLM API Key for Scoring

The validator needs an LLM to judge miner response quality. Choose one:

- **Chutes.ai** (~$0.0001/query) — set `CHUTES_API_KEY`
- **OpenRouter** (~$0.001/query, used as fallback) — set `OPENROUTER_API_KEY`

Both can be set — the validator tries Chutes first, falls back to OpenRouter.

If neither is available, a heuristic scorer is used (capped at 0.5 — less accurate).

## Step 5: Run

```bash
# Set API keys
export CHUTES_API_KEY="your-chutes-key"
export OPENROUTER_API_KEY="your-openrouter-key"  # Optional fallback
export WALLET_PASSWORD="your-password"  # If coldkey is encrypted

# Run directly
python neurons/validator.py \
    --wallet.name my_validator_wallet \
    --wallet.hotkey nobi-validator \
    --subtensor.network test \
    --netuid 272 \
    --neuron.epoch_length 100 \
    --neuron.sample_size 10 \
    --neuron.axon_off \
    --logging.debug
```

### With PM2 (Recommended)

```bash
CHUTES_API_KEY="your-key" \
OPENROUTER_API_KEY="your-backup-key" \
WALLET_PASSWORD="your-password" \
pm2 start python3 --name nobi-validator -- \
    neurons/validator.py \
    --wallet.name my_validator_wallet \
    --wallet.hotkey nobi-validator \
    --subtensor.network test \
    --netuid 272 \
    --neuron.epoch_length 100 \
    --neuron.sample_size 10 \
    --neuron.axon_off \
    --logging.debug

pm2 save
```

## Step 6: Verify It's Working

```bash
# Watch validator logs
pm2 logs nobi-validator --lines 20
```

**Expected log output:**
```
INFO | step(5) block(6710539)
INFO | [Single-turn] Querying 3 miners: 'I'm feeling a bit curious lately...'
INFO | Scored responses: [0.87 0.72 0.45]
INFO | [Multi-turn] Testing: Name (Kai) + career (teacher) + hobby (photography)
INFO | [Multi-turn] Setup 1: 3/3 responded
INFO | [Multi-turn] Setup 2: 3/3 responded
INFO | [Multi-turn] Scored: [0.81 0.65 0.38] (keywords: ['kai', 'teacher', 'photography'])
INFO | set_weights on chain successfully!
```

## What the Validator Does

Every ~20 seconds, the validator:

1. **Selects random miners** to query (sample_size per round)
2. **Generates a unique test** — either single-turn (40%) or multi-turn memory test (60%)
3. **Queries miners** and measures response latency
4. **Scores responses** using LLM-as-judge (quality + personality) + keyword memory check + latency

### Scoring Breakdown

**Single-turn (40% of rounds):**
- 90% → Quality + Personality (LLM judge)
- 10% → Reliability (response latency)

**Multi-turn (60% of rounds):**
- 60% → Quality + Personality (LLM judge)
- 30% → Memory recall (did the miner remember user details?)
- 10% → Reliability (response latency)

5. **Updates moving averages** (α=0.1 — scores smooth over time)
6. **Commits weights on-chain** every epoch (~100 blocks = ~20 minutes)

**All queries are dynamically generated** — different every round. You don't need to configure or seed the test bank.

## Configuration Options

| Flag | Default | Description |
|------|---------|-------------|
| `--neuron.epoch_length` | 100 | Blocks between weight updates |
| `--neuron.sample_size` | 10 | Miners to query per round |
| `--neuron.timeout` | 30 | Seconds to wait for miner response |
| `--neuron.axon_off` | false | Set true — validators don't need to serve an axon |
| `--neuron.moving_average_alpha` | 0.1 | Score smoothing (lower = more stable) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No miners available` | No miners are serving axons — wait for miners to come online |
| `set_weights failed` | Check stake, validator permit, and `commit_reveal_weights_enabled` |
| `LLM judge failed` | Both CHUTES_API_KEY and OPENROUTER_API_KEY missing or invalid |
| `Wrong password` | Set `WALLET_PASSWORD` env var |
| `Not registered` | Register with `btcli subnets register` |
| `btcli` shows bittorrent | Use `python3 -m bittensor_cli.cli` instead |
| Scores all 0.0 | Miners returning empty responses — check if miners are actually running |

## Monitoring

```bash
# Check metagraph — see all miners and their scores
python -c "
import bittensor as bt
sub = bt.Subtensor(network='test')
mg = sub.metagraph(272)
print(f'Neurons: {mg.n}')
for uid in range(mg.n):
    s = float(mg.S[uid])
    inc = float(mg.I[uid])
    active = '✅' if mg.active[uid] else '❌'
    vp = '✅' if mg.validator_permit[uid] else '  '
    print(f'  UID {uid}: stake={s:>10.0f}  inc={inc:.6f}  active={active}  vp={vp}')
"
```

## Questions?

- **GitHub:** [project-nobi](https://github.com/ProjectNobi/project-nobi)
- **Discord:** Bittensor testnet channel
- **Full scoring details:** [INCENTIVE_MECHANISM.md](INCENTIVE_MECHANISM.md)
- **Issues:** [Open a GitHub issue](https://github.com/ProjectNobi/project-nobi/issues)

---
*By validating, you're ensuring every human gets a quality Nori. Thank you. 🤖*
