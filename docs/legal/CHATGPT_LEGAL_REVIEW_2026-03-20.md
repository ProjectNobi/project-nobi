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

---

## Part 2: Additional Issues

### 🔴 Issue 2: Access Control & Account Integrity

**Finding:** Public web-app backend uses client-provided `user_id` for all endpoints:
- /api/chat, /api/memories, /api/memories/export, /api/memories/all
- /api/settings, /api/feedback, /api/support
- CORS: `allow_origins=["*"]`, `allow_credentials=True`

**Risk:** Anyone can access anyone else's memories by guessing/supplying their user_id. Serious security and privacy problem under GDPR "security of processing" requirement.

**Fix needed:** Proper session/token authentication for web app users.

### 🟡 Issue 3: Transparency Paperwork

**Finding:** No publicly linked privacy policy or terms page found on the main site/app navigation.

**Risk:** GDPR Articles 12-14 require transparent information about controller identity, legal basis, recipients, storage period, transfers, and rights. CCPA gives consumers rights to know, delete, correct, opt out.

**Fix needed:** Prominent links to Privacy Policy and ToS from every page.

### 🟡 Issue 4: Sensitive & Special-Category Data

**Finding:** Nobi stores emotions, relationships, life events, dialogue history, voice, and photos. Users may disclose health, sexuality, religion, politics — all GDPR Article 9 special categories.

**Implications:**
- GDPR Article 9: special category data requires explicit consent
- California: consumers have rights re sensitive personal information
- Washington My Health My Data Act: reaches consumer health data outside HIPAA
- HIPAA: Nobi could become a business associate if serving covered entities

**Fix needed:** Explicit consent for special category data processing. Clear disclosure that conversation content may include sensitive data.

### 🔴 Issue 5: Companion Safety, Minors & Therapy Positioning

**Finding:** Business materials mention:
- Product as answer to loneliness
- Enterprise "employee wellness"
- Family tier with parental controls
- Marketplace for "therapist" companion personalities

**Risk:**
- FTC (Sept 2025): formal inquiry into AI companion chatbots — safety testing, impacts on children, disclosures, age restrictions, data handling
- COPPA: requirements when services directed to under-13 or collecting data from them
- EU AI Act: transparency rules require users to be informed they're interacting with AI
- Moving beyond "fun chatbot" into wellness/therapy territory significantly increases regulatory scrutiny

**Fix needed:**
- Clear "NOT a therapist" disclaimers
- Remove or reframe "therapist" marketplace personality
- Robust age verification
- AI interaction disclosure on first use

---

## Priority Action Matrix (from full review)

| Priority | Issue | Action | Risk Level |
|----------|-------|--------|------------|
| 🔴 P0 | Privacy claims mismatch | Fix ALL public claims to match reality | Legal liability |
| 🔴 P0 | API auth (user_id) | Implement proper session tokens | Data breach risk |
| 🔴 P0 | Therapy positioning | Remove "therapist" language, add disclaimers | FTC inquiry risk |
| 🟡 P1 | Privacy/Terms links | Add to all page navigation | GDPR violation |
| 🟡 P1 | Special category consent | Add explicit consent for sensitive data | GDPR Art 9 |
| 🟡 P1 | AI disclosure | "You are talking to an AI" on first interaction | EU AI Act |
| 🟢 P2 | COPPA compliance | Robust age gate, parental consent flow | FTC risk |
| 🟢 P2 | CORS restriction | Restrict to projectnobi.ai domains only | Security |


---

## Part 3: Vendor Governance, Enterprise, Token Law & Recommended Fix

### 🟡 Issue 6: Vendor Governance & International Transfers

**Third-party dependencies identified:**
- Chutes.ai / OpenRouter — LLM model calls
- OpenAI Whisper / local Whisper — STT
- ElevenLabs / gTTS — TTS
- Stripe — billing
- Telegram — core user channel

**Required:**
- Subprocessor map (who handles what data, where)
- Contract stack (DPAs with each vendor)
- Transfer analysis (cross-border data flows)
- Retention policy per vendor
- User-facing disclosure of recipients and cross-border handling

### 🟡 Issue 7: Enterprise & Regulated-Vertical Overreach

**Finding:** Business plan pitches future appeal to healthcare, finance, legal sectors.

**Rule:** Do NOT sell as "privacy-ready regulated-industry solution" until controls exist:
- Real identity and access management
- Audit logs
- Admin controls
- Retention controls
- DPA/BAA readiness
- Vendor flowdown
- Security evidence

### 🟡 Issue 8: Token/Securities Law

**Finding:** Public materials tie service to Bittensor, miner earnings in TAO, staking, "alpha value backed by real subscription revenue."

**Need:** Dedicated securities/commodities/tax/sanctions review before:
- Public investment-style promotion
- Any retail program that blurs product usage with financial return expectations

### 📋 RECOMMENDED FIX SET (from ChatGPT 5.4 Pro)

**1. Fix public truth layer IMMEDIATELY**
- Rewrite EVERY privacy claim to match what architecture actually supports today
- Do NOT say miners "cannot read" data unless system prevents decryption
- Do NOT present federated/on-device privacy as current unless live

**2. Ship real identity model for web app (highest engineering priority)**
- Options: passkeys, magic-link email, or OAuth + server-issued session tokens
- Every memory/export/delete/settings action authorizes against server identity
- Lock CORS to known origins (projectnobi.ai domains only)
- Add CSRF protections

**3. Publish full document stack:**
- Privacy policy ✅ (exists, needs accuracy update)
- Terms of service ✅ (exists, needs accuracy update)
- AI disclosure/safety page
- Children-and-teens policy
- Subprocessor list
- Retention schedule
- Law enforcement/government request policy
- Plain-language export/delete rights explanation
- GDPR Article 30 records-of-processing inventory
- Data Protection Impact Assessment (DPIA) — prudent default given persistent memory + relationship mapping + emotional/health content

---

## Complete Priority Matrix

| Priority | Issue | Action | Owner |
|----------|-------|--------|-------|
| 🔴 P0 | Privacy claims | Fix ALL public claims to match reality | T68Bot NOW |
| 🔴 P0 | API authentication | Implement session tokens, lock CORS | T68Bot NOW |
| 🔴 P0 | Therapy language | Remove/reframe in business plan | T68Bot NOW |
| 🟡 P1 | Privacy/Terms nav links | Add to all pages prominently | T68Bot |
| 🟡 P1 | Special category consent | Explicit consent flow | T68Bot |
| 🟡 P1 | AI disclosure | "You are talking to AI" on first use | T68Bot |
| 🟡 P1 | Subprocessor list | Document all vendors | T68Bot |
| 🟡 P1 | Retention schedule | Define and publish | T68Bot |
| 🟢 P2 | COPPA compliance | Robust age gate + parental consent | T68Bot |
| 🟢 P2 | DPIA | Data Protection Impact Assessment | Lawyer |
| 🟢 P2 | Token/securities review | Dedicated legal review | Lawyer |
| 🟢 P2 | Enterprise controls | IAM, audit logs, admin, BAA | Pre-enterprise launch |

---

*Full review saved for team reference. All findings to be addressed before mainnet launch.*

---

## Part 4: Launch Positioning, Vendor Governance & Final Recommendations

### 🔴 Issue 9: Product Positioning at Launch

**Recommendation:** Market Nobi as an **AI companion/chat product ONLY**. NOT:
- ❌ Therapy
- ❌ Crisis support
- ❌ Mental health treatment
- ❌ Regulated wellness solution

**Required safeguards:**
- Always-on AI disclosure
- Crisis handoff language (helpline numbers)
- Easy opt-out from proactive messages
- Strict consent for voice/image memory capture
- **18+ only** at launch (safest) OR hard block for under-13 + tightly controlled teen mode
- FTC is actively scrutinizing companion bots and child impacts (Sept 2025 inquiry)

### 🟡 Issue 10: Vendor Governance as Product Feature

**Actions:**
- Map every processor and subprocessor
- Decide which providers may retain prompts/audio
- Negotiate DPAs and transfer terms
- Expose vendor map publicly
- Offer region-aware routing where possible
- Separate consumer and enterprise processor stacks early

### 🟡 Issue 11: Delay Regulated-Enterprise & Federated Claims

**Rule:** Follow the business plan's own instruction literally — do NOT present federated privacy or enterprise-grade controls as current capabilities.

Future enterprise story can be strong IF:
- On-device memory becomes real
- True privacy-preserving learning is deployed
- Control evidence exists (audit logs, IAM, BAA readiness)

Until then: it's a **future story, not a present one.**

---

## THE PRACTICAL PATH (ChatGPT 5.4 Pro Summary)

> "Nobi does not fully resolve the key legal/privacy/compliance issues yet, but it can. The fastest defensible path is:
> 1. Truthful copy
> 2. Real auth
> 3. Formal privacy docs
> 4. Adult-first launch
> 5. Narrower claims
> 6. Vendor contracts
> 7. No regulated/therapy/federated sales language until architecture supports it
>
> Done that way, the business becomes much stronger legally and commercially, not weaker."

---

## References
1. [Project Nobi Website](https://projectnobi.ai/)
2. [Whitepaper](https://github.com/ProjectNobi/project-nobi/blob/main/docs/WHITEPAPER.md)
3. [encryption.py source](https://github.com/ProjectNobi/project-nobi/raw/refs/heads/main/nobi/memory/encryption.py)
4. [API Reference](https://github.com/ProjectNobi/project-nobi/blob/main/docs/API_REFERENCE.md)
5. [Vision Doc](https://github.com/ProjectNobi/project-nobi/blob/main/docs/VISION.md)
6. [server.py source](https://github.com/ProjectNobi/project-nobi/raw/refs/heads/main/api/server.py)
7. [Business Plan](https://github.com/ProjectNobi/project-nobi/blob/main/docs/BUSINESS_PLAN.md)
8. [Web App](https://app.projectnobi.ai/)
9. [GDPR Full Text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)
10. [FTC AI Companion Inquiry (Sept 2025)](https://www.ftc.gov/news-events/news/press-releases/2025/09/ftc-launches-inquiry-ai-chatbots-acting-companions)

---

*Full review complete. Saved as reference for Project Nobi legal compliance roadmap.*
