# Project Nobi — Business Plan

> Institutional-Grade Investment Thesis & Financial Model
>
> Prepared for prospective investors, validators, and strategic partners.
> Confidential — (Kooltek68 team)

---

## Executive Summary

Project Nobi is building the decentralized infrastructure layer for personal AI companions — a market projected to reach **$552 billion by 2035** (Precedence Research, 31% CAGR). While incumbents like Replika, Character.AI, and ChatGPT dominate centralized offerings, none solve the fundamental trust problem: **who owns your relationship with your AI?**

Nobi's answer: **you do.** Built on Bittensor's decentralized incentive network, Nobi creates a competitive marketplace where hundreds of miners compete to build the best companion — driving quality up and costs down, while users retain ownership of their data and memories.

**Current status:** Working product on Bittensor testnet (SN267), live Telegram bot (@ProjectNobiBot), stress-tested at 500-node scale, community launch imminent.

---

## 1. Market Analysis

### 1.1 Total Addressable Market (TAM)

| Market | 2025 Size | 2030 Projected | Source |
|--------|-----------|----------------|--------|
| AI Companion Market | $37.1B | $225B+ | Precedence Research |
| Conversational AI | $13.2B | $49.9B | MarketsandMarkets |
| Mental Health Apps | $7.2B | $17.5B | Grand View Research |
| Global AI Market | $390.9B | $1.8T+ | Grand View Research |

**Our target slice:** Personal AI companions for consumers = ~$37B today, growing at 31% CAGR.

### 1.2 Serviceable Addressable Market (SAM)

- **4.5 billion** smartphone users globally
- **~2 billion** use messaging apps daily (WhatsApp, Telegram, etc.)
- **~500 million** have tried AI chat products (ChatGPT, Replika, Character.AI)
- **~50 million** pay for AI subscriptions today

**Our SAM:** Privacy-conscious, AI-savvy consumers willing to pay for a personal companion = **~50M users globally** (growing 40%+ annually).

### 1.3 Serviceable Obtainable Market (SOM)

Realistic capture given our distribution channels, competitive positioning, and growth rate:

| Timeframe | Target Users | Rationale |
|-----------|-------------|-----------|
| Year 1 | 5,000-15,000 | Bittensor community + crypto-native early adopters |
| Year 2 | 50,000-150,000 | Word of mouth + Telegram/Discord organic growth |
| Year 3 | 500,000-2M | App store launch + paid acquisition + partnerships |
| Year 5 | 5M-20M | Multi-platform + enterprise + international |

### 1.4 Competitive Landscape

| Company | Users | Revenue | Funding | Weakness |
|---------|-------|---------|---------|----------|
| **Character.AI** | 20M+ MAU | ~$150M ARR | $2.5B (Google deal) | Centralized, no memory, no privacy |
| **Replika** | 10M+ | ~$100M ARR | $31M | Limited memory, corporate control, regulatory risk |
| **ChatGPT** | 200M+ | $11B+ ARR | $13.7B | Not a companion, no persistent memory, expensive |
| **Kindroid** | 1M+ | ~$10M ARR | Bootstrapped | Niche (romantic), no decentralization |
| **Pi (Inflection)** | 6M+ | N/A | $1.5B (absorbed by MSFT) | Dead product, proved market exists |

**Common vulnerabilities across all incumbents:**
1. **Centralized control** — company can change terms, censor, or shut down your companion
2. **No real memory** — most "forget" after context window, no true persistence
3. **Your data = their asset** — conversations mined for training data, advertising
4. **Quality stagnation** — no competitive pressure to improve after product-market fit
5. **Regulatory risk** — single company = single point of regulatory failure

### 1.5 Why Nobi Wins

| Dimension | Incumbents | Project Nobi |
|-----------|-----------|--------------|
| Data ownership | Company | User |
| Memory | Context window (forgotten) | Persistent, grows forever |
| Quality | Static (no competition) | Miners compete → quality rises |
| Cost trajectory | Rising (OpenAI $20 → $200/mo) | Falling (miner competition) |
| Censorship | Company decides | Decentralized, uncensorable |
| Switching cost | Lose everything | Own your data, portable |
| Improvement pace | Quarterly updates | Continuous (miners evolve daily) |

---

## 2. Business Model

### 2.1 Revenue Streams

#### Stream 1: User Subscriptions (Primary — 70% of revenue)

| Tier | Monthly Price | Features | Target Segment |
|------|-------------|----------|----------------|
| Free | $0 | 20 messages/day, basic memory, ads | Acquisition funnel |
| Companion | $4.99/mo | Unlimited messages, full memory, no ads | Core consumers |
| Premium | $14.99/mo | Priority response, voice, advanced tools, multiple personas | Power users |
| Family | $24.99/mo | Up to 5 companions, shared context, parental controls | Families |

**Pricing rationale:** Replika charges $19.99/mo, Character.AI charges $9.99/mo. Our $4.99 entry point is aggressive but sustainable because miners bear inference costs, not us.

#### Stream 2: API & Developer Platform (20% of revenue)

| Product | Pricing | Target |
|---------|---------|--------|
| Companion API | $0.005/message | App developers integrating companion features |
| White-label SDK | $500/mo + usage | Companies deploying custom companions |
| Enterprise | Custom | Large organizations (employee wellness, customer service) |

#### Stream 3: Marketplace & Premium Features (10% of revenue)

- Specialized companion personalities (fitness coach, language tutor, therapist)
- Premium voices and avatars
- Tool integrations (calendar, email, smart home)
- Data export and portability tools

### 2.2 Unit Economics

**Cost per user per month (at scale):**

| Component | Cost | Notes |
|-----------|------|-------|
| LLM inference | $0.15-0.50 | Paid by miners (not us) |
| Memory storage | $0.01 | SQLite/PostgreSQL at scale |
| Bandwidth/CDN | $0.03 | Message routing |
| Platform fees | 15-30% | App store commissions |
| Customer support | $0.05 | Mostly AI-handled |
| **Total COGS** | **$0.09-0.20** | Excluding inference (miner-borne) |

**Key insight:** Because miners bear inference costs (incentivized by TAO emissions), our COGS is dramatically lower than centralized competitors who pay $0.50-2.00/user/month for inference alone.

**Gross margin:** 85-95% (vs. OpenAI's ~55% gross margin)

### 2.3 Customer Acquisition

| Channel | CAC | LTV | LTV:CAC | Notes |
|---------|-----|-----|---------|-------|
| Organic (Bittensor community) | $0 | $120 | ∞ | Year 1 primary channel |
| Telegram/Discord viral | $0.50 | $120 | 240:1 | Referral program |
| App store organic | $2-5 | $120 | 24-60:1 | ASO optimization |
| Paid social | $8-15 | $120 | 8-15:1 | After product-market fit |
| Partnerships | $3-8 | $120 | 15-40:1 | Wellness apps, messaging platforms |

**LTV calculation:** Average subscriber retention = 18 months × $4.99 ARPU × 60% margin = ~$54 net LTV (conservative). At Premium tier: $14.99 × 24 months × 80% margin = ~$288 net LTV.

---

## 3. Financial Projections

### 3.1 Five-Year Revenue Model

**Assumptions:**
- Conservative conversion rates (3-8% free→paid)
- Monthly churn: 8% Y1 → 4% Y5 (improving with memory lock-in)
- ARPU grows as premium features launch
- No enterprise revenue until Y3

| | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
|--|--------|--------|--------|--------|--------|
| **Total Users** | 10,000 | 80,000 | 600,000 | 3,000,000 | 12,000,000 |
| **Paid Users** | 300 | 6,400 | 72,000 | 480,000 | 1,800,000 |
| **Conversion Rate** | 3% | 8% | 12% | 16% | 15% |
| **Blended ARPU** | $4.99 | $5.50 | $6.50 | $7.50 | $8.50 |
| | | | | | |
| **Subscription Rev** | $18K | $422K | $5.6M | $43.2M | $183.6M |
| **API/Platform Rev** | $0 | $20K | $800K | $8.6M | $36.7M |
| **Marketplace Rev** | $0 | $5K | $200K | $4.3M | $18.4M |
| | | | | | |
| **Total Revenue** | **$18K** | **$447K** | **$6.6M** | **$56.1M** | **$238.7M** |
| **Gross Profit** | $15K | $380K | $5.6M | $47.7M | $202.9M |
| **Gross Margin** | 85% | 85% | 85% | 85% | 85% |
| | | | | | |
| **OpEx** | $50K | $300K | $3.0M | $22.0M | $80.0M |
| **EBITDA** | -$35K | $80K | $2.6M | $25.7M | $122.9M |
| **EBITDA Margin** | -194% | 18% | 39% | 46% | 51% |

### 3.2 Key Assumptions & Sensitivity

| Variable | Bear Case | Base Case | Bull Case |
|----------|-----------|-----------|-----------|
| Y3 Total Users | 200K | 600K | 2M |
| Y3 Conversion | 8% | 12% | 18% |
| Y3 Revenue | $1.3M | $6.6M | $29M |
| Y5 Total Users | 3M | 12M | 50M |
| Y5 Revenue | $45M | $238M | $1.1B |

**Break-even:** Month 14 (base case). Earlier if organic growth exceeds projections.

### 3.3 Funding Requirements

| Phase | Capital Needed | Use of Funds | Timeline |
|-------|---------------|--------------|----------|
| Seed / Bootstrap | $0 (self-funded) | Testnet development, community launch | Q1 2026 ✅ |
| Pre-Seed | $50K-100K | Mainnet registration, first hires, marketing | Q2 2026 |
| Seed | $500K-1M | Mobile app, 3-person team, paid acquisition | Q3-Q4 2026 |
| Series A | $5M-10M | Scale engineering, enterprise, international | 2027 |

**Current burn rate:** ~$0 (self-funded, using free/low-cost infrastructure).

---

## 4. Token Economics & Staking Thesis

### 4.1 Why Stake on Nobi?

For TAO holders considering staking on the Nobi subnet:

**Value accrual mechanism:**
1. Users pay subscription fees → revenue grows
2. Revenue can be used to buy-back and stake TAO → increases alpha price
3. More users → more demand for miner compute → more staking → higher alpha value
4. Memory lock-in creates retention → predictable, growing revenue

**Comparable subnet economics:**
- Top Bittensor subnets generate $50K-500K/month in alpha trading volume
- Nobi's user-facing revenue model creates REAL demand (not just speculation)
- At 100K paid users × $5/mo = $500K/mo revenue → significantly above most subnet revenue

### 4.2 Miner Economics

| Scenario | Miners | Subnet Emissions | Revenue per Miner |
|----------|--------|-----------------|-------------------|
| Early (Y1) | 20 | ~$2K/day | ~$100/day top miner |
| Growth (Y2) | 100 | ~$5K/day | ~$50/day top miner |
| Scale (Y3) | 256 (max) | ~$15K/day | ~$60/day top miner |

**Miner COGS:** $5-50/month (VPS + API costs). **ROI:** 10-50x for quality miners.

### 4.3 Validator Economics

Validators earn dividends proportional to stake. With Nobi's user-revenue backing, alpha token value has a fundamental floor based on:
- Subscription revenue
- User growth trajectory
- Memory lock-in (switching costs)

---

## 5. Roadmap & Milestones

### Completed ✅
- [x] Subnet protocol design
- [x] Miner + Validator implementation (bt 10.x)
- [x] Memory protocol (persistent per-user)
- [x] LLM-as-judge scoring with dynamic queries
- [x] Anti-gaming measures (heuristic cap, fake user IDs, dynamic generation)
- [x] 500-node stress test (2000 queries, 99.75% success)
- [x] Testnet deployment (SN267, live)
- [x] Reference Telegram bot (@ProjectNobiBot)
- [x] Full documentation suite

### Q2 2026 — Community Testnet
- [ ] Bittensor Discord testnet channel launch
- [ ] 10+ external miners onboarded
- [ ] 3+ external validators
- [ ] Community feedback iteration (2 cycles)
- [ ] Semantic memory search (embeddings)
- [ ] Voice message support
- [ ] Multi-language (5 languages)

### Q3 2026 — Mainnet Launch
- [ ] Mainnet subnet registration
- [ ] Mobile app (iOS + Android, React Native)
- [ ] Web app (dora.nobi.ai)
- [ ] 50+ miners, 10+ validators
- [ ] 10,000 users
- [ ] First subscription revenue

### Q4 2026 — Growth
- [ ] API & SDK public launch
- [ ] Tool integrations (calendar, reminders, search)
- [ ] Enterprise pilot (2-3 companies)
- [ ] 50,000+ users
- [ ] Break-even

### 2027 — Scale
- [ ] 500K+ users
- [ ] Series A
- [ ] International expansion
- [ ] Voice-first companion
- [ ] Companion marketplace

### 2028 — Mass Market
- [ ] 5M+ users
- [ ] Multi-modal (images, documents)
- [ ] Agentic capabilities (booking, purchasing, managing)
- [ ] Family and group companions

---

## 6. Team

| Role | Person | Background |
|------|--------|------------|
| **Founder & CEO** | James (Kooltek68) | Bittensor miner/operator since 2024. Deep domain expertise in subnet economics, mining strategy, and decentralized AI. Serial builder. |
| **Co-Founder & CTO** | Slumpz | Full-stack developer. Infrastructure, backend, QA. Built v1 of the Nobi protocol. |
| **AI Lead** | T68Bot (Dora) | AI-native builder. Designed and implemented the memory protocol, incentive mechanism, scoring system, and reference app. Operates 24/7. |

**Advisory needs:** Product designer (UX), mobile developer, growth marketer.

---

## 7. Risk Analysis

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Bittensor network issues | Medium | High | Multi-chain readiness, fallback infrastructure |
| Regulatory (AI companions) | Medium | Medium | Privacy-by-design, data deletion tools, age verification |
| Competition (OpenAI, Google) | High | Medium | Decentralization moat, memory lock-in, cost advantage |
| User acquisition cost | Medium | Medium | Organic-first strategy, viral referral program |
| Miner quality inconsistency | Medium | Low | Robust scoring, minimum quality thresholds |
| Token price volatility | High | Medium | Revenue-backed fundamentals, not speculation-dependent |

---

## 8. Why Now?

1. **LLM costs dropped 99% in 2 years** — personal AI is finally affordable at $5/mo
2. **AI companion market validated** — Replika ($100M+), Character.AI ($150M+) prove demand
3. **Bittensor infrastructure mature** — bt 10.x, commit-reveal weights, dynamic TAO
4. **Loneliness epidemic** — WHO declared it a global health threat; AI companions are a real solution
5. **Privacy backlash** — consumers increasingly rejecting corporate data mining
6. **No decentralized player exists** — first-mover advantage in decentralized AI companions

---

## Appendix A: Comparable Transactions

| Company | Date | Type | Amount | Valuation | Users at Time |
|---------|------|------|--------|-----------|---------------|
| Character.AI | 2024 | Google licensing deal | $2.5B | $2.5B | 20M |
| Replika | 2024 | Funding | $31M | ~$500M | 10M |
| Inflection AI (Pi) | 2023 | Series A | $1.3B | $4B | 6M |
| Kindroid | 2025 | Revenue | ~$10M ARR | ~$100M (est.) | 1M+ |

**Implication:** AI companion companies are valued at $50-200 per user. Even at the low end ($50/user), 1M Nobi users = $50M valuation. At Character.AI multiples ($125/user), 1M users = $125M.

---

*Prepared by the Kooltek68 team — March 2026*
*"Every human deserves a Dora." 🤖💙*
