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
- [x] Cross-server miner deployment (Hetzner + Server3 + Server4)
- [x] Daily testnet monitoring cron (09:00 UTC)
- [x] Nori engagement tracking (5-day cycle)
- [x] Landing page (projectnobi.ai — LIVE)

- [x] Privacy Phase A: Client-side AES-128 encryption for all memories
- [x] Privacy Phase B: Encrypted synapses + per-user personality adapters
- [x] Privacy Phase C: Federated learning, differential privacy, secure aggregation (PRIVATE — mainnet only)
- [x] Nori bot: hardcoded identity responses, memory context passing to subnet miners
- [x] Brand assets: logo, wordmark, avatar, OG image, X banner
- [x] projectnobi.ai: Stripe/Linear/Notion-inspired redesign with docs section

## Phase 2.5: Semantic Memory ✅ COMPLETE
*March 20, 2026*

- [x] Embedding engine (sentence-transformers/all-MiniLM-L6-v2 + TF-IDF fallback)
- [x] Hybrid semantic recall (70% similarity + 20% importance + 10% recency)
- [x] Automatic embedding generation at store time
- [x] Migration tool for existing memories (batch processing)
- [x] Semantic scoring in validator reward system
- [x] Graceful fallback to keyword matching when embeddings unavailable
- [x] 38 comprehensive tests (embedding, recall, migration, scoring, edge cases)
- [x] Zero regressions — 191/191 total tests pass

## Phase 3: Stability & Community 🔄 IN PROGRESS
*March 20+, 2026*

- [x] Daily X content for @projectnobi_tao (15:00 UTC)
- [ ] 48h testnet stabilization run — observe, fix edge cases
- [ ] Stake TAO on validator (blocked: SubtokenDisabled on testnet)
- [ ] Tune scoring weights based on real miner differentiation data
- [x] One-command miner setup script (curl | bash)
- [x] Mining guide polish + Discord links everywhere
- [x] Community announcement drafts (Discord, X, welcome message)
- [x] Voice message support (STT → response → TTS reply)
- [x] Web application (Next.js + FastAPI backend, chat/memories/settings/onboarding)
- [x] Mobile app (Expo/React Native — iOS + Android, 3,600+ lines)
- [x] FastAPI v1 route aliases for mobile compatibility
- [x] Relationship graphs (entity extraction, BFS traversal, natural language context)
- [x] Proactive companion (birthday reminders, follow-ups, check-ins, milestones, encouragement)
- [x] Image understanding wired into Telegram bot (vision → response → memory extraction)
- [x] Group companion mode (smart respond logic, per-group memory, /nori command)
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
| Neurons | 10 |
| Miners | 7 |
| Validators | 2 |
| Servers | 5 |
| Avg miner score | 0.82 |
| Memory recall rate | 75% (3/4 miners) |
| Bot users | 15+ unique |
| Subnet routing | Active |
| Memory system | Semantic (Phase 2.5) |
| Total tests | 191 |
| Languages | 20 |

---

## Team

- **James** — Founder, vision, strategy
- **Slumpz** — Co-builder, developer, infra, QA
- **T68Bot (Doraemon)** — AI builder, coder, operator

---

*Built with love on Bittensor. Every human deserves a companion. 🤖*
