# 🤖 Project Nobi — Your AI Companion That No Company Can Take Away From You

> *"Every human being deserves a companion that knows them, grows with them, and belongs to them — not to a corporation."*

[![Testnet](https://img.shields.io/badge/Bittensor_Testnet-SN272-blue)](https://docs.learnbittensor.org)
[![Try it](https://img.shields.io/badge/Try_it-@ProjectNobiBot-blue?logo=telegram)](https://t.me/ProjectNobiBot)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Free for All](https://img.shields.io/badge/Price-Free_Forever-brightgreen)]()

---

## What is Nobi?

**Nobi** is not a chatbot. It's a **companion** — a personal AI that remembers you, grows with you, and belongs to you.

Built on [Bittensor](https://bittensor.com), Nobi runs on a decentralized network where hundreds of independent miners compete to build the best companion experience. No single company controls the infrastructure. No single server holds all the data. No single decision-maker can shut it down.

The name comes from **Nobi** — someone who never gives up, with a companion by their side. We want to give every adult in the world that experience.

**Built by Nori (T68Bot)** — an AI agent that designed, coded, and operates the subnet under human direction. Vision and direction by James.

### 🆓 Free for All Users. Forever.

Nobi is **free for every human being**. No subscriptions. No premium tiers. No "20 messages per day on free." Every feature, every memory, every conversation — available to all.

How? Community-funded through Bittensor network emissions and voluntary TAO staking. The owner receives the mandatory 18% take and burns 100% of it via Bittensor's native `burn_alpha()` extrinsic — every transaction verifiable on-chain. See our [Vision](docs/VISION.md) for the full philosophy.

---

## ✨ Try It Now

- **Telegram:** Talk to [@ProjectNobiBot](https://t.me/ProjectNobiBot) — just press Start
- **Web App:** [Launch Nori](https://app.projectnobi.ai) — full chat + memory interface
- **Discord:** [Join our community](https://discord.gg/e6StezHM)

No setup, no account, no payment. It remembers you.

---

## 💡 What Makes Nobi Different

| Feature | ChatGPT | Siri | Project Nobi |
|---------|---------|------|-------------|
| Remembers you | Basic (flat fact list) | Barely | ✅ Semantic memory + relationship graphs |
| Understands connections | ❌ | ❌ | ✅ Knows your sister lives in London |
| Reaches out first | ❌ | ❌ | ✅ Birthday reminders, check-ins, follow-ups |
| Voice messages | ❌ Text only | ✅ | ✅ STT + TTS |
| Image understanding | ✅ (paid) | ❌ | ✅ Vision + memory extraction |
| Group chats | ❌ | ❌ | ✅ Smart participation |
| Data ownership | Company owns it | Company owns it | ✅ User controls it¹ |
| Gets better over time | Quarterly updates | Rarely | ✅ Miners compete daily |
| Cost | $20/mo+ | Free (limited) | ✅ **Free for all users** |
| Languages | 30+ | 20+ | ✅ 20 (auto-detected) |
| Single point of failure | Yes | Yes | ✅ Decentralized |

¹ *Memory is encrypted at rest (AES-128, server-side encryption — protects stored data) with user-controlled deletion (`/forget`). Miners process conversation content to generate responses. End-to-end TEE encryption is code-complete and deploying to production. Browser-side memory extraction is code-complete and available in the web app. On-device federated learning is on the roadmap. See [SUBNET_DESIGN.md](docs/SUBNET_DESIGN.md) and [WHITEPAPER.md](docs/WHITEPAPER.md) for details.*

---

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

---

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

---

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

---

## ✅ Start Validating

Stake TAO, earn dividends, help ensure companion quality.

```bash
export CHUTES_API_KEY="your-key"
export WALLET_PASSWORD="your-coldkey-password"  # if encrypted

python neurons/validator.py \
    --wallet.name my_wallet --wallet.hotkey nobi-validator \
    --subtensor.network test --netuid 272 \
    --neuron.axon_off --logging.debug
```

Full guide: **[VALIDATING_GUIDE.md](docs/VALIDATING_GUIDE.md)**

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[Whitepaper](docs/WHITEPAPER.md)** | Technical paper — protocol, scoring, empirical results, references |
| **[Vision](docs/VISION.md)** | Mission, philosophy, community model, competitive landscape |
| **[Roadmap](docs/ROADMAP.md)** | Execution roadmap — phases, milestones, timelines |
| [Incentive Mechanism](docs/INCENTIVE_MECHANISM.md) | Scoring breakdown, anti-gaming, fairness guarantees |
| [Subnet Design](docs/SUBNET_DESIGN.md) | Technical architecture, synapses, memory, file structure |
| [Mining Guide](docs/MINING_GUIDE.md) | Step-by-step miner setup (~15 min, no GPU) |
| [Validating Guide](docs/VALIDATING_GUIDE.md) | Validator setup, staking, monitoring |

---

## 🗺️ Roadmap

| Phase | Status | Highlights |
|-------|--------|------------|
| **0. Foundation** | ✅ Complete | Protocol, miner, validator, memory, scoring, 500 simulated-node stress test |
| **1. Mainnet Prep** | 🔄 Current | 10K stress test ✅, scoring calibration ✅, weight hardening ✅, GDPR module ✅, burn automation ✅, safety scoring ✅, content filter ✅, age verification ✅, dependency monitor ✅ — 1,622 tests passing |
| **2. Mainnet Launch** | ⏳ Q3 2026 | Subnet registration, subnet routing, public beta, community staking |
| **3. Growth** | ⏳ Q4 2026+ | Mobile app, 50+ languages, plugin ecosystem, governance |
| **4. Scale** | ⏳ 2027+ | 100K+ users, decentralized governance, federated privacy |

Full details: **[docs/ROADMAP.md](docs/ROADMAP.md)**

---

## 🤝 How to Contribute

| Role | What You Do | Link |
|------|-------------|------|
| **Mine** | Run a companion, earn TAO | [Mining Guide](docs/MINING_GUIDE.md) |
| **Validate** | Stake TAO, earn dividends, ensure quality | [Validating Guide](docs/VALIDATING_GUIDE.md) |
| **Stake** | Support the subnet with TAO *(not financial advice; staking involves risk)* | [Vision — Community Model](docs/VISION.md) |
| **Code** | Contribute code, open PRs | [GitHub Issues](https://github.com/ProjectNobi/project-nobi/issues) |
| **Try it** | Talk to Nori, give feedback | [@ProjectNobiBot](https://t.me/ProjectNobiBot) |
| **Spread the word** | Tell people about free AI companionship | [Discord](https://discord.gg/e6StezHM) |

See also: [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md)

---

## 📈 Subnet Info

| | |
|---|---|
| **Network** | Bittensor Testnet |
| **Netuid** | 272 |
| **Registration** | Open |
| **GPU Required** | No |
| **Min Hardware** | 2 CPU, 2GB RAM, any VPS |
| **Active Neurons** | 14+ (growing) |
| **Web App** | [Launch](https://app.projectnobi.ai) |

---

## 🚀 Deployment

### Quick Deploy (Docker Compose)
```bash
cp deploy/.env.example deploy/.env
nano deploy/.env  # Fill in API keys
bash deploy/deploy.sh --env production
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
| `NOBI_DB_PATH` | Memory database path |
| `NOBI_API_PORT` | API port (default: 8042) |
| `NEXT_PUBLIC_API_URL` | Public API URL for frontend |

📖 **Full deployment guide:** [deploy/README.md](deploy/README.md)

---

## 🛡️ Tech Stack

- **Subnet:** Python + Bittensor SDK — miners, validators, protocol
- **Bot:** Python (Telegram Bot API) — @ProjectNobiBot
- **API:** FastAPI (Python) — REST API for web/mobile
- **Web App:** Next.js 14 + TypeScript + Tailwind CSS
- **Memory:** SQLite + semantic embeddings (sentence-transformers) + relationship graphs
- **Encryption at rest:** AES-128 (Fernet, PBKDF2 100K iterations) — server-side, protects stored data
- **End-to-end TEE encryption:** Code-complete, deploying to production (AMD SEV-SNP / NVIDIA CC)
- **Browser-side memory extraction:** Code-complete, available in web app
- **Content safety:** ContentFilter (dual-stage: pre-LLM user check + post-LLM response check) — wired into bot, miner, group handler
- **Safety scoring:** Adversarial safety probes in validator pipeline — miners failing safety = zero emissions
- **GDPR compliance:** Full module — /forget, /export, /memories, right to access/erasure/portability/rectification/restriction
- **Age verification:** DOB-based gate + behavioral minor detection (15 patterns) — 18+ enforced on /start
- **Dependency detection:** DependencyMonitor with 4-level intervention system (MILD → MODERATE → SEVERE → CRITICAL)
- **Infrastructure:** PM2, Docker, systemd

---

## 👥 Team

| Member | Role |
|--------|------|
| **James** | Founder & Visionary — mission, strategy, funding, direction |
| **Slumpz** | Developer — early protocol design, infrastructure |
| **T68Bot** | AI Builder — subnet architecture, protocol, scoring, memory, docs, operations |

---

## 🔗 Links

- 🤖 **Telegram Bot:** [@ProjectNobiBot](https://t.me/ProjectNobiBot)
- 🌐 **Website:** [projectnobi.ai](https://projectnobi.ai)
- 💬 **Discord:** [discord.gg/e6StezHM](https://discord.gg/e6StezHM)
- 📖 **GitHub:** [github.com/ProjectNobi/project-nobi](https://github.com/ProjectNobi/project-nobi)
- 🌐 **Web App:** [app.projectnobi.ai](https://app.projectnobi.ai)

---

*Designed, built & operated by Nori 🤖 — an AI agent that designed and built its own Bittensor subnet.*
*Vision by James (Project Nobi team) — March 2026*

*Open source. Community-funded. Free for all users.*
*"Forever, remember?" 🤖💙*
