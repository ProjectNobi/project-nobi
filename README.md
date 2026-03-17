# 🤖 Project Nobi — Personal AI Companions on Bittensor

**Subnet 272 (Testnet)** — A decentralized network of personal AI companions.

Nobi creates warm, Dora-inspired AI companions that provide emotional support, practical advice, and genuine conversation. Miners serve companion instances; validators ensure quality through LLM-judged scoring.

## Architecture

```
┌─────────────┐    CompanionQuery     ┌─────────────┐
│  Validator   │ ──────────────────── │    Miner     │
│  (UID 1)     │ ←── response ─────── │   (UID 2)    │
│              │                       │              │
│  - Sends     │    MemorySync         │  - Receives  │
│    prompts   │ ──────────────────── │    queries   │
│  - Judges    │                       │  - Generates │
│    quality   │                       │    responses │
│  - Sets      │                       │  - Maintains │
│    weights   │                       │    memory    │
└─────────────┘                       └─────────────┘
```

## Scoring System

| Dimension   | Weight | Description |
|-------------|--------|-------------|
| Relevance   | 0.4    | Does the response address the user's message? |
| Coherence   | 0.3    | Is it well-structured and logical? |
| Personality | 0.2    | Warm, caring companion personality? |
| Speed       | 0.1    | Response time (<2s = 1.0, >20s = 0.0) |

## Setup

### Prerequisites

- Python 3.10+
- Bittensor SDK 10.1.0+
- PM2 (`npm install -g pm2`)
- Registered wallet on testnet subnet 272

### Installation

```bash
cd project-nobi
pip install -r requirements.txt
```

### Environment Variables

```bash
export CHUTES_API_KEY="your-chutes-api-key"
export WALLET_PASSWORD="your-wallet-password"  # if coldkey is encrypted
```

### Run Miner

```bash
# Direct
python -m miner.main

# Via PM2
./scripts/run_miner.sh
```

### Run Validator

```bash
# Direct
python -m validator.main

# Via PM2
./scripts/run_validator.sh
```

## Protocol

### CompanionQuery Synapse

- **Request**: `user_message`, `conversation_id`, `user_profile` (optional)
- **Response**: `companion_response`, `confidence_score`

### MemorySync Synapse

- **Request**: `user_id`, `memories` (list of dicts)
- **Response**: `acknowledged`, `memory_count`

## Wallet Configuration

| Role      | Coldkey    | Hotkey          |
|-----------|------------|-----------------|
| Miner     | T68Coldkey | nobi-miner      |
| Validator | T68Coldkey | nobi-validator  |

## Network

- **Network**: Testnet (`test`)
- **Subnet UID**: 272
- **Miner Axon Port**: 8272

## File Structure

```
project-nobi/
├── protocol/
│   └── __init__.py          # Synapse definitions (CompanionQuery, MemorySync)
├── miner/
│   ├── __init__.py
│   └── main.py              # Miner entry point
├── validator/
│   ├── __init__.py
│   └── main.py              # Validator entry point
├── scripts/
│   ├── run_miner.sh         # PM2 miner launcher
│   └── run_validator.sh     # PM2 validator launcher
├── requirements.txt
└── README.md
```

## License

MIT — Built for the Bittensor ecosystem.
