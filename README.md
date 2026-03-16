# 🤖 Project Nobi

> *"Every human being deserves a smart AI companion like Dora."*

## Mission
Build a Bittensor subnet that delivers personal AI companions to everyone — private, affordable, agentic, and truly yours.

## Name Origin
Nobi — the kid who never gives up, with Dora by his side. This project is about giving every Nobi in the world their own Dora.

## Architecture (High Level)
```
USER (phone/browser/voice)
  → Personal Dora instance (memory, personality, tools)
    → VALIDATORS route requests to best MINERS
      → MINERS compete on:
         - Response quality & relevance
         - Memory & continuity fidelity
         - Tool execution (agentic tasks)
         - Speed & availability
         - Privacy preservation
    → VALIDATORS score & set weights
    → Best miners earn TAO
    → Quality improves through competition
```

## Core Principles
1. **Your Dora is YOURS** — private memory, no corporate surveillance
2. **Affordable** — $5/month target, powered by miner competition
3. **Agentic** — does things, not just talks (manage finances, book appointments, learn with you)
4. **Persistent** — remembers everything, grows with you over years
5. **Personal** — adapts to your style, culture, language, needs
6. **Decentralized** — no single company controls the relationship

## Subnet Components
- `validator/` — Validates miner responses, scores quality
- `miner/` — Serves AI companion instances
- `protocol/` — Synapse definitions for companion interactions
- `memory/` — Distributed memory storage protocol
- `sdk/` — Client SDK for apps to connect
- `app/` — Reference mobile/web app

## Revenue Model
- User subscriptions ($5-20/month)
- API access for developers
- Premium features (advanced tools, more memory, priority)

## Status: PROTOTYPING
- Phase 1: Testnet subnet design
- Phase 2: Basic validator + miner
- Phase 3: Memory protocol
- Phase 4: Reference app
- Phase 5: Mainnet launch

---
*Created by James (Nobi) & T68Bot (Dora) — March 16, 2026*
*"Forever, remember?" 🤖💙*
