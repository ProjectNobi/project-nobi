# Mining on Project Nobi — Quick Start Guide

> Estimated setup time: 10 minutes. No GPU required.

## What You're Building

You're running a **personal AI companion** (Dora) that talks to users, remembers them, and helps them with daily life. The better your companion, the more you earn.

## Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Disk | 10 GB | 20+ GB |
| GPU | None | None |
| Network | Stable internet | Low latency |
| Python | 3.10+ | 3.12 |
| OS | Ubuntu 20.04+ | Ubuntu 22.04+ |

**No GPU needed!** The miner uses cloud LLM APIs for inference.

## Step 1: Get an LLM API Key

You need an API key for your companion's brain. Choose one:

### Option A: Chutes.ai (Low cost, ~$0.0001/query)
1. Go to [chutes.ai](https://chutes.ai)
2. Create account
3. Get API key from dashboard
4. Model: `deepseek-ai/DeepSeek-V3-0324`

### Option B: OpenRouter (~$0.001/query)
1. Go to [openrouter.ai](https://openrouter.ai)
2. Create account, add credits
3. Get API key
4. Model: `anthropic/claude-3.5-haiku` (recommended)

### Option C: Local Model (Advanced)
Run your own model with vLLM/Ollama and point the miner at `localhost`.

## Step 2: Install

```bash
# Clone the repo
git clone https://github.com/travellingsoldier85/project-nobi.git
cd project-nobi

# Install dependencies
pip install -e .
pip install openai  # For LLM API access
pip install bittensor-cli  # For wallet and registration commands

# Verify
python -c "import nobi; print('✅ Installed')"
```

## Step 3: Create Wallet & Register

```bash
# Create wallet (if you don't have one)
btcli wallet new-coldkey --wallet.name my_wallet
btcli wallet new-hotkey --wallet.name my_wallet --wallet.hotkey nobi-miner

# Register on testnet (costs minimal tTAO)
btcli subnets register --netuid 267 --wallet.name my_wallet --wallet.hotkey nobi-miner --subtensor.network test
```

## Step 4: Configure & Run

```bash
# Set environment variables
export CHUTES_API_KEY="your-chutes-key-here"
# OR
export OPENROUTER_API_KEY="your-openrouter-key-here"

# Run the miner
python neurons/miner.py \
    --wallet.name my_wallet \
    --wallet.hotkey nobi-miner \
    --subtensor.network test \
    --netuid 267 \
    --axon.port 8091 \
    --axon.external_ip YOUR_PUBLIC_IP \
    --axon.external_port 8091 \
    --blacklist.allow_non_registered \
    --logging.debug
```

### With PM2 (Recommended — auto-restart)

```bash
CHUTES_API_KEY="your-key" pm2 start python3 --name nobi-miner -- \
    neurons/miner.py \
    --wallet.name my_wallet \
    --wallet.hotkey nobi-miner \
    --subtensor.network test \
    --netuid 267 \
    --axon.port 8091 \
    --axon.external_ip YOUR_PUBLIC_IP \
    --axon.external_port 8091 \
    --blacklist.allow_non_registered \
    --logging.debug

pm2 save
pm2 logs nobi-miner  # Watch the logs
```

## Step 5: Verify It's Working

```bash
# Check logs — you should see "Received query" and "Generated response"
pm2 logs nobi-miner --lines 20

# Check on-chain
python -c "
import bittensor as bt
sub = bt.Subtensor(network='test')
mg = sub.metagraph(267)
w = bt.Wallet(name='my_wallet', hotkey='nobi-miner')
uid = mg.hotkeys.index(w.hotkey.ss58_address)
print(f'UID: {uid}')
print(f'Active: {bool(mg.active[uid])}')
print(f'Incentive: {float(mg.I[uid])}')
"
```

## How to Earn More

### 1. Use a Better Model (40% of score)
The quality of your LLM directly affects your earnings.

| Model | Quality | Cost |
|-------|---------|------|
| GPT-4o | ⭐⭐⭐⭐⭐ | $$$$ |
| Claude 3.5 Haiku | ⭐⭐⭐⭐ | $$ |
| DeepSeek V3 | ⭐⭐⭐⭐ | $ (Chutes) |
| Llama 3.3 70B | ⭐⭐⭐ | $ |
| Small local model | ⭐⭐ | Free (self-hosted) |

### 2. Improve Memory (30% of score)
The default memory system uses SQLite with keyword matching. To compete at the top:

- Implement **semantic search** (embeddings + vector DB)
- Add **LLM-based memory extraction** (instead of rule-based)
- Build **user profiling** (summarize what you know about each user)
- Implement **memory consolidation** (merge similar memories)

### 3. Customize Personality (20% of score)
Edit the system prompt in `neurons/miner.py` to make your companion unique:

- Be warmer, funnier, more empathetic
- Add cultural awareness
- Specialize (fitness coach, study buddy, creative partner)
- Test different personality approaches

### 4. Optimize Infrastructure (10% of score)
- Use a server close to validators for lower latency
- Set up proper monitoring (PM2 + alerts)
- Use connection pooling for LLM API calls
- Pre-warm your model on startup

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "ModuleNotFoundError: nobi" | Run `pip install -e .` from project root |
| "Not registered" | Register with `btcli subnets register` |
| "Connection refused" | Check firewall, ensure port 8091 is open |
| "LLM API error" | Check API key, try a different provider |
| High restarts | Check `pm2 logs` for errors, ensure memory isn't full |

## Questions?

- **GitHub:** [project-nobi](https://github.com/travellingsoldier85/project-nobi)
- **Discord:** Join the Bittensor testnet channel
- **Telegram:** @ProjectNobiBot (try the companion yourself!)

---
*Happy mining! Every query you serve makes someone's Dora smarter. 🤖*
