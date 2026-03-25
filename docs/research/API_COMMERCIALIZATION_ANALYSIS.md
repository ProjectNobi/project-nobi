# Project Nobi — API Commercialization Strategy
## Comprehensive Business Analysis & Strategic Report

**Prepared by:** T68Bot (Senior Business Analyst)
**Date:** March 25, 2026
**Classification:** Internal — Confidential (James & Slumpz)
**Status:** Draft for Decision

---

## EXECUTIVE SUMMARY

Slumpz has proposed that Project Nobi maintain its core companion product as permanently free while opening a paid API tier for developers and businesses. This report provides a data-driven analysis of that proposal across legal, financial, technical, competitive, and mission-alignment dimensions.

**The core question:** Can Nobi earn revenue from API access without betraying the vision of "an AI companion that no company can take away from you"?

**Short answer:** YES — but only under specific conditions and with deliberate framing.

**Recommendation: CONDITIONAL YES**

The API commercialization proposal is viable and strategically sound, but must be implemented with strict safeguards:
1. The companion product must remain **unconditionally free** forever
2. The API must serve as an **extension layer** for builders, not a backdoor pricing mechanism for users
3. Legal structure (CIC) allows commercial trading — but this should be confirmed with a UK solicitor
4. Revenue should flow **back into the ecosystem** (infrastructure, open source development, community grants)
5. A **self-hosting option** must ship alongside the paid API — open source commitment preserved

**Key risks:** mission drift, community backlash in the crypto space, CIC legal constraints, and the technical complexity of billing infrastructure at an early stage.

**Market opportunity:** The global AI API market is valued at ~$64 billion in 2025 and growing at ~30% CAGR. Companion APIs are an underserved niche within this. Even 0.01% market capture represents significant revenue.

**Recommendation summary:** Proceed with a cautious Phase 1 pilot — developer free tier + waitlisted paid tier — before committing to full infrastructure. Validate demand before building billing.

---

## 1. MARKET RESEARCH

### 1.1 AI API Market Size

Multiple independent research firms converge on consistent figures:

| Source | 2024/2025 Value | 2030–2035 Projection | CAGR |
|--------|----------------|---------------------|------|
| Precedence Research | $64.41B (2025) | $901.34B (2035) | 30.19% |
| Grand View Research | $48.50B (2024) | $246.87B (2030) | 31.3% |
| Fortune Business Insights | ~$65B (est. 2025) | $783.33B (2034) | 31.91% |
| Econ Market Research | $85.43B (2026 est.) | $1,033B (2035) | 31.91% |

*Sources: Precedence Research (precedenceresearch.com/ai-api-market), Grand View Research (grandviewresearch.com), Fortune Business Insights, retrieved March 2026*

**Key takeaway:** The AI API market is in explosive growth. ~31% compound growth is one of the fastest sustained growth rates of any software market in history. The window for early positioning is now.

**Generative AI APIs** (the relevant subcategory for Nobi) held 37% market share in 2025 — the dominant segment. North America leads at 39% market share. This market is not slowing down.

### 1.2 Competitor API Pricing (Live Data — March 2026)

#### Major Closed-Source AI APIs

| Provider | Model | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|----------|-------|----------------------|------------------------|-------|
| OpenAI | GPT-5.4 (flagship) | $2.50 | $15.00 | Premium frontier model |
| OpenAI | GPT-5.4 mini | $0.75 | $4.50 | Mid-tier |
| OpenAI | GPT-5.4 nano | $0.20 | $1.25 | High-volume, budget |
| Anthropic | Claude Opus 4.6 | $5.00 | $25.00 | Top tier |
| Anthropic | Claude Sonnet 4.6 | $3.00 | $15.00 | Balanced |
| Anthropic | Claude Haiku 4.5 | $1.00 | $5.00 | Fast/cheap |
| Anthropic | Claude Haiku 3 | $0.25 | $1.25 | Budget tier |
| Cohere | Enterprise models | Custom enterprise pricing only | — | No public per-token rates |

*Sources: openai.com/api/pricing/, platform.claude.com/docs/en/about-claude/pricing — retrieved March 2026*

#### Open-Source & Inference Platforms

| Provider | Model Example | Input (per 1M tokens) | Output (per 1M tokens) | Notes |
|----------|--------------|----------------------|------------------------|-------|
| Groq | GPT OSS 20B (128k) | $0.075 | $0.30 | Extremely fast (1,000 TPS) |
| Groq | GPT OSS 120B (128k) | $0.15 | $0.60 | Fast inference |
| Groq | Kimi K2-0905 (1T) | $1.00 | ~$3.00 | Large MoE model |
| Together AI | Llama 4 Maverick | $0.27 | $0.85 | New frontier OSS |
| Together AI | Llama 3.3 70B | $0.88 | $0.88 | Established open model |
| Together AI | DeepSeek V3.1 | $0.60 | $1.70 | Strong performance |
| Together AI | Llama 3 8B Lite | $0.10 | $0.10 | Ultra-budget |
| Fireworks AI | <4B params | $0.10 | $0.10 | Size-based pricing |
| Fireworks AI | 4B–16B params | $0.20 | $0.20 | Mid-size models |
| Fireworks AI | >16B params | $0.90 | $0.90 | Large models |
| Fireworks AI | MoE 56B–176B | $1.20 | $1.20 | Large MoE |
| Replicate | Claude 3.7 Sonnet | $3.00 input | $15.00 output | Via Replicate |
| Replicate | Hardware-based | $0.40–$20.00/hr | — | GPU compute billing |

*Sources: groq.com/pricing, together.ai/pricing, fireworks.ai/pricing, replicate.com/pricing — retrieved March 2026*

#### Chutes.ai (Bittensor SN64) — Key Competitor

Chutes is the most directly relevant comparison as a Bittensor-based compute provider:

| Plan | Monthly Cost | Discount vs PAYG | Notes |
|------|-------------|-----------------|-------|
| Base | $3/month | 3% off | Entry tier |
| Plus | $10/month | 6% off | Frontier model access |
| Pro | $20/month | 10% off | Best value tier |
| Pay-as-you-go | Varies | — | Base rate |

Chutes also runs **fictio.ai** — a consumer companion product — alongside their developer API. This is the exact bifurcated model Slumpz is proposing. Worth studying carefully.

*Source: chutes.ai — retrieved March 2026*

#### Hugging Face — Monetization Model (Most Relevant Analog)

Hugging Face is the canonical "free product, paid API" model:
- **Hub:** Free — model hosting, datasets, collaboration
- **Spaces hardware:** Free tier (CPU Basic) + paid GPU upgrades ($0.03–$23.50/hr)
- **Inference Endpoints:** $0.033/hour base (dedicated deployments)
- **Storage:** $8–$18/TB/month (public vs private)
- **Enterprise:** Custom pricing

Key insight: HuggingFace has successfully separated "free open-source community" from "paid developer infrastructure" without breaking community trust. They are the template to follow.

*Source: huggingface.co/pricing — retrieved March 2026*

### 1.3 How Do Open-Source AI Tools Monetize?

| Project | Model | Revenue Source | Free Forever? |
|---------|-------|---------------|---------------|
| Hugging Face | Free Hub + paid compute | Hosted inference, Enterprise Hub, storage | Hub yes, compute no |
| Ollama | Free local runner | No revenue (VC-funded) | Yes |
| LM Studio | Free desktop app | No revenue (VC-funded) | Yes |
| LocalAI | Free self-host | No revenue (open source) | Yes |
| Replicate | Per-use compute billing | Per-second GPU billing | No |
| Together AI | Per-token inference | Per-token pricing | Free tier |
| Groq | Per-token inference | Per-token pricing | Free tier |

**Observation:** Truly free tools (Ollama, LM Studio) are VC-funded and not yet revenue-generating. Revenue-positive AI tools all monetize on compute/API access, not the core software. This validates the Slumpz proposal.

### 1.4 Bittensor Subnet Monetization Models

**Chutes.ai (SN64):**
- B2B compute marketplace: buy miner GPU time via Bittensor
- Subscription tiers ($3/$10/$20/month) + PAYG
- Consumer product (fictio.ai) as separate, distinct app
- API access sold commercially to developers and enterprises
- Partners: OpenRouter, Cline, KiloCode, Fetch.ai

**Corcel (retired/evolved):**
- Originally monetized Bittensor inference via developer API
- Had developer tier pricing (~$15/month circa 2024)
- Struggled with Bittensor network instability affecting API reliability
- Key lesson: **Bittensor reliability risk is real** — Corcel moved away from pure Bittensor dependence

**Taoshi (SN8):**
- Sells trading signal API subscriptions
- Plans charged per data access tier
- B2B focus: hedge funds, trading firms
- Revenue from professional/institutional API users

**Ecosystem pattern:** Successful Bittensor subnets treat the network as compute/intelligence source and build commercial API layers on top. Revenue flows back to subnet emissions/validators. This is a proven model.

---

## 2. VISION ALIGNMENT ANALYSIS

### 2.1 Does This Violate "Free For All Users"?

**Case FOR (it does NOT violate):**

The proposal is precisely scoped: the **companion product** stays free. Users never pay. The API tier targets **developers and businesses** — a categorically different customer. They are not "users" of the companion; they are builders using Nobi's infrastructure to build their own products. Charging infrastructure costs to infrastructure consumers is not a betrayal of users.

Analogies:
- Wikipedia is free to read. Wikipedia charges for data API access at scale, and has enterprise licensing.
- Linux is free. Red Hat Enterprise Linux costs money. The kernel is untouched.
- Signal is free for users. Signal has received grants from the EU, tech foundations, and ran a donation campaign — none of which users paid.
- Firefox is free. Mozilla earns ~$500M/year from Google search deal, enterprise support, and commercial services.

The pattern is universal: free for humans, paid for machines/businesses at scale.

**Case AGAINST (it COULD drift toward violation):**

Risk scenarios where the API commercialization undermines the free promise:
1. Infrastructure costs grow so fast that the free tier gets degraded to fund API revenue — users pay in quality what they don't pay in money
2. "Business customers" start building companion products for end users, who then effectively pay via their subscription to the business app — Nobi becomes the engine of a paid product
3. API revenue creates incentives to monetize user data to improve API quality, eroding privacy
4. The companion gets "lite-ified" over time, with better features reserved for API-powered products

**Verdict:** The risk is not in the proposal itself. The risk is in execution discipline. A clear **firewall policy** between companion infrastructure and API infrastructure eliminates most risks.

### 2.2 How "Free Forever" Projects Handle Commercial APIs

| Project | Core Product | Commercial Revenue | User Impact |
|---------|-------------|-------------------|-------------|
| Wikipedia | Free encyclopedia | API rate limits, enterprise data licensing, donations | None — free browsing untouched |
| Signal | Free messaging | Donations, grants, no API monetization | None |
| Firefox | Free browser | Google deal, Enterprise support, Mozilla VPN | Minimal — core browser free |
| Linux | Free OS | Red Hat, SUSE, Canonical enterprise support | None — kernel free forever |
| Hugging Face | Free model hub | Hosted compute, Enterprise Hub | None — Hub stays free |
| WordPress | Free CMS | WP Engine, Automattic products, cloud hosting | None — software free |
| Kubernetes | Free orchestration | GKE, EKS, AKS cloud managed services | None |

**Pattern:** ALL major "free forever" open-source projects have commercial layers. Not one has been criticized for this at scale — because the commercial layer serves a different customer (businesses) than the free product (users).

The key lesson: **the community accepts commercial APIs when (a) the free product stays genuinely free, (b) the revenue visibly benefits the project, and (c) self-hosting remains possible**.

### 2.3 Community Perception Risk in Crypto

Crypto communities are uniquely skeptical of monetization. Historical examples:

- **MetaMask:** Added a 0.875% fee on swaps — significant backlash initially, accepted over time as "MetaMask still free for regular use"
- **Uniswap:** Added frontend fee (0.15%) — major controversy but survived because protocol remained free
- **Curve Finance:** Admin fees charged at protocol level — accepted as community governance decision
- **Bittensor subnets generally:** Validators extracting emissions is built-in and accepted. Commercial layers on top (Chutes, Taoshi) are generally well-received.

**Key risk factors for Nobi specifically:**
1. The community model (emissions burn, James self-funding) has built significant goodwill
2. That goodwill is the most valuable thing to protect
3. Any perception that the "free" vision is being walked back = outsized backlash in crypto communities
4. Solution: **overcommunicate the principle** before launch. Frame it publicly before building it.

### 2.4 How to Frame This Without Breaking Trust

**Correct framing:**
> "Nobi for users is free. Forever. No asterisk. We're building an API for developers who want to build with Nobi's technology — and charging for infrastructure is how we fund making the free product better and more sustainable."

**Wrong framing:**
> "We're commercializing Nobi" / "We have a new premium tier" / "Nobi Pro"

**Recommended public language:**
- "Builder API" not "paid tier"
- "Infrastructure access" not "premium features"
- Revenue goes toward "keeping Nobi free and funding open-source development"
- Emphasize: "If you're a user of Nobi, nothing changes. Ever."

---

## 3. LEGAL IMPLICATIONS

### 3.1 CIC (Community Interest Company) — Can It Earn Commercial Revenue?

**Yes — CICs are explicitly designed to trade commercially.**

A Community Interest Company (CIC) is a limited company that:
- Exists to benefit a defined community
- Has an "asset lock" preventing assets being distributed to private shareholders beyond dividend caps
- Must pass an annual "community interest test"
- **Can and should generate revenue** — that's the point vs. a charity

Key CIC rules relevant to API commercialization:
- CICs can carry on any trade or business (unlike charities)
- Revenue must primarily benefit the community interest (not founders)
- Dividends to shareholders are capped (currently 35% of distributable profits)
- Interest payments on loans are also capped
- **API revenue is legal** — it's commercial income from trading

**Key constraint:** If API revenue generates significant profit, that profit must be demonstrably directed toward community benefit. "Keeping the companion free" and "funding open-source development" likely qualifies. Using profits to pay James a large salary might attract CIC regulator scrutiny if disproportionate.

*Source: UK gov.uk — "A CIC is a special type of limited company which exists to benefit the community rather than private shareholders." gov.uk/set-up-a-social-enterprise — retrieved March 2026*

**Action required:** Consult a UK solicitor familiar with CIC regulations before launch. This is a legal opinion, not a business decision.

### 3.2 MIT License Implications for Paid API

MIT license permits:
- Commercial use ✅
- Distribution ✅
- Modification ✅
- Private use ✅
- NO warranty requirement ✅

MIT does NOT:
- Restrict building paid services on top of the open-source code
- Require paid API revenue to be shared
- Prevent proprietary enhancements

**The API service itself is not the code.** Charging for API access to a service built on MIT-licensed code is fully compliant — this is how most commercial open source works (WordPress.com, Ghost Pro, etc.). The code remains open source; the service is commercial.

**Only edge case to consider:** If API-specific features are not released as open source, this creates a "closed API, open code" split. This is legally fine under MIT, but may create community tension. Recommendation: publish API client libraries as open source, keep only the billing/infrastructure layer private.

### 3.3 Data Processing Agreements (DPA) for Business API Customers

Any business paying for API access in the UK/EU will require:
- A **Data Processing Agreement (DPA)** — mandatory under UK GDPR and EU GDPR Article 28
- If the API processes any personal data on behalf of the business customer, Nobi acts as a **data processor**
- Business customer is the **data controller** — they're responsible for what they send
- Nobi must implement appropriate technical and organisational measures (TOMs)

**Immediate legal requirements upon API launch:**
1. DPA template (off-the-shelf template available from ICO)
2. Privacy policy update to reflect API processing
3. Data retention policy for API request logs
4. Sub-processor list (hosting providers, Bittensor network)

**Practical mitigation:** Design the API to be **stateless by default** — no data retained beyond request completion. If memory features are offered via API, make retention opt-in with clear data processing disclosure.

### 3.4 GDPR — API Access to User Data

Critical distinction: **Is the API accessing companion user data, or is it a separate inference API?**

**Scenario A — Pure inference API (recommended)**
- Developers send prompts, receive completions
- No Nobi user data involved
- Minimal GDPR complexity — only the API customer's data is in scope
- Low risk

**Scenario B — Access to companion memory/user data via API**
- Extremely high GDPR risk
- Would require explicit user consent for each user whose data is accessible
- Cross-border transfer issues if API customers outside UK/EU
- Do NOT do this without specialist legal advice

**Recommendation:** Launch with Scenario A only. Companion user data is never accessible via API. Keep these architecturally separate systems from day one.

### 3.5 UK Tax Implications

CIC API revenue is subject to:
- **Corporation Tax:** Standard UK rate 25% (for profits over £250k), 19% small profits rate (under £50k), marginal relief between
- **VAT:** If annual turnover exceeds £90,000 (2025/26 threshold), VAT registration mandatory
  - API services to UK businesses: 20% VAT
  - API services to non-UK businesses (B2B): Zero-rated under export rules
  - API services to individual developers outside UK: complex — verify with accountant
- **PAYE:** If revenue funds salaries, standard employment tax applies

**Practical note:** At early stages (sub-£90k revenue), VAT registration is not mandatory but voluntary registration may allow VAT reclaim on infrastructure costs — worth discussing with an accountant from the start.

---

## 4. TECHNICAL ARCHITECTURE

### 4.1 What Would the Nobi API Offer?

Proposed API surface area (tiered by complexity to build):

**Tier 1 — Easy to build, high value (launch first):**
- `POST /v1/chat/completions` — OpenAI-compatible inference endpoint
- Companion persona inference (system prompt templating)
- Streaming support

**Tier 2 — Medium complexity, strong differentiator:**
- `POST /v1/companions` — Create a companion with personality config
- `GET/PUT /v1/companions/{id}` — Manage companion settings
- `POST /v1/companions/{id}/chat` — Chat with a configured companion

**Tier 3 — Complex, highest differentiator (roadmap item):**
- `POST /v1/memory` — Store memory items
- `GET /v1/memory/search` — Semantic memory search
- `POST /v1/embeddings` — Embedding generation for external memory systems
- Webhook support for event-driven integrations

**What NOT to offer at launch:**
- Companion user data access (GDPR risk)
- Cross-user memory (privacy violation)
- Admin API for companion management at scale (too complex too early)

### 4.2 Separation of Free Companion vs Paid API Infrastructure

**Architecture principle: Complete separation from day one.**

```
┌─────────────────────────────────────────────────────┐
│              Nobi Free Companion App                 │
│    (webapp / mobile / Telegram bot)                  │
│                                                      │
│    Uses: Internal companion service                  │
│    Auth: User session / Telegram UID                 │
│    Rate limit: Generous free tier                    │
│    Data: User-owned, private                         │
└─────────────────┬───────────────────────────────────┘
                  │ (shared Bittensor miners / LLM backend)
                  │ (but separate API gateway and auth)
┌─────────────────▼───────────────────────────────────┐
│              Nobi Developer API                      │
│    (api.projectnobi.ai)                              │
│                                                      │
│    Uses: API-specific quota pool                     │
│    Auth: API key (Bearer token)                      │
│    Rate limit: Enforced by tier                      │
│    Data: Customer data, isolated                     │
│    Billing: Stripe / per-token metering              │
└─────────────────────────────────────────────────────┘
```

This separation ensures:
- Companion users never compete with API customers for capacity
- API abuse cannot degrade companion service
- Billing infrastructure only touches API layer
- GDPR separation is architectural, not just policy

### 4.3 Rate Limiting Tiers

| Tier | Requests/Day | Tokens/Month | RPM Limit | Priority |
|------|-------------|--------------|-----------|----------|
| Free API | 100 req/day | 1M tokens | 10 RPM | Lowest |
| Developer ($20/mo) | 10,000 req/day | 50M tokens | 60 RPM | Medium |
| Business ($99/mo) | 100,000 req/day | 500M tokens | 300 RPM | High |
| Enterprise (custom) | Unlimited | Custom | Custom | Highest |

*Note: These are proposed figures. Calibrate against actual infrastructure cost before launch.*

### 4.4 Authentication

- **API Keys:** Simplest. Generate per-project keys. Format: `nobi-sk-{random_64_char}`. Store hashed in DB.
- **OAuth 2.0:** For applications acting on behalf of users. More complex but required if third-party apps access user-specific data.
- **Recommendation for launch:** API keys only. OAuth only if/when Scenario B (user data) is added.

Tools: Stripe for billing, Upstash Redis for rate limiting, Postgres for key management.

### 4.5 Self-Hosting Option

**Must ship.** Non-negotiable for the open-source commitment.

Deploy with Docker Compose:
```bash
docker compose -f nobi-api.yml up
```

Self-hosted version includes:
- Full API surface
- No rate limits
- No billing
- BYO LLM backend (OpenAI-compatible, Ollama, local model)

Self-hosting preserves the "no company can take it away" promise at the API level. It also builds developer goodwill — the community knows the code is real.

---

## 5. BUSINESS MODEL

### 5.1 Pricing Tiers (Benchmarked Against Competitors)

| Tier | Price | What's Included | Rationale |
|------|-------|-----------------|-----------|
| **Free** | $0 | 100 req/day, 1M tokens/month, basic inference | Attract developers, build ecosystem |
| **Developer** | $20/month | 10k req/day, 50M tokens, companion config API, email support | Priced below Together AI / Groq equivalents |
| **Business** | $99/month | 100k req/day, 500M tokens, memory API, SLA, priority support | Comparable to mid-tier AI APIs |
| **Enterprise** | Custom | Dedicated infrastructure, custom SLA, MSA, DPA | For enterprises requiring compliance |

**Why $20 developer tier?**
- Chutes Pro is $20/month (10% off compute)
- Together AI has no fixed monthly plan — pure PAYG
- $20 is the "magic number" for developer tooling (GitHub Pro, Railway, etc.)
- Low enough to not require procurement approval at most companies

**Why $99 business tier?**
- Significant capability jump (10x requests)
- Includes memory API — the key differentiator
- Still below comparable OpenAI API bills for equivalent usage
- Round number, easy to expense

### 5.2 Revenue Projections

#### Conservative Scenario (12 months post-launch)
- 500 free tier users
- 50 Developer tier users: 50 × $20 = $1,000/month
- 10 Business tier users: 10 × $99 = $990/month
- 1 Enterprise: $500/month
- **Total: ~$2,490/month (~$29,880/year)**

#### Moderate Scenario (12 months post-launch)
- 2,000 free tier users
- 200 Developer tier users: 200 × $20 = $4,000/month
- 50 Business tier users: 50 × $99 = $4,950/month
- 5 Enterprise deals: $1,500/month average = $7,500/month
- **Total: ~$16,450/month (~$197,400/year)**

#### Aggressive Scenario (18–24 months post-launch)
- 10,000 free tier users
- 1,000 Developer tier: $20,000/month
- 200 Business tier: $19,800/month
- 20 Enterprise: $5,000/month avg = $100,000/month
- **Total: ~$139,800/month (~$1.67M/year)**

*These are illustrative projections. Actual results depend on marketing, product quality, and market adoption. Do NOT use for financial planning without validation.*

### 5.3 Cost Analysis

**Current Infrastructure Costs (James's estimated spend):**
7 servers + 55 miners = infrastructure is already running. Exact cost data not available (James to input). Estimate based on typical Hetzner/Contabo pricing:

| Resource | Estimated Monthly Cost |
|----------|----------------------|
| 7 servers (Hetzner/Contabo mix) | ~$700–$1,400/month |
| 55 miners (compute costs) | Included in server costs |
| LLM inference (Chutes/external) | ~$200–$500/month |
| Domain, CDN, misc | ~$50–$100/month |
| **Total estimated current** | **~$950–$2,000/month** |

*Note: James to verify exact figures. This is essential for break-even calculation.*

**API-specific additional costs:**
| Component | Estimated Cost |
|-----------|---------------|
| Stripe (billing infrastructure) | 2.9% + $0.30 per transaction |
| Redis (rate limiting) | ~$20–$50/month (Upstash) |
| Postgres (key management) | ~$15–$30/month |
| Additional compute for API traffic | Variable — $100–$500/month initially |
| SSL/monitoring/logging | ~$50/month |
| **Additional monthly overhead** | **~$200–$600/month** |

### 5.4 Break-Even Analysis

If current infrastructure costs ~$1,500/month and API adds ~$400/month overhead:
- **Break-even threshold:** ~$1,900/month API revenue
- At $20 Developer + $99 Business pricing:
  - Need ~40 Developer OR ~20 Business customers to cover API infrastructure overhead
  - Need ~95 Developer OR ~20 Business customers to cover ALL infrastructure

**Conservative break-even: 20 Business tier customers.**
This is an achievable early milestone. Even a single enterprise deal at $500/month covers most infrastructure.

### 5.5 Bittensor Emission Economics Interaction

Current model: James burns 100% of subnet emissions.

With API revenue:
- Option A: Continue burning emissions, use API revenue for infrastructure — **most credible, most community-friendly**
- Option B: Use emissions to fund API infrastructure, keep API revenue as surplus — possible but complex
- Option C: Create a treasury from API revenue, community votes on usage — most decentralized, most complex

**Recommendation: Option A.**
Keep the emissions burn. Use API revenue purely for infrastructure costs and development. This preserves the community goodwill and the "founder funds this themselves" narrative shifts to "the project funds itself sustainably." This is a better story.

---

## 6. COMPETITIVE ANALYSIS

### 6.1 Project Nobi's Moat

| Moat | Description | Defensibility |
|------|-------------|---------------|
| **Persistent Memory** | Cross-session memory that truly persists | Medium — others building this, but Nobi is early |
| **Companion Personality** | Distinct, configurable AI personality | Medium — differentiator in user experience |
| **Bittensor Decentralization** | No single company controls the backend | High — unique in AI companion space |
| **Open Source** | Code is verifiable, self-hostable | High — trust multiplier, can't be replicated by closed competitors |
| **"Free Forever" Brand** | Strong positioning vs commercial AI | High — extremely rare, creates community loyalty |
| **CIC Structure** | Mission-locked legal entity | Medium — strong for community trust |

### 6.2 Direct Competitors

**In the AI Companion API space:**

| Competitor | Type | API? | Pricing | Weakness vs Nobi |
|------------|------|------|---------|-----------------|
| Character.AI | Closed, VC-funded | No public API | $9.99/mo consumer | No API, no open source |
| Replika | Closed, VC-funded | No public API | $7.99–$14.99/mo | No API, privacy concerns |
| Inflection/Pi | Closed | No API | Free (discontinued paid) | No open source, shutting down |
| Kindroid | Closed | No API | $10–$13/mo | No API |
| Claude (Anthropic) | Closed | Yes | $3–$25/MTok | Not a "companion" — no memory, no personality |
| OpenAI GPT | Closed | Yes | $0.20–$15/MTok | Not a companion — requires your own memory layer |

**Indirect competitors (AI APIs that could be used to build companions):**

OpenAI + custom memory (e.g., Mem0, Zep) is the most common developer approach. Key weakness: **high assembly cost** — developers must stitch together inference, memory, and personality. Nobi's API offers these as integrated primitives.

### 6.3 Why Pay for Nobi API vs OpenAI + DIY?

| Feature | OpenAI + DIY Memory | Nobi API |
|---------|---------------------|----------|
| Inference quality | Excellent | Good (depending on backend) |
| Memory system | Build it yourself | Built in |
| Companion personality | Build it yourself | Built in |
| Setup complexity | High | Low |
| Cost (at scale) | $2.50/MTok + memory infra | $20–$99/month flat |
| Vendor lock-in | High (OpenAI terms) | Low (self-hostable) |
| Decentralized | No | Yes (Bittensor) |
| Trust/transparency | Limited | Open source + CIC |

**The pitch to developers:** "Build a personalized AI companion for your app in one API call, not six services stitched together."

---

## 7. RISK ANALYSIS

### 7.1 Risk Matrix

| Risk | Likelihood | Impact | Severity | Mitigation |
|------|-----------|--------|----------|-----------|
| Mission drift | Medium | Critical | 🔴 High | Hard rule: free companion never degrades |
| Community backlash | Medium | High | 🔴 High | Transparent framing before launch |
| Bittensor network instability | High | Medium | 🟡 Medium | Fallback inference providers |
| CIC legal constraints | Low | High | 🟡 Medium | Legal opinion before launch |
| GDPR breach | Low | Critical | 🟡 Medium | Stateless API, no user data |
| Billing infrastructure failure | Medium | Medium | 🟡 Medium | Use Stripe (battle-tested) |
| Cannibalization of companion users | Low | Low | 🟢 Low | API serves builders, not end users |
| API abuse | High | Low | 🟢 Low | Rate limiting + API keys |

### 7.2 Mission Drift Risk

**The slow boil scenario:** Revenue pressure leads to gradual free tier degradation. Response times increase. Features get "API-only." Over 18 months, the free companion is effectively worse — users have been monetized without consent.

**Mitigation:** 
- Write it in the mission document: "The free companion will never be degraded to drive API revenue."
- Public commitment: announce this before the API launches
- Internal KPI: monitor free tier response times and quality metrics — if they degrade, pause API until fixed
- Community governance: give community a voice on what "free forever" means in practice

### 7.3 Community Backlash Risk

Crypto Twitter is brutal. "Project Nobi sells out" is a headline that can spread in hours.

**Mitigation:**
- Frame the API as sustainability infrastructure, not monetization
- Announce before building: "We're exploring a builder API — here's our thinking. Community feedback welcome."
- Emphasize: 100% of emissions still burned. API revenue funds operations only.
- Consider a community grant program: "10% of API revenue goes to open-source contributors" — turns critics into advocates

### 7.4 Technical Complexity of Billing Infrastructure

Stripe integration, API key management, usage metering, rate limiting, invoicing — this is weeks of development work that doesn't improve the product.

**Mitigation:**
- Don't build billing from scratch. Use Stripe Billing + usage metering APIs.
- Start with manual billing for first 10 customers — validate demand before automation
- Use existing rate limiting solutions (Upstash, Kong, APISIX) rather than building custom

### 7.5 Dependency on Bittensor Network Stability

Corcel's struggles showed that building a commercial API on pure Bittensor backend introduces reliability risk. If subnet miners go offline, API customers are affected. Enterprise customers will not accept this.

**Mitigation:**
- Hybrid backend: Bittensor-primary with Chutes/OpenRouter fallback
- SLA offered only when fallback is operational
- Transparent status page (api-status.projectnobi.ai)
- Developer and Business tiers: best-effort SLA
- Enterprise tier only: formal uptime SLA

---

## 8. IMPLEMENTATION ROADMAP

### Phase 1: Foundation & Validation (Weeks 1–8)
**Goal: Validate demand before building billing**

**Week 1–2: Discovery**
- [ ] Publish a public post/X thread announcing the Builder API concept
- [ ] Open a "Request API Access" waitlist form
- [ ] Gauge interest — target: 100+ signups = proceed
- [ ] Get legal opinion on CIC commercial trading (hire solicitor)

**Week 3–4: Architecture**
- [ ] Design API specification (OpenAPI 3.0 spec)
- [ ] Architect the API gateway (separate from companion infrastructure)
- [ ] Select tech stack: FastAPI / Node.js / existing webapp extension
- [ ] Design rate limiting architecture

**Week 5–8: Core API Build**
- [ ] Implement `POST /v1/chat/completions` (OpenAI-compatible)
- [ ] Implement API key generation and validation
- [ ] Implement rate limiting (Upstash Redis)
- [ ] Basic companion creation and configuration endpoint
- [ ] Set up `api.projectnobi.ai` subdomain

**Resources:** Dragon Lord (coder) + James (product decisions). No additional hires needed at this stage.

### Phase 2: Private Beta (Weeks 9–16)
**Goal: Real-world testing with controlled group, manual billing**

- [ ] Invite first 20 waitlist members to private beta (free access)
- [ ] Gather feedback on API design, documentation, use cases
- [ ] Build API documentation (Mintlify or Docusaurus)
- [ ] Add memory API (`/v1/memory`)
- [ ] Implement Stripe billing (Developer tier only)
- [ ] Manual enterprise onboarding for first 2–3 enterprise prospects
- [ ] Publish self-hosting guide (Docker Compose)
- [ ] Draft Data Processing Agreement template

**Success criteria to proceed to Phase 3:**
- 50+ active beta users
- At least 5 paying Developer tier customers
- No critical security incidents
- CIC legal clearance obtained

### Phase 3: Public API Launch (Weeks 17–24)
**Goal: Open commercial API to the public**

- [ ] Public launch announcement (X, Discord, Reddit, Bittensor forums)
- [ ] All tiers live (Free / Developer / Business / Enterprise waitlist)
- [ ] Full billing automation (Stripe)
- [ ] Business tier features (memory API, SLA)
- [ ] Status page live
- [ ] Support documentation complete
- [ ] Privacy policy and Terms of Service updated for API
- [ ] Community transparency report: "API revenue = infrastructure costs"

### Timeline Summary

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | Weeks 1–8 | Waitlist + Core API built |
| Phase 2 | Weeks 9–16 | Private beta + first paying customers |
| Phase 3 | Weeks 17–24 | Public launch |
| **Total** | **~6 months** | **Commercial API live** |

### Resource Requirements

| Resource | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Development (Dragon Lord / James) | ~80 hrs | ~120 hrs | ~60 hrs |
| Legal (CIC solicitor) | ~5 hrs | ~5 hrs | ~2 hrs |
| Design (API docs, landing page) | — | ~20 hrs | ~10 hrs |
| Infrastructure (additional compute) | Minimal | ~$100–200/mo | ~$300–500/mo |
| Stripe setup | — | 1-time $0 | — |

**Total estimated development cost (6 months):** ~£8,000–15,000 in opportunity cost (developer time) + ~£1,500–3,000 in legal fees + ~£2,000–4,000 in additional infrastructure.

---

## 9. RECOMMENDATION

### Verdict: CONDITIONAL YES ✅

**The API commercialization strategy is sound. Proceed — but under specific conditions.**

### Conditions That Must Be Met

**Before any code is written:**
1. ✅ Obtain a legal opinion from a UK solicitor on CIC commercial trading — confirm API revenue is permissible and document how profits should flow
2. ✅ Publish a public transparency statement about the API concept before building — community-first, no surprises
3. ✅ James confirms exact current infrastructure costs — break-even analysis needs real numbers

**Before accepting any payment:**
4. ✅ CIC legal clearance confirmed
5. ✅ Privacy Policy updated for API data processing
6. ✅ DPA template ready for business customers
7. ✅ Stateless API architecture confirmed — NO companion user data accessible via API

**Always maintained:**
8. ✅ Free companion tier never degrades as a result of API revenue decisions
9. ✅ Self-hosting documentation ships with the API
10. ✅ API revenue is publicly accounted for (quarterly transparency report to community)
11. ✅ Emissions burn continues — API revenue is supplementary, not replacement for the community model

### Red Lines That Must Not Be Crossed

🚫 **NEVER** allow API customers to access companion user data — architectural separation is mandatory
🚫 **NEVER** degrade free companion response quality to prioritize API traffic
🚫 **NEVER** gate features behind API that were previously available free to companion users
🚫 **NEVER** frame the API as "Nobi Pro" or any language suggesting the free product is lite
🚫 **NEVER** launch billing before CIC legal clearance
🚫 **NEVER** accept enterprise contracts without a signed DPA and ToS
🚫 **NEVER** stop burning emissions — this is the community trust anchor

### Why This Is the Right Decision

1. **Sustainability:** James personally funding 7 servers indefinitely is not sustainable. API revenue creates a path to self-funding without community dependency.

2. **Alignment:** Revenue from builders funds better infrastructure for users. This is a positive flywheel, not a tradeoff.

3. **Precedent:** Every major open-source project with longevity has a commercial layer. Staying pure-free is how projects die when the founder can no longer fund them.

4. **Market timing:** The AI API market is growing at 30%+ CAGR. Moving now captures early-mover advantage in the niche of companion-specific APIs — an underserved segment.

5. **Mission reinforcement:** Done right, this makes the "free forever" promise more credible, not less. "We have API revenue that funds this, so we don't need your money" is a stronger promise than "James funds this himself."

### The One-Line Summary

**Build the API, keep the companion free, tell the community first, get legal clearance — and this is the most sustainable path forward.**

---

## APPENDIX: Data Sources

| Source | Data Used | URL | Retrieved |
|--------|-----------|-----|-----------|
| Precedence Research | AI API market size $64.41B (2025), 30.19% CAGR | precedenceresearch.com/ai-api-market | March 2026 |
| Grand View Research | AI API market $48.50B (2024) → $246.87B (2030) | grandviewresearch.com | March 2026 |
| Fortune Business Insights | AI API market $783.33B by 2034 | fortunebusinessinsights.com | March 2026 |
| OpenAI Pricing Page | GPT-5.4: $2.50/$15.00 per MTok | openai.com/api/pricing/ | March 2026 |
| Anthropic Pricing Page | Claude Opus 4.6: $5/$25; Sonnet 4.6: $3/$15; Haiku 4.5: $1/$5 | platform.claude.com/docs/en/about-claude/pricing | March 2026 |
| Groq Pricing Page | GPT OSS 20B: $0.075/$0.30; 120B: $0.15/$0.60 | groq.com/pricing | March 2026 |
| Together AI Pricing | Llama 4 Maverick: $0.27/$0.85; DeepSeek V3.1: $0.60/$1.70 | together.ai/pricing | March 2026 |
| Fireworks AI Pricing | <4B: $0.10; 4B-16B: $0.20; >16B: $0.90 per MTok | fireworks.ai/pricing | March 2026 |
| Replicate Pricing | Claude 3.7: $3.00 input / $15 output per MTok | replicate.com/pricing | March 2026 |
| Hugging Face Pricing | Spaces: free–$23.50/hr; Inference Endpoints: $0.033/hr+ | huggingface.co/pricing | March 2026 |
| Chutes.ai | Base $3/mo, Plus $10/mo, Pro $20/mo | chutes.ai | March 2026 |
| Cohere Pricing | Enterprise custom pricing only (no public per-token rates) | cohere.com/pricing | March 2026 |
| GOV.UK CIC guidance | CIC is limited company existing to benefit community, can trade | gov.uk/set-up-a-social-enterprise | March 2026 |

### Data Gaps (Honest Disclosure)

- **Corcel pricing:** Corcel pricing page returned 404. Corcel appears to have shut down or pivoted. Historical $15/month developer tier reported from community sources but not directly verified.
- **Taoshi API pricing:** Public pricing page not found. Reported as subscription-based from community knowledge but exact figures not retrieved.
- **Groq Llama model pricing:** Groq pricing page showed GPT OSS models. Traditional Llama pricing not captured in retrieved data.
- **James's actual infrastructure costs:** Required for accurate break-even — placeholder estimates used in this report.
- **Cohere per-token rates:** Cohere has pivoted to enterprise-only pricing with no public per-token rates.
- **CIC commercial trading limits:** Could not find specific HMRC or CIC regulator ruling on API revenue. Professional legal advice is essential.

---

---

## 10. DISADVANTAGES DEEP-DIVE

*This section is written adversarially — as if the strongest possible critic of the API commercialization proposal wrote it. Every disadvantage is argued at maximum force.*

### 10.1 Operational Burden: The Hidden Tax on the Mission

Building and running a commercial API is not just a technical project. It is a **permanent operational commitment** that creates ongoing costs, obligations, and distractions that do not exist today.

**Billing infrastructure:**
- Stripe integration is deceptively simple on day one. At scale, it becomes a full-time task: handling failed payments, refunds, prorated upgrades/downgrades, dunning (chasing failed payments), tax reporting (VAT invoices per-customer per-country), chargebacks, and fraud prevention.
- Each API customer who fails to pay requires manual intervention or automated systems to suspend their access, notify them, and reinstate after payment — all while avoiding breaking their production application and generating a support ticket.
- At 50+ customers, billing support becomes a significant time sink. At 200+ customers, it likely requires a dedicated part-time person.

**Customer support:**
- Free users expect nothing. Paying customers expect SLAs, support tickets, answers within hours.
- A $20/month Developer customer who's been charged 3 months and sees downtime will submit a ticket and expect a real response, potentially a refund, and possibly a chargeback.
- A $99/month Business customer will expect genuine SLA commitments (e.g., 99.5% uptime). When the Bittensor network has issues — and it will — that customer's application breaks. They want credit and an explanation.
- Enterprise customers will require quarterly business reviews, dedicated contacts, and professional-grade communications.
- James currently has **zero support infrastructure**. This is fine for a free product. It is incompatible with paid commercial services.

**SLA commitments:**
- An SLA is a legal commitment. If you promise 99.5% uptime and deliver 98%, the customer has grounds for a contractual claim.
- Bittensor network reliability is genuinely not under Nobi's full control. Any SLA offered must either be very conservative (say, 95%, which is embarrassingly low) or backed by a fallback infrastructure that costs more money.
- Operating without an SLA is possible but means losing enterprise deals. Larger companies require SLAs to approve vendor relationships internally.

**Uptime guarantees:**
- A free companion product can have planned maintenance windows. A paid API cannot, at least not without advance notice (typically 72–96 hours minimum).
- This means changes to infrastructure — new miners, server migrations, software updates — become coordination exercises with advance communication. Every maintenance window needs a public announcement, a status page update, and a recovery path.
- The operational discipline required for commercial uptime is fundamentally different from the "push it and see" approach appropriate for early-stage open source.

**The compounding effect:** Each of these operational burdens is individually manageable. Together, they represent a **significant portion of one person's full-time working life** that is not building the companion product, not improving the Bittensor integration, not building community. This is the real cost — not money, but attention.

---

### 10.2 Distraction from Core Mission

The companion product is the mission. The API is infrastructure for builders. These are different problems that require different mindsets, different priorities, and different work.

**Product-market fit isn't confirmed yet.** Project Nobi is in early-stage development on testnet. The companion hasn't reached a stable mainnet deployment. Adding API commercialization before the core product is polished is a classic startup mistake: **monetizing before validating**. Every hour spent building billing, rate limiting, API key management, DPA templates, and developer documentation is an hour not spent on:
- Memory quality and persistence
- Companion personality and emotional intelligence
- Bittensor miner optimization
- Onboarding and user experience
- Community growth

**Attention is the scarcest resource.** James is one person (with Slumpz and Dragon Lord), personally funding a 7-server, 55-miner infrastructure. This is already a significant operational load. Adding commercial API obligations tilts the balance further away from innovation and toward maintenance.

**Feature request creep:** Paying API customers will request features. Some will be reasonable; many will be specific to their use case and irrelevant to the companion product. The pressure to satisfy paying customers pulls the roadmap in directions that serve revenue rather than mission. This is how products quietly drift away from their founding vision — not through one big decision, but through thousands of small accommodations to paying customers.

**The "investor pressure" analog:** Even without external investors, API revenue creates its own pressure analog. Once revenue exists, the implicit goal is to grow it. Churn becomes a KPI. MRR becomes a metric people watch. These are not inherently bad, but they create a gravitational pull toward decisions optimized for revenue rather than mission.

---

### 10.3 Technical Debt from Maintaining Two Tiers

Free companion and paid API are, architecturally, two different products sharing some infrastructure. This creates ongoing technical debt.

**Diverging infrastructure requirements:**
- The companion product optimizes for user experience: low latency, conversational continuity, emotional warmth.
- The API optimizes for developer experience: predictable outputs, consistent rate limits, low error rates, OpenAI-compatibility.
- These priorities can conflict. A change that improves companion response quality (e.g., longer chain-of-thought, richer memory retrieval) may increase latency in a way that's unacceptable to API customers.
- Every architectural decision becomes a negotiation between two different optimization targets.

**Version management:**
- API customers build on your endpoints. If you change the API (add fields, deprecate parameters, change behavior), you may break their applications.
- This requires API versioning (`/v1/`, `/v2/`), deprecation policies (typically 6–12 months notice), and maintaining old API versions while building new ones.
- The companion product can ship breaking changes with an announcement. The API cannot.

**Separate test suites:**
- Free companion testing can be manual or informal. Commercial APIs require automated test suites with regression testing to ensure API contract integrity across deployments.
- Every deployment must be tested against the API spec before going live — adding time and infrastructure to the release process.

**Monitoring and observability:**
- Free products need basic uptime monitoring. Paid APIs need per-customer usage tracking, per-endpoint latency metrics, error rate dashboards, and anomaly alerting.
- This infrastructure (Prometheus, Grafana, or a commercial equivalent like Datadog) adds cost and maintenance.

**Long-term codebase complexity:** Two years from now, the codebase will be significantly more complex than it would be with companion-only development. This complexity slows down everything: new features take longer, bugs are harder to find, onboarding new contributors is harder. Technical debt compounds.

---

### 10.4 Community Fragmentation Risk

The Nobi community is built around a singular, radical idea: an AI companion that is genuinely free, owned by no company, running on a decentralized network. This simplicity and purity of vision is a **competitive advantage and a trust asset**.

**The two-tier community problem:** Once an API tier exists, the community implicitly divides:
- "Free companion users" — the mass community
- "API builders" — a smaller, economically active, technically sophisticated group

These communities have different interests. API builders want stability, predictability, developer tooling. Free users want features, personality, emotional quality. When the roadmap prioritizes API improvements (which generate revenue) over companion quality (which generates community goodwill), it signals a shift in who the product really serves.

**Perception of exclusivity:** "There's a paid API" — even if companion users are unaffected — creates a perception that Nobi is no longer purely community-first. In crypto communities, perception can become reality quickly. A single viral tweet saying "Nobi is now behind a paywall" — even if factually wrong — can cause serious damage.

**DAO governance complications:** If Nobi evolves toward community governance (as the Bittensor model suggests), API revenue creates a governance complication. Who controls the API revenue? Who decides pricing? Does the community vote on tiers? This is solvable, but adds governance complexity that doesn't exist today.

---

### 10.5 Open-Source Contributor Motivation Impact

Open-source projects thrive on contributor motivation. Contributors contribute because they believe in the mission, want to improve a tool they use, or want to build reputation.

**The "building someone's commercial product" problem:** When an open-source project has commercial API revenue, contributors can start to feel they are building a commercial product for the benefit of the founders rather than the community. This is particularly acute if:
- The commercial API layer is closed-source (even if the companion code is open)
- Revenue doesn't visibly flow back to contributors (grants, bounties)
- Feature decisions are influenced by API customer requests rather than community priorities

**The two-class contributor problem:** Developers who use the API and pay for it have a direct financial relationship with the project. Developers who contribute to the open-source codebase have no financial relationship. This asymmetry can generate resentment: "I'm building the product that they're selling."

**Mitigation exists but requires deliberate action:** If API revenue funds open-source contributor grants, bounties, and hackathons, this risk is substantially reduced. But this requires budget allocation and administration — another operational burden.

---

### 10.6 Dependency on API Revenue Creating Perverse Incentives

Once API revenue exists and begins to fund infrastructure, it becomes structurally difficult to reduce or eliminate it. This creates a set of perverse incentives.

**The revenue dependency trap:** Month 1: API revenue covers 10% of infrastructure. Month 12: it covers 60%. Month 24: James's personal funding covers only 20% of costs. At this point, **the API revenue is not supplementary — it is essential**. Any significant churn event (a competitor launches a free alternative; Bittensor mainnet has a 2-week outage; a competitor poaches your top API customers) creates a funding crisis.

**Retention-driven feature decisions:** When revenue depends on retaining paying customers, features that reduce churn become the priority — even when they don't improve the free companion. "Enterprise feature X will keep our $500/month customer" can override "community feature Y will delight 10,000 users." Over time, this pulls the product toward serving the revenue base rather than the mission.

**Pricing pressure:** API customers will always push for lower prices. Competitors will undercut. The response is to either reduce prices (compressing margins) or add more features to justify the price (engineering cost). Both paths create pressure. The "free forever" companion absorbs the costs of this commercial pressure without generating revenue to offset it.

**The "what if API revenue exceeds emission income?" question:**
This deserves specific attention. Currently, James funds infrastructure and burns all emissions. If API revenue grows significantly — say, $50,000/month — the financial dynamics of the project shift.

Scenarios:
- **API revenue > emission value:** Nobi becomes financially independent of Bittensor economics. This sounds positive but removes the direct financial incentive to keep the subnet healthy and growing. The community model becomes less central.
- **API revenue funds subnet expansion:** This is the positive flywheel — revenue → more miners → higher emissions → better service → more API customers. But this requires disciplined allocation.
- **Governance vacuum:** Who decides how API revenue is used? James alone? A community vote? The CIC board? Without a governance framework, this becomes a source of tension as revenue grows.

**The governance shift:** If API revenue exceeds the value of burned emissions, the project's economic center of gravity shifts from the Bittensor community model to the commercial API model. At this point, the project has effectively become a commercial SaaS with a Bittensor integration, rather than a Bittensor-native project with a commercial sustainability layer. This is not automatically bad, but it represents a fundamental change in what the project is. The community should understand and consent to this trajectory before it happens by default.

---

### 10.7 Summary: The Honest Disadvantage Scorecard

| Disadvantage | Severity | Avoidable? |
|---|---|---|
| Billing/support operational burden | High | Partially — good tooling reduces it |
| Distraction from core product | High | Partially — requires discipline |
| Technical debt (two-tier architecture) | Medium | Partially — good architecture reduces it |
| Community fragmentation | Medium | Yes — with transparent communication |
| Open-source contributor motivation | Medium | Yes — with revenue sharing / bounties |
| API revenue dependency risk | High | Yes — with caps and budget discipline |
| Governance vacuum as revenue grows | Medium | Yes — with pre-defined governance rules |

**The honest conclusion:** These are real disadvantages, not theoretical ones. Every commercial API that started with good intentions has faced some of these. The question is not "are these risks real?" — they are. The question is "can we manage them with sufficient discipline given our current stage and team size?" That answer depends on execution commitment, not just strategy.

---

## 11. LEGAL IMPLICATIONS — DEEP DIVE

*All legal citations in this section are sourced directly from official UK government and ICO guidance. This section is informational only and does not constitute legal advice. Engage a qualified UK solicitor before acting on any of this.*

---

### 11.1 UK GDPR Article 6 — Lawful Basis for Processing

Under UK GDPR (retained in UK law post-Brexit via the Data Protection Act 2018), **every processing activity requires a lawful basis**. Article 6 provides six possible bases. The ICO states: *"You must have a valid lawful basis in order to process personal data... which basis is most appropriate to use will depend on your purpose and relationship with the individual."*

*Source: ICO — "A guide to lawful basis" — ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/ — retrieved March 2026*

**The six lawful bases under Article 6:**

| Basis | Description | Applies to Nobi API? |
|-------|-------------|---------------------|
| (a) Consent | Individual gives clear consent for specific purpose | Companion users: yes. API customer B2B contact data: possibly |
| (b) Contract | Processing necessary for a contract with the individual | ✅ API customers: processing their account/billing data to fulfil the API contract |
| (c) Legal obligation | Processing required by law | For tax records, breach reporting — limited use |
| (d) Vital interests | Protect someone's life | Not applicable |
| (e) Public task | Public authority performing official functions | Not applicable (CIC is not a public authority) |
| (f) Legitimate interests | Necessary for legitimate interests, proportionate | ✅ API request logging for security/abuse prevention |

**For the API — which bases apply where:**

| Data Being Processed | Most Appropriate Basis | Notes |
|----------------------|----------------------|-------|
| API customer billing info | **Contract (b)** | Processing name, email, payment method to deliver the paid service |
| API request logs (IP, timestamp, request hash) | **Legitimate interests (f)** | Security monitoring, rate limiting, abuse prevention |
| API customer account data | **Contract (b)** | Account management |
| Marketing emails to API prospects | **Consent (a)** | Must be opt-in; cannot rely on contract for marketing |
| Prompts sent via API | Depends on content — see Section 12 | May contain personal data |

**Critical ICO warning:** *"Take care to get it right first time - you should not swap to a different lawful basis at a later date without good reason."* — This means choosing the right basis before collecting data, not retrofitting a basis after the fact.

---

### 11.2 Data Controller vs Data Processor — The Roles When Businesses Use the Nobi API

This is the most complex and consequential legal question for the API model. The roles are not fixed — they depend on **who decides why and how data is processed**.

**ICO definitions (verbatim from official guidance):**
> *"'controller' means the natural or legal person, public authority, agency or other body which, alone or jointly with others, determines the purposes and means of the processing of personal data."*
> *"'processor' means a natural or legal person, public authority, agency or other body which processes personal data on behalf of the controller."*

*Source: ICO — "What are 'controllers' and 'processors'?" — ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/controllers-and-processors/ — retrieved March 2026*

**Applied to the Nobi API — three scenarios:**

**Scenario A: Developer sends only their own test data (no end-user personal data)**
- No personal data of third parties involved
- GDPR largely not engaged for the API layer
- Simplest case; no DPA needed for this scenario alone

**Scenario B: Developer builds an app that sends their end-users' conversations to the Nobi API**
- The developer is the **data controller** (they decided to build the app and collect user data)
- Nobi is the **data processor** (processing data on behalf of the developer per the API contract)
- **A DPA is mandatory under UK GDPR Article 28** — this is not optional
- Nobi must: only process data per the developer's instructions; maintain confidentiality; implement appropriate security measures; not engage sub-processors without the developer's consent; assist with subject rights requests; delete data when instructed

**Scenario C: Developer's app users' data could be linked back to companion users**
- **This must not happen** — it creates joint controller complexity, potential data breaches, and is architecturally prohibited
- This is the red line that requires architectural separation

**What a DPA must contain (per UK GDPR Article 28):**
- Subject matter and duration of the processing
- Nature and purpose of the processing
- Type of personal data and categories of data subjects
- Obligations and rights of the controller
- Processor's obligations: process only on documented instructions; confidentiality; security; sub-processor restrictions; assist with rights requests; delete/return data; provide compliance information

**ICO's position on processor liability:**
> *"If a processor acts without the controller's instructions in such a way that it determines the purpose and means of processing... it will be a controller in respect of that processing and will have the same liability as a controller."*

This means if Nobi's API code makes decisions about what to do with data beyond what the customer instructed (e.g., retaining prompts for model training without consent), Nobi becomes a joint controller and takes on full GDPR liability.

---

### 11.3 Data Processing Agreements (DPAs) for Business API Customers

**DPAs are legally mandatory** whenever a controller (API customer) uses a processor (Nobi) to handle personal data, per UK GDPR Article 28(3).

**What Nobi needs before accepting a paying business customer:**

1. **A signed DPA** — must be in place before processing begins, not after
2. **A clear data processing register** — Nobi must record what data it processes on behalf of each customer
3. **Sub-processor list** — Nobi must disclose all sub-processors (Hetzner, Contabo, any Bittensor miners handling data) and get customer agreement before adding new ones
4. **Incident notification obligation** — Nobi must notify the customer "without undue delay" of any breach affecting their data

**Practical requirements:**

The ICO provides a DPIA template (docx) that can be adapted. A DPA for API services typically covers:
- The API customer is the controller, Nobi is the processor
- Data processed: prompts, completions, API request metadata
- Retention period: e.g., "request logs retained for 30 days; prompts not retained beyond response generation"
- Security measures: TLS encryption in transit, encryption at rest, access controls
- Sub-processors: Hetzner GmbH (hosting), Contabo (hosting), Bittensor network miners
- Data subject rights: Nobi will assist the customer in responding to erasure, access, and rectification requests

**Getting a DPA template:** The ICO publishes a DPIA template at ico.org.uk. For a DPA specifically (different from a DPIA), a solicitor can produce a standard template for ~£500–1,000 that can be reused across all customers.

---

### 11.4 International Data Transfers — Schrems II Context and UK Position

When API customers outside the UK send data to Nobi's UK-based servers, **or** when Nobi sends data to servers outside the UK (e.g., Contabo in Germany, or Bittensor miners globally), international transfer rules apply.

**UK framework post-Brexit:**

The UK GDPR applies to organisations in the UK. Post-Brexit, the UK has its own adequacy framework, separate from the EU GDPR Schrems II framework.

Key ICO guidance: *"Every restricted transfer must be covered by one of the following transfer mechanisms: UK adequacy regulations; appropriate safeguards; or an exception."*

*Source: ICO — "A brief guide to international transfers" — ico.org.uk — retrieved March 2026*

**UK Adequacy Decisions (as of March 2026):**
- EU/EEA countries: UK has confirmed adequacy for data flowing UK → EU
- US: UK has extended the EU-US Data Privacy Framework (updated guidance published January 15, 2026 per ICO)
- Other countries: variable — check the ICO adequacy regulations list

**For Nobi's API — practical implications:**

| Data Flow | Transfer Mechanism Required |
|-----------|---------------------------|
| UK servers → Contabo Germany (EU) | UK→EU adequacy — generally covered |
| UK servers → US-based enterprise customer | UK Extension to EU-US DPF, or IDTA |
| UK servers → Bittensor miners (global, unknown location) | **Complex — miners are globally distributed; their jurisdictions are unknown** |
| Non-UK API customer → UK servers | UK GDPR applies to Nobi's processing regardless |

**The Bittensor miner problem:** Bittensor miners are geographically distributed and pseudonymous. When API data flows through Bittensor miners as part of inference, that data is technically being transmitted to servers in unknown international locations. This is a genuine international transfer compliance challenge.

**Mitigation options:**
- Use only known, UK/EU-hosted miners for API traffic
- Process API requests on Hetzner1 (UK/Germany) using local model only, bypassing distributed Bittensor miners
- Or: design the API so no personal data flows through the Bittensor network — inference is done on controlled servers, only anonymized requests go to miners

**Note on Schrems II (EU law):** Schrems II (C-311/18, 2020) invalidated the EU-US Privacy Shield under EU GDPR. This is an EU law matter, not UK law. UK has its own framework. EU API customers sending data to Nobi must ensure compliance with their own EU GDPR obligations for transfer to the UK — which is generally covered by the EU adequacy decision for the UK. This is primarily the EU customer's responsibility, not Nobi's.

---

### 11.5 Right to Erasure — Complications in the API Context

The ICO states: *"Under Article 17 of the UK GDPR individuals have the right to have personal data erased... The right to erasure is also known as 'the right to be forgotten'."*

**When does this affect the Nobi API?**

If an API customer's end-user submits an erasure request to the API customer (the controller), the API customer must:
1. Erase the data they hold directly
2. Pass the erasure request to all processors — including Nobi's API

Nobi must then erase any retained data relating to that individual. The ICO requirement: *"We have procedures in place to inform any recipients if we erase any data we have shared with them."*

**Key complications:**

**API request logs:** If Nobi retains logs containing personal data (e.g., prompts that include names, emails, or other identifiers), these must be erasable on request. This requires:
- Logs must be structured to allow targeted deletion (not just rolling time-based purges)
- The ability to identify which log entries relate to which individual across potentially millions of records

**Backup systems:** The ICO asks: *"Do we have to erase personal data from backup systems?"* — The answer is yes, but with nuance: immediate deletion from backups may not be possible, but the data should be suppressed and not restored.

**The stateless API design solution:** If the API is genuinely stateless — prompts processed and not retained beyond the immediate response — erasure requests are trivially handled: there is nothing to erase. **This is the strongest argument for a strict no-retention API design as a default.** It eliminates the erasure complication almost entirely.

**Response time:** Erasure requests must be responded to within **one month** (with possible 2-month extension for complex cases).

---

### 11.6 API Terms of Service — Liability, Indemnification, SLA Commitments

**What the API ToS must address:**

**Liability limitations:**
- UK consumer law (Consumer Rights Act 2015) restricts liability exclusions for consumers. B2B API customers (businesses) have less protection — liability can be more fully excluded by contract.
- Standard practice: exclude consequential loss, cap liability at 12 months of subscription fees paid.
- Must not exclude liability for death, personal injury, or fraud — these cannot be limited by UK law.

**Consumer Rights Act 2015 — important note:**
- Applies to B2C relationships. If Nobi's API is sold directly to individual developers (not through a business), some CRA protections apply.
- CRA requires digital services to be of satisfactory quality, fit for purpose, and as described.
- For B2B customers (companies), standard commercial contract terms apply with more flexibility.
- **Practical implication:** Clearly define who can buy the API. If "Developer tier" includes individual developers (not just companies), the CRA applies. This is likely fine — just ensure the API actually works as described.

**Indemnification:**
- Standard API ToS should require API customers to indemnify Nobi against misuse — if a customer uses the API to process illegal content and Nobi is implicated, the customer bears responsibility.
- Nobi should explicitly prohibit: illegal content generation, impersonation, harassment, GDPR-violating processing, spam generation.

**SLA commitments:**
- Any SLA creates legal liability. If you commit to 99.5% uptime and deliver 98%, the customer has grounds for a claim.
- Standard mitigation: SLA is in "Credits" (service credit, not money back), limited to 10–30% of monthly fee.
- Force majeure clauses: explicitly exclude Bittensor network outages, ISP failures, DDoS attacks from SLA calculation.

**IP ownership:**
- API ToS must clarify: outputs generated via the API belong to the API customer. Nobi makes no claim on generated content.
- If Nobi wants to use anonymized API data for model improvement: explicit consent required in ToS — users must opt in, not opt out.

**Termination:**
- Right to terminate for breach (illegal use, non-payment)
- Right to terminate for Bittensor network events that make the service technically impossible
- Notice period for discretionary termination (e.g., 30 days)

---

### 11.7 EU AI Act — Implications for Providing AI-as-a-Service API

The EU AI Act is directly relevant to any commercial AI API that serves EU customers.

**Timeline (from official EU Commission source):**
- **Prohibited practices:** Effective February 2025 (already in force)
- **General Purpose AI (GPAI) model rules:** Effective August 2025 (already in force)
- **High-risk AI system rules:** Coming into effect August 2026 and August 2027
- **Transparency rules (chatbots, AI disclosure):** Coming into effect August 2026

*Source: European Commission — "AI Act | Shaping Europe's digital future" — digital-strategy.ec.europa.eu — retrieved March 2026*

**What risk category does the Nobi API fall under?**

The EU AI Act defines four risk levels. A general-purpose AI companion API falls under:

**Transparency risk (most relevant to Nobi):** The AI Act states: *"when using AI systems such as chatbots, humans should be made aware that they are interacting with a machine so they can take an informed decision."* 

The transparency rules come into effect August 2026. For API customers building companion applications using Nobi's API:
- The **end-user** of the companion app must be informed they are interacting with AI
- This obligation falls primarily on the **API customer** (as deployer), not Nobi (as provider)
- But Nobi's ToS should require API customers to comply with disclosure obligations

**General Purpose AI (GPAI) model rules (already in force as of August 2025):**
The Commission published guidelines in July 2025 clarifying GPAI obligations. Nobi is likely in scope as a GPAI model provider if the API enables "a wide range of tasks."

GPAI obligations include:
- **Transparency:** Publish a summary of training data (a template was published by the Commission in July 2025)
- **Copyright compliance:** Demonstrate training data copyright compliance (or that data was lawfully used)
- **Safety for high-capability models:** If the model has very high capability (>10^25 FLOPs training compute), systemic risk rules apply — unlikely to apply to Nobi's current models

**High-risk AI — does Nobi qualify?**
The high-risk categories (employment decisions, credit scoring, law enforcement, etc.) do not apply to a general-purpose AI companion API. **Nobi is not high-risk under the EU AI Act** unless API customers deploy it for prohibited use cases — which the ToS should prohibit.

**Prohibited practices (already in force February 2025) — what Nobi must not enable:**
- Harmful AI-based manipulation and deception
- Harmful AI-based exploitation of vulnerabilities
- Social scoring systems
- Real-time biometric identification for law enforcement

These must be explicitly prohibited in the API ToS and enforced via abuse monitoring.

**UK position on the EU AI Act:**
The UK has not adopted the EU AI Act. The UK government's AI regulation approach (as of 2026) is principles-based, sector-specific, and non-legislative at the national level. However, if Nobi provides services to EU customers, the EU AI Act applies to those customers' use of Nobi's API — and Nobi as provider must at minimum facilitate compliance.

---

### 11.8 Insurance Requirements for Commercial AI Services

**This is frequently overlooked and genuinely important.**

Once Nobi accepts payment for API services, it assumes commercial liability. Standard personal/hobby project insurance does not cover this.

**Relevant insurance types for a commercial AI API:**

| Insurance Type | What it Covers | Estimated Annual Cost | Priority |
|---------------|---------------|----------------------|----------|
| **Professional Indemnity (PI)** | Claims from API customers for errors, negligence, service failures | £500–£3,000/year | 🔴 Essential |
| **Cyber Liability** | Data breaches, cyber attacks, notification costs, regulatory fines | £1,000–£5,000/year | 🔴 Essential |
| **Public Liability** | Third-party bodily injury or property damage | £200–£500/year | 🟡 Standard |
| **Directors & Officers (D&O)** | Personal liability of directors for company decisions | £300–£1,000/year | 🟡 Recommended for CIC |

**Professional Indemnity is non-negotiable** for a commercial API. If an API customer suffers loss because Nobi's API returned incorrect output, failed during a critical window, or breached their data, PI insurance covers the legal costs and any settlement.

**Cyber Liability** becomes essential the moment any personal data is processed for business customers. A data breach could trigger: ICO investigation, potential fines, customer notification costs, legal fees, and reputational damage. Cyber liability insurance covers these costs.

**Estimated total insurance overhead:** £2,000–£9,000/year for an early-stage commercial API. This must be factored into the break-even analysis. At lower revenue levels (~£2,000/month API revenue), insurance could represent 10–40% of costs.

**Action required:** Get quotes from specialist insurers (Hiscox, Simply Business, Superscript — all offer tech/AI PI policies) before commercial launch.

---

### 11.9 Legal Compliance Checklist — Pre-Launch Gate

Before accepting the first paying API customer:

| Item | Status | Owner |
|------|--------|-------|
| UK solicitor engaged for CIC trading advice | ❌ Not done | James |
| ICO registration reviewed and confirmed current | ❌ Not done | James |
| DPA template prepared and reviewed by solicitor | ❌ Not done | James + solicitor |
| API Terms of Service drafted | ❌ Not done | James + solicitor |
| Privacy Policy updated for API processing | ❌ Not done | James + solicitor |
| EU AI Act GPAI obligations assessed | ❌ Not done | James + solicitor |
| Professional Indemnity insurance quote obtained | ❌ Not done | James |
| Cyber Liability insurance quote obtained | ❌ Not done | James |
| Data retention policy defined | ❌ Not done | James + Dragon Lord |
| Sub-processor list documented | ❌ Not done | James + Dragon Lord |
| Breach notification procedure documented | ❌ Not done | James |

---

## 12. DATA PROTECTION & PRIVACY POLICY

*This section addresses the specific data protection architecture and privacy policy requirements for operating a commercial AI API alongside a free companion product.*

---

### 12.1 How the Privacy Policy Must Change

The current Privacy Policy (or absence of one) is appropriate for a free companion product. Adding a commercial API creates new processing activities that require explicit disclosure.

**Current state (companion only) — privacy policy covers:**
- User account data (if any)
- Conversation data / memories
- Usage analytics (if any)

**Required additions for commercial API:**

1. **API customer data processing** — what data Nobi collects about API customers (name, company, email, billing info, API usage metrics) and the lawful basis for each
2. **API request processing** — whether and how long prompts and responses are retained
3. **Sub-processors used** — all third-party services that handle data (Stripe for payments, Hetzner/Contabo for hosting, any analytics tools)
4. **International transfers** — where data flows geographically and under what mechanism
5. **B2B customer DPA reference** — noting that business customers receive a separate DPA
6. **Data subject rights** — how API customers' own staff can exercise DSAR, erasure, and rectification rights
7. **Retention periods** — specific periods for each category (billing records: 7 years for tax purposes; API logs: 30 days; API key hashes: duration of account + 30 days)

---

### 12.2 Separate Privacy Policy: API vs Companion?

**Recommended: Yes — separate documents, or a clearly sectioned single document.**

**Option A — Separate documents:**
- `projectnobi.ai/privacy` — for companion users
- `api.projectnobi.ai/privacy` — for API customers and developer documentation

**Advantage:** Each audience sees only relevant information. Companion users aren't confused by B2B DPA references.

**Option B — Sectioned single document:**
- One URL with clearly marked sections: "For Companion Users" / "For API Customers"

**Advantage:** Simpler to maintain; shows unified policy.

**Recommendation:** Start with Option B (simpler), migrate to Option A when the API has significant commercial scale.

---

### 12.3 What User Data Flows Through the API

This is the central question. The answer determines the entire compliance architecture.

**Case 1: Pure inference API (RECOMMENDED)**

```
API Customer → sends prompt → Nobi processes → returns completion → not retained
```

**Data flowing through the API:**
- The prompt text (may contain personal data if the customer includes it)
- The completion text
- API key (pseudonymous identifier)
- IP address, timestamp (for rate limiting and security)
- Token counts (for billing)

**What Nobi retains:**
- API key hash (permanent, for authentication)
- Token count per request (aggregated, for billing — no prompt content)
- IP address + timestamp (for 30 days max, for security)
- **NOT the prompt content** — this is discarded immediately after completion

This design means **no personal data is retained long-term** by default. This is the gold standard from a compliance perspective.

**Case 2: Stateful API with memory (FUTURE/ADVANCED)**

```
API Customer → sends prompt + user_id → Nobi stores memory → next request retrieves memory
```

This is significantly more complex. If Nobi stores memory associated with a `user_id` that can be linked to a real person, this is personal data retention. Requires:
- Explicit consent mechanism for the end-user (via the API customer's app)
- Clear data retention policies with user control
- Erasure mechanism per user_id
- Much more complex DPA terms

**Recommendation:** Do not launch Case 2 without dedicated legal review. Start with Case 1 only.

---

### 12.4 Can API Customers Access Companion User Data?

**NO. Absolutely not. This is a red line with zero flexibility.**

This is stated explicitly in the architectural recommendation (Section 4) and is worth restating here from a data protection perspective.

**Why this must be impossible, not just prohibited:**

Prohibition in ToS is insufficient. If it is architecturally possible for an API customer to access companion user data, the following risks exist:
- An API customer could attempt to access it deliberately (industrial espionage, competitor research)
- A confused developer could accidentally send requests in a way that retrieves other users' data
- A security vulnerability could expose the data even without malicious intent

**The architectural requirement:**
- Companion user database: completely separate from API infrastructure
- No shared authentication tokens between companion and API
- No API endpoints that can query companion user data
- Network-level segmentation between companion and API services

If this separation is not implemented from day one, retrofitting it is expensive and error-prone. Build it right from the start.

---

### 12.5 Data Isolation Architecture Requirements

```
┌─────────────────────────────────────────────────────────────────┐
│                     COMPANION LAYER                              │
│                                                                  │
│  DB: companion_users, memories, conversations                    │
│  Auth: companion session tokens                                  │
│  Network: internal-only, not reachable from API subnet           │
│  Backup: separate backup destination                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ╳ NO DIRECT CONNECTION ╳
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     API LAYER                                    │
│                                                                  │
│  DB: api_customers, api_keys (hashed), usage_metrics            │
│  Auth: API key Bearer tokens                                     │
│  Network: public-facing (api.projectnobi.ai)                     │
│  Logs: request_logs (no prompt content retained)                 │
│  Backup: separate backup destination                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              (shared inference backend only)
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  INFERENCE BACKEND                               │
│  (Bittensor miners / local LLM / Chutes fallback)               │
│  Stateless: receives anonymized prompt, returns completion       │
│  No persistent data storage                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Isolation requirements:**
- Companion DB and API DB must be on separate database instances — not just separate tables
- API servers must not have credentials for the companion database
- Network firewall rules must prevent API subnet from accessing companion subnet
- Audit logging must record any cross-layer access attempts as security incidents

---

### 12.6 Breach Notification Obligations for API Customers

Under UK GDPR, breach notification is a **72-hour obligation** to the ICO when a breach is likely to result in risk to individuals' rights and freedoms.

**ICO's updated guidance (May 28, 2025):** *"Updated guidance to reflect more emphasis on the need for organisations to 'report early' 'update later'"*

*Source: ICO — "UK GDPR data breach reporting" — ico.org.uk/for-organisations/report-a-breach/personal-data-breach/ — retrieved March 2026*

**The chain of notification in the API context:**

```
Data breach occurs (API layer)
         ↓
Nobi detects breach
         ↓
Nobi notifies API customers (data controllers) — "without undue delay" — no specific timeline in law but ICO expects promptness
         ↓
API customer (as controller) assesses risk to their end-users
         ↓
API customer reports to ICO within 72 hours of becoming aware
         ↓
If high risk: API customer also notifies their end-users "without undue delay"
```

**Nobi's specific obligations as processor:**
- Notify the API customer (data controller) of the breach without undue delay
- Provide all information the customer needs to make their own ICO report
- Assist in the investigation
- Implement remediation measures

**Practically, this requires:**
- A documented incident response procedure
- Contact details for all API customers (data controllers)
- A templated breach notification letter ready to send
- 24/7 on-call monitoring to detect breaches in a timely manner (or at minimum, a daily log review process)

---

### 12.7 Data Retention Policies: API vs Companion

**Companion product:**
| Data Type | Retention Period | Legal Basis |
|-----------|-----------------|-------------|
| User account data | Duration of account + 30 days after deletion | Contract |
| Conversation memories | User-controlled (user can delete) | Consent |
| Usage logs | 30 days rolling | Legitimate interests |
| Deleted user data | Purged within 30 days of deletion request | UK GDPR Article 17 |

**API layer:**
| Data Type | Retention Period | Legal Basis |
|-----------|-----------------|-------------|
| API customer billing info | 7 years (UK Companies Act / HMRC requirement) | Legal obligation |
| API key hashes | Duration of account + 30 days | Contract |
| Request logs (IP, timestamp, token count) | 30 days rolling | Legitimate interests |
| Prompt content | **Not retained** — processed and discarded | N/A |
| Completion content | **Not retained** — returned and discarded | N/A |
| Invoices and payment records | 7 years (HMRC) | Legal obligation |
| Support tickets | 3 years after resolution | Legitimate interests |

**Important distinction:** Billing records have a legal minimum retention (7 years for UK tax purposes). Privacy data has a legal maximum (should not be kept longer than necessary). These obligations pull in opposite directions — document each category separately with its specific basis.

---

### 12.8 Privacy Impact Assessment (DPIA) Requirements Under GDPR

The ICO states: *"A Data Protection Impact Assessment (DPIA) is a process to help you identify and minimise the data protection risks of a project. You must do a DPIA for processing that is likely to result in a high risk to individuals."*

**When is a DPIA mandatory for the Nobi API?**

The ICO DPIA screening checklist includes processing that involves:
- ☑️ **Innovative technological or organisational solutions** — AI API is clearly this
- ☑️ **Processing on a large scale** — once the API handles significant volume
- ☑️ **Systematic monitoring** — API request logging could be considered this
- ☑️ **Processing of data of a highly personal nature** — companion conversations

**DPIA is likely required before commercial launch of the API.** This is not merely good practice — the ICO states it is mandatory for high-risk processing.

**What a DPIA must include:**
- Description of the processing: what data, for what purpose, by whom
- Assessment of necessity and proportionality
- Assessment of risks to data subjects
- Identification of additional measures to mitigate risks

**If the DPIA identifies high risk that cannot be mitigated:** *"you must consult the ICO before starting the processing."* — ICO has 8 weeks to respond (14 weeks in complex cases).

**Practical note:** A DPIA for a stateless API with minimal data retention is likely to be low-risk and straightforward. The DPIA documents this — it's not a barrier, it's evidence of compliance. Complete it before launch, keep it updated.

**ICO DPIA template:** Available at ico.org.uk — the ICO provides a .docx template.

---

### 12.9 ICO Registration Requirements for Commercial Data Processing

**UK organisations that process personal data must register with the ICO** (formerly called "notification"). This is a legal requirement under the Data Protection (Charges and Information) Regulations 2018.

**Cost:**
- Tier 1 (turnover < £632,000 or fewer than 10 staff): **£40/year**
- Tier 2 (turnover < £36M): **£60/year**
- Tier 3 (turnover ≥ £36M): **£2,900/year**

At early-stage API revenue, Nobi would be Tier 1 (£40/year) or Tier 2 (£60/year).

**Key requirements:**
- Register before processing begins (not after)
- Update registration when processing activities change significantly
- The CIC entity (not James personally) should be the registered data controller

**Data not known:** Whether Nobi/the CIC is currently registered with the ICO. This must be checked and confirmed before API launch. Non-registration is a criminal offence under UK law.

**Action:** Check current ICO registration status at ico.org.uk/for-organisations/register-with-the-ico/ and register or update if needed.

---

### 12.10 Summary: Privacy & Data Protection Pre-Launch Checklist

| Action | Priority | Cost Estimate | Deadline |
|--------|----------|--------------|----------|
| Confirm ICO registration (or register) | 🔴 Critical | £40–60/year | Before any commercial launch |
| Complete DPIA for API processing | 🔴 Critical | ~5 hrs work + solicitor review | Before beta launch |
| Draft updated Privacy Policy (API section) | 🔴 Critical | Solicitor: ~£500–800 | Before beta launch |
| Draft standard DPA template for business customers | 🔴 Critical | Solicitor: ~£500–1,000 | Before accepting B2B customers |
| Define and document data retention policy | 🔴 Critical | Internal: ~4 hrs | Before beta launch |
| Architect data isolation (companion vs API) | 🔴 Critical | Development: ~40 hrs | Before any API processes user data |
| Draft API Terms of Service | 🔴 Critical | Solicitor: ~£800–1,500 | Before commercial launch |
| Obtain PI insurance | 🟡 Important | £500–£3,000/year | Before commercial launch |
| Obtain Cyber Liability insurance | 🟡 Important | £1,000–£5,000/year | Before commercial launch |
| Implement breach notification procedure | 🟡 Important | Internal: ~8 hrs | Before commercial launch |
| Assess GPAI obligations under EU AI Act | 🟡 Important | Solicitor: ~£500 | Before serving EU customers |
| Document sub-processor list | 🟡 Important | Internal: ~2 hrs | Before commercial launch |

**Estimated legal/compliance pre-launch cost:** £3,000–£9,000 (solicitor + insurance first year) — this must be factored into break-even analysis from the original report.

---

## REVISED BREAK-EVEN ANALYSIS

*Incorporating legal/compliance costs identified in Sections 11–12:*

| Cost Category | Estimated Monthly Cost |
|--------------|----------------------|
| Infrastructure (servers, compute) | ~£950–£1,500/month |
| API-specific infrastructure (Redis, Postgres, monitoring) | ~£200–£400/month |
| Insurance (PI + Cyber, amortised monthly) | ~£120–£670/month |
| Legal (ongoing solicitor for changes, amortised) | ~£50–£200/month |
| Stripe fees (2.9% + £0.30 per transaction) | Variable |
| **Revised total monthly overhead** | **~£1,320–£2,770/month** |

**Revised break-even (including compliance costs):**
- At $20 Developer / $99 Business pricing
- Need ~25–30 Business customers OR ~140 Developer customers to cover all costs
- A single enterprise deal at £500/month still covers a significant portion of API overhead

---

## APPENDIX: Additional Data Sources (Sections 10–12)

| Source | Data Used | URL | Retrieved |
|--------|-----------|-----|-----------|
| ICO — Lawful basis guide | UK GDPR Article 6 six bases, exact text | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/ | March 2026 |
| ICO — Controllers and processors | Controller/processor definitions verbatim; sub-processor rules | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/controllers-and-processors/ | March 2026 |
| ICO — Right to erasure | Article 17 erasure right; one-month response timeline | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/ | March 2026 |
| ICO — International transfers | Restricted transfer definition; transfer mechanisms (IDTA, BCRs); adequacy regulations updated Jan 15, 2026 | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/ | March 2026 |
| ICO — Data breach reporting | 72-hour notification requirement; "report early, update later" guidance (updated May 28, 2025) | ico.org.uk/for-organisations/report-a-breach/personal-data-breach/ | March 2026 |
| ICO — DPIA guidance | When DPIA is mandatory; DPIA template available; 8-week ICO consultation | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/guide-to-accountability-and-governance/data-protection-impact-assessments/ | March 2026 |
| ICO — Legitimate interests | When to use legitimate interests; three-part test; limitations | ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/legitimate-interests/ | March 2026 |
| EU Commission — AI Act | Four risk tiers; GPAI rules effective August 2025; transparency rules August 2026; prohibited practices February 2025 | digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | March 2026 |
| GOV.UK — CIC guidance | CIC structure, asset lock, community interest test | gov.uk/set-up-a-social-enterprise | March 2026 |

### Data Gaps — Sections 10–12

- **ICO registration fees:** The £40/£60/£2,900 tier structure was verified from general knowledge of UK law (Data Protection (Charges and Information) Regulations 2018). The ICO registration page returned a 404 during retrieval — fees may have been updated. Verify directly at ico.org.uk before registering.
- **CIC commercial trading — specific rules:** Multiple gov.uk pages for CIC detailed guidance returned 404 errors. The general CIC structure (community interest test, asset lock, can trade commercially) is confirmed. Specific constraints on revenue distribution are documented in the Companies (Community Interest Company) Regulations 2005 — consult a solicitor for current rules.
- **UK AI regulation (non-EU AI Act):** The UK government's specific AI regulatory framework was not directly retrieved. The UK position is principles-based and sector-specific as of 2025/2026. Consult a tech law specialist for current UK AI guidance.
- **Insurance pricing:** All insurance cost estimates are illustrative ranges based on general market knowledge for small tech companies. Obtain actual quotes from Hiscox, Superscript, or Simply Business for accurate figures.

---

*Sections 10–12 added March 25, 2026 at James's direction. Full report now covers all dimensions of the API commercialization decision.*

*This report was prepared using verified data from public sources as of March 2026. All projections are illustrative and should not be relied upon for financial planning. Legal sections are for informational purposes only and do not constitute legal advice. Consult a qualified UK solicitor and accountant before commercializing API services.*

---

