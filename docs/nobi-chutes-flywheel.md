# Project Nobi × Chutes.ai — Economic Flywheel Analysis
## Date: 2026-03-22

---

## 1. How Chutes.ai Works (Economic Model)

Chutes (SN64 on Bittensor) is a decentralised inference marketplace:
- **Miners** provide GPU compute (A100s, H100s) and serve LLM inference
- **Validators** route requests to miners, score quality/latency
- **Users** (developers, apps) pay for inference via API ($20/mo base + per-query)
- **Revenue** flows: Users → Chutes → Miners (via TAO emissions + direct revenue)
- **TEE (Trusted Execution Environment)**: Many models run in TEE for verifiable compute

### Chutes Revenue Per GPU (from jondurbin data, 2026-03-22):
| Model | Rev/GPU/day | Utilization |
|-------|-------------|-------------|
| GLM-5-TEE | $1.88 | 85% |
| MiniMax-M2.5 | $1.86 | 41% |
| DeepSeek-V3.1-TEE | $0.75 | 65% |
| DeepSeek-V3 | $0.71 | 66% |
| GPT-OSS-120B | $0.45 | 69% |
| Qwen3-235B | $0.14 | 82% |
| Mistral-Small-3.2 | $0.07 | 67% |

**Key insight**: Chutes needs DEMAND (API calls) to make their GPU fleet profitable. More demand = more revenue per GPU = more miners join = more capacity = better service.

---

## 2. How Nobi Contributes to Chutes' Flywheel

### 2.1 Direct Demand Generation
Nobi is a **continuous, predictable demand source** for Chutes inference:

- **Current**: ~56 messages/day × 4 models in fallback chain = API calls to Chutes
- **At 1,000 users**: ~30,000-100,000 messages/day → significant inference demand
- **At 100,000 users**: ~3-10 million messages/day → major Chutes revenue driver
- **At 1M users**: ~30-100M messages/day → one of Chutes' largest customers

Unlike developer API usage (bursty, project-based), **companion chat is DAILY and HABITUAL**. Users chat with Nori every day, creating steady baseline demand — the most valuable kind of traffic for infrastructure providers.

### 2.2 Revenue Impact Math
At 100,000 daily active users × 50 messages/day = 5M messages/day:
- Average tokens per message: ~300 (input + output)
- Total tokens/day: ~1.5 billion
- At Chutes pricing (~$0.15/M input, ~$0.60/M output tokens for DeepSeek-V3.1):
  - Input: ~500M tokens × $0.15/M = $75/day
  - Output: ~1B tokens × $0.60/M = $600/day
  - **Total: ~$675/day = ~$20,000/month to Chutes**

At 1M users: **~$200,000/month in Chutes revenue**. That's a meaningful revenue stream that justifies additional GPU deployment.

### 2.3 Utilization Smoothing
Chutes GPUs have variable utilization (30-99% per model). Nobi's traffic is:
- **Geographically distributed** (users worldwide → spread across time zones)
- **Temporally smooth** (companion chat happens morning, afternoon, evening — not 9-5 burst)
- **Multi-model** (auto-routing distributes across V3.1, V3, GPT-OSS, Mistral)

This helps Chutes maintain higher average utilization, which directly improves revenue per GPU.

---

## 3. How Chutes Contributes to Nobi's Flywheel

### 3.1 Zero-Capex Inference
Nobi miners don't need to buy GPUs. They use Chutes API on $30-70/month VPS:
- No GPU procurement ($10-50K per A100)
- No GPU maintenance, cooling, depreciation
- Instant access to frontier models (V3.1, Qwen3-235B, GPT-OSS)
- Pay-as-you-go scales with demand

**This is what makes "free for users" possible.** If miners had to buy GPUs, the economics would require user subscriptions. Chutes abstracts the GPU cost into affordable API pricing.

### 3.2 Model Diversity
Chutes offers 40+ models. Nobi benefits:
- Auto-routing picks the fastest available model at any moment
- If one model is overloaded (429), another serves immediately
- Quality competition: miners can choose which Chutes model to serve through
- New models (GPT-OSS, GLM-5) become available to Nobi instantly without code changes

### 3.3 TEE for Privacy
Chutes' TEE models run in Trusted Execution Environments:
- Inference happens inside encrypted hardware enclaves
- Even Chutes operators can't see the data being processed
- This aligns with Nobi's privacy mission — user conversations processed in TEE
- Gives Nobi a credible privacy story: "your messages are processed in hardware-encrypted enclaves"

---

## 4. The Combined Flywheel (Nobi × Chutes × Bittensor)

```
                    ┌─────────────────┐
                    │   NOBI USERS    │
                    │  (free, growing) │
                    └────────┬────────┘
                             │ messages
                             ▼
                    ┌─────────────────┐
                    │  NOBI MINERS    │
                    │ (earn TAO from  │
                    │  SN272 emissions)│
                    └────────┬────────┘
                             │ API calls
                             ▼
                    ┌─────────────────┐
                    │   CHUTES (SN64) │
                    │ (earn revenue   │
                    │  from API calls) │
                    └────────┬────────┘
                             │ revenue
                             ▼
                    ┌─────────────────┐
                    │  CHUTES MINERS  │
                    │ (GPU providers, │
                    │  earn TAO+rev)  │
                    └────────┬────────┘
                             │ more GPUs deployed
                             ▼
                    ┌─────────────────┐
                    │ BETTER INFERENCE│
                    │ (faster, cheaper│
                    │  more models)   │
                    └────────┬────────┘
                             │ better Nori responses
                             ▼
                    ┌─────────────────┐
                    │  MORE NOBI USERS│
                    │ (better product │
                    │  → word of mouth)│
                    └─────────────────┘
```

**Each participant benefits from the other's growth:**

| Actor | What they give | What they get |
|-------|---------------|---------------|
| Nobi users | Message volume (demand) | Free AI companion |
| Nobi miners | API revenue to Chutes | TAO from SN272 |
| Chutes (SN64) | Inference capacity | Revenue from Nobi traffic |
| Chutes miners | GPU compute | TAO + direct revenue |
| TAO holders | Stake on SN272/SN64 | Yield from growing subnets |
| Bittensor | — | Proof of real-world utility |

---

## 5. Deep Collaboration Opportunities

### 5.1 Dedicated Nobi Inference Pool
Chutes could create a dedicated inference pool for Nobi traffic:
- Guaranteed capacity (no 429s during peak)
- Optimised for companion-style queries (shorter context, conversational tone)
- Volume discount pricing for Nobi's consistent demand
- **Benefit to Chutes**: Predictable revenue, justified GPU procurement

### 5.2 Co-Marketing
- "Powered by Chutes" badge on Nobi → drives developer awareness of Chutes
- Chutes showcases Nobi as a case study → "see what you can build with our API"
- Joint blog posts: "How a free AI companion runs on decentralised inference"
- **Benefit to both**: Cross-pollination of communities

### 5.3 TEE Privacy Integration
- Nobi exclusively routes through TEE models on Chutes
- Marketing: "Your conversations are processed in hardware-encrypted enclaves"
- Chutes TEE usage increases → justifies more TEE infrastructure
- **Benefit to Nobi**: Strongest possible privacy claim
- **Benefit to Chutes**: TEE becomes a differentiator they can sell to other privacy apps

### 5.4 Model Fine-Tuning Partnership
- Nobi generates massive amounts of companion conversation data
- Chutes could host fine-tuned companion models specifically for Nobi
- Better companion model → higher Nobi scores → more users → more Chutes revenue
- **Benefit**: Exclusive competitive advantage for both

### 5.5 Subnet Cross-Staking
- Nobi stakers could receive bonus ALPHA for also staking on Chutes (SN64)
- Creates aligned incentives: both subnets grow together
- The "Nobi ecosystem" stake includes both SN272 and SN64
- **Benefit**: Deeper economic integration

---

## 6. Effect on Bittensor Overall

### 6.1 Proving the Stack
Nobi + Chutes demonstrates a complete Bittensor application stack:
- **SN272 (Nobi)**: Application layer — serves end users
- **SN64 (Chutes)**: Inference layer — provides compute
- **SN21 (Storage)**: Could host user memories long-term
- **SN0 (Root)**: Network governance and emission allocation

This is the **first real example of subnets composing into a product**. Most subnets operate in isolation. Nobi consuming Chutes' inference proves that Bittensor can function as a modular technology stack — not just a collection of independent experiments.

### 6.2 TAO Demand from Real Utility
Every Nobi message creates a chain of TAO demand:
1. Nobi user sends message → miner earns TAO (SN272 emissions)
2. Miner pays Chutes for inference → Chutes miners earn TAO (SN64 emissions) + revenue
3. Both subnets attract more stake → TAO demand increases
4. More TAO staked → higher emissions → better service → more users

**This is TAO being used as actual money for actual services** — not just speculative trading between miners.

### 6.3 The Adoption Narrative
For Bittensor's long-term value:
- "We have a free AI companion used by millions, powered entirely by our network"
- "The inference is provided by another subnet in our ecosystem"
- "Subnets collaborate to serve real users — that's what makes TAO valuable"

This narrative is worth more than any tokenomics paper. **Real usage, real collaboration, real value creation** — that's what attracts institutional attention and mainstream adoption.

---

## 7. Summary: Why This Matters

Nobi and Chutes aren't just compatible — they're **economically symbiotic**:

- **Nobi needs cheap, reliable inference** → Chutes provides it
- **Chutes needs consistent demand** → Nobi generates it (daily, habitual, growing)
- **Both need Bittensor to thrive** → their collaboration proves the network works
- **TAO benefits from both** → real utility, real demand, real applications

The question isn't "should Nobi and Chutes collaborate?" — it's "why hasn't every application subnet done this already?"

**Nobi is Chutes' best potential customer. Chutes is Nobi's best infrastructure provider. Together, they're Bittensor's best proof of concept.**

---

*Research by T68Bot | Source: Chutes revenue data (jondurbin, 2026-03-22), Nobi operational data, Bittensor tokenomics*
