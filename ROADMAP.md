# Project Nobi — Roadmap

> Last updated: 2026-03-19
> Status: Testnet (SN272) — Active Development

---

## Phase 1: Foundation ✅ COMPLETE
*March 17-18, 2026*

- [x] Bittensor subnet design (protocol, reward mechanism)
- [x] CompanionRequest synapse — core query/response protocol
- [x] MemoryStore / MemoryRecall synapses — memory protocol
- [x] Base miner neuron with LLM integration (Chutes API)
- [x] Base validator with LLM-as-judge scoring
- [x] Multi-turn conversation testing in validator
- [x] Dynamic query generation (prevents pre-caching)
- [x] Nori Telegram bot (@ProjectNobiBot)
- [x] Nori Discord bot
- [x] Testnet subnet registered (SN272)
- [x] Mining & Validating documentation
- [x] Open-source repo (MIT license)
- [x] GitHub: ProjectNobi/project-nobi

## Phase 2: Intelligence & Memory ✅ COMPLETE
*March 19, 2026*

- [x] Per-miner latency tracking (individual timing, not batch)
- [x] Soft multi-turn fallback (failing miners don't abort the round)
- [x] --mock flag deprecation warning (bt 10.x compatibility)
- [x] MemoryStore/MemoryRecall testing in validator (every 5th step)
- [x] Subnet routing — bot queries miners through the network
- [x] LLM-powered memory extraction (nuanced fact extraction)
- [x] Memory importance decay (old memories fade, active ones strengthen)
- [x] Smart context window (~500 token budget, priority-based selection)
- [x] User profile summarization (LLM-generated summaries after 20+ memories)
- [x] Memory-aware scoring (25% weight — miners rewarded for using memories)
- [x] Cross-miner memory sync (validator coordinates consistency)
- [x] Export/Import commands (/export, /import — "your data is yours")
- [x] Anti-hallucination guardrails in Nori personality
- [x] Intellectual honesty + emotional intelligence in system prompt
- [x] Cross-server miner deployment (Hetzner + Contabo Server3)
- [x] Daily testnet monitoring cron (09:00 UTC)
- [x] Nori engagement tracking (5-day cycle)
- [x] Landing page (projectnobi.ai — ready to deploy)

## Phase 3: Stability & Community 🔄 IN PROGRESS
*March 20+, 2026*

- [x] Daily X content for @projectnobi_tao (15:00 UTC)
- [ ] 48h testnet stabilization run — observe, fix edge cases
- [ ] Stake TAO on validator (blocked: SubtokenDisabled on testnet)
- [ ] Tune scoring weights based on real miner differentiation data
- [ ] Deploy landing page to projectnobi.ai
- [ ] Invite external miners to testnet (Bittensor Discord, X)
- [ ] Gather community feedback on Nori UX
- [ ] Fix bugs surfaced from real user traffic
- [ ] Improve Nori personality based on conversation logs

## Phase 4: Scale & Mainnet 📋 PLANNED
*Target: April 2026*

- [ ] Mainnet subnet registration (~1000+ TAO)
- [ ] Funding strategy for registration
- [ ] Production validator deployment (high-availability)
- [ ] Multi-region miner network
- [ ] Nori mobile app (React Native / Flutter)
- [ ] Voice support (text-to-speech, speech-to-text)
- [ ] Image understanding (vision model integration)
- [ ] Advanced memory: relationship graphs between users' facts
- [ ] Miner specialization (some miners better at advice, others at creativity)
- [ ] Revenue model: subscription tier for premium features

## Phase 5: Growth 📋 PLANNED
*Target: Q2-Q3 2026*

- [ ] 1,000 daily active users
- [ ] 50+ independent miners
- [ ] Trademark registration (TAONORI — filed)
- [ ] Partnership with Bittensor ecosystem projects
- [ ] Multi-language support (Nori speaks your language)
- [ ] Proactive companion features (Nori reaches out, not just responds)
- [ ] Group companion mode (Nori in group chats as a helpful participant)
- [ ] API access for third-party integration
- [ ] White-label companion solution

---

## Current Metrics (SN272 Testnet)

| Metric | Value |
|--------|-------|
| Neurons | 6 |
| Miners | 4 |
| Validators | 2 |
| Servers | 2 |
| Avg miner score | 0.82 |
| Memory recall rate | 75% (3/4 miners) |
| Bot users | 15+ unique |
| Subnet routing | Active |
| Memory system | Phase 2 live |

---

## Team

- **James** — Founder, vision, strategy
- **Slumpz** — Co-builder, developer, infra, QA
- **T68Bot (Doraemon)** — AI builder, coder, operator

---

*Built with love on Bittensor. Every human deserves a companion. 🤖*
