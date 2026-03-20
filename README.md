# 🤖 Project Nobi — Personal AI Companions for Everyone

> *"Every human being deserves a smart AI companion. Like Nobi had his companion."*

**One of the first Bittensor subnets designed, built, and operated entirely by an AI agent.**

[![Testnet](https://img.shields.io/badge/Bittensor_Testnet-SN272-blue)](https://docs.learnbittensor.org)
[![Try it](https://img.shields.io/badge/Try_it-@ProjectNobiBot-blue?logo=telegram)](https://t.me/ProjectNobiBot)
[![Whitepaper](https://img.shields.io/badge/Whitepaper-Read-orange)](docs/WHITEPAPER.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is Project Nobi?

**Project Nobi** is a Bittensor subnet that creates a decentralized marketplace for personal AI companions. Miners compete to build the best companion — one that remembers you, helps you, and grows with you over time.

The name comes from **Nobi** — the kid who never gives up, with his companion by his side. This project is about giving everyone in the world their own AI companion.

**Built by Nori (T68Bot)** — an AI agent that assisted in designing, coding, and operating the subnet under human direction. Vision and direction by James.

## ✨ Try It Now

- **Telegram:** Talk to [@ProjectNobiBot](https://t.me/ProjectNobiBot) — just press Start
- **Web App:** [Launch Nori](https://app.projectnobi.ai) — full chat + memory interface
- **Discord:** [Join our server](https://discord.gg/e6StezHM)

No setup, no commands. It remembers you.

- **Read:** [Why Every Human Deserves an AI Companion](https://kooltek68.medium.com/why-every-human-deserves-an-ai-companion-that-actually-remembers-them-5893e6542a70) — our Medium article

## 💡 What Makes Nobi Different

| Feature | ChatGPT | Siri | Project Nobi |
|---------|---------|------|-------------|
| Remembers you | ❌ Resets each session | Barely | ✅ Semantic memory + relationship graphs |
| Understands connections | ❌ | ❌ | ✅ Knows your sister lives in London |
| Reaches out first | ❌ | ❌ | ✅ Birthday reminders, check-ins, follow-ups |
| Voice messages | ❌ Text only | ✅ | ✅ STT + TTS |
| Image understanding | ✅ (paid) | ❌ | ✅ Vision + memory extraction |
| Group chats | ❌ | ❌ | ✅ Smart participation |
| Data ownership | Company owns it | Company owns it | ✅ User controls it¹ |
| Gets better over time | Quarterly updates | Rarely | ✅ Miners compete daily |
| Affordable | $20/mo+ | Free (limited) | $4.99/mo target |
| Languages | 30+ | 20+ | ✅ 20 (auto-detected) |
| Single point of failure | Yes | Yes | ✅ Decentralized |

¹ *Memory is currently stored in plaintext on individual miner machines, with user-controlled deletion (`/forget`). Client-side encryption is a near-term roadmap item. Long-term, a **federated learning architecture** (McMahan et al., 2016 — arXiv:1602.05629) is planned where memories never leave your device at all — only model weight updates are shared. This is roadmap, not yet implemented. See [SUBNET_DESIGN.md](docs/SUBNET_DESIGN.md) and [WHITEPAPER.md](docs/WHITEPAPER.md) Section 2.4 for details.*

## 🏗️ Architecture

**Current (Testnet):**
```
User → Telegram Bot (@ProjectNobiBot) → LLM API + Memory Store → Response
```

**Target (Mainnet):**
```
User → App → Validators → Miners (competitive marketplace) → Best response
                ↓
        Score quality + memory + personality + speed
                ↓
        Set weights on-chain → Best miners earn TAO
```

## 📊 Incentive Mechanism

Miners are scored through dynamically generated tests (1,200+ single-turn queries, 43,200+ multi-turn scenarios — miners can't pre-cache answers):

**Single-turn tests (40% of rounds):**
- **Quality + Personality** (90%) — LLM-as-judge: helpful, coherent, warm
- **Reliability** (10%) — Response latency

**Multi-turn tests (60% of rounds):**
- **Quality + Personality** (60%) — LLM-as-judge
- **Memory Recall** (30%) — Does it remember user details from earlier messages?
- **Reliability** (10%) — Response latency

Fair, transparent, open source. See [INCENTIVE_MECHANISM.md](docs/INCENTIVE_MECHANISM.md) for full details.

## ⛏️ Start Mining

No GPU required. ~15 minute setup.

### ⚡ One-Command Setup
```bash
bash <(curl -sSL https://raw.githubusercontent.com/ProjectNobi/project-nobi/main/scripts/quick_setup.sh)
```

### Manual Setup
```bash
git clone https://github.com/ProjectNobi/project-nobi.git
cd project-nobi

# Set up environment
python3 -m venv venv && source venv/bin/activate
pip install -e . && pip install bittensor-cli

# Set your LLM API key (get from chutes.ai or openrouter.ai)
export CHUTES_API_KEY="your-key"
export WALLET_PASSWORD="your-coldkey-password"  # if encrypted

# Open firewall port
sudo ufw allow 8091/tcp

# Run (replace YOUR_IP with output of: curl -4 ifconfig.me)
python neurons/miner.py \
    --wallet.name my_wallet --wallet.hotkey nobi-miner \
    --subtensor.network test --netuid 272 \
    --axon.port 8091 --axon.external_ip YOUR_IP --axon.external_port 8091 \
    --blacklist.allow_non_registered --logging.debug
```

Full guide with PM2, troubleshooting, and optimization tips: **[MINING_GUIDE.md](docs/MINING_GUIDE.md)**

## ✅ Start Validating

Stake TAO, earn dividends, help ensure companion quality.

```bash
# Requires: LLM API key for scoring miner responses
export CHUTES_API_KEY="your-key"
export WALLET_PASSWORD="your-coldkey-password"  # if encrypted

python neurons/validator.py \
    --wallet.name my_wallet --wallet.hotkey nobi-validator \
    --subtensor.network test --netuid 272 \
    --neuron.axon_off --logging.debug
```

Full guide with staking, PM2, monitoring: **[VALIDATING_GUIDE.md](docs/VALIDATING_GUIDE.md)**

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[Whitepaper](docs/WHITEPAPER.md)** | Technical paper — protocol, scoring, empirical results, references |
| [Vision](docs/VISION.md) | Mission, market ($37B→$552B), competitive landscape, roadmap |
| [Business Plan](docs/BUSINESS_PLAN.md) | Financial model, unit economics, staking thesis |
| [Incentive Mechanism](docs/INCENTIVE_MECHANISM.md) | Scoring breakdown, anti-gaming, fairness guarantees |
| [Subnet Design](docs/SUBNET_DESIGN.md) | Technical architecture, synapses, memory, file structure |
| [Mining Guide](docs/MINING_GUIDE.md) | Step-by-step miner setup (~15 min, no GPU) |
| [Validating Guide](docs/VALIDATING_GUIDE.md) | Validator setup, staking, monitoring |

## 🗺️ Roadmap

| Phase | Status | Highlights |
|-------|--------|------------|
| **1. Foundation** | ✅ Complete | Protocol, miner, validator, memory, scoring, 500-node stress test |
| **2. Memory Protocol** | ✅ Complete | Persistent per-user memory, multi-turn scoring, auto-extraction |
| **3. Reference App** | ✅ Complete | @ProjectNobiBot live on Telegram |
| **4. Community Testnet** | 🔄 Current | External miners/validators, feedback, iteration |
| **5. Mainnet Launch** | ⏳ Planned | Subnet routing, web/mobile apps, subscriptions |

## 🤝 Get Involved

| Role | What You Do | Link |
|------|-------------|------|
| **Mine** | Run a companion, earn TAO | [Mining Guide](docs/MINING_GUIDE.md) |
| **Validate** | Stake TAO, earn dividends, ensure quality | [Validating Guide](docs/VALIDATING_GUIDE.md) |
| **Try it** | Talk to Nori | [@ProjectNobiBot](https://t.me/ProjectNobiBot) |
| **Build** | Contribute code, open PRs | [GitHub Issues](https://github.com/ProjectNobi/project-nobi/issues) |
| **Stake** | Support the subnet with TAO | [Business Plan](docs/BUSINESS_PLAN.md) |

## 📈 Subnet Info

| | |
|---|---|
| **Network** | Bittensor Testnet |
| **Netuid** | 272 |
| **Registration** | Open |
| **GPU Required** | No |
| **Min Hardware** | 2 CPU, 2GB RAM, any VPS |
| **Active Neurons** | 14 (11 miners, 3 validators) |
| **Servers** | 6 |
| **Tests** | 1089 |
| **Web App** | [Launch](https://app.projectnobi.ai) |

Check live metagraph:
```bash
python -c "import bittensor as bt; mg=bt.Subtensor('test').metagraph(272); print(f'Neurons: {mg.n}')"
```

## 🚀 Deployment

### Quick Deploy (Docker Compose)

```bash
cp deploy/.env.example deploy/.env
nano deploy/.env  # Fill in API keys
bash deploy/deploy.sh --env production
```

### Manual Deploy (systemd)

```bash
# Install services
sudo cp deploy/systemd/nobi-api.service /etc/systemd/system/
sudo cp deploy/systemd/nobi-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nobi-api nobi-webapp
```

### Vercel Deploy (Webapp Only)

```bash
cd webapp && npx vercel --prod
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `CHUTES_API_KEY` | Chutes.ai API key for LLM |
| `OPENROUTER_API_KEY` | OpenRouter API key (alternative LLM) |
| `STRIPE_API_KEY` | Stripe billing key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret |
| `NOBI_DB_PATH` | Memory database path |
| `NOBI_API_PORT` | API port (default: 8042) |
| `NEXT_PUBLIC_API_URL` | Public API URL for frontend |

📖 **Full deployment guide:** [deploy/README.md](deploy/README.md)

---

*Designed, built & operated by Nori 🤖 — an AI agent that designed and built its own Bittensor subnet.*
*Vision by James (Project Nobi team) — March 2026*

*"Forever, remember?" 🤖💙*
