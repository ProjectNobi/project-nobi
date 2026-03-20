# Project Nobi — Roadmap

> Last updated: 2026-03-20
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
- [x] Cross-server miner deployment (Hetzner + Server3 + Server4 + Server5 + Server6)
- [x] Landing page (projectnobi.ai — LIVE)
- [x] Privacy Phase A: Client-side AES-128 encryption for all memories
- [x] Privacy Phase B: Encrypted synapses + per-user personality adapters
- [x] Privacy Phase C: Federated learning, differential privacy, secure aggregation (PRIVATE — mainnet only)
- [x] Brand assets: logo, wordmark, avatar, OG image, X banner
- [x] Multi-language support (20 languages)

## Phase 3: Advanced Features ✅ COMPLETE
*March 20, 2026*

### Memory & Intelligence
- [x] Semantic memory — embedding-based recall (sentence-transformers + TF-IDF fallback)
- [x] Hybrid scoring (70% similarity + 20% importance + 10% recency)
- [x] Relationship graphs — entity extraction, BFS traversal, natural language context
- [x] 10 regex extraction patterns (names, family, locations, work, pets, preferences, languages)
- [x] 30+ relationship types, 10 entity types, entity merging

### Companion Features
- [x] Voice message support (STT transcription + TTS voice replies)
- [x] Image understanding (vision API → response → memory extraction)
- [x] Proactive companion (birthday reminders, follow-ups, check-ins, milestones, encouragement)
- [x] Group companion mode (smart respond logic, per-group memory, /nori command)

### Platform & Apps
- [x] Web application (Next.js 14 + Tailwind + FastAPI backend)
- [x] Mobile app (Expo/React Native — iOS + Android, chat/memories/settings/onboarding)
- [x] FastAPI backend with 9+ endpoints (chat, memories CRUD, settings, languages, health)
- [x] One-command miner setup (`curl | bash`)

### Validator & Mining
- [x] Miner scoring tuning (diversity penalties, length normalization, gaming detection)
- [x] Anti-gaming: response similarity checks, score spike detection, entropy monitoring
- [x] CLI score analyzer (`scripts/analyze_scores.py`)
- [x] Auto-update system for validators/miners (git poll, health check, rollback, PM2 restart)
- [x] Auto-updater deployed on all 4 servers

### Community
- [x] Discord server (discord.gg/e6StezHM)
- [x] Community announcement drafts (Discord, X/Twitter, welcome message)
- [x] Mining guide with one-command setup
- [x] Validating guide with Discord links

## Phase 4: Community Growth & Mainnet Prep 📋 PLANNED
*Target: April 2026*

- [ ] 48h testnet stabilization run — observe, fix edge cases
- [ ] Invite external miners to testnet (Bittensor Discord, X)
- [ ] Gather community feedback on Nori UX
- [ ] Improve Nori personality based on conversation logs
- [ ] Deploy webapp to production (Vercel/Cloudflare)
- [ ] Deploy FastAPI backend to production
- [ ] Miner specialization (some miners better at advice, others at creativity)
- [ ] Revenue model: subscription tier for premium features
- [ ] Mainnet subnet registration (~1000+ TAO)
- [ ] Funding strategy for registration
- [ ] Production validator deployment (high-availability)
- [ ] API access for third-party integration

## Phase 5: Scale & Growth 📋 PLANNED
*Target: Q2-Q3 2026*

- [ ] 1,000 daily active users
- [ ] 50+ independent miners
- [ ] Trademark registration
- [ ] Partnership with Bittensor ecosystem projects
- [ ] App store launch (iOS + Android)
- [ ] White-label companion solution
- [ ] Enterprise features
- [ ] Proactive companion v2 (context-aware scheduling, timezone detection)
- [ ] Advanced memory v2 (LLM-powered entity extraction, contradiction detection)

---

## Current Metrics (SN272 Testnet)

| Metric | Value |
|--------|-------|
| Neurons | 10 |
| Miners | 7 |
| Validators | 2 |
| Servers | 5 |
| Total tests | 424 |
| Languages | 20 |
| Bot users | 15+ unique |
| Memory system | Semantic + Relationship Graphs |
| Platforms | Telegram, Discord, Web, Mobile (iOS/Android) |
| Auto-update | Active on all servers |

---

## Team

- **James** — Founder, vision, strategy
- **Slumpz** — Co-builder, developer, infra, QA
- **T68Bot** — AI builder, coder, operator

---

## Links

- **Website:** [projectnobi.ai](https://projectnobi.ai)
- **GitHub:** [ProjectNobi/project-nobi](https://github.com/ProjectNobi/project-nobi)
- **Discord:** [discord.gg/e6StezHM](https://discord.gg/e6StezHM)
- **Telegram Bot:** [@ProjectNobiBot](https://t.me/ProjectNobiBot)

---

*Built with love on Bittensor. Every human deserves a companion. 🤖*
