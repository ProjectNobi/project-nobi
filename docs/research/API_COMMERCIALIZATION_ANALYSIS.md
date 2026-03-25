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
3. **Recommended jurisdiction: Ireland** — incorporate as an Irish Private Company Limited by Shares (LTD) for EU market access, 12.5% corporation tax, and DPC as lead EU data regulator. Confirm structure with an Irish solicitor.
4. Revenue should flow **back into the ecosystem** (infrastructure, open source development, community grants)
5. A **self-hosting option** must ship alongside the paid API — open source commitment preserved

**Key risks:** mission drift, community backlash in the crypto space, Irish incorporation setup (CMC risk, EEA director), and the technical complexity of billing infrastructure at an early stage.

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

### 3.1 Irish Entity Options — LTD or CLG?

**Recommended structure: Irish Private Company Limited by Shares (LTD)**

Ireland's Companies Act 2014 provides a modern, flexible corporate framework. The recommended entity for Nobi's commercial API is the **Private Company Limited by Shares (LTD)**:

- One director is sufficient (plus a company secretary)
- No minimum share capital requirement
- Can carry on any lawful business activity — no restrictions on trading
- Profits can be distributed to shareholders
- Subject to corporation tax at **12.5%** on active trading income
- Eligible for the **Knowledge Development Box (10% effective rate on IP income)** and **35% R&D tax credit**
- Audit exemption available for small companies (turnover ≤ €12M)
- Registration fee: €50 (CRO online)

**Alternative: Company Limited by Guarantee (CLG)**

A CLG is the Irish equivalent of a community/not-for-profit entity. It *can* earn commercial revenue, but:
- No share capital — members guarantee a nominal sum (e.g. €1)
- Profits must generally be reinvested in the company's objects
- Not suitable for investment or eventual exit
- Would be appropriate for a separate community-focused arm — **not** for the commercial API entity

**Action required:** Engage an Irish solicitor to advise on incorporation structure, CMC risk (central management and control — see Section 14.6), and the EEA-resident director requirement. This is a legal opinion, not a business decision.

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

Any business paying for API access in the EU/UK will require:
- A **Data Processing Agreement (DPA)** — mandatory under EU GDPR Article 28 (directly applicable in Ireland via the Data Protection Act 2018)
- If the API processes any personal data on behalf of the business customer, Nobi acts as a **data processor**
- Business customer is the **data controller** — they're responsible for what they send
- Nobi must implement appropriate technical and organisational measures (TOMs)

**Immediate legal requirements upon API launch:**
1. DPA template (DPC provides guidance; a solicitor can produce a reusable template for ~€500–€1,000)
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

### 3.5 Irish Tax Regime

An Irish LTD is subject to:
- **Corporation Tax:** **12.5%** on active trading income (one of the lowest in the EU/world). Passive income (dividends, royalties, interest) taxed at 25%. Capital gains at 33%.
- **Knowledge Development Box (KDB):** **10% effective rate** on profits from qualifying intellectual property (copyrighted software, patents). API revenue from software Nobi owns and developed may qualify, reducing the effective rate from 12.5% to 10%.
- **R&D Tax Credit:** **35% fully refundable** credit on qualifying R&D expenditure (AI model development, novel software engineering). Combined with the standard 12.5% deduction, the effective benefit is **47.5% of qualifying R&D spend** returned to the company.
- **Startup Corporation Tax Exemption:** New companies may be exempt from corporation tax for the first three years (up to €40,000 relief per year), subject to trading income thresholds.
- **VAT:** Standard rate is 23%. VAT registration mandatory if annual turnover exceeds **€42,500** (for services). B2B sales to VAT-registered EU businesses use the reverse charge mechanism (0% Irish VAT charged — customer accounts for VAT in their own jurisdiction). Lower threshold than UK (£90k), so registration required earlier.
- **PAYE:** If revenue funds salaries paid to Irish-based employees or directors, standard Irish PAYE applies.

**Key advantage vs UK:** On €1M trading profit, Irish corp tax = €125,000. UK corp tax = £250,000. Ireland is roughly half the tax burden. The R&D credit (35% vs UK's 20%) also delivers significantly more cash back to fund development.

**Practical note:** Engage a qualified Irish chartered accountant from day one. Confirm KDB eligibility before assuming the 10% rate applies. The CMC (central management and control) issue must be correctly structured to ensure Irish tax residency holds — see Section 14.6.

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
| **Irish LTD Structure** | Flexible, commercial, EU market access | Medium — strong for investors and EU customers |

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
| Trust/transparency | Limited | Open source + Irish LTD (no asset lock, community transparency) |

**The pitch to developers:** "Build a personalized AI companion for your app in one API call, not six services stitched together."

---

## 7. RISK ANALYSIS

### 7.1 Risk Matrix

| Risk | Likelihood | Impact | Severity | Mitigation |
|------|-----------|--------|----------|-----------|
| Mission drift | Medium | Critical | 🔴 High | Hard rule: free companion never degrades |
| Community backlash | Medium | High | 🔴 High | Transparent framing before launch |
| Bittensor network instability | High | Medium | 🟡 Medium | Fallback inference providers |
| Irish legal/compliance setup | Low | Medium | 🟡 Medium | Engage Irish solicitor before launch; address CMC risk |
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
- [ ] Get legal opinion from Irish solicitor on LTD incorporation, CMC risk, and EEA-resident director requirement

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
- Irish LTD incorporated, solicitor legal clearance obtained

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
| Legal (Irish solicitor) | ~5 hrs | ~5 hrs | ~2 hrs |
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
1. ✅ Engage an Irish solicitor: incorporate Irish LTD, address CMC risk, appoint EEA-resident director or arrange Section 137 bond, confirm DPC registration requirements
2. ✅ Publish a public transparency statement about the API concept before building — community-first, no surprises
3. ✅ James confirms exact current infrastructure costs — break-even analysis needs real numbers

**Before accepting any payment:**
4. ✅ Irish LTD incorporated and DPC registration confirmed
5. ✅ Privacy Policy updated for API data processing (referencing Irish DPA 2018 and GDPR)
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
🚫 **NEVER** launch billing before Irish LTD is incorporated and DPC-registered
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
| CRO Ireland | Irish LTD structure, €50 registration fee, one director rule | cro.ie | March 2026 |

### Data Gaps (Honest Disclosure)

- **Corcel pricing:** Corcel pricing page returned 404. Corcel appears to have shut down or pivoted. Historical $15/month developer tier reported from community sources but not directly verified.
- **Taoshi API pricing:** Public pricing page not found. Reported as subscription-based from community knowledge but exact figures not retrieved.
- **Groq Llama model pricing:** Groq pricing page showed GPT OSS models. Traditional Llama pricing not captured in retrieved data.
- **James's actual infrastructure costs:** Required for accurate break-even — placeholder estimates used in this report.
- **Cohere per-token rates:** Cohere has pivoted to enterprise-only pricing with no public per-token rates.
- **Irish LTD CMC risk:** The central management and control question for a UK-resident founder operating an Irish company requires specialist Irish tax advice. Engage an Irish chartered tax adviser before incorporating.

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

*All legal citations in this section are sourced from official EU/Irish government and DPC guidance, supplemented by ICO guidance where relevant to UK users. This section is informational only and does not constitute legal advice. Engage a qualified Irish solicitor before acting on any of this.*

---

### 11.1 GDPR Article 6 — Lawful Basis for Processing (Irish Law)

Under **EU GDPR** (directly applicable in Ireland; implemented via the Irish Data Protection Act 2018), **every processing activity requires a lawful basis**. Article 6 provides six possible bases. The DPC (Data Protection Commission, Ireland) states that controllers must identify the correct basis before processing begins.

*Source: DPC — GDPR guidance — dataprotection.ie; EU GDPR Article 6 — EUR-Lex — retrieved March 2026*

**The six lawful bases under Article 6:**

| Basis | Description | Applies to Nobi API? |
|-------|-------------|---------------------|
| (a) Consent | Individual gives clear consent for specific purpose | Companion users: yes. API customer B2B contact data: possibly |
| (b) Contract | Processing necessary for a contract with the individual | ✅ API customers: processing their account/billing data to fulfil the API contract |
| (c) Legal obligation | Processing required by law | For tax records, breach reporting — limited use |
| (d) Vital interests | Protect someone's life | Not applicable |
| (e) Public task | Public authority performing official functions | Not applicable (Irish LTD is not a public authority) |
| (f) Legitimate interests | Necessary for legitimate interests, proportionate | ✅ API request logging for security/abuse prevention |

**For the API — which bases apply where:**

| Data Being Processed | Most Appropriate Basis | Notes |
|----------------------|----------------------|-------|
| API customer billing info | **Contract (b)** | Processing name, email, payment method to deliver the paid service |
| API request logs (IP, timestamp, request hash) | **Legitimate interests (f)** | Security monitoring, rate limiting, abuse prevention |
| API customer account data | **Contract (b)** | Account management |
| Marketing emails to API prospects | **Consent (a)** | Must be opt-in; cannot rely on contract for marketing |
| Prompts sent via API | Depends on content — see Section 12 | May contain personal data |

**DPC/GDPR principle:** The correct lawful basis must be identified before collecting data, not retrofitted after the fact. This is a core GDPR principle enforced by the DPC.

---

### 11.2 Data Controller vs Data Processor — The Roles When Businesses Use the Nobi API

This is the most complex and consequential legal question for the API model. The roles are not fixed — they depend on **who decides why and how data is processed**.

**EU GDPR definitions (Article 4):**
> *"'controller' means the natural or legal person, public authority, agency or other body which, alone or jointly with others, determines the purposes and means of the processing of personal data."*
> *"'processor' means a natural or legal person, public authority, agency or other body which processes personal data on behalf of the controller."*

*Source: EU GDPR Article 4 — EUR-Lex; DPC guidance — dataprotection.ie — retrieved March 2026*

**Applied to the Nobi API — three scenarios:**

**Scenario A: Developer sends only their own test data (no end-user personal data)**
- No personal data of third parties involved
- GDPR largely not engaged for the API layer
- Simplest case; no DPA needed for this scenario alone

**Scenario B: Developer builds an app that sends their end-users' conversations to the Nobi API**
- The developer is the **data controller** (they decided to build the app and collect user data)
- Nobi is the **data processor** (processing data on behalf of the developer per the API contract)
- **A DPA is mandatory under EU GDPR Article 28** — this is not optional
- Nobi must: only process data per the developer's instructions; maintain confidentiality; implement appropriate security measures; not engage sub-processors without the developer's consent; assist with subject rights requests; delete data when instructed

**Scenario C: Developer's app users' data could be linked back to companion users**
- **This must not happen** — it creates joint controller complexity, potential data breaches, and is architecturally prohibited
- This is the red line that requires architectural separation

**What a DPA must contain (per EU GDPR Article 28):**
- Subject matter and duration of the processing
- Nature and purpose of the processing
- Type of personal data and categories of data subjects
- Obligations and rights of the controller
- Processor's obligations: process only on documented instructions; confidentiality; security; sub-processor restrictions; assist with rights requests; delete/return data; provide compliance information

**GDPR position on processor liability (Article 28 / recital 81):**
If a processor acts without the controller's instructions in such a way that it determines the purpose and means of processing, it will be treated as a controller in respect of that processing and will have the same liability as a controller.

This means if Nobi's API code makes decisions about what to do with data beyond what the customer instructed (e.g., retaining prompts for model training without consent), Nobi becomes a joint controller and takes on full GDPR liability.

---

### 11.3 Data Processing Agreements (DPAs) for Business API Customers

**DPAs are legally mandatory** whenever a controller (API customer) uses a processor (Nobi) to handle personal data, per EU GDPR Article 28(3).

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

**Getting a DPA template:** The DPC publishes GDPR guidance and templates at dataprotection.ie. For a DPA specifically (different from a DPIA), an Irish solicitor can produce a standard template for ~€500–€1,000 that can be reused across all customers.

---

### 11.4 International Data Transfers — EU GDPR Framework (Irish Entity)

When API customers outside the EEA send data to Nobi's Irish-incorporated entity, **or** when Nobi sends data to servers outside the EEA (e.g., US-based Bittensor miners globally), international transfer rules apply.

**Irish/EU framework:**

EU GDPR Chapter V governs restricted transfers — transfers of personal data to third countries outside the EEA. As an Irish entity, Nobi uses the EU framework directly (Standard Contractual Clauses, adequacy decisions, etc.) — no UK-specific instruments (IDTAs) required.

**EU Adequacy Decisions (as of March 2026):**
- UK: The EU has an adequacy decision for the UK (subject to periodic review). Data can flow from Ireland → UK without additional safeguards for now.
- US: EU-US Data Privacy Framework (DPF, adopted July 2023) covers transfers to certified US companies. For non-certified US recipients, EU Standard Contractual Clauses (Commission Decision 2021/914) apply.
- Other countries: check the EU Commission adequacy list

**Schrems II context:** Schrems II (C-311/18, 2020) invalidated the EU-US Privacy Shield. The current EU-US DPF is the replacement, though it faces ongoing legal challenges. For transfers to the US, EU SCCs remain the safer backstop.

**For Nobi's API — practical implications:**

| Data Flow | Transfer Mechanism Required |
|-----------|---------------------------|
| Ireland servers → Contabo Germany (EU) | EEA-internal — no restricted transfer |
| Ireland servers → UK-based customers/servers | EU adequacy decision for UK |
| Ireland servers → US-based enterprise customer | EU-US DPF (if certified) or EU SCCs |
| Ireland servers → Bittensor miners (global, unknown location) | **Complex — miners are globally distributed; their jurisdictions are unknown** |
| Non-EU/non-EEA API customer → Irish servers | EU GDPR applies to Nobi's processing regardless |

**The Bittensor miner problem:** Bittensor miners are geographically distributed and pseudonymous. When API data flows through Bittensor miners as part of inference, that data is technically being transmitted to servers in unknown international locations. This is a genuine international transfer compliance challenge.

**Mitigation options:**
- Use only known, EU/EEA-hosted miners for API traffic
- Process API requests on controlled servers (Hetzner1, Contabo Germany) using local model only, bypassing distributed Bittensor miners for personal data
- Or: design the API so no personal data flows through the Bittensor network — inference is done on controlled servers, only anonymised requests go to miners

**UK users and ICO:** UK users of Nobi's companion app have rights under UK GDPR enforced by the UK ICO. When dealing with complaints or rights requests from UK users, Nobi should be aware of ICO jurisdiction. However, **the DPC is Nobi's lead supervisory authority** for all EU operations under the One-Stop-Shop mechanism.

---

### 11.5 Right to Erasure — Complications in the API Context

Under **EU GDPR Article 17**, individuals have the right to have personal data erased ("right to be forgotten"). This applies to Nobi as an Irish-incorporated entity processing EU personal data.

**When does this affect the Nobi API?**

If an API customer's end-user submits an erasure request to the API customer (the controller), the API customer must:
1. Erase the data they hold directly
2. Pass the erasure request to all processors — including Nobi's API

Nobi must then erase any retained data relating to that individual and inform sub-processors accordingly.

**Key complications:**

**API request logs:** If Nobi retains logs containing personal data (e.g., prompts that include names, emails, or other identifiers), these must be erasable on request. This requires:
- Logs must be structured to allow targeted deletion (not just rolling time-based purges)
- The ability to identify which log entries relate to which individual across potentially millions of records

**Backup systems:** Under EU GDPR, immediate deletion from backups may not always be possible, but the data should be suppressed and not restored from backup after an erasure request.

**The stateless API design solution:** If the API is genuinely stateless — prompts processed and not retained beyond the immediate response — erasure requests are trivially handled: there is nothing to erase. **This is the strongest argument for a strict no-retention API design as a default.** It eliminates the erasure complication almost entirely.

**Response time:** Erasure requests must be responded to within **one month** (with possible 2-month extension for complex cases).

---

### 11.6 API Terms of Service — Liability, Indemnification, SLA Commitments

**What the API ToS must address:**

**Liability limitations:**
- Irish consumer law (Consumer Rights Act 2022, implementing EU directives) restricts liability exclusions for consumers. B2B API customers (businesses) have less protection — liability can be more fully excluded by contract.
- Standard practice: exclude consequential loss, cap liability at 12 months of subscription fees paid.
- Must not exclude liability for death, personal injury, or fraud — these cannot be limited under Irish/EU law.

**Irish/EU Consumer Rights Act 2022 — important note:**
- Applies to B2C relationships. If Nobi's API is sold directly to individual developers (not through a business), consumer protection rules apply.
- Digital services must be of satisfactory quality, fit for purpose, and as described.
- For B2B customers (companies), standard commercial contract terms apply with more flexibility.
- **Practical implication:** Clearly define who can buy the API. If "Developer tier" includes individual developers (not just companies), the consumer rules apply. This is likely fine — just ensure the API actually works as described.

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

**Irish/EU position on the EU AI Act:**
Ireland, as an EU member state, is subject to the EU AI Act directly — no implementing legislation required. As an Irish-incorporated entity, Nobi is within the EU AI Act's scope. This is an advantage as well as an obligation: once compliant, Nobi can claim conformity across the entire EU single market without navigating 27 separate national frameworks.

**Note on UK API customers:** The UK has not adopted the EU AI Act. UK customers using Nobi's API are not subject to it on their end. However, Nobi (as an Irish entity providing AI services) must comply with the AI Act regardless of the customer's location.

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
| Irish solicitor engaged for LTD incorporation, CMC risk, EEA director | ❌ Not done | James |
| Irish LTD incorporated (CRO, €50 online) | ❌ Not done | James + solicitor |
| DPC registration confirmed for Irish entity | ❌ Not done | James + solicitor |
| DPA template prepared and reviewed by solicitor | ❌ Not done | James + solicitor |
| API Terms of Service drafted (Irish law) | ❌ Not done | James + solicitor |
| Privacy Policy updated for API processing (referencing DPA 2018 and GDPR) | ❌ Not done | James + solicitor |
| EU AI Act GPAI obligations assessed | ❌ Not done | James + solicitor |
| Professional Indemnity insurance quote obtained (Irish/EU provider) | ❌ Not done | James |
| Cyber Liability insurance quote obtained | ❌ Not done | James |
| Data retention policy defined | ❌ Not done | James + Dragon Lord |
| Sub-processor list documented | ❌ Not done | James + Dragon Lord |
| Breach notification procedure documented (DPC 72-hour rule) | ❌ Not done | James |

---

## 12. DATA PROTECTION & PRIVACY POLICY

*This section addresses the specific data protection architecture and privacy policy requirements for operating a commercial AI API alongside a free companion product. Ireland is the chosen jurisdiction — all references are to Irish DPA 2018, EU GDPR, and the DPC (Data Protection Commission) as lead supervisory authority.*

---

### 12.1 How the Privacy Policy Must Change

The current Privacy Policy (or absence of one) is appropriate for a free companion product. Adding a commercial API creates new processing activities that require explicit disclosure under EU GDPR (directly applicable in Ireland via the Data Protection Act 2018).

**Applicable law:** EU GDPR + Irish Data Protection Act 2018. The DPC (dataprotection.ie) is the supervisory authority. GDPR applies directly — no UK-specific framework required.

**Current state (companion only) — privacy policy covers:**
- User account data (if any)
- Conversation data / memories
- Usage analytics (if any)

**Required additions for commercial API:**

1. **API customer data processing** — what data Nobi collects about API customers (name, company, email, billing info, API usage metrics) and the lawful basis for each
2. **API request processing** — whether and how long prompts and responses are retained
3. **Sub-processors used** — all third-party services that handle data (Stripe for payments, Hetzner/Contabo for hosting, any analytics tools)
4. **International transfers** — where data flows geographically and under what mechanism (EU SCCs, EU-UK adequacy, etc.)
5. **B2B customer DPA reference** — noting that business customers receive a separate DPA
6. **Data subject rights** — how API customers' own staff can exercise DSAR, erasure, and rectification rights under EU GDPR
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

Under **EU GDPR Article 33**, breach notification is a **72-hour obligation** to the DPC when a breach is likely to result in risk to individuals' rights and freedoms.

*Source: DPC — dataprotection.ie/en/news-media/press-releases; EU GDPR Article 33 — EUR-Lex — retrieved March 2026*

**The chain of notification in the API context:**

```
Data breach occurs (API layer)
         ↓
Nobi detects breach
         ↓
Nobi notifies API customers (data controllers) — "without undue delay" — Article 33(2) processor obligation
         ↓
API customer (as controller) assesses risk to their end-users
         ↓
API customer reports to their lead supervisory authority within 72 hours of becoming aware
  (DPC if Irish/EU entity; ICO if UK-based controller for UK-user data)
         ↓
If high risk: API customer also notifies their end-users "without undue delay" (Article 34)
```

**Nobi's specific obligations as processor (Article 33(2)):**
- Notify the API customer (data controller) of the breach without undue delay
- Provide all information the customer needs to make their own DPC/ICO report
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
| Deleted user data | Purged within 30 days of deletion request | EU GDPR Article 17 |

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

**Important distinction:** Billing records have a legal minimum retention (7 years for Irish/EU tax purposes). Privacy data has a legal maximum (should not be kept longer than necessary). These obligations pull in opposite directions — document each category separately with its specific basis.

---

### 12.8 Privacy Impact Assessment (DPIA) Requirements Under GDPR

Under **EU GDPR Article 35**, a Data Protection Impact Assessment (DPIA) is mandatory when processing is likely to result in a high risk to individuals' rights and freedoms. The DPC follows the EDPB (European Data Protection Board) guidelines on when DPIAs are required.

**When is a DPIA mandatory for the Nobi API?**

The EDPB/DPC criteria for mandatory DPIA includes processing that involves:
- ☑️ **Innovative technological or organisational solutions** — AI API is clearly this
- ☑️ **Processing on a large scale** — once the API handles significant volume
- ☑️ **Systematic monitoring** — API request logging could be considered this
- ☑️ **Processing of data of a highly personal nature** — companion conversations (emotional/mental health context)

**DPIA is likely required before commercial launch of the API.** This is not merely good practice — EU GDPR Article 35 makes it mandatory for high-risk processing.

**What a DPIA must include:**
- Description of the processing: what data, for what purpose, by whom
- Assessment of necessity and proportionality
- Assessment of risks to data subjects
- Identification of additional measures to mitigate risks

**If the DPIA identifies high risk that cannot be mitigated:** Prior consultation with the DPC is required (Article 36). The DPC has 8 weeks to respond (14 weeks in complex cases).

**Practical note:** A DPIA for a stateless API with minimal data retention is likely to be low-risk and straightforward. The DPIA documents this — it's not a barrier, it's evidence of compliance. Complete it before launch, keep it updated.

**DPC DPIA guidance:** Available at dataprotection.ie — the DPC provides templates and guidance aligned with EDPB standards.

---

### 12.9 DPC Registration Requirements for Commercial Data Processing (Ireland)

**Irish organisations that process personal data must register with the DPC** as a data controller. This is a legal requirement under the Irish Data Protection Act 2018 and EU GDPR.

**DPC registration fees (approximate as of March 2026):**
- Small organisations / not-for-profits: ~**€100/year**
- Commercial companies: fee based on size and nature of processing

**Key requirements:**
- Register before processing personal data
- Update registration when processing activities change significantly
- The Irish LTD (not James personally) is the registered data controller

**One-Stop-Shop advantage:** As an Irish entity with its main EU establishment in Ireland, Nobi benefits from the GDPR One-Stop-Shop mechanism — the DPC acts as lead supervisory authority for all cross-border EU processing. This means one regulator, one set of rules, across all 27 EU member states.

**Action:** Register with the DPC at dataprotection.ie before API launch. Confirm current registration requirements with the Irish solicitor at incorporation.

---

### 12.10 Summary: Privacy & Data Protection Pre-Launch Checklist

| Action | Priority | Cost Estimate | Deadline |
|--------|----------|--------------|----------|
| Register with DPC (Irish entity, data controller) | 🔴 Critical | ~€100/year | Before any commercial launch |
| Complete DPIA for API processing (referencing DPC/EDPB guidelines) | 🔴 Critical | ~5 hrs work + solicitor review | Before beta launch |
| Draft updated Privacy Policy (API section, EU GDPR / Irish DPA 2018) | 🔴 Critical | Solicitor: ~€500–€800 | Before beta launch |
| Draft standard DPA template for business customers | 🔴 Critical | Solicitor: ~€500–€1,000 | Before accepting B2B customers |
| Define and document data retention policy | 🔴 Critical | Internal: ~4 hrs | Before beta launch |
| Architect data isolation (companion vs API) | 🔴 Critical | Development: ~40 hrs | Before any API processes user data |
| Draft API Terms of Service (Irish law) | 🔴 Critical | Solicitor: ~€800–€1,500 | Before commercial launch |
| Obtain PI insurance (Irish/EU provider) | 🟡 Important | €500–€3,000/year | Before commercial launch |
| Obtain Cyber Liability insurance | 🟡 Important | €1,000–€5,000/year | Before commercial launch |
| Implement breach notification procedure (DPC 72-hour rule) | 🟡 Important | Internal: ~8 hrs | Before commercial launch |
| Assess GPAI obligations under EU AI Act (mandatory for Irish entity) | 🟡 Important | Solicitor: ~€500 | Before serving EU customers |
| Document sub-processor list | 🟡 Important | Internal: ~2 hrs | Before commercial launch |

**Estimated legal/compliance pre-launch cost:** €3,000–€9,000 (solicitor + insurance first year) + Irish company incorporation/compliance (~€5,500–€7,000/year) — factor both into break-even analysis.

---

## REVISED BREAK-EVEN ANALYSIS

*Incorporating legal/compliance costs identified in Sections 11–12 (Irish jurisdiction):*

| Cost Category | Estimated Monthly Cost |
|--------------|----------------------|
| Infrastructure (servers, compute) | ~€950–€1,500/month |
| API-specific infrastructure (Redis, Postgres, monitoring) | ~€200–€400/month |
| Irish company compliance (registered office, secretary, accountant, amortised) | ~€460–€580/month |
| Insurance (PI + Cyber, amortised monthly) | ~€120–€670/month |
| Legal (ongoing solicitor for changes, amortised) | ~€50–€200/month |
| Stripe fees (2.9% + €0.30 per transaction) | Variable |
| **Revised total monthly overhead** | **~€1,780–€3,350/month** |

**Revised break-even (including compliance costs):**
- At $20 Developer / $99 Business pricing
- Need ~30–35 Business customers OR ~165 Developer customers to cover all costs
- A single enterprise deal at €500/month covers a significant portion of API overhead
- The Irish R&D tax credit (35% refundable) partially offsets development costs — factor this into annual cash flow planning

---

## APPENDIX: Additional Data Sources (Sections 10–12)

| Source | Data Used | URL | Retrieved |
|--------|-----------|-----|-----------|
| EU GDPR Article 6 (EUR-Lex) | Six lawful bases for processing; directly applicable in Ireland | eur-lex.europa.eu/eli/reg/2016/679/oj | March 2026 |
| DPC — GDPR guidance | Controller/processor definitions; DPC as lead supervisory authority; DPIA and breach guidance | dataprotection.ie | March 2026 |
| EU GDPR Article 17 (EUR-Lex) | Right to erasure; one-month response timeline | eur-lex.europa.eu/eli/reg/2016/679/oj | March 2026 |
| EU Commission — International transfers | SCCs; EU-UK adequacy decision; EU-US DPF | ec.europa.eu/info/law/law-topic/data-protection/international-dimension-data-protection | March 2026 |
| DPC Press Releases | Breach notification guidance; 72-hour rule; DPC investigations | dataprotection.ie/en/news-media/press-releases | March 2026 |
| EDPB — DPIA guidelines | When DPIA is mandatory; 8-week prior consultation | edpb.europa.eu/our-work-tools/our-documents/guidelines | March 2026 |
| EU Commission — AI Act | Four risk tiers; GPAI rules effective August 2025; transparency rules August 2026; prohibited practices February 2025 | digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | March 2026 |
| Irish DPA 2018 | Ireland's implementation of EU GDPR; opening clauses (age of consent: 16) | legislation.ie | March 2026 |
| ICO (UK) — data protection | Referenced only where UK users' rights are discussed; ICO is NOT Nobi's lead authority | ico.org.uk | March 2026 |

### Data Gaps — Sections 10–12

- **DPC registration fees:** The ~€100/year figure is approximate. Verify directly at dataprotection.ie before registering — fees may have been updated.
- **Irish LTD compliance costs:** Annual cost estimates (€5,500–€7,000) are market estimates based on Irish professional fee norms. Obtain actual quotes from an Irish solicitor, accountant, and company secretarial firm.
- **EU AI Act compliance:** The GPAI rules (effective August 2025) and transparency obligations (effective August 2026) require specialist assessment. Engage an Irish tech law solicitor for a full EU AI Act gap analysis before API launch.
- **Insurance pricing:** All insurance cost estimates are illustrative ranges based on general market knowledge for small tech companies. Obtain actual quotes from Irish/EU insurers (Allianz, AXA, FBD, or specialist brokers) for accurate figures.
- **ICO note:** The ICO remains relevant only where Nobi processes data of UK users. For Nobi's own obligations as a data controller/processor, the DPC is the lead authority.

---

*Sections 10–12 added March 25, 2026 at James's direction. Updated March 25, 2026 to reflect Ireland as the chosen jurisdiction (UK/CIC references removed).*

*This report was prepared using verified data from public sources as of March 2026. All projections are illustrative and should not be relied upon for financial planning. Legal sections are for informational purposes only and do not constitute legal advice. Consult a qualified Irish solicitor and chartered accountant before incorporating in Ireland or commercializing API services.*

---


---

## 14. Irish Jurisdiction Analysis

**Prepared:** March 25, 2026 | **Research basis:** PwC Worldwide Tax Summaries (Ireland), Revenue.ie, EU AI Act (Regulation 2024/1689 — Wikipedia/EUR-Lex), DPC press releases, Companies Registration Office (CRO), general knowledge of Irish company law.

James asked this question: *Is Ireland a better place to incorporate Nobi's commercial entity than the UK?* This section answers that directly, with real data and honest caveats.

---

### 14.1 Why Ireland?

Ireland has become the undisputed European headquarters of choice for global technology companies. Google, Meta (Facebook), Apple, LinkedIn, Twitter/X, Stripe, Airbnb, Zoom, and TikTok have all established their European or international headquarters in Dublin or Cork. This is not coincidental — it reflects a deliberate, multi-decade policy of creating one of the world's most business-friendly environments for technology companies.

**Key structural advantages for a UK-based founder building an AI startup:**

1. **EU Single Market Access (post-Brexit):** Ireland is an EU member state. An Irish-incorporated company can sell, contract, process data, and employ across all 27 EU member states under a single legal framework. A UK company must navigate separate regulatory access negotiations for each EU market — impossible at startup scale. For Nobi, where the companion app and API will target European consumers and businesses, Irish incorporation puts you inside the tent.

2. **English-speaking common law jurisdiction:** Ireland's legal system is a common law system derived from English law, substantially similar to UK law. Courts apply similar principles of contract, tort, and corporate law. There's no language barrier, no need for legal translation, and many UK solicitors have Irish counterpart relationships. This is fundamentally different from incorporating in Germany, France, or the Netherlands.

3. **Strong tech/startup ecosystem:** Enterprise Ireland, the state development agency, actively funds and supports startups. IDA Ireland recruits FDI. The startup ecosystem in Dublin includes world-class talent pipelines from Trinity College Dublin, UCD, DCU, and University College Cork. Co-working spaces (Dogpatch Labs, WeWork Dublin) serve hundreds of startups. Venture capital availability (connected to London, New York, and San Francisco ecosystems) is strong.

4. **Proximity to UK:** Dublin is ~80 minutes by air from London. Daily business flights. GMT timezone (same as London outside BST — Ireland observes IST = GMT+1 in summer, while UK observes BST = GMT+1, so they are virtually always aligned). Banking, legal, and financial services in Dublin and London are deeply integrated.

5. **Tax efficiency (see Section 14.3):** Ireland's 12.5% corporation tax rate (for trading income) is the lowest in the EU for commercially active companies, compared to the UK's 25%. For an AI startup with high margins (API revenue), this difference compounds significantly over time.

---

### 14.2 Corporate Structure Options in Ireland

Ireland's Companies Act 2014 created a simplified, modern company law framework. The main vehicle types for Nobi are:

#### Private Company Limited by Shares (LTD)
Ireland's equivalent of a UK private limited company. This is the **recommended primary structure** for a commercial AI company. Key features:
- One director is sufficient (though a company secretary is also required)
- No minimum share capital
- Can carry on any lawful business activity — no restrictions on trading
- Can distribute profits to shareholders
- Subject to corporation tax at 12.5% on active trading profits
- CRO registration fee: €50 for online registration via the Registrar's online portal
- Annual return to CRO required, including financial statements (within 28 days of the Annual Return Date)
- **Audit exemption available** for small companies meeting two of three thresholds: turnover ≤ €12 million, balance sheet ≤ €6 million, employees ≤ 50
- **This is the most flexible structure** and the correct choice for the commercial API entity

#### Company Limited by Guarantee (CLG)
Ireland's CLG is functionally similar to a UK Company Limited by Guarantee (CLC) — the structure often used for charities, community organisations, and not-for-profit entities. A CLG **can** earn commercial revenue, but:
- Members guarantee a nominal amount (e.g. €1) rather than holding shares
- No share capital or equity investment possible
- Profits generally must be reinvested in the objects of the company
- Not suitable for a commercial API business seeking investment or eventual exit
- Would be appropriate for a separate community-focused charitable arm, but **not** for the commercial API entity
- **Not recommended** for the API commercialisation vehicle

#### Designated Activity Company (DAC)
A DAC is a private company with a restricted objects clause in its constitution — it can only carry on the specific activities stated. This structure is typically used for:
- Subsidiaries of multinational groups with restricted purposes
- Special purpose vehicles (SPVs)
- Financial services entities
- **Not appropriate** for an early-stage startup where the business model is evolving. A DAC's restricted objects would require constitutional amendments every time the business pivots. Use a LTD instead.

#### Cooperative Society
Registered under the Industrial and Provident Societies Act. Community-owned structure, democratic governance (one member, one vote). Not suitable for a commercial tech company seeking investment. Interesting in theory for a community-owned AI companion, but impractical at startup stage.

**Verdict for Nobi:** The **Private Company Limited by Shares (LTD)** is the correct structure. Simple, flexible, commercially unlimited, tax-efficient. CLG or Cooperative are worth considering *only* for a separate community/charitable arm.

**Registration costs and process:**
- CRO online registration: **€50** (the cheapest company formation fee in the EU)
- Typical solicitor/agent assisted formation: **€200–€400** total
- Timeline: 5–10 business days for online incorporation via CORE (Companies Online Registration Environment)
- Requirements: Company name, registered office address in Ireland, at least one director (can be non-Irish resident), company secretary, memorandum and articles of association
- Note: At least one director must be EEA-resident, *OR* the company must hold a **Section 137 bond** (€25,000 bond) if all directors are non-EEA resident. James is UK-resident (non-EEA post-Brexit), so either a bond is required or a nominee EEA-resident director must be appointed.

---

### 14.3 Irish Tax Regime

**⚠️ Important update from PwC Worldwide Tax Summaries (2025/2026):** The headline rates require careful reading.

#### Corporation Tax: 12.5% (trading) — not 15%
The Irish headline rate for active trading income is **12.5%**, *not* 15%. This is one of the lowest in the world for corporate income. Ireland maintains this rate for qualifying trading companies.

The **15% minimum** is the OECD Pillar Two global minimum tax — Ireland legislated for this with effect from **1 January 2024** (Income Inclusion Rule and Qualified Domestic Top-up Tax) and **1 January 2025** (Undertaxed Profits Rule). However — and this is critical — **Pillar Two only applies to businesses with consolidated group revenues of €750 million or more in at least two of the four preceding fiscal years.** Nobi will not hit €750M revenue in any foreseeable planning horizon. Therefore, Pillar Two is irrelevant to Nobi, and the **12.5% rate applies in full**.

Ireland has implemented a Qualified Domestic Top-up Tax (QDTT) to ensure that large multinationals operating in Ireland pay at least 15% effective tax — but this is specifically scoped to the €750M threshold. Small and medium-sized companies retain the 12.5% rate.

| Scenario | Rate |
|----------|------|
| Nobi API Ltd (Irish LTD, trading income) | **12.5%** |
| Passive income (dividends, interest, royalties) | 25% |
| Capital gains | 33% |
| Large multinationals (>€750M revenue) | 15% minimum (Pillar Two) |

#### R&D Tax Credit: 35% (upgraded from 25%)
**Important correction from PwC data:** The Irish R&D tax credit was increased. As of Finance Act 2024, the credit rate is **35%** (previously 25%), effective for accounting periods where the corporation tax return is due on or after 23 September 2027. This is **fully refundable** — paid in cash over three years (50% Year 1, 30% Year 2, 20% Year 3).

Combined with the normal 12.5% deduction for R&D expenditure, the total benefit is **47.5%** of qualifying R&D spend returned to the company.

**Does AI/software development qualify?** Yes. Qualifying R&D activities must constitute "systematic, investigative or experimental activities in a field of science or technology" — software development and AI model development routinely qualify, provided the work seeks to resolve scientific or technological uncertainty (not just routine software development). Building novel AI companion systems, training proprietary models, or developing new inference architectures would qualify.

**Finance Act 2025 update:** Companies can now claim the first **€87,500** of an R&D credit as payable in Year 1 (increased from €75,000).

#### Knowledge Development Box (KDB): 10% effective rate
The KDB provides a **10% effective corporation tax rate** on profits arising from **qualifying assets** — specifically including **copyrighted software** and patented inventions — where some or all of the related R&D is undertaken by the Irish company.

**Would Nobi's API revenue qualify?** Potentially yes, if:
- The underlying AI models and software are owned by the Irish entity (not licensed from a third party)
- The R&D was undertaken (at least partially) by the Irish company
- The software is protected by copyright (it automatically is under Irish/EU law)
- The profits are attributable to the exploitation of that software

API revenue = income from exploiting copyrighted software → KDB applies → **10% effective rate** on those profits (vs 12.5% standard).

The KDB currently applies for accounting periods commencing before **1 January 2027** (extended multiple times; likely to be extended again, but this is not guaranteed).

#### VAT: Standard rate 23%
Irish VAT standard rate is **23%** (vs UK 20%). For digital services:
- **B2C sales to EU customers:** VAT at destination country rate applies (via OSS — One Stop Shop)
- **B2B sales to VAT-registered EU businesses:** Reverse charge mechanism applies — Irish entity charges 0% VAT, customer accounts for their own VAT. This is extremely efficient for B2B API sales.
- **VAT registration threshold:** €42,500 for services (vs UK £90,000). Much lower than UK. An Irish company would need to register for VAT earlier.

#### Ireland-UK Double Taxation Treaty
A comprehensive DTA exists between Ireland and the UK (updated 1976, with subsequent protocols). Key provisions:
- Dividends paid from Irish subsidiary to UK parent: typically 0% withholding (participation exemption)
- Interest: reduced withholding (5% or 0%)
- Royalties: reduced withholding
- James's personal income from an Irish company would be subject to Irish PAYE (if employed by it) or UK income tax on dividends — specialist advice required

#### Net tax comparison for API startup

| Scenario | Ireland (LTD) |
|----------|---------------|
| Corp tax on trading profit | **12.5%** |
| Corp tax with KDB (IP income) | **10%** |
| R&D credit on qualifying spend | **35% refundable** |
| VAT threshold | €42,500 |

On €1M trading profit: Irish company pays **€125,000** in corporation tax.

---

### 14.4 GDPR Under Irish Law

Ireland implemented GDPR via the **Data Protection Act 2018** (DPA 2018). GDPR is directly applicable EU law — the DPA 2018 gives effect to member state choices within GDPR's "opening clauses" (age of consent for children: 16 in Ireland, vs 13 in UK).

**DPC (Data Protection Commission) as lead supervisory authority:**
The DPC is headquartered in Dublin and is Ireland's national supervisory authority under GDPR. Crucially, under GDPR's **One-Stop-Shop (OSS) mechanism** (Article 56), when a controller or processor has its main establishment in a member state, the supervisory authority of that member state acts as the **lead supervisory authority** for cross-border processing across the entire EU.

This is why every major tech company incorporated in Ireland — Google, Meta, Apple, LinkedIn, TikTok, Airbnb — has the DPC as its lead EU regulator. For Nobi, incorporating in Ireland means:
- **Single regulator for all EU operations** — the DPC handles complaints and investigations involving data subjects across all 27 EU member states
- **DPC guidance and interpretations** bind Nobi's EU operations (vs fragmented national authorities under the non-OSS framework)

**What does DPC lead authority mean for a startup like Nobi?**
- You must maintain your "main establishment" in Ireland — this means the place where central administration decisions are made, which for a small company typically means where the board decisions are taken and where key management is based
- You register with the DPC (required for data controllers in Ireland) — current fee: **€100 per year** for non-profits; commercial companies pay based on size
- DPC has published guidance on AI and data protection, chatbots, automated decision-making, and children's data that would be directly relevant

**SCCs for international transfers:**
An Irish company uses **EU Standard Contractual Clauses** (Commission Decision 2021/914) for transfers of personal data outside the EEA (to UK, US, etc.). Post-Brexit, data transfers from Ireland to the UK are covered by the EU's adequacy decision for the UK (currently valid, though subject to review). Data transfers from Ireland to the US require EU SCCs. This is simpler than managing both UK IDTAs and EU SCCs.

**DPIA requirements:**
The DPC follows the Article 29 Working Party / EDPB guidelines on DPIA. For AI companions processing sensitive personal data (conversations, emotional state, mental health context), a DPIA is likely mandatory before deployment in Ireland/EU. The DPC has a DPIA template and guidance.

---

### 14.5 EU AI Act — Direct Application

The **EU AI Act (Regulation 2024/1689)** entered into force on **1 August 2024**. Ireland, as an EU member state, is subject to this regulation directly — no implementing legislation required, no voluntary adoption.

**Implementation timeline:**
- **2 February 2025:** Prohibited AI practices (Article 5) took effect — bans on subliminal manipulation, social scoring, real-time facial recognition in public spaces
- **2 August 2025:** GPAI (General Purpose AI) model rules took effect — transparency requirements for general-purpose AI providers
- **2 August 2026:** High-risk AI system rules take full effect — conformity assessments, technical documentation, human oversight
- **2 August 2027:** Limited risk and other provisions fully applicable

**Classification of Nobi's AI companion API:**
An AI companion API (providing conversational AI, emotional support, companionship) would most likely be classified as **limited risk** or potentially **minimal risk** under the EU AI Act:

- **Not unacceptable risk:** Nobi does not manipulate users subliminally, does not use biometric identification, does not engage in social scoring
- **Potentially limited risk:** As a chatbot/conversational AI system that interacts with natural persons, Nobi would have a **transparency obligation** — users must be informed they are interacting with an AI system (Article 50). This is already best practice and Nobi should implement this regardless
- **Not high-risk:** Nobi is not used in healthcare decision-making, law enforcement, education credentialing, recruitment, or critical infrastructure
- **GPAI considerations:** If Nobi builds and distributes a general-purpose AI model (rather than just using third-party models like OpenAI), GPAI rules apply

**Key compliance obligations for Nobi under EU AI Act:**
1. AI system transparency notice to users (Article 50) — must tell users they're talking to AI
2. If generating synthetic content (voice, images): deepfake labelling obligations
3. Register in the EU database if deploying in high-risk categories (not applicable)
4. For GPAI (if applicable): publish technical documentation, copyright policy, training data summary

**Contrast with UK approach:**
The UK has deliberately chosen **not** to enact an equivalent of the EU AI Act. The UK government's AI strategy (as of 2025/2026) is sector-specific, principles-based, and relies on existing regulators (ICO, FCA, CMA) to apply sector rules to AI. There is no UK-equivalent registration requirement, no mandatory risk classification, no GPAI model transparency obligations. This creates a lighter compliance burden for a UK company — but also less clarity and no access to the EU AI Act's "presumption of conformity" once standards are published.

---

### 14.6 Irish Employment & Operations

**Can James run an Irish company while living in the UK?**

Yes — with caveats. There is no legal requirement for directors of an Irish LTD to be Irish residents. However:

1. **Tax residency of the company:** An Irish company is tax-resident in Ireland if it is incorporated in Ireland (automatic under Finance Act 1999 — the "incorporation rule"). However, Revenue can challenge this if the company's "central management and control" (CMC) is exercised outside Ireland. If all board decisions are made by James from his UK home, and no Irish directors are involved, Revenue could argue the company is UK-tax-resident under CMC principles, **removing the Irish tax benefit**. This is the central operational risk for a UK-resident founder running an Irish entity.

2. **Mitigation:** Appoint at least one Irish or EEA-resident director who participates actively in board decisions. This director must be a real, active director — not just a nominee figurehead. Professional director services are available in Dublin from ~**€2,000–€5,000/year**.

3. **Company secretary requirement:** An Irish LTD must have a company secretary (separate from director). Can be a director if there's more than one director. Professional company secretarial services available from ~**€500–€1,500/year**.

4. **Registered office in Ireland (mandatory):** All Irish companies must have a registered office address in Ireland for service of legal documents and official notices. Virtual registered office services: **€100–€350/year** from providers like Company Bureau, Company Formations IE, or law firm services.

5. **Section 137 Bond:** If all directors are non-EEA resident (post-Brexit, James is non-EEA), the company must either appoint an EEA-resident director or take out a Section 137 bond of **€25,000** lodged with the CRO, ensuring Irish Revenue can pursue debts. Bond costs approximately €500–€1,500/year in insurance premiums.

**Annual CRO filing requirements:**
- **Annual Return (B1 form):** Filed once per year, due 28 days after the Annual Return Date. Includes financial statements, list of directors, secretary details. **CRO fee: €20 online**
- **Audit exemption:** Available for companies below two of three thresholds: turnover ≤ €12M, balance sheet ≤ €6M, employees ≤ 50. Nobi will qualify for audit exemption at startup stage
- **Revenue tax returns:** Corporation tax return filed with Irish Revenue, VAT returns (bi-monthly if turnover exceeds threshold)
- **Beneficial Ownership Register:** Must register ultimate beneficial owners with the CRO's RBO (Register of Beneficial Ownership) — no fee, online filing

**Estimated total annual compliance cost (small Irish LTD):**
- Registered office: ~€200/year
- Company secretarial services: ~€800/year
- Director fee (if EEA-resident nominee required): ~€3,000/year
- Accountant for annual return + tax: ~€1,500–€3,000/year
- **Total: approximately €5,500–€7,000/year** for a well-run small Irish company

---

### 14.7 Comparison Table: Ireland vs UK

> **Note: Ireland is the chosen jurisdiction.** The UK columns are shown for reference only. Nobi's commercial entity will be an Irish Private Company Limited by Shares (LTD).

| Factor | UK (CIC) *(ref only)* | UK (Ltd) *(ref only)* | **Ireland (LTD) ← CHOSEN** |
|--------|----------|----------|---------------|
| **Corporation Tax (trading)** | 25% | 25% | **12.5%** |
| **Corporation Tax (IP income, KDB)** | 25% | 25% | **10%** |
| **R&D Credit** | 20% (RDEC, above-line) | 20% | **35% refundable** |
| **GDPR Authority** | ICO (UK) | ICO (UK) | **DPC (EU, One-Stop-Shop)** |
| **EU Single Market Access** | No (post-Brexit) | No (post-Brexit) | **Yes (all 27 EU states)** |
| **AI Act (mandatory)** | Voluntary/No | Voluntary/No | **Yes (Mandatory)** |
| **Company Formation Cost** | ~£50–£100 | ~£50–£100 | **~€50–€400** |
| **Annual Filing Cost** | ~£300–£1,000 | ~£300–£1,000 | ~€5,500–€7,000 |
| **Asset Lock** | Yes (CIC — asset lock) | No | No |
| **Profit Distribution** | Restricted (CIC cap) | Unrestricted | Unrestricted |
| **VAT Threshold** | £90,000 | £90,000 | €42,500 (lower) |
| **VAT Standard Rate** | 20% | 20% | 23% |
| **Data Transfer (to UK)** | Domestic | Domestic | EU SCCs / adequacy decision |
| **Data Transfer (to US)** | UK IDTA + US framework | UK IDTA | EU SCCs + US framework |
| **Startup Corp Tax Exemption** | No | No | **Yes (€40K relief, 3 years)** |
| **Director residency requirement** | No | No | EEA or Section 137 bond |
| **Registered office requirement** | UK | UK | **Ireland (additional cost)** |
| **Currency** | GBP | GBP | EUR (FX risk for UK founder) |
| **Company Secretary (mandatory)** | No | No | Yes |
| **Regulatory complexity** | Low | Low | Medium |
| **Investor-friendliness** | Medium | High | **High (EU investment market)** |
| **Enforcement risk (data)** | ICO (proportionate for small cos) | ICO | **DPC (aggressive on Big Tech)** |

---

### 14.8 ~~Dual Structure Option~~ — *Removed*

*A dual UK/Ireland structure is not needed. Ireland is the chosen jurisdiction. All commercial API and companion operations will be structured under the Irish LTD. No UK entity is required. See Section 14.10 for the recommendation.*

---

### 14.9 Irish Legal Risks & Disadvantages

Ireland is not a perfect jurisdiction. James should go in with clear eyes:

**1. DPC enforcement — genuinely aggressive:**
The DPC has levied some of the largest GDPR fines in EU history:
- Meta/Facebook: **€1.2 billion** (2023) — data transfers to US
- Instagram/Meta: **€405 million** (2022) — children's data
- WhatsApp/Meta: **€225 million** (2021) — transparency failures
- TikTok: **€345 million** (2023) — children's data processing
- Twitter/X: **€450,000** (2022)
- DPC opened a new investigation into X (XIUC) in **February 2026**

The DPC has faced criticism for being slow to investigate Big Tech, but when decisions are issued, fines are substantial. For Nobi — a company processing emotional data from vulnerable users (loneliness, mental health) — the DPC would be particularly vigilant. An AI companion holds **sensitive personal data by nature of the interactions**, even if not explicitly categorised as health data.

This is a double-edged sword: DPC scrutiny is heavy for large companies, but a small startup like Nobi (minimal revenue, minimal user base initially) is unlikely to attract DPC investigation unless there is a data breach or targeted complaint. The risk scales with user growth.

**2. UK-resident director running Irish company — the CMC problem:**
As noted in 14.6, if James (UK-based) controls all board decisions, Irish Revenue could classify the company as UK-tax-resident under central management and control rules. This would **negate all tax advantages**. Requires either a real Irish/EEA director or careful structuring.

**3. Currency risk: EUR vs GBP:**
An Irish company operates in EUR. James's personal expenses are in GBP. EUR/GBP exchange rate fluctuation (typically 2–5% annually) creates FX exposure. If GBP strengthens vs EUR, the after-tax Irish profits are worth less when converted. For a small company at startup stage, this is manageable (use EUR business accounts, pay costs in EUR). But it's a real friction that a UK company doesn't have.

**4. OECD Pillar Two erosion at scale:**
Ireland's 12.5% rate is protected for companies below the €750M threshold. But if Nobi becomes a large company (unlikely to be Nobi specifically, but worth noting), the rate floor of 15% would apply. Ireland legislated for this from 1 January 2024. The KDB (10% IP rate) may also face future EU State Aid challenges — it has been extended multiple times and may not be available beyond January 2027 in its current form.

**5. Irish company law is more complex than UK:**
Ireland's Companies Act 2014 is comprehensive (over 1,400 sections), but is considered more complex than UK's Companies Act 2006 in practice. Annual return filings, company secretarial requirements, and the CRO system add friction compared to UK Companies House. Professional fees are higher as a result.

**6. Limited Irish startup funding ecosystem:**
While Enterprise Ireland provides grants, the Irish VC market is smaller than London's. For early-stage seed and Series A, London remains the deeper capital pool. An Irish company can still raise from UK/US VCs, but the local ecosystem is thinner.

**7. VAT registration threshold is lower:**
€42,500 service threshold (vs UK £90,000) means Nobi Ireland would need to register for VAT much earlier. EU OSS scheme simplifies cross-border EU sales, but the administration burden increases.

---

### 14.10 Recommendation

## ✅ Recommended Jurisdiction: Ireland

**Incorporate as an Irish Private Company Limited by Shares (LTD). This is the jurisdiction.**

---

#### Why Ireland — the core reasoning:

1. **EU Single Market access from day one.** Post-Brexit, a UK entity cannot access EU markets under a single regulatory framework. An Irish LTD can sell, contract, and process data across all 27 EU member states. The AI API market in Europe is too significant to cede voluntarily.

2. **12.5% corporation tax (vs 25% UK).** On growing API profits, this is a structural cost advantage — roughly half the tax burden of a UK entity. At €500K profit, that's €62,500 saved per year.

3. **35% refundable R&D tax credit.** AI model development and novel software engineering qualifies. This is cash back to reinvest in the product — 35% vs UK's 20%.

4. **10% Knowledge Development Box rate.** API revenue from copyrighted software Nobi develops and owns in Ireland can qualify for 10% effective corp tax — the lowest legitimate rate in the EU.

5. **DPC as lead EU data regulator (One-Stop-Shop).** One regulator, one set of rules, for all 27 EU member states. This is why every major tech company is in Ireland. It dramatically simplifies EU GDPR compliance.

6. **EU AI Act compliance from a single jurisdiction.** Ireland is inside the EU AI Act framework. Once compliant, Nobi can serve the entire EU market with confidence.

7. **English-speaking common law jurisdiction.** Contracts, employment, corporate governance — substantially similar to UK. No translation, no legal distance.

---

#### Critical operational requirements for Irish incorporation:

- **EEA-resident director (mandatory):** James is UK-based (non-EEA post-Brexit). Either appoint an EEA-resident active director (~€2,000–€5,000/year for professional director service) OR take out a Section 137 bond (€25,000 lodged with CRO, ~€500–€1,500/year insurance cost). The EEA director route is preferable and more credible for CMC purposes.

- **Central Management and Control (CMC):** Irish Revenue will tax the company in Ireland only if central management decisions (board meetings, strategic decisions) are genuinely made in Ireland. A nominee Irish director who participates actively in board decisions addresses this. Structure board meetings to occur in Ireland (can be virtual). Document board minutes carefully.

- **Registered office in Ireland:** Mandatory. Virtual registered office services cost €100–€350/year.

- **Company secretarial and accounting:** ~€500–€1,500/year (secretarial) + €1,500–€3,000/year (accountant). Total annual compliance: ~€5,500–€7,000/year.

---

#### What Ireland is NOT:

Ireland is not a tax dodge or a shell arrangement. The 12.5% rate is genuine, long-standing, and EU-approved (it has survived multiple EU State Aid challenges). But it only delivers its full benefit if:
- The company is genuinely managed from Ireland (CMC properly structured)
- Profits are real trading income from an active Irish business
- Compliance costs are properly budgeted

For a UK founder, the structure requires deliberate setup — but it is entirely legitimate and used by thousands of UK-based founders who incorporate in Ireland.

---

#### Steps to incorporate:

1. Engage an Irish solicitor (1–2 weeks to identify and instruct)
2. Choose company name, prepare constitution (solicitor drafts)
3. Appoint EEA-resident director (professional director service or EEA co-founder)
4. Register with CRO online (€50, 5–10 business days)
5. Register registered office address (virtual service, €100–€350/year)
6. Register with DPC as data controller (before processing personal data)
7. Open Irish business bank account (AIB, Bank of Ireland, or fintech like Revolut Business)
8. Register for Irish corporation tax and VAT (Revenue.ie)

**Timeline:** 4–8 weeks from decision to operational Irish LTD. Can run in parallel with API development.

---

**Summary verdict:**
> **Incorporate in Ireland. One entity. One regulator. EU market access. 12.5% tax. Build it right from the start.**

---

### 14.11 Sources

| Source | Key data | URL | Date accessed |
|--------|----------|-----|---------------|
| PwC Worldwide Tax Summaries — Ireland (Corporate Tax) | Corp tax 12.5%/25%; Pillar Two €750M threshold; QDTT from Jan 2024 | taxsummaries.pwc.com/ireland/corporate/taxes-on-corporate-income | March 2026 |
| PwC Worldwide Tax Summaries — Ireland (Credits & Incentives) | R&D credit 35% (from 2027 returns); KDB 10%; startup exemption €40K; IP regime 80% cap | taxsummaries.pwc.com/ireland/corporate/tax-credits-and-incentives | March 2026 |
| PwC Worldwide Tax Summaries — Ireland (VAT) | VAT 23%; services threshold €42,500; B2B reverse charge | taxsummaries.pwc.com/ireland/corporate/other-taxes | March 2026 |
| EU AI Act (Regulation 2024/1689) | Risk tiers; timeline (Aug 2024 entry into force; Feb 2025 prohibited practices; Aug 2025 GPAI; Aug 2026 high-risk) | Wikipedia / EUR-Lex | March 2026 |
| DPC Press Releases | DPC investigations: X (Feb 2026), TikTok China transfers (Jul 2025), Children's Health Ireland (Aug 2025) | dataprotection.ie/en/news-media/press-releases | March 2026 |
| Companies Act 2014 (Ireland) | LTD, CLG, DAC structures; one director rule; company secretary requirement | legislation.ie | March 2026 |
| CRO (Companies Registration Office) | €50 online registration fee; €20 annual return; audit exemption thresholds | cro.ie | March 2026 |
| Finance Act 2025 (Ireland) | R&D first-year payable limit increased to €87,500 | oireachtas.ie | March 2026 |

### Notes on Data Confidence

- **Irish corporation tax (12.5%):** High confidence — verified from PwC Worldwide Tax Summaries, confirmed by revenue.ie structure
- **R&D credit rate (35%):** High confidence — PwC states "35%...effective for accounting periods for which the corporation tax return is due on or after 23 September 2027"; the previously cited 25% was the pre-Finance Act 2024 rate
- **KDB 10% rate:** High confidence — PwC confirms this, notes applies for accounting periods commencing before 1 January 2027
- **DPC fines for Meta/TikTok:** High confidence — these are public decisions, widely reported; figures are accurate as of the decision dates
- **Company registration fees:** High confidence — €50 online CRO fee is official; professional service costs are market estimates based on Irish professional fee norms, should be verified with actual quotes
- **Section 137 bond requirement:** Confirmed from Companies Act 2014 — relevant because James is UK-resident (non-EEA post-Brexit)
- **EU AI Act timeline:** High confidence — verified from Wikipedia citing EUR-Lex, cross-checked with known implementation dates

---

*Section 14 added March 25, 2026 at James's direction. Updated March 25, 2026: Ireland confirmed as the chosen jurisdiction. UK/CIC references removed throughout the document.*

*Legal sections are for informational purposes only and do not constitute legal advice. Irish tax analysis is based on publicly available sources as of March 2026; engage a qualified Irish solicitor and chartered accountant before incorporating in Ireland. CMC risk analysis in particular requires specialist advice.*

---
