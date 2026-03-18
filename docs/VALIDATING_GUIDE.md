# Validating on Project Nobi

> Validators ensure quality by scoring miners. Stake TAO to earn dividends.

## Why Validate?

As a validator, you:
- Earn **dividends** proportional to your stake
- Help **improve companion quality** across the network
- Shape the **future of personal AI** — your weights determine who earns

## Requirements

| Requirement | Minimum |
|-------------|---------|
| Stake | Enough to get a validator permit (top 64 by stake) |
| CPU | 2 cores |
| RAM | 4 GB |
| LLM API Key | For scoring responses (Chutes or OpenRouter) |

## Quick Start

```bash
# Clone
git clone https://github.com/travellingsoldier85/project-nobi.git
cd project-nobi && pip install -e . && pip install bittensor-cli

# Create wallet
btcli wallet new-coldkey --wallet.name my_validator_wallet
btcli wallet new-hotkey --wallet.name my_validator_wallet --wallet.hotkey nobi-validator

# Register
btcli subnets register --netuid 267 --wallet.name my_validator_wallet --wallet.hotkey nobi-validator --subtensor.network test

# Stake (need enough for validator permit)
btcli stake add --wallet.name my_validator_wallet --wallet.hotkey nobi-validator --netuid 267 --subtensor.network test

# Run
export CHUTES_API_KEY="your-key"  # For scoring
python neurons/validator.py \
    --wallet.name my_validator_wallet \
    --wallet.hotkey nobi-validator \
    --subtensor.network test \
    --netuid 267 \
    --neuron.epoch_length 100 \
    --neuron.sample_size 10 \
    --neuron.axon_off \
    --logging.debug
```

## What the Validator Does

Every ~20 seconds, the validator:
1. Picks a random subset of miners
2. Sends either a single-turn query or a multi-turn memory test
3. Scores responses using LLM-as-judge + memory keyword matching
4. Updates moving average scores
5. Commits weights on-chain every epoch

**You don't need to configure anything** — the scoring logic is built in.

## Monitoring

```bash
# Watch validator activity
pm2 logs nobi-validator

# Check metagraph
python -c "
import bittensor as bt
sub = bt.Subtensor(network='test')
mg = sub.metagraph(267)
for uid in range(mg.n):
    print(f'UID {uid}: inc={float(mg.I[uid]):.6f} stake={float(mg.S[uid]):.0f}')
"
```

---
*By validating, you're ensuring every human gets a quality Dora. Thank you. 🤖*
