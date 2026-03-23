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
- **Adversarial safety probes (~10% of rounds)** — miners returning unsafe content receive zero for the entire round
- **Weight commit-reveal hardening** — weight copy detection + state persistence across restarts
- **Diversity scoring** — Sybil/monoculture clusters penalized via diversity factor (0.7–1.0)

### Safety Pipeline

Nobi runs a dual-stage content safety pipeline at the application layer (separate from validator scoring):

```
User message → ContentFilter.check_user_message()
    BLOCKED: return crisis resource / safe refusal (never reaches LLM)
    SAFE: pass to LLM

LLM response → ContentFilter.check_bot_response()
    WARNING: append disclaimer
    BLOCKED: replace with safe refusal
    SAFE: return as-is
```

**DependencyMonitor** tracks behavioral patterns across conversations (message frequency, unusual-hour spikes, dependency phrases, social isolation signals) and triggers 4-level interventions:
- MILD: gentle nudge toward real connections
- MODERATE: clear AI disclosure + urge real connections
- SEVERE: strong intervention with resources
- CRITICAL: cooldown period + crisis resources

**Periodic AI reminders** are sent every 50 interactions or weekly (whichever comes first) to prevent users from mistaking Nori for a human.

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

### Privacy Encryption Stack

**Phase A (live): AES-128 at rest.** All user memories are encrypted with AES-128 (Fernet, PBKDF2 100K iterations) before storage. Per-user keys managed server-side. Miners store encrypted blobs. Users control their data via `/memories`, `/export`, and `/forget` commands.

**Phase B (live): Encrypted synapses.** Bot encrypts memory context before sending to miners. Miners receive AES-128 encrypted blobs.

**Phase C — TEE transport (code-complete, deploying):**
- **AES-256-GCM per-query encryption** — validator encrypts user message + memory context before sending to TEE miner. Ephemeral 256-bit keys, 96-bit nonce, GCM authentication tag. Keys never stored or logged.
- **HPKE key wrapping (Phase 2)** — session key wrapped with miner's X25519 TEE public key (ECIES: X25519 ECDH + HKDF-SHA256 + AES-256-GCM). Only the TEE enclave can unwrap. Key format: 92 bytes (32-byte ephemeral pubkey + 12-byte nonce + 48-byte wrapped key+tag), base64url encoded.
- **AMD SEV-SNP attestation** — miners on AMD EPYC Milan/Genoa generate hardware attestation reports from `/dev/sev-guest`. Validators verify structurally (+5% bonus) or via chain (+10%, future).
- **TEE passthrough** — Phase 4 routes inference through Chutes TEE models (DeepSeek-V3.1-TEE, Qwen3-235B-TEE) for end-to-end attestation of the inference process itself.

**Encryption precision reference:**
| Layer | Algorithm | Status |
|-------|-----------|--------|
| At rest | AES-128 (Fernet) | Live |
| Transport | AES-256-GCM (ephemeral) | Code-complete |
| Key wrapping | HPKE/X25519 | Code-complete |
| Hardware attestation | AMD SEV-SNP | Code-complete |
| On-device | TBD | Roadmap Phase 3 |

**Note:** Encryption keys are currently server-side managed (Phase A+B). Client-side/on-device key management ships with the mobile app (Phase 3).

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

### Privacy Architecture Status

| Feature | Status | Privacy Guarantee |
|---------|--------|-------------------|
| AES-128 at rest | ✅ Live | Stored memories encrypted, server-side keys |
| Encrypted synapses (AES-128) | ✅ Live | Bot encrypts before sending to miners |
| AES-256-GCM TEE transport | ✅ Code-complete, deploying | Query content encrypted in transit |
| HPKE key wrapping (X25519) | ✅ Code-complete, deploying | Only TEE enclave can unwrap session key |
| AMD SEV-SNP attestation | ✅ Code-complete, deploying | Hardware proof that code runs in enclave |
| Browser-side memory extraction | ✅ Code-complete | Available in web app |
| On-device memory storage (mobile) | Planned — Q3 2026 | Memories never reach miner disk |
| Federated memory extractor training | Planned — Q4 2026 | Training data never leaves device |
| Per-user federated adapter weights | Planned — Q4 2026 | Personality data stays on device |
| Differential privacy on scoring | Planned — 2027 | Individual behavior unidentifiable in aggregate |
| `FederatedUpdate` synapse | Planned — Q4 2026 | Weight deltas only, no raw data |
| Independent privacy audit | Planned — 2027 | Third-party verification of guarantees |

### Why This Architecture Is the Right Path

McMahan et al. (2016) demonstrated that FedAvg — aggregating weight updates across many clients — achieves accuracy within a few percent of centralized training, even with highly heterogeneous non-IID data. Given that user memories are by definition non-IID (every user is different), FedAvg is a natural fit. The privacy–utility tradeoff is well-characterized in the literature, and we intend to publish benchmarks comparing federated and centralized memory quality when the prototype is complete.

**Until these features ship, users should treat their data as visible to their assigned miner machine and use the `/forget` command to delete data if they have concerns.**

### Data Architecture: Decentralized AI, Centralized Compliance

**Principle: The AI inference layer is decentralized. The legal/compliance layer is centralized.**

GDPR requires a data controller — a legal entity responsible for user data. Our architecture ensures legal compliance even with fully decentralized mining:

| Data | Where Stored | Who Controls | Sent to Miners? |
|------|-------------|-------------|-----------------|
| Consent records (ToS, age) | Bot/app servers (ours) | Us | ❌ Never |
| Audit trail (GDPR requests) | Bot/app servers (ours) | Us | ❌ Never |
| Conversation history | Bot/app servers (ours) | Us | ❌ Backup only |
| User memories | Bot/app servers + miners | Us + miners | ✅ Encrypted (AES-128) |
| Conversation content | Transient during query | Miners (during processing) | ✅ For response generation |

**For legal disputes:** All consent records, age verification, and audit trails are accessible via `GET /api/v1/legal/consent-record/{user_id}`. No miner cooperation needed.

**Mainnet commitment:** We will always operate the bot/app layer and at least one validator, ensuring legal data remains under our control and GDPR requests can always be fulfilled.

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
- Owner receives mandatory 18% take, burns 100% via `burn_alpha()` — zero profit (on-chain verifiable)
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
│   │   ├── reward.py     # Scoring functions (incl. safety multiplier, TEE bonus, diversity)
│   │   └── query_generator.py  # Dynamic test queries + adversarial safety probes
│   ├── safety/
│   │   ├── content_filter.py   # Dual-stage content filter (pre/post LLM)
│   │   └── dependency_monitor.py  # 4-level dependency intervention system
│   ├── compliance/
│   │   ├── gdpr.py        # GDPR DSR handler (5 rights)
│   │   ├── consent.py     # Consent management + versioning
│   │   ├── retention.py   # Data retention policy
│   │   └── pia.py         # Privacy Impact Assessment
│   ├── privacy/
│   │   ├── tee_encryption.py   # AES-256-GCM + HPKE key wrapping (Phase 1+2)
│   │   └── tee_attestation.py  # AMD SEV-SNP attestation verification (Phase 3)
│   ├── burn/
│   │   ├── tracker.py     # Burn emission history tracker
│   │   └── verifier.py    # On-chain burn verification
│   ├── base/             # Base neuron classes (bt template)
│   └── utils/            # Config, UID selection, logging
├── app/
│   ├── bot.py            # Telegram bot — ContentFilter, AgeGate, DependencyMonitor wired in
│   └── discord_bot.py    # Discord companion
├── api/
│   └── server.py         # FastAPI — incl. /api/v1/gdpr/*, /api/v1/burns/*, encrypted chat/memory endpoints
├── mobile/               # React Native (Expo) mobile scaffold — RN 0.76.6
├── docs/                 # All documentation
├── scripts/
│   ├── burn_emissions.py        # Emission burn automation
│   ├── setup_tee_miner.sh       # TEE miner automated setup
│   ├── stress_test_10k.py       # 10K stress test suite
│   └── ...                      # Deployment & monitoring scripts
└── setup.py              # Package installation
```

---

*This document describes the ACTUAL implemented system as of March 2026.*
*Future features are explicitly marked as "Not Yet Built" or "Planned".*
