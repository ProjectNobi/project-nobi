# ChatGPT 5.4 Pro — Legal Review of Project Nobi
## Date: 2026-03-20
## Source: ChatGPT 5.4 Pro Research Mode (commissioned by James)

---

### Summary

> "Nobi has a serious privacy-forward direction, but it only partially resolves the main legal and compliance concerns today."

### Key Findings

#### ✅ GOOD (what's working):
- Project is public/open source
- Website promises export/delete controls
- Codebase includes encryption primitives
- API keys are hashed and rate-limited
- Stripe webhooks are verified when configured
- TLS deployment is documented
- Proactive outreach has frequency and quiet-hour limits

#### 🔴 CRITICAL ISSUE: Truth in advertising / Privacy representation mismatch

**What we claim:**
- "All memories are AES-128 encrypted"
- "No single company owns your data"
- "Export or delete anytime"
- "Miners store encrypted blobs they cannot read"
- "Phase A+B are live"

**What's actually true:**
- README says memory is "currently stored in plaintext on individual miner machines"
- Subnet design says "current testnet architecture stores plaintext SQLite on miner machines"
- encryption.py says "the miner can decrypt in the current phase because it has the master secret"
- Stronger protection deferred to later phases

**Risk:** FTC has warned it will examine AI products by "looking under the hood" comparing claims to implementation. This mismatch is a material legal risk under consumer-protection law.

#### 🟡 OTHER CONCERNS:
- Web app backend trusts caller-supplied user_id with permissive CORS
- No strong authenticated identity for memory/settings endpoints
- Product accumulates intimate personal profiles without traditional account system
- Not a "low-risk plain chatbot" — stores typed memories, conversation history, user profiles, embeddings, relationship graphs, names, geography, jobs, preferences, life events, emotional states, voice, images

### Recommended Fix (from the review):

> "The safest and most accurate public wording right now would be closer to: 'memories are encrypted in storage and users can export/delete them; stronger on-device/federated privacy is planned.' Until the technical reality matches the stronger marketing copy, I would treat the current claims as a material legal risk."

---

### Action Items from this Review

1. **IMMEDIATE: Fix privacy claims across all public materials**
   - README, whitepaper, website, webapp, bot — all must use accurate wording
   - Remove "miners can't read" claims until Phase C is actually deployed
   - Change to: "memories are encrypted in storage; user-controlled deletion; federated privacy planned"

2. **IMMEDIATE: Fix CORS + user_id authentication**
   - API endpoints should not trust caller-supplied user_id
   - Add proper session/token auth for web app

3. **BEFORE MAINNET: Align encryption.py with claims**
   - Either implement true user-exclusive key control
   - Or clearly document that current encryption protects at-rest but miner has decrypt capability

4. **ONGOING: Maintain consistency between all public documents**
   - One source of truth for privacy status
   - Regular audit of claims vs reality

---

*This review was conducted by ChatGPT 5.4 Pro Research Mode and saved as reference for the team.*
