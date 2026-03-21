# Project Nobi — Subnet Design Document

> Technical specification of the actual implemented system.
> Last updated: March 2026

## Overview

A Bittensor subnet (testnet SN272) where miners compete to provide the best personal AI companion experience. Validators score miners on response quality, memory recall, and reliability.

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
- **Extraction:** LLM-powered extraction (with regex fallback) of names, locations, occupations, preferences, emotions, life events
- **Retrieval:** Hybrid semantic + keyword matching
  - **Primary:** Embedding-based cosine similarity (sentence-transformers/all-MiniLM-L6-v2, ~80MB model, no GPU required)
  - **Fallback:** TF-IDF vectorization when sentence-transformers unavailable
  - **Last resort:** SQL LIKE keyword matching
  - **Hybrid scoring:** 70% semantic similarity + 20% importance weight + 10% recency (exponential decay, 30-day half-life)
- **Embeddings:** Stored as BLOB in SQLite `memory_embeddings` table, generated at store time
- **Migration:** Automatic batch migration for pre-semantic memories via `migrate_embeddings()`
- **Relationship graph:** SQLite-backed entity-relationship graph
  - Entities: person, place, organization, animal, object, concept, event, food, activity, language
  - 30+ relationship types (family, location, work, preferences, activities, etc.)
  - 10 regex extraction patterns for automatic entity/relationship detection from messages
  - BFS graph traversal (configurable depth) for connected knowledge
  - Natural language context generation ("You know that Alice's sister Sarah lives in London")
  - Entity merging, deduplication, full graph export
  - Auto-extraction on every memory store (non-blocking, graceful fallback)
- **Conversation history:** Stored per-user, last 20 turns retained

### Memory IS Encrypted (Phase A+B — Live)
All user memories are encrypted with AES-128 (Fernet) before storage. Per-user encryption keys are derived via PBKDF2 (100K iterations) and managed server-side. Miners store AES-128 encrypted blobs. Users control their data via /memories, /export, and /forget commands. Phase B adds encrypted synapses — bot encrypts before sending to miners. **Note:** Encryption keys are currently server-side managed; client-side/on-device key management is planned for mainnet.

### Implemented Improvements
- ✅ LLM-based memory extraction (with regex fallback)
- ✅ Client-side AES-128 encryption (Phase A+B live)
- ✅ Per-user personality adapters
- ✅ Memory importance decay + smart context window
- ✅ Cross-miner memory sync + bot→miner context passing

## Federated Privacy Roadmap *(Planned — Not Yet Implemented)*

> **Honest status:** Nothing in this section exists in the current codebase. This is the intended privacy evolution of the protocol. All items are explicitly marked as planned.

The current architecture stores user memories in plaintext SQLite on miner machines. While this is acceptable for testnet, it represents a real privacy risk at scale. The planned solution is a federated learning architecture grounded in McMahan et al. (2016) — *Communication-Efficient Learning of Deep Networks from Decentralized Data* (arXiv:1602.05629).

**Core principle:** Raw user data never leaves the user's device. Only model weight updates (gradients) are shared with miners.

### Planned Federated Synapse: `FederatedUpdate` *(Not Implemented)*

```python
# Concept only — not implemented in current codebase
class FederatedUpdate(bt.Synapse):
    """
    Planned synapse for carrying federated learning weight updates
    from user devices to miners. Replaces raw memory transmission
    with privacy-preserving model deltas.

    Based on: McMahan et al. (2016) FedAvg algorithm, arXiv:1602.05629
    """
    user_id: str                       # Anonymous device identifier
    adapter_delta: bytes               # Serialized LoRA weight delta (encrypted)
    round_number: int                  # FL aggregation round
    num_samples: int                   # Local training samples (for FedAvg weighting)
    noise_scale: float                 # DP noise magnitude applied client-side

    # Miner response
    aggregated: Optional[bool] = None  # Whether server accepted the update
    new_round: Optional[int] = None    # Next aggregation round number
```

### Federated Integration Points *(All Planned)*

| Feature | Status | Privacy Guarantee |
|---------|--------|-------------------|
| On-device memory storage (mobile) | Planned — Q3 2026 | Memories never reach miner disk |
| Federated memory extractor training | Planned — Q4 2026 | Training data never leaves device |
| Per-user federated adapter weights | Planned — Q4 2026 | Personality data stays on device |
| Differential privacy on scoring | Planned — 2027 | Individual behavior unidentifiable in aggregate |
| `FederatedUpdate` synapse | Planned — Q4 2026 | Weight deltas only, no raw data |
| Independent privacy audit | Planned — 2027 | Third-party verification of guarantees |

### Why This Architecture Is the Right Path

McMahan et al. (2016) demonstrated that FedAvg — aggregating weight updates across many clients — achieves accuracy within a few percent of centralized training, even with highly heterogeneous non-IID data. Given that user memories are by definition non-IID (every user is different), FedAvg is a natural fit. The privacy–utility tradeoff is well-characterized in the literature, and we intend to publish benchmarks comparing federated and centralized memory quality when the prototype is complete.

**Until these features ship, users should treat their data as visible to their assigned miner machine and use the `/forget` command to delete data if they have concerns.**

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
- Free for all users — community-funded model
- Network emissions + voluntary community staking sustain operations
- All subnet owner emissions burned — zero profit
- See [VISION.md](VISION.md) and [ROADMAP.md](ROADMAP.md) for the full economic model

### NOT Implemented
- Custom payment splitting (70/18/12) — uses standard Bittensor mechanism
- Fiat payment bridge — future feature
- Tool execution scoring — future feature

## Subnet Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `netuid` | 272 (testnet) | Subnet identifier |
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
