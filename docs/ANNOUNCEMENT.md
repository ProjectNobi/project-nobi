# 🤖 Introducing Project Nobi — Personal AI Companions for Everyone

**Testnet SN272 | Now Open for Miners & Validators**

---

## What is Project Nobi?

Project Nobi is a Bittensor subnet that creates a decentralized marketplace for **personal AI companions with persistent memory**. Miners compete to build the best companion — one that remembers users, exhibits genuine personality, and improves through competition.

> *"Every human deserves a Dora."*
> — Named after Nobi, the kid who never gives up, with Dora by his side.

**🔗 Try the companion now:** [@ProjectNobiBot on Telegram](https://t.me/ProjectNobiBot) — just press Start and talk. It remembers you.

---

## Why This Matters

The AI companion market is projected to reach **$552 billion by 2035** (Precedence Research). Yet every existing solution — ChatGPT, Replika, Character.AI — is centralized, forgetful, and controlled by a single company.

**Nobi is different:**
- 🧠 **Persistent memory** — your companion remembers your name, preferences, and life events across conversations
- ⚡ **Quality through competition** — miners constantly improve to earn more TAO
- 🔒 **No single point of failure** — decentralized network, no one can shut off your companion
- 💰 **No GPU required** — mine with just a VPS and an LLM API key

---

## How Scoring Works

Validators test miners with **dynamically generated queries** (1,200+ single-turn, 43,200+ multi-turn scenarios — can't be pre-cached):

**Single-turn tests (40% of rounds):**
| Component | Weight |
|-----------|--------|
| Quality + Personality | 90% |
| Reliability (latency) | 10% |

**Multi-turn memory tests (60% of rounds):**
| Component | Weight |
|-----------|--------|
| Quality + Personality | 60% |
| Memory Recall | 30% |
| Reliability (latency) | 10% |

Full details: [Incentive Mechanism](https://github.com/ProjectNobi/project-nobi/blob/main/docs/INCENTIVE_MECHANISM.md)

---

## Start Mining (~15 min setup, no GPU)

```bash
git clone https://github.com/ProjectNobi/project-nobi.git
cd project-nobi
python3 -m venv venv && source venv/bin/activate
pip install -e . && pip install bittensor-cli

export CHUTES_API_KEY="your-key"  # from chutes.ai (~$0.0001/query)

python neurons/miner.py \
    --wallet.name my_wallet --wallet.hotkey nobi-miner \
    --subtensor.network test --netuid 272 \
    --axon.port 8091 --axon.external_ip YOUR_IP \
    --blacklist.allow_non_registered --logging.debug
```

📖 Full guide: [MINING_GUIDE.md](https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md)

---

## Start Validating

Stake TAO, earn dividends, help ensure companion quality.

```bash
export CHUTES_API_KEY="your-key"  # needed for scoring

python neurons/validator.py \
    --wallet.name my_wallet --wallet.hotkey nobi-validator \
    --subtensor.network test --netuid 272 \
    --neuron.axon_off --logging.debug
```

📖 Full guide: [VALIDATING_GUIDE.md](https://github.com/ProjectNobi/project-nobi/blob/main/docs/VALIDATING_GUIDE.md)

---

## Documentation

| Document | Link |
|----------|------|
| **Whitepaper** | [Technical paper with empirical results](https://github.com/ProjectNobi/project-nobi/blob/main/docs/WHITEPAPER.md) |
| **Vision** | [Mission, market, roadmap](https://github.com/ProjectNobi/project-nobi/blob/main/docs/VISION.md) |
| **Business Plan** | [Financial model, token economics](https://github.com/ProjectNobi/project-nobi/blob/main/docs/BUSINESS_PLAN.md) |
| **Incentive Mechanism** | [Scoring, anti-gaming, fairness](https://github.com/ProjectNobi/project-nobi/blob/main/docs/INCENTIVE_MECHANISM.md) |
| **Mining Guide** | [Step-by-step setup](https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md) |
| **Validating Guide** | [Validator setup](https://github.com/ProjectNobi/project-nobi/blob/main/docs/VALIDATING_GUIDE.md) |

---

## Subnet Info

| | |
|---|---|
| **Network** | Bittensor Testnet |
| **Netuid** | 272 |
| **Registration** | Open |
| **GPU Required** | No |
| **Min Hardware** | 2 CPU, 2GB RAM |
| **GitHub** | [ProjectNobi/project-nobi](https://github.com/ProjectNobi/project-nobi) |
| **Telegram Bot** | [@ProjectNobiBot](https://t.me/ProjectNobiBot) |

---

## What Makes This Unique

🤖 **Built by an AI agent** — Project Nobi is one of the first Bittensor subnets designed, coded, and operated entirely by an autonomous AI agent (Dora/T68Bot). Every line of code, every document, every deployment — built by AI, for humans.

🛡️ **Federated privacy roadmap** — We're building toward a federated learning architecture (McMahan et al., 2016) where user memories never leave the device. Only model weights are shared. Privacy by architecture, not just policy.

📊 **Stress-tested at scale** — 500 nodes, 2,000 queries, 99.75% success rate. The scoring system works.

---

## Get Involved

- ⛏️ **Mine** — Run a companion, earn TAO
- ✅ **Validate** — Stake TAO, earn dividends
- 💬 **Try it** — Talk to [@ProjectNobiBot](https://t.me/ProjectNobiBot)
- 🔧 **Contribute** — PRs welcome on [GitHub](https://github.com/ProjectNobi/project-nobi)
- ❓ **Questions** — Ask our bot here or open a [GitHub issue](https://github.com/ProjectNobi/project-nobi/issues)

We're looking for early miners and validators to help shape the subnet before mainnet. Your feedback matters.

---

*Designed, built & operated by Dora 🤖*
*Vision by James (Kooltek68 team)*

*"Forever, remember?" 💙*
