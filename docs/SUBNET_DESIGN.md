# Project Nobi — Subnet Design Document

> Technical specification of the actual implemented system.
> Last updated: March 2026

## Overview

A Bittensor subnet (testnet SN267) where miners compete to provide the best personal AI companion experience. Validators score miners on response quality, memory recall, and reliability.

## Synapse Protocol

### CompanionRequest (Implemented ✅)

The primary synapse for all companion interactions:

```python
class CompanionRequest(bt.Synapse):
    # Required — the user's message
    message: str

    # Optional — conversation history for context
    conversation_history: List[dict] = []   # [{"role": "user", "content": "..."}]
    user_id: str = ""                       # Anonymous user identifier
    preferences: dict = {}                  # Language, style, etc.

    # Response fields (filled by miner)
    response: Optional[str] = None          # The companion's response
    confidence: Optional[float] = None      # 0.0 to 1.0
    memory_context: Optional[List[dict]] = None  # Memory entries used
```

### MemoryStore (Implemented ✅)

For explicit memory storage instructions:

```python
class MemoryStore(bt.Synapse):
    user_id: str
    memory_type: str = "fact"       # fact | event | preference | context | emotion
    content: str = ""
    importance: float = 0.5         # 0.0 to 1.0
    tags: List[str] = []
    expires_at: Optional[str] = None

    # Response
    stored: Optional[bool] = None
    memory_id: Optional[str] = None
```

### MemoryRecall (Implemented ✅)

For testing miner memory retrieval:

```python
class MemoryRecall(bt.Synapse):
    user_id: str
    query: str = ""
    memory_type: Optional[str] = None
    tags: List[str] = []
    limit: int = 10

    # Response
    memories: Optional[List[dict]] = None
    total_count: Optional[int] = None
```

## Scoring Mechanism

### Actual Implementation

| Test Type | Frequency | Quality+Personality | Memory Recall | Reliability |
|-----------|-----------|-------------------|---------------|-------------|
| Single-turn | 40% of rounds | 90% | — | 10% |
| Multi-turn | 60% of rounds | 60% | 30% | 10% |

**Quality + Personality** is evaluated by an LLM-as-judge using three sub-criteria:
- Helpfulness (0–0.4)
- Coherence (0–0.3)
- Personality/warmth (0–0.3)

**Memory Recall** checks keyword presence from setup messages in the test response, with word-boundary matching for short keywords.

**Reliability** is based on response latency (<5s = 1.0, <10s = 0.8, <20s = 0.6, <30s = 0.4, ≥30s = 0.2).

**Heuristic fallback** (when LLM judge API is unavailable) is capped at 0.5 to prevent gaming.

### Anti-Gaming

- **Dynamic query generation** — thousands of unique queries from combinatorial templates
- **Fake user_id on single-turn** — miners can't detect validator tests
- **Heuristic cap at 0.5** — top scores require real LLM evaluation
- **Moving average (α=0.1)** — can't game one round and coast

## Memory Architecture

### Current Implementation
- **Storage:** SQLite per-miner (lightweight, no external dependencies)
- **Extraction:** Regex-based auto-extraction of names, locations, occupations, preferences, emotions, life events
- **Retrieval:** Keyword matching with importance weighting and word-boundary checks
- **Conversation history:** Stored per-user, last 20 turns retained

### Memory is NOT encrypted
Memory is stored in plaintext SQLite on the miner's machine. Users trust their assigned miner with their data. The `/forget` command in the Telegram bot deletes all user data.

### Future Improvements (Not Yet Built)
- Semantic search with embeddings
- LLM-based memory extraction (replacing regex)
- User-controlled encryption (client-side key management)
- Memory consolidation (merging similar memories)
- Distributed storage across miners for redundancy

## Network Architecture

```
User (Telegram bot / future: web, mobile)
  ↓ sends message
Nobi Bot (app/bot.py)
  ↓ currently: direct LLM call (testnet phase)
  ↓ future: routes through subnet via dendrite
Validator (neurons/validator.py)
  ↓ queries miners via dendrite
Miner (neurons/miner.py)
  ↓ generates response via LLM API + memory
  ↓ returns CompanionRequest with response filled
Validator
  ↓ scores response (LLM judge + memory + latency)
  ↓ updates weights on-chain
```

**Note:** In the current testnet phase, the Telegram bot calls the LLM directly (not through the subnet). In mainnet, the bot will route through the subnet's dendrite for decentralized serving.

## Economics

### Current (Testnet)
- Standard Bittensor emission model
- Miners earn TAO proportional to their quality scores
- No user payments yet

### Planned (Mainnet)
- User subscriptions ($4.99–$24.99/month)
- Subscription revenue used to buy-back TAO and stake → increases alpha value
- API access for developers ($0.005/message)

### NOT Implemented
- Custom payment splitting (70/18/12) — uses standard Bittensor mechanism
- Fiat payment bridge — future feature
- Tool execution scoring — future feature

## Subnet Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `netuid` | 267 (testnet) | Subnet identifier |
| `tempo` | 99 blocks (~20 min) | Weight update interval |
| `max_validators` | 64 | Maximum validator slots |
| `immunity_period` | 5000 blocks | New miner grace period |
| `commit_reveal_weights_enabled` | true | Anti-gaming weight commits |

## File Structure

```
project-nobi/
├── neurons/
│   ├── miner.py          # Miner neuron (LLM + memory)
│   └── validator.py      # Validator neuron
├── nobi/
│   ├── protocol.py       # Synapse definitions
│   ├── memory/
│   │   └── store.py      # SQLite memory manager
│   ├── validator/
│   │   ├── forward.py    # Validation logic
│   │   ├── reward.py     # Scoring functions
│   │   └── query_generator.py  # Dynamic test queries
│   ├── base/             # Base neuron classes (bt template)
│   └── utils/            # Config, UID selection, logging
├── app/
│   └── bot.py            # Telegram bot (@ProjectNobiBot)
├── docs/                 # All documentation
├── scripts/              # Deployment & monitoring scripts
└── setup.py              # Package installation
```

---

*This document describes the ACTUAL implemented system as of March 2026.*
*Future features are explicitly marked as "Not Yet Built" or "Planned".*
