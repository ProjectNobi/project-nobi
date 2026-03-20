# Mining on Project Nobi — Quick Start Guide

> Estimated setup time: 10-15 minutes. No GPU required.

## ⚡ One-Command Setup

```bash
bash <(curl -sSL https://raw.githubusercontent.com/ProjectNobi/project-nobi/main/scripts/quick_setup.sh)
```

This interactive script handles everything: installs dependencies, clones the repo, creates your wallet, registers on the subnet, configures your LLM, opens firewall, and starts mining with PM2.

**Prefer manual setup?** Follow the steps below.

---

## What You're Building

You're running a **personal AI companion** (Nori) that talks to users, remembers them, and helps them with daily life. The better your companion, the more you earn.

## Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Disk | 10 GB | 20+ GB |
| GPU | **None** | **None** |
| Network | Stable internet | Low latency |
| Python | 3.10+ | 3.12 |
| OS | Ubuntu 20.04+ | Ubuntu 22.04+ |

**No GPU needed!** The miner uses cloud LLM APIs for inference.

## Step 1: Get an LLM API Key

You need an API key for your companion's brain. Choose one:

### Option A: Chutes.ai (~$0.0001/query)
1. Go to [chutes.ai](https://chutes.ai)
2. Create account and add credits
3. Get API key from dashboard
4. Model: `deepseek-ai/DeepSeek-V3-0324`

### Option B: OpenRouter (~$0.001/query)
1. Go to [openrouter.ai](https://openrouter.ai)
2. Create account, add credits
3. Get API key
4. Recommended model: `anthropic/claude-3.5-haiku`

### Option C: Self-Hosted Model (Advanced, no API cost)
Run your own model with vLLM or Ollama, then point the miner at `http://localhost:8000/v1`. Requires a machine with GPU.

## Step 2: Install

```bash
# Clone the repo
git clone https://github.com/ProjectNobi/project-nobi.git
cd project-nobi

# (Recommended) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Install bittensor CLI for wallet management
pip install bittensor-cli

# Verify installation
python -c "import nobi; print('✅ Nobi installed')"
python -c "import bittensor as bt; print(f'✅ Bittensor {bt.__version__}')"
```

**Note:** If `btcli` shows bittorrent commands instead of Bittensor, use `python3 -m bittensor_cli.cli` instead of `btcli` for all commands below.

## Step 3: Create Wallet & Register

```bash
# Create wallet (skip if you already have one)
btcli wallet new-coldkey --wallet.name my_wallet
btcli wallet new-hotkey --wallet.name my_wallet --wallet.hotkey nobi-miner

# Register on testnet (costs minimal tTAO)
btcli subnets register \
    --netuid 272 \
    --wallet.name my_wallet \
    --wallet.hotkey nobi-miner \
    --subtensor.network test
```

## Step 4: Open Firewall Port

The miner's axon needs to be reachable by validators. Open the port:

```bash
# Ubuntu/Debian with ufw
sudo ufw allow 8091/tcp

# Or with iptables
sudo iptables -A INPUT -p tcp --dport 8091 -j ACCEPT
```

## Step 5: Find Your Public IP

```bash
curl -4 ifconfig.me
# Example output: 203.0.113.45
```

Use this IP in the `--axon.external_ip` flag below.

## Step 6: Configure & Run

```bash
# Set your LLM API key
export CHUTES_API_KEY="your-chutes-key-here"
# OR
export OPENROUTER_API_KEY="your-openrouter-key-here"

# If your coldkey is encrypted, set the password
export WALLET_PASSWORD="your-coldkey-password"

# Run the miner (replace YOUR_PUBLIC_IP with your actual IP)
python neurons/miner.py \
    --wallet.name my_wallet \
    --wallet.hotkey nobi-miner \
    --subtensor.network test \
    --netuid 272 \
    --axon.port 8091 \
    --axon.external_ip YOUR_PUBLIC_IP \
    --axon.external_port 8091 \
    --blacklist.allow_non_registered \
    --logging.debug
```

### With PM2 (Recommended — auto-restart on crash)

```bash
# Install PM2 if needed
npm install -g pm2

# Start miner
CHUTES_API_KEY="your-key" \
WALLET_PASSWORD="your-password" \
pm2 start python3 --name nobi-miner -- \
    neurons/miner.py \
    --wallet.name my_wallet \
    --wallet.hotkey nobi-miner \
    --subtensor.network test \
    --netuid 272 \
    --axon.port 8091 \
    --axon.external_ip YOUR_PUBLIC_IP \
    --axon.external_port 8091 \
    --blacklist.allow_non_registered \
    --logging.debug

pm2 save
```

## Step 7: Verify It's Working

```bash
# Check logs — look for "Received query" and "Generated response"
pm2 logs nobi-miner --lines 20

# Check on-chain status
python -c "
import bittensor as bt
sub = bt.Subtensor(network='test')
mg = sub.metagraph(272)
w = bt.Wallet(name='my_wallet', hotkey='nobi-miner')
hk = w.hotkey.ss58_address
if hk in mg.hotkeys:
    uid = mg.hotkeys.index(hk)
    print(f'UID: {uid}')
    print(f'Active: {bool(mg.active[uid])}')
    print(f'Incentive: {float(mg.I[uid]):.6f}')
else:
    print('Not found in metagraph — check registration')
"
```

**Expected log output:**
```
INFO | Received query from user 'user_123456': I'm feeling a bit stressed...
INFO | Generated response (245 chars), memories used: 2
```

## How Scoring Works

Your earnings depend on your score. Here's how it breaks down:

### Single-Turn Tests (40% of validation rounds)
| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Quality + Personality | 90% | LLM judge rates helpfulness, coherence, warmth |
| Reliability | 10% | Response latency (< 5s = full marks) |

### Multi-Turn Tests (60% of validation rounds)
| Component | Weight | What It Measures |
|-----------|--------|------------------|
| Quality + Personality | 60% | LLM judge rates helpfulness, coherence, warmth |
| Memory Recall | 30% | Did you remember the user's details from earlier messages? |
| Reliability | 10% | Response latency |

### How to Earn More

**1. Use a better model (biggest impact — affects 60-90% of your score)**

| Model | Quality | Cost |
|-------|---------|------|
| GPT-4o / Claude 3.5 Sonnet | ⭐⭐⭐⭐⭐ | $$$ |
| Claude 3.5 Haiku | ⭐⭐⭐⭐ | $$ |
| DeepSeek V3 (Chutes) | ⭐⭐⭐⭐ | $ |
| Llama 3.3 70B | ⭐⭐⭐ | $ |
| Small local model (7B) | ⭐⭐ | Free (self-hosted) |

**2. Improve memory (affects 18% of your overall score)**

The default memory now includes **semantic search** (sentence-transformers embeddings with cosine similarity). To compete at the top:
- Install `sentence-transformers` for best results: `pip install sentence-transformers` (~80MB model, no GPU needed)
- Without it, the system falls back to TF-IDF, then keyword matching
- Customize **LLM-based memory extraction** (tune what facts get extracted)
- Build **user profiling** (summarize what you know about each user)
- Implement **memory consolidation** (merge similar memories over time)

**3. Tune personality (included in quality score)**

Edit the system prompt in `neurons/miner.py` — the `COMPANION_SYSTEM_PROMPT` variable:
- Be warmer, funnier, more empathetic
- Specialize (fitness coach, study buddy, creative partner)
- Test different approaches and watch your scores

**4. Optimize speed (affects 10% of your overall score)**

| Latency | Reliability Score |
|---------|-------------------|
| < 5s | 1.0 (full marks) |
| < 10s | 0.8 |
| < 20s | 0.6 |
| < 30s | 0.4 |
| ≥ 30s | 0.2 |

Tips: use a server geographically close to validators, use connection pooling, pre-warm your LLM client.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: nobi` | Run `pip install -e .` from project root |
| `Not registered` | Run `btcli subnets register --netuid 272 ...` |
| `Connection refused` on axon | Check firewall (`ufw allow 8091/tcp`), verify external IP is correct |
| `LLM API error` | Check API key, try `curl` to test: `curl https://llm.chutes.ai/v1/models -H "Authorization: Bearer $CHUTES_API_KEY"` |
| `Wrong password` / `DecryptionError` | Set `WALLET_PASSWORD` env var, or recreate wallet without password |
| `btcli` shows bittorrent | Use `python3 -m bittensor_cli.cli` instead |
| High restarts in PM2 | Check `pm2 logs nobi-miner --err` for the root cause |
| Score is 0 | Verify axon is reachable from outside: `curl http://YOUR_IP:8091` |

## Auto-Updates (Optional)

Stay up to date automatically — the auto-updater polls for new commits, pulls changes, runs health checks, and restarts your PM2 processes:

```bash
bash scripts/install_auto_updater.sh
```

**What it does:**
- Checks for new commits every 5 minutes (configurable)
- Pulls updates and runs a health check before restarting
- Automatically rolls back if the health check fails
- Logs everything to `~/.nobi/update_log.json`

**Configuration (environment variables):**
| Variable | Default | Description |
|---|---|---|
| `AUTO_UPDATE_INTERVAL` | `300` | Check interval in seconds |
| `AUTO_UPDATE_PM2_NAMES` | auto-detect | Comma-separated PM2 process names |
| `AUTO_UPDATE_ENABLED` | `true` | Set to `false` to disable |
| `AUTO_UPDATE_BRANCH` | `main` | Git branch to track |

**Manual one-time check:**
```bash
python3 scripts/auto_updater.py --once
```

**Manage:**
```bash
pm2 logs nobi-auto-updater    # View logs
pm2 stop nobi-auto-updater    # Pause
pm2 restart nobi-auto-updater # Resume
pm2 delete nobi-auto-updater  # Remove
```

## Questions?

- **GitHub:** [project-nobi](https://github.com/ProjectNobi/project-nobi)
- **Discord:** [Join our community](https://discord.gg/e6StezHM)
- **Telegram:** [@ProjectNobiBot](https://t.me/ProjectNobiBot) (try the companion yourself!)
- **Website:** [projectnobi.ai](https://projectnobi.ai)
- **Issues:** [Open a GitHub issue](https://github.com/ProjectNobi/project-nobi/issues)

---
*Happy mining! Every query you serve makes someone's Nori smarter. 🤖*
