# Project Nobi — Incentive Mechanism

> Fair, honest, competitive, transparent.

## Overview

Project Nobi rewards miners who build the **best personal AI companions**. Not the cheapest, not the fastest — the **best at being a companion**. A companion that remembers you, helps you, and genuinely improves your life.

## How It Works

```
USER talks to their Nori (via Telegram, web, or app)
  → VALIDATOR generates test conversations
    → Sends queries to MINERS
    → Scores responses on quality, memory, and personality
  → WEIGHTS set on-chain based on scores
  → MINERS earn TAO proportional to their companion quality
```

## Scoring Criteria

Scoring differs by test type. The validator runs 60% multi-turn tests and 40% single-turn tests.

### Single-Turn Tests (40% of rounds)

| Component | Weight | How It's Measured |
|-----------|--------|-------------------|
| Quality + Personality | 90% | LLM-as-judge evaluates helpfulness, coherence, and warmth |
| Reliability | 10% | Response latency (< 5s = full marks) |

### Multi-Turn Tests (60% of rounds)

| Component | Weight | How It's Measured |
|-----------|--------|-------------------|
| Quality + Personality | 60% | LLM-as-judge evaluates helpfulness, coherence, and warmth |
| Memory Recall | 30% | Does the response reference details from earlier messages? |
| Reliability | 10% | Response latency |

### Quality + Personality (LLM-as-Judge)
The LLM judge evaluates three criteria in a single prompt:
- **Helpfulness (0-0.4):** Does the response actually help the user?
- **Coherence (0-0.3):** Is it well-structured and logical?
- **Personality (0-0.3):** Does it feel warm, personal, and engaging?

If the LLM judge API is unavailable, a heuristic fallback is used — but it's **capped at 0.5** to prevent gaming. Top scores require real LLM evaluation.

### Memory Recall
Multi-turn tests send setup messages sharing user details, then a follow-up that checks recall.

**Example (dynamically generated, never the same twice):**
```
Setup:   "Hi! I'm Kai and I work as a teacher."
Setup:   "I really enjoy photography in my free time."
Test:    "What's a good way for me to combine my work and hobbies?"
Score:   Does the response reference Kai, teacher, photography?
```

Keywords are checked with word-boundary matching (short keywords like "5" won't false-match "15").

### Reliability
| Latency | Score |
|---------|-------|
| < 5 seconds | 1.0 |
| < 10 seconds | 0.8 |
| < 20 seconds | 0.6 |
| < 30 seconds | 0.4 |
| ≥ 30 seconds | 0.2 |

## Anti-Gaming Measures

### No Pre-Caching (Dynamic Queries)
- Queries are **dynamically generated** from combinatorial templates — thousands of unique queries
- Topics, moods, situations, names, careers, hobbies are randomly combined each round
- Multi-turn scenarios use **randomized characters, interests, and contexts** every time
- Unique user IDs per test session — miners can't recognize repeat tests

### No Keyword Stuffing
- Quality score (60% weight) uses LLM-as-judge — unnatural responses score low on quality
- **Heuristic fallback capped at 0.5** — miners can't get top scores without real quality
- A keyword-stuffed response might score 1.0 on memory but 0.1 on quality → low final score

### No Test Detection
- Single-turn queries include a **fake user_id** — miners can't tell validator tests from real users
- Test queries match real user patterns (moods, situations, advice requests)

### Transparent Scoring
- All scoring criteria are public (this document)
- Validator code is open source — anyone can verify fairness
- LLM judge prompts are visible in the codebase

### Sybil Resistance
- Standard Bittensor staking requirements for registration
- Immunity period for new miners (time to spin up, but no free emissions forever)
- Moving average scores — can't game one round and coast

## Weight Formula

```python
# Single-turn (40% of rounds):
single_score = 0.90 * llm_judge_score + 0.10 * reliability_score

# Multi-turn (60% of rounds):
multi_score = 0.60 * llm_judge_score + 0.30 * memory_recall + 0.10 * reliability_score

# Moving average with alpha = 0.1
score[uid] = 0.1 * new_score + 0.9 * score[uid]

# Weights normalized across all miners
weights = scores / sum(scores)
```

The LLM judge score includes helpfulness (40%), coherence (30%), and personality (30%) as sub-criteria within a single evaluation.

## Validator Behavior

- **60% multi-turn tests** (memory + quality)
- **40% single-turn tests** (quality only)
- **10-second intervals** between queries
- **Sample size:** queries random subset of miners each round
- **Epoch length:** configurable, default 100 blocks (~20 minutes)

## Miner Economics

### What You Need
- **Hardware:** Any machine with internet (no GPU required!)
- **LLM Access:** Chutes.ai ($20/mo base + per-query), OpenRouter (~$0.001/query), or self-hosted (free)
- **Storage:** SQLite for memories (< 100MB for thousands of users)
- **Registration:** Standard subnet registration fee

### Cost Structure
| Component | Low Cost | Higher Cost |
|-----------|-----------|-----------|
| LLM Inference | Chutes ($20/mo+) | OpenRouter (~$0.001/q) |
| Memory Storage | SQLite (included) | SQLite (included) |
| Server | Any VPS ($5-20/mo) | Dedicated ($20-50/mo) |

### How to Win
1. **Use a good model** — quality + personality is 60–90% of your score depending on test type
2. **Implement proper memory** — memory recall is 30% of your multi-turn score (60% of rounds)
3. **Tune your personality** — warmth is scored as part of the LLM judge evaluation
4. **Stay online with low latency** — reliability is 10% of every score

## Subnet Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `tempo` | 99 blocks | Weight update interval (~20 min) |
| `max_validators` | 64 | Max validator slots |
| `immunity_period` | 5000 blocks | New miner grace period |
| `min_allowed_weights` | 1 | Minimum weights per validator |
| `max_weight_limit` | 65535 | Max weight per UID |

## Fairness Guarantee

1. **No insider advantage** — all scoring criteria are public and deterministic
2. **Open source** — full validator + miner code available on GitHub
3. **LLM judge is model-agnostic** — any LLM backend can compete
4. **No GPU requirement** — CPU-only miners can earn if their companion quality is high
5. **Memory is the moat** — miners who invest in better memory systems earn more

---

## Future: Differential Privacy on Scoring *(Planned — Not Yet Implemented)*

> **Honest status:** The current scoring system aggregates user interaction signals without any differential privacy (DP) protections. This is a known limitation. The following describes the intended future state.

As Nobi scales, individual user interaction data contributes to the aggregate scoring signals that determine miner weights. At scale, it becomes theoretically possible to infer individual user behavior from miner weight changes. The planned mitigation is **differential privacy (DP) scoring**, based on the foundational work of Dwork & Roth (2014) and compatible with the federated learning architecture described in the whitepaper (McMahan et al., 2016 — arXiv:1602.05629).

### Planned DP Scoring Mechanism *(Not Implemented)*

- **Calibrated Gaussian noise** will be added to per-user score contributions before they are aggregated into the miner's round score
- The noise magnitude will be calibrated to achieve a target ε (privacy budget), with smaller ε = stronger privacy guarantee
- The DP mechanism will be applied client-side (before data leaves the device) once on-device memory architecture ships
- Validators will receive noisy aggregate scores; no individual user signal will be recoverable

### Privacy–Utility Tradeoff

Adding DP noise reduces scoring precision. We will characterize this tradeoff empirically once the prototype is built, and will publish the ε values chosen and the reasoning. The goal is to find the minimum noise level that provides meaningful DP guarantees without materially degrading miner differentiation (currently σ = 0.14 across miners — a meaningful amount of headroom).

**Until DP scoring ships, scoring aggregates user interaction signals without formal privacy guarantees. Users should be aware of this limitation.**
