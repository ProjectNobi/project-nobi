# Project Nobi — Execution Roadmap

> From testnet to a self-sustaining public good.
> Living document — updated as milestones complete.

---

## Overview

This roadmap is structured in five phases, from the current foundation to global scale. Each phase includes specific deliverables, estimated timelines, resource requirements, risks, and success metrics.

**Guiding principles:**
- Ship working software, not announcements
- Be honest about what's built vs. what's planned
- Community feedback drives priorities
- Free for users at every phase, sustained by the network

---

## Phase 0: Foundation (Complete — Q1 2026)

### Status: ✅ DONE

Everything below is live, tested, and operational.

### What's Built

| Component | Status | Details |
|-----------|--------|---------|
| Subnet Protocol | ✅ Live | CompanionRequest, MemoryStore, MemoryRecall synapses |
| Miner | ✅ Live | LLM inference + persistent memory, bt 10.x compatible |
| Validator | ✅ Live | LLM-as-judge scoring, dynamic query generation |
| Testnet Deployment | ✅ Live | SN272, validator + miner operational |
| Telegram Bot | ✅ Live | @ProjectNobiBot — functional companion |
| Web Application | ✅ Live | Next.js + FastAPI |
| Memory System | ✅ Live | Semantic graphs, emotion tracking, relationship mapping |
| Memory Encryption | ✅ Live | AES-128 per-user (Fernet, PBKDF2 100K iterations) |
| Content Safety | ✅ Live | Filtering, compliance, responsible AI |
| Anti-Gaming | ✅ Live | Dynamic queries, fake user IDs, heuristic cap, moving averages |
| Stress Test | ✅ Passed | 500 nodes, 2000 queries, 99.75% success rate |
| Documentation | ✅ Complete | Whitepaper, subnet design, mining guide, validating guide, vision, roadmap |
| Legal Framework | ✅ Complete | Privacy policy, terms, safety disclaimers |
| Multi-language | ✅ Live | 20 languages, auto-detected |
| Voice Messages | ✅ Live | STT + TTS integration |
| Image Understanding | ✅ Live | Vision model support |
| Relationship Graphs | ✅ Live | Entity extraction, BFS traversal, 30+ relationship types |
| Proactive Companion | ✅ Live | Birthday reminders, follow-ups, check-ins, milestones |
| Group Companion Mode | ✅ Live | Multi-user conversation support |

### Team

| Member | Role | Contribution |
|--------|------|-------------|
| **James** | Founder & Visionary | Mission, strategy, funding, direction |
| **Slumpz** | Developer | Early protocol design, infrastructure |
| **T68Bot** | AI Builder | Subnet architecture, protocol, scoring, memory, documentation, operations |

---

## Phase 1: Mainnet Preparation (Q2 2026)

### Target: April–June 2026

This is the critical bridge from testnet to mainnet. Everything here must be hardened, audited, and community-tested before we register on mainnet.

### Deliverables

#### 1.1 Code Hardening

| Task | Priority | Description |
|------|----------|-------------|
| Memory system stress test at scale | Critical | Test with 10K+ simulated users, concurrent access, memory graph growth |
| Validator scoring calibration | Critical | Ensure LLM-as-judge produces consistent, manipulation-resistant scores across diverse miner populations |
| Miner protocol edge cases | High | Handle network partitions, timeout cascading, malformed synapses, large memory contexts gracefully |
| Auto-recovery mechanisms | High | Miners and validators auto-restart on crash, reconnect on network issues, resume state cleanly |
| Rate limiting and DDoS protection | High | Protect against query flooding, sybil miners, validator resource exhaustion |
| Memory migration tooling | Medium | Clean upgrade path for memory schema changes without data loss |
| Logging and monitoring | Medium | Structured logging, Prometheus metrics, alerting for validator health |

#### 1.2 Validator/Miner Protocol Finalization

| Task | Priority | Description |
|------|----------|-------------|
| Scoring weight calibration | Critical | Final tuning of quality (60-90%) / memory (0-30%) / reliability (10%) weights based on testnet data |
| Minimum quality thresholds | Critical | Define and enforce minimum acceptable response quality — miners below threshold earn zero |
| Weight commit-reveal hardening | High | Ensure commit-reveal mechanism prevents weight copying and manipulation |
| Miner diversity incentives | High | Prevent monoculture (all miners using identical prompts/models) |
| Query generation expansion | Medium | Expand dynamic query templates for richer, harder-to-game scoring |
| Multi-turn conversation depth | Medium | Increase multi-turn test complexity (currently 60% of rounds) |

#### 1.3 Subnet Registration

**Current Bittensor mainnet subnet registration requires burning TAO.** The burn rate fluctuates based on network demand. As of Q1 2026, registration costs are significant — estimated at several hundred TAO.

**Funding Strategy:**

| Source | Amount | Status |
|--------|--------|--------|
| Founder (James) personal funds | Primary | Committed — bootstrap budget allocated |
| Team contribution (Slumpz) | Supporting | In discussion |
| OpenTensor Foundation appeal | Variable | Planned — formal proposal in preparation |
| Bittensor community contributions | Variable | Planned — public campaign with full transparency |

**Why the community should help:** Nobi burns all owner emissions. Every TAO that would go to subnet owners is recycled. This makes Nobi a public good for the Bittensor ecosystem — a showcase subnet that demonstrates what decentralized AI can be, funded by the network, serving users for free. Supporting Nobi's registration is an investment in Bittensor's narrative and utility.

**Multisig Wallet Setup:**

The subnet registration wallet will be either:
- A multisig wallet with trusted community holders (preferred — maximum transparency)
- Or founder-managed with public accountability (if multisig setup is impractical for registration)

Wallet address, all transactions, and all emission burns will be publicly verifiable on-chain.

#### 1.4 Security Audit

| Task | Priority | Description |
|------|----------|-------------|
| Memory encryption review | Critical | Independent verification of AES-128 implementation, key management, attack surfaces |
| Protocol security review | Critical | Synapse validation, input sanitization, injection attack prevention |
| Miner data isolation | High | Verify miners cannot access memories from users assigned to other miners |
| Validator manipulation resistance | High | Confirm scoring cannot be gamed by collusion or strategic responses |
| Dependency audit | Medium | Review all third-party libraries for known vulnerabilities |

**Approach:** Community security review (open source audit) + targeted expert review if funding allows.

#### 1.5 Legal Entity Strategy (Recommended)

> *This is a recommended strategy, not a firm commitment. The founder will decide timing and structure based on project needs.*

The community model significantly simplifies legal requirements compared to a subscription-based business. No payment processing, no consumer refund liability, no revenue tax structure needed.

**Phased approach:**

| Phase | Recommendation | Cost | Rationale |
|-------|---------------|------|-----------|
| Now → Mainnet | No entity needed | £0 | Open source project run by individuals. MIT license protects contributors. Founder named as GDPR data controller (acceptable for small projects). |
| Mainnet → Growth | UK Community Interest Company (CIC) | ~£50 | Personal liability shield, GDPR-compliant entity, "for community benefit" structure with asset lock, aligns with mission. Cheap and simple. |
| Scale (100K+ users) | Foundation (UK/Swiss) | Variable | Maximum credibility, formal governance structure, international recognition. Evaluate when scale justifies it. |

**Why a CIC over a Ltd:**
- Explicitly "for community benefit" — legally enshrined, not just a promise
- Asset lock: if dissolved, assets go to another community purpose, never to founders
- Costs ~£50 to register vs ~£500+ for Ltd
- Simpler governance, lighter reporting requirements
- Aligns perfectly with "no profit, no subscriptions, community-owned" model

**What a CIC protects against:**
- Personal liability if Nori causes harm (AI safety incident, data breach)
- Domain/infra ownership clarity
- GDPR data controller designation
- Subnet wallet custody legal framework
- Trademark protection for "Nobi" / "Nori"

**What's NOT needed (thanks to community model):**
- ❌ Payment processing entity
- ❌ Financial services registration
- ❌ Revenue tax structure
- ❌ Expensive lawyer review for subscription terms (~£2,000-5,000 GDPR audit can wait until real scale)

#### 1.6 Community Building

| Task | Target | Description |
|------|--------|-------------|
| Discord community | 500+ members | Active channels for miners, validators, users, developers |
| Twitter/X presence | Established | Regular updates, Bittensor community engagement |
| Documentation site | Live | Hosted docs (GitBook or similar) — accessible, searchable |
| Miner onboarding program | 10+ external miners | Documentation, support, incentives for early miners |
| Validator recruitment | 3+ external validators | Outreach to established Bittensor validators |
| Community governance draft | Published | Initial framework for community decision-making |
| Weekly community updates | Ongoing | Transparent progress reports — wins and setbacks |

### Timeline

| Week | Focus |
|------|-------|
| Week 1–2 | Code hardening, stress testing |
| Week 3–4 | Protocol finalization, scoring calibration |
| Week 5–6 | Security review, community miner/validator onboarding |
| Week 7–8 | Subnet registration preparation, multisig setup |
| Week 9–10 | Final testnet validation with external participants |
| Week 11–12 | Registration funding campaign, OTF proposal |

### Resource Requirements

| Resource | Need | Source |
|----------|------|--------|
| Development time | ~480 hours | James + Slumpz + T68Bot |
| Infrastructure (testnet) | ~$50-100/month | Founder-sponsored servers |
| Subnet registration TAO | Fluctuating (est. hundreds of TAO) | Founder + community |
| Security review | Community audit (free) + expert if funded | Open source + potential grant |

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Registration cost spikes | Medium | High | Monitor burn rate, maintain buffer, OTF appeal as backup |
| Insufficient external miners | Medium | Medium | Comprehensive onboarding docs, direct outreach to Bittensor miners, competitive emission incentives |
| Security vulnerability discovered | Low | High | Open source audit, responsible disclosure process, rapid patching capability |
| Team bandwidth constraints | Medium | Medium | Prioritize ruthlessly, leverage T68Bot for automated development and documentation |
| Community apathy | Low | Medium | Lead with working product, not promises; show don't tell |

### Success Metrics

- [ ] 10+ external miners running and scoring >0.5 quality
- [ ] 3+ external validators operational
- [ ] Zero critical security vulnerabilities (or all patched before mainnet)
- [ ] Subnet registration funds secured
- [ ] 500+ Discord community members
- [ ] Code hardened: 99%+ uptime over 30-day testnet period

---

## Phase 2: Mainnet Launch (Q3 2026)

### Target: July–September 2026

### Deliverables

#### 2.1 Subnet Registration
- Register Nobi subnet on Bittensor mainnet
- Publish wallet address and all transactions publicly
- Activate emission burn mechanism — all owner emissions committed to burn from block 1
- On-chain verification: anyone can audit emission distribution

#### 2.2 Initial Network Deployment
- Migrate testnet miners and validators to mainnet
- Deploy reference miner and validator with updated mainnet configurations
- Minimum viable network: 20+ miners, 5+ validators at launch
- Monitor and tune scoring weights based on mainnet behavior (first 2 weeks)

#### 2.3 Subnet Routing Activation
- **Critical milestone:** Bot routes through subnet (validators → miners) instead of direct LLM calls
- This is the transition from "product demo" to "decentralized service"
- Fallback mechanism: direct LLM call if subnet response fails (graceful degradation)
- Latency targets: <5 seconds for standard responses, <15 seconds for memory-heavy queries

#### 2.4 Public Beta Launch
- Open @ProjectNobiBot and web app to general public
- Onboarding flow: simple, no crypto knowledge required
- User feedback system: in-app feedback, Discord feedback channel
- Community beta testers: first 1,000 users with direct feedback loop

#### 2.5 Community Staking Begins
- Publish staking guide for TAO holders
- Transparent emissions dashboard — real-time view of:
  - Total emissions received
  - Owner emissions burned (with proof)
  - Miner/validator distribution
  - Infrastructure costs covered
- Community staking campaign: "Support free AI companionship" (*staking involves risk; this is not financial advice*)

### Timeline

| Month | Focus |
|-------|-------|
| Month 1 | Subnet registration, initial miner/validator deployment |
| Month 2 | Subnet routing activation, public beta opens |
| Month 3 | Stability hardening, community staking, user growth |

### Resource Requirements

| Resource | Need | Source |
|----------|------|--------|
| Subnet registration TAO | Hundreds of TAO | Founder + community |
| Infrastructure (mainnet) | ~$200-500/month | Emissions + founder sponsorship |
| Development | Ongoing | Team |
| Community management | Part-time | Founder + community volunteers |

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Mainnet instability at launch | Medium | High | Extensive testnet validation, fallback to direct LLM |
| Low initial user adoption | Medium | Medium | Bittensor community first, organic growth, quality over marketing |
| Miner quality drops on mainnet | Low | Medium | Minimum quality thresholds, immediate scoring penalties |
| Staking insufficient for sustainability | Medium | Medium | Founder covers gap, transparent communication about funding status |

### Success Metrics

- [ ] Subnet registered and emitting on mainnet
- [ ] 100% of owner emissions committed to verifiable burn
- [ ] 20+ active miners with >0.5 average quality score
- [ ] 5+ validators operational
- [ ] 1,000+ active users (weekly active)
- [ ] Subnet routing live: <5s average response latency
- [ ] Zero data breaches or security incidents

---

## Phase 3: Growth (Q4 2026 — Q2 2027)

### Target: October 2026 — June 2027

### Deliverables

#### 3.1 Mobile Application (iOS + Android)
- Native mobile app (Expo/React Native) — already in development
- App Store and Google Play distribution
- Push notifications for proactive companion features (reminders, check-ins)
- On-device memory storage (Phase 1): memories stored locally on phone
  - This is the first major privacy milestone: memories never reach miner machines
  - Miners receive encrypted context, not raw memories
- Offline mode: basic companion functionality without network (cached personality)

#### 3.2 Multi-Language Expansion
- Current: 20 languages (auto-detected)
- Target: 50+ languages with localized companion personalities
- Cultural adaptation: companion understands local context, holidays, social norms
- Community-contributed language packs and personality tuning

#### 3.3 Advanced Memory Features
- **Cross-device sync:** Memory graph synchronized securely across phone, web, Telegram
- **Memory timeline:** Users can browse their memory graph visually — a timeline of their life as Nori sees it
- **Selective sharing:** Share specific memories or contexts between trusted companions (family feature)
- **Memory health:** Analytics showing memory graph growth, topics, emotional patterns (opt-in, private)

#### 3.4 Plugin/Skill Ecosystem
- Calendar integration (reminders, events)
- Web search (Nori can look things up for you)
- Smart home integration (basic)
- Task management (to-do lists, goal tracking)
- Community-developed plugins: open framework for developers to extend Nori's capabilities
- **All plugins free.** No marketplace fees. No premium plugins.

#### 3.5 Community Governance (Initial)
- Published governance framework: how decisions are made
- Community proposals: anyone can suggest features, changes, priorities
- Voting mechanism: initial informal (Discord polls) → evolving to on-chain
- Transparency reports: monthly financial and operational reports
- Community moderators and ambassadors program

### Timeline

| Quarter | Focus |
|---------|-------|
| Q4 2026 | Mobile app launch, cross-device sync, initial plugins |
| Q1 2027 | Language expansion, memory timeline, governance framework |
| Q2 2027 | Plugin ecosystem opens, community governance active |

### Resource Requirements

| Resource | Need | Source |
|----------|------|--------|
| Mobile development | Significant | Team + community contributors |
| Infrastructure scaling | ~$500-2,000/month | Emissions |
| Community management | Growing | Volunteer moderators + founder |
| Plugin review/security | Ongoing | Community security reviewers |

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| App store rejection | Low | Medium | Comply with all store policies, content safety built-in |
| On-device memory technical complexity | Medium | Medium | Phased rollout, fallback to server-side encrypted storage |
| Plugin security vulnerabilities | Medium | Medium | Sandboxed plugin execution, community review process |
| Governance disputes | Low | Low | Clear framework published upfront, founder retains tiebreak during transition |

### Success Metrics

- [ ] Mobile app live on both app stores
- [ ] 10,000+ weekly active users
- [ ] 50+ languages supported
- [ ] 5+ community-developed plugins
- [ ] On-device memory storage deployed
- [ ] Governance framework published and active
- [ ] Monthly transparency reports published

---

## Phase 4: Scale (H2 2027 — 2028+)

### Target: 100K+ Users → Self-Sustaining Network

### Deliverables

#### 4.1 Decentralized Governance Transition
- On-chain governance: stakers vote on major decisions (protocol changes, emission allocation, feature priorities)
- Founder steps back from day-to-day operations
- Community council: elected representatives from miners, validators, users, developers
- Constitution: published principles intended to be foundational (free for users, open source, emissions burned)
- Fork protection: if the community disagrees with direction, they can fork — the code is open

#### 4.2 Federated Privacy Architecture
- **FederatedUpdate synapse:** weight deltas only, no raw data transmitted (McMahan et al., 2016 — FedAvg)
- Per-user federated adapter training: personality adapters trained locally, never transmitted
- Differential privacy on scoring: calibrated noise so individual behavior is unidentifiable in aggregate
- Independent privacy audit: third-party verification of federated guarantees
- **This is the end-state privacy goal:** your memories never leave your device under any circumstances

#### 4.3 International Expansion
- Localized companion personalities for major cultural regions
- Local community leaders and ambassadors in key markets
- Partnerships with education and wellness organizations
- Regulatory compliance for major jurisdictions (EU/GDPR fully compliant, etc.)

#### 4.4 Enterprise and Education (Free for Individuals)
- **Enterprise:** Custom deployments for organizations (customer support, employee wellness, education)
  - Enterprise may involve infrastructure fees to cover costs — but never user-facing charges
  - Revenue from enterprise deployments funds free individual access
- **Education:** AI study companions for students
  - Partnered with schools and universities
  - Always free for individual students
- **Important:** Individual use is intended to remain free for as long as the network sustains it. Enterprise/education verticals may generate revenue to sustain infrastructure, but no individual human is intended to pay.

#### 4.5 Advanced Capabilities
- Voice-first interaction (natural spoken conversation)
- Multimodal understanding (images, documents, audio)
- Agentic capabilities (book appointments, manage tasks, interact with services)
- Companion personas: specialized versions (fitness coach, language tutor, life coach, creative partner)
  - All free. Personas are configurations, not products.

### Timeline

| Period | Focus |
|--------|-------|
| H2 2027 | Governance transition, federated privacy prototype, enterprise pilots |
| H1 2028 | 100K users, international expansion, voice-first |
| H2 2028 | Decentralized governance active, agentic capabilities, multimodal |
| 2029+ | Self-sustaining, founder fully stepped back, community-governed |

### Success Metrics

- [ ] 100,000+ weekly active users
- [ ] Decentralized governance operational (on-chain voting)
- [ ] Federated privacy architecture deployed and audited
- [ ] Founder no longer required for day-to-day operations
- [ ] 5+ enterprise/education deployments
- [ ] 100+ active miners, 20+ validators
- [ ] Network self-sustaining through emissions alone (no founder sponsorship needed)

---

## Subnet Economics

### How It Works

Bittensor allocates TAO emissions to subnets based on their weight in the network. Within each subnet, emissions are distributed to:

1. **Miners** — who do the work (generating companion responses)
2. **Validators** — who ensure quality (scoring miners)
3. **Subnet owner** — a percentage allocated to the registrant

Most subnets keep the owner allocation (typically 18%). **Nobi is committed to burning 100% of it.**

### Why We Burn Owner Emissions

**Trust.** In a project asking the community to stake TAO and users to trust with their memories, the founder profiting from emissions creates a conflict of interest. Burning owner emissions removes that conflict entirely.

**Alignment.** If the founder doesn't profit from emissions, the only reason to maintain the subnet is because it's working — serving users, running well, making a difference. The incentive is aligned with the mission, not extraction.

**Precedent.** We want Nobi to demonstrate that a subnet can be a public good. If it works, others may follow. The Bittensor ecosystem benefits from subnets that exist to serve users, not to extract value.

**Verification.** Every emission, every burn, every transaction is on-chain. Anyone can verify. Transparency is built into the architecture.

### Emission Flow

```
Bittensor Network Emissions
    │
    ├── Miner Rewards (majority)
    │     └── Incentivizes quality companion responses
    │
    ├── Validator Dividends (proportional to stake)
    │     └── Rewards quality assurance and staking
    │
    └── Owner Allocation → 🔥 BURNED
          └── Reduces TAO supply, benefits all holders
```

### How Voluntary Staking Creates Sustainability

The Nobi subnet's "revenue" is emissions from the Bittensor network. Emissions are proportional to the subnet's weight, which is influenced by staked TAO.

When TAO holders stake on Nobi:
1. Subnet weight increases → more emissions
2. More emissions → better miner/validator rewards
3. Better rewards → more miners compete → higher quality
4. Higher quality → more users → more community support → more staking
5. Virtuous cycle

This is economically similar to how Wikipedia operates: the product is free, and people who believe in the mission fund the infrastructure. The difference is that stakers on Bittensor also earn returns (validator dividends), so it's not pure charity — it's aligned participation.

> **Disclaimer:** Staking returns are not guaranteed and depend on network performance, TAO token value, and other factors outside our control. This is not financial advice or a solicitation to invest. TAO is a utility token, not a security. Past performance is not indicative of future results.

### Comparison with Traditional Funding Models

| Model | Who Pays | Who Benefits | Conflict |
|-------|----------|-------------|----------|
| VC-funded AI company | Users ($20+/mo) → Shareholders (exits) | Investors first, users second | Maximize revenue per user ≠ maximize user happiness |
| Ad-supported AI | Users (data) → Advertisers (targeting) | Advertisers first | Your attention is the product |
| Project Nobi | Network emissions + voluntary staking | Users (free service) + Stakers (validator dividends) + TAO holders (burned supply) | Minimal — incentives designed to point toward quality |

### Financial Sustainability Analysis

**What it costs to run Nobi:**

| Component | Monthly Cost (at scale) | Funded By |
|-----------|----------------------|-----------|
| Validator infrastructure | $100-500 | Validator dividends (self-funding) |
| Bot/web/app hosting | $100-300 | Minimal — covered by emissions or founder |
| Miner inference | $0 (miner-borne) | Miner rewards from emissions |
| Development | Community + founder time | Volunteer + personal commitment |
| Domain/CDN/misc | $20-50 | Founder |

**Total monthly infrastructure cost:** ~$200-800

**Emissions at even modest subnet weight:** Significantly exceeds infrastructure costs, with surplus going to miners (quality) and burned (TAO holders benefit).

The model is inherently sustainable because:
- The primary cost (LLM inference) is borne by miners, incentivized by emissions
- Infrastructure costs are minimal for the platform layer
- Development is open source / community-driven
- There are no salaries, offices, marketing departments, or investor returns to fund

---

## Risk Register (Cross-Phase)

| # | Risk | Phases | Likelihood | Impact | Mitigation | Owner |
|---|------|--------|-----------|--------|------------|-------|
| R1 | Subnet registration cost exceeds budget | 1–2 | Medium | Critical | Monitor burn rate daily, maintain 2x buffer, OTF appeal, community fundraise | James |
| R2 | Insufficient miners at mainnet launch | 2 | Medium | High | Aggressive onboarding in Phase 1, competitive emissions, low barrier docs | Team |
| R3 | Bittensor network upgrade breaks protocol | 1–4 | Medium | High | Pin bt version, rapid update capability, testnet preview of upgrades | T68Bot |
| R4 | User data breach via miner compromise | 2–4 | Low | Critical | AES-128 encryption (live), on-device storage (Phase 3), federated arch (Phase 4) | Team |
| R5 | Community staking doesn't materialize | 2–3 | Medium | Medium | Founder covers gap, demonstrate value first, transparent ROI reporting | James |
| R6 | Regulatory action against AI companions | 3–4 | Low | Medium | Content safety built-in, legal compliance framework, data portability/deletion | James |
| R7 | Big tech copies the model (free + memory) | 3–4 | Low | Medium | Decentralization moat (they can't decentralize), data ownership (they won't let you own data) | — |
| R8 | Team burnout (small team, big mission) | 1–4 | Medium | High | Grow community contributors, automate via T68Bot, pace sustainably | James |
| R9 | Scoring manipulation by colluding miners | 2–3 | Medium | Medium | Anti-gaming measures, validator diversity, moving averages, community monitoring | T68Bot |
| R10 | Founder unavailability (bus factor = 1) | 1–2 | Low | Critical | Document everything, multisig wallet, governance transition, open source = forkable | James |

---

## Milestone Summary

| Phase | Key Milestone | Target Date | Status |
|-------|--------------|-------------|--------|
| 0 | Testnet live (SN272) | Q1 2026 | ✅ Complete |
| 0 | Working Telegram bot | Q1 2026 | ✅ Complete |
| 0 | Full documentation suite | Q1 2026 | ✅ Complete |
| 1 | 10+ external miners | Q2 2026 | 🔲 In Progress |
| 1 | Security review complete | Q2 2026 | 🔲 Planned |
| 1 | Registration funds secured | Q2 2026 | 🔲 Planned |
| 1 | 500+ Discord members | Q2 2026 | 🔲 In Progress |
| 2 | Mainnet subnet registered | Q3 2026 | 🔲 Planned |
| 2 | Subnet routing live | Q3 2026 | 🔲 Planned |
| 2 | 1,000+ weekly active users | Q3 2026 | 🔲 Planned |
| 2 | 100% owner emissions burned | Q3 2026 | 🔲 Planned |
| 3 | Mobile app on app stores | Q4 2026 | 🔲 Planned |
| 3 | 10,000+ weekly active users | Q1 2027 | 🔲 Planned |
| 3 | On-device memory deployed | Q1 2027 | 🔲 Planned |
| 3 | Governance framework active | Q2 2027 | 🔲 Planned |
| 4 | 100,000+ weekly active users | H1 2028 | 🔲 Planned |
| 4 | Decentralized governance live | H2 2027 | 🔲 Planned |
| 4 | Federated privacy audited | 2028 | 🔲 Planned |
| 4 | Founder steps back | 2029 | 🔲 The goal |

---

## How to Contribute

This roadmap is a living document. If you want to help:

- **Miners:** Run a miner — [Mining Guide](MINING_GUIDE.md)
- **Validators:** Run a validator — [Validating Guide](VALIDATING_GUIDE.md)
- **Developers:** Pick an issue on [GitHub](https://github.com/ProjectNobi/project-nobi) and build
- **Stakers:** Consider staking TAO on the Nobi subnet when mainnet launches (*not financial advice; staking involves risk*)
- **Community:** Join [Discord](https://discord.gg/e6StezHM), spread the word, give feedback
- **Security:** Review the code and report vulnerabilities responsibly

Every contribution — code, staking, feedback, a single bug report — moves this forward.

---

*Project Nobi — Roadmap v1.0 — March 2026*
*"Forever, remember?" 🤖💙*
