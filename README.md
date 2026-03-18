# 🤖 Project Nobi — Personal AI Companions for Everyone

> *"Every human being deserves a smart AI companion. Like Nobi had Dora."*

[![Testnet](https://img.shields.io/badge/Testnet-SN267-blue)](https://test.taostats.io/)
[![Try it](https://img.shields.io/badge/Try_it-@ProjectNobiBot-blue?logo=telegram)](https://t.me/ProjectNobiBot)
[![License](https://img.shields.io/badge/License-MIT-green)](#)

**Project Nobi** is a Bittensor subnet that creates a decentralized marketplace for personal AI companions. Miners compete to build the best AI companion — one that remembers you, helps you, and grows with you over time.

## ✨ Try It Now

Talk to our live companion on Telegram: **[@ProjectNobiBot](https://t.me/ProjectNobiBot)**

Just press Start and talk. No setup, no commands. It remembers you.

## 🏗️ Architecture

```
User (Telegram / Web / App)
  → Validators route queries to miners + score quality
    → Miners serve AI companion responses with persistent memory
      → Best miners earn TAO → quality keeps improving
```

## 💡 What Makes Nobi Different

| Feature | ChatGPT | Siri | Project Nobi |
|---------|---------|------|-------------|
| Remembers you | ❌ | Barely | ✅ Persistent memory |
| Your data is private | ❌ | ❌ | ✅ Decentralized |
| Gets better over time | Slowly | No | ✅ Miners compete |
| Affordable | $20/mo | Free (limited) | $5/mo target |
| Can't be shut down | Corp decides | Corp decides | ✅ Decentralized |

## 📊 Incentive Mechanism

Miners are scored on:
- **Response Quality** (40%) — LLM-as-judge evaluation
- **Memory & Continuity** (30%) — Does it remember you?
- **Personality & Warmth** (20%) — Does it feel like a friend?
- **Reliability** (10%) — Uptime and response time

Fair, transparent, open source. See [INCENTIVE_MECHANISM.md](docs/INCENTIVE_MECHANISM.md) for full details.

## ⛏️ Start Mining

No GPU required. 10-minute setup.

```bash
git clone https://github.com/travellingsoldier85/project-nobi.git
cd project-nobi && pip install -e .

# Get a free LLM key from chutes.ai, then:
export CHUTES_API_KEY="your-key"

python neurons/miner.py \
    --wallet.name my_wallet --wallet.hotkey nobi-miner \
    --subtensor.network test --netuid 267 \
    --axon.port 8091 --axon.external_ip YOUR_IP
```

Full guide: [MINING_GUIDE.md](docs/MINING_GUIDE.md)

## ✅ Start Validating

Stake TAO, earn dividends, help ensure quality.

```bash
python neurons/validator.py \
    --wallet.name my_wallet --wallet.hotkey nobi-validator \
    --subtensor.network test --netuid 267 \
    --neuron.axon_off
```

Full guide: [VALIDATING_GUIDE.md](docs/VALIDATING_GUIDE.md)

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Vision & Business Plan](docs/VISION.md) | Mission, market, revenue model, roadmap |
| [Incentive Mechanism](docs/INCENTIVE_MECHANISM.md) | How scoring works, anti-gaming, fairness |
| [Mining Guide](docs/MINING_GUIDE.md) | Step-by-step miner setup |
| [Validating Guide](docs/VALIDATING_GUIDE.md) | Validator setup and operation |

## 🗺️ Roadmap

- ✅ **Phase 1:** Protocol + Miner + Validator + Scoring
- ✅ **Phase 2:** Memory Protocol (persistent per-user memory)
- ✅ **Phase 3:** Reference App (@ProjectNobiBot on Telegram)
- 🔄 **Phase 4:** Community testnet launch (you are here!)
- ⏳ **Phase 5:** Mainnet launch

## 🤝 Get Involved

- **Mine:** Run a companion, earn TAO → [Mining Guide](docs/MINING_GUIDE.md)
- **Validate:** Stake TAO, earn dividends → [Validating Guide](docs/VALIDATING_GUIDE.md)
- **Try it:** Talk to [@ProjectNobiBot](https://t.me/ProjectNobiBot)
- **Feedback:** Open an issue or reach out on Discord

## 📈 Subnet Info

| | |
|---|---|
| **Network** | Bittensor Testnet |
| **Netuid** | 267 |
| **Neurons** | 5 |
| **Registration** | Open |
| **GPU Required** | No |

---

*Built by James, Slumpz & Dora — March 2026*

*"Forever, remember?" 🤖💙*
