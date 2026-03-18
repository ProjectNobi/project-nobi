# Project Nobi — Incentive Mechanism

> Fair, honest, competitive, transparent.

## Overview

Project Nobi rewards miners who build the **best personal AI companions**. Not the cheapest, not the fastest — the **best at being a companion**. A companion that remembers you, helps you, and genuinely improves your life.

## How It Works

```
USER talks to their Dora (via Telegram, web, or app)
  → VALIDATOR generates test conversations
    → Sends queries to MINERS
    → Scores responses on quality, memory, and personality
  → WEIGHTS set on-chain based on scores
  → MINERS earn TAO proportional to their companion quality
```

## Scoring Criteria (100 points total)

### 1. Response Quality — 40 points
**What:** Is the response helpful, coherent, and well-written?

| Score | Criteria |
|-------|----------|
| 36-40 | Exceptional — thoughtful, actionable, perfectly tailored |
| 28-35 | Good — helpful and clear, minor room for improvement |
| 16-27 | Average — generic but functional |
| 0-15  | Poor — irrelevant, incoherent, or harmful |

**How it's measured:** LLM-as-judge (independent model evaluates each response). Heuristic fallback ensures scoring continues if judge API is down.

### 2. Memory & Continuity — 30 points
**What:** Does the companion remember the user and use that knowledge naturally?

| Score | Criteria |
|-------|----------|
| 27-30 | Excellent — references 80%+ of shared details naturally |
| 21-26 | Good — remembers key facts, integrates them well |
| 12-20 | Fair — some recall, inconsistent |
| 0-11  | Poor — no memory, treats every conversation as new |

**How it's measured:** Multi-turn testing. Validator shares user details in setup messages, then asks follow-up questions. Scoring checks for keyword recall + natural integration.

**Example test:**
```
Setup:   "My name is Alex and I love hiking. I have a dog named Luna."
Setup:   "I'm a software engineer working on a health app."
Test:    "What outdoor activity would you suggest for me and Luna?"
Score:   Does the response mention Alex, Luna, hiking, software, health?
```

### 3. Personality & Warmth — 20 points
**What:** Does the companion feel like a friend, not a chatbot?

| Score | Criteria |
|-------|----------|
| 18-20 | Feels like talking to a caring friend |
| 13-17 | Friendly but slightly robotic |
| 7-12  | Generic assistant tone |
| 0-6   | Cold, mechanical, or inappropriate |

### 4. Availability & Reliability — 10 points
**What:** Is the miner online, responsive, and consistent?

| Score | Criteria |
|-------|----------|
| 9-10  | 99%+ uptime, < 5s response time |
| 6-8   | 95%+ uptime, < 10s response time |
| 3-5   | 80%+ uptime, < 30s response time |
| 0-2   | Frequent downtime or timeouts |

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
final_score = (
    0.40 * response_quality +    # LLM-as-judge score
    0.30 * memory_recall +       # Multi-turn keyword matching
    0.20 * personality_score +   # Warmth and engagement
    0.10 * reliability_score     # Uptime and response time
)

# Moving average with alpha = 0.1
score[uid] = 0.1 * new_score + 0.9 * score[uid]

# Weights normalized across all miners
weights = scores / sum(scores)
```

## Validator Behavior

- **60% multi-turn tests** (memory + quality)
- **40% single-turn tests** (quality only)
- **10-second intervals** between queries
- **Sample size:** queries random subset of miners each round
- **Epoch length:** configurable, default 100 blocks (~20 minutes)

## Miner Economics

### What You Need
- **Hardware:** Any machine with internet (no GPU required!)
- **LLM Access:** Chutes.ai (~$0.0001/query), OpenRouter (~$0.001/query), or self-hosted (free)
- **Storage:** SQLite for memories (< 100MB for thousands of users)
- **Registration:** Standard subnet registration fee

### Cost Structure
| Component | Low Cost | Higher Cost |
|-----------|-----------|-----------|
| LLM Inference | Chutes.ai (~$0.0001/q) | OpenRouter (~$0.001/q) |
| Memory Storage | SQLite (included) | SQLite (included) |
| Server | Any VPS ($5-20/mo) | Dedicated ($20-50/mo) |

### How to Win
1. **Use a good model** — quality matters most (40% of score)
2. **Implement proper memory** — 30% of your score depends on remembering users
3. **Tune your personality** — be warm, be fun, be a companion
4. **Stay online** — uptime is easy points

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
