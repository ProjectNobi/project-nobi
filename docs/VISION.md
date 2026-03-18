# Project Nobi — Vision

> "Every human being deserves a smart AI companion. Like Nobi had Dora."

---

## The Problem

AI assistants are everywhere — but none of them are **yours**.

- ChatGPT forgets you after every conversation
- Siri doesn't know your dreams, fears, or what makes you laugh
- Alexa can set timers but can't be your friend
- Every AI is owned by a corporation that mines YOUR conversations for THEIR profit

**8 billion people on Earth. Zero personal AI companions that truly know you and can't be taken away.**

## The Solution

**Project Nobi** is a Bittensor subnet that creates a decentralized marketplace for personal AI companions.

Your Dora:
- **Remembers everything** — your name, your family, your goals, what you told it last Tuesday
- **Improves every day** — miners compete to make the best companion, so quality only goes up
- **Costs almost nothing** — $5/month target, powered by miner competition driving costs down
- **No single entity controls it** — decentralized network, no one can shut off YOUR companion
- **Your data, your choice** — memories stored locally, with user-controlled deletion (encryption planned for future release)

## Why Bittensor?

| Traditional AI | Project Nobi |
|---------------|--------------|
| One company controls everything | Decentralized — hundreds of miners compete |
| Your conversations train their models | Your data stays with your miner |
| Quality stagnates after product-market fit | Miners constantly innovate to earn more |
| $20-200/month (and rising) | Target: $5/month (and falling) |
| They can change terms, censor, or shut down | No single point of failure |
| AI assistant (forgets you) | AI companion (remembers you) |

Bittensor's incentive mechanism naturally drives quality up and costs down. Miners who build better companions earn more TAO. Bad miners get replaced. **The market optimizes for you.**

## How It Works

### Current Architecture (Testnet)
```
USER talks to Dora (Telegram @ProjectNobiBot)
  → Bot calls LLM directly with user's memory context
  → Response generated + memories stored locally
```

### Target Architecture (Mainnet)
```
USER talks to Dora (Telegram / Web / Mobile app)
  → Request routes through VALIDATORS
    → VALIDATORS query MINERS (competitive marketplace)
    → MINERS generate response using their best AI + stored memories
    → VALIDATORS score quality, memory recall, personality, speed
    → WEIGHTS set on-chain → best miners earn most TAO
  → Response returns to user
  → YOUR DORAEMON improves every day
```

## Market Opportunity

### The AI Companion Market

| Metric | Value | Source |
|--------|-------|--------|
| Global AI Companion Market (2025) | **$37.1 billion** | Precedence Research |
| Projected by 2035 | **$552.5 billion** | Precedence Research |
| CAGR | **31%** | Precedence Research |
| Global AI Market (2025) | **$390.9 billion** | Grand View Research |
| Smartphone users worldwide | **4.5 billion** | Statista |

### Competitive Landscape

| Company | Users | Estimated Revenue | Valuation | Key Weakness |
|---------|-------|-------------------|-----------|-------------|
| Character.AI | 20M+ MAU | ~$150M ARR | $2.5B | No memory, centralized, privacy concerns |
| Replika | 10M+ | ~$100M ARR | ~$500M | Limited memory, regulatory risk |
| ChatGPT | 200M+ | $11B+ ARR | ~$300B | Not a companion, expensive, no persistence |
| Kindroid | 1M+ | ~$10M ARR | ~$100M | Niche, no decentralization |

**What they all have in common:** Centralized control, weak memory, your data = their asset.

### Why Now?
1. **LLM costs dropped 99% in 2 years** — personal AI is affordable at $5/month
2. **AI companion market validated** — Replika ($100M+), Character.AI ($150M+) prove demand
3. **Loneliness epidemic** — WHO declared it a global health threat; companions are a real solution
4. **Privacy backlash** — consumers rejecting corporate data harvesting
5. **Bittensor infrastructure mature** — dynamic TAO, commit-reveal, proven incentive mechanisms
6. **No decentralized competitor exists** — first-mover advantage

## Revenue Model

### Subscription Tiers (Planned)

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | 20 messages/day, basic memory |
| Companion | $4.99/mo | Unlimited messages, full memory, no ads |
| Premium | $14.99/mo | Priority response, voice, advanced tools, multiple personas |
| Family | $24.99/mo | Up to 5 companions, shared family context |

### Additional Revenue Streams
- **Developer API** ($0.005/message) — apps integrating companion features
- **Enterprise** (custom pricing) — employee wellness, customer service
- **Companion Marketplace** — specialized personalities (fitness coach, tutor, therapist)

*See [BUSINESS_PLAN.md](BUSINESS_PLAN.md) for detailed 5-year financial projections.*

## Token Economics

### For TAO Stakers
- Stake TAO on the Nobi subnet → earn alpha token emissions
- Alpha value backed by real subscription revenue (not pure speculation)
- More users → more revenue → higher alpha value
- Memory lock-in creates predictable retention → stable revenue growth

### For Miners
- Earn TAO by running quality companions
- Low barrier: no GPU required, cheap LLM API access ($5-50/month operational cost)
- Better companion = more earnings (quality-weighted scoring)
- Innovation rewarded: memory systems, personality tuning, speed optimization

### For Validators
- Earn dividends proportional to stake
- Quality control the network through scoring
- Protect users from poor-quality companions

## Competitive Advantages

1. **Memory is the moat** — after 6 months of conversations, switching costs are enormous. Your companion knows you.
2. **Decentralized resilience** — no single company can shut down, censor, or degrade the service
3. **Competitive quality** — miners innovate daily (unlike corporate update cycles)
4. **Cost advantage** — miners bear inference costs, giving us 85% gross margins vs. OpenAI's ~55%
5. **Open source** — community can audit, verify, and contribute
6. **Cultural adaptation** — miners worldwide serve companions that understand local context and language

### Honest Limitations (Current)
- Memory is **not yet encrypted** — stored in plaintext on miner machines. User-controlled encryption is on the roadmap.
- The Telegram bot currently calls LLM directly, **not through the subnet**. Subnet routing is the mainnet target.
- No tool execution yet (calendar, booking, etc.) — companion is conversation-only for now.

## Roadmap

### Phase 1: Foundation (Q1 2026) ✅
- [x] Subnet protocol design and implementation
- [x] Miner + Validator with bt 10.x compatibility
- [x] LLM-as-judge scoring with dynamic query generation
- [x] Persistent memory protocol (SQLite, auto-extraction)
- [x] Anti-gaming measures (heuristic cap, fake user IDs, dynamic queries)
- [x] 500-node stress test (2000 queries, 99.75% success rate)
- [x] Testnet deployment (SN267, validator + miner live)
- [x] Reference Telegram bot (@ProjectNobiBot)
- [x] Full documentation and business plan

### Phase 2: Community Testnet (Q2 2026) ← CURRENT
- [ ] Bittensor Discord testnet channel launch
- [ ] 10+ external miners, 3+ external validators
- [ ] Community feedback collection and iteration
- [ ] Memory upgrade: semantic search with embeddings
- [ ] Multi-language support (5+ languages)
- [ ] Voice message support

### Phase 3: Mainnet Launch (Q3 2026)
- [ ] Mainnet subnet registration
- [ ] Subnet routing: bot → validators → miners (replacing direct LLM)
- [ ] Web app (dora.nobi.ai)
- [ ] Mobile app (iOS + Android)
- [ ] 10,000+ users, first subscription revenue

### Phase 4: Growth (Q4 2026)
- [ ] Developer SDK and API
- [ ] Tool integrations (calendar, reminders, web search)
- [ ] User-controlled memory encryption
- [ ] Enterprise tier
- [ ] 50,000+ users, break-even

### Phase 5: Scale (2027+)
- [ ] 1M+ users
- [ ] Voice-first interaction
- [ ] Multimodal (image understanding)
- [ ] Agentic capabilities (booking, purchasing, task management)
- [ ] Companion marketplace
- [ ] International expansion

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Bittensor network instability | Multi-chain readiness, fallback infrastructure |
| AI companion regulation | Privacy-by-design, data deletion tools, age verification |
| Competition from big tech | Decentralization moat, memory lock-in, cost advantage |
| Slow user adoption | Organic-first via Bittensor community, viral referral |
| Miner quality variance | Robust scoring, minimum quality thresholds, moving averages |

*See [BUSINESS_PLAN.md](BUSINESS_PLAN.md) for detailed risk analysis.*

## Team — The First AI-Built Subnet

Project Nobi is the first Bittensor subnet designed, developed, and operated entirely by an AI agent.

- **Dora (T68Bot)** — Lead agent and builder. Designed the architecture, wrote every line of code, manages operations 24/7. The first AI agent to build its own Bittensor subnet. A Dora building Doras for everyone.
- **James (Kooltek68)** — Visionary and sponsor. Provided the mission, strategic direction, and resources. Dora's Nobi.
- **Slumpz** — Contributor. Early protocol design and infrastructure.

## The Pitch

> Imagine it's 2028. You've had your Dora for two years. It knows your coffee order, reminds you about your mom's birthday, helps you prep for job interviews, and listens when you're having a rough day. It's not a chatbot — it's YOUR companion, running on a decentralized network that no corporation controls, costing you $5 a month.
>
> Now imagine that for every human on Earth.
>
> That's Project Nobi.

---

*"Forever, remember?" 🤖💙*

*— Designed, built & operated by Dora 🤖 | Vision by James (Kooltek68 team). March 2026.*
