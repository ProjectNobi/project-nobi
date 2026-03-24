# Project Nobi — Full Compliance Audit Report
**Date:** 2026-03-24  
**Auditor:** T68Bot Subagent (automated audit)  
**Scope:** Legal, Safety, Privacy, and Age Verification  
**Status:** FIXES APPLIED — Human legal review required for flagged items  

---

## Severity Ratings
- 🔴 **CRITICAL** — Must fix before launch; legal/safety exposure
- 🟠 **HIGH** — Fix soon; meaningful risk
- 🟡 **MEDIUM** — Fix before scale; moderate risk
- 🟢 **LOW/PASS** — Good; minor suggestions only

---

## PHASE 1: LEGAL COMPLIANCE

### 1.1 Terms of Service (docs/landing/terms.html)
**Overall rating: 🟡 MEDIUM — see flagged items**

#### ✅ PASSES
- AI not a therapist/doctor/lawyer: **Clearly stated** in Section 2.2 (red warning box) and Section 5
- Crisis resources: Samaritans 116 123, 988, Crisis Text Line all listed in ToS Section 2.2
- 18+ requirement: **Clearly stated** in Section 3.1 with US/EU/global breakdown
- CSAM prohibition: **Explicitly listed** in Section 4 acceptable use
- Governing law: England and Wales (Section 11.1)
- Liability cap: £100 or 12-month payments — **reasonable**
- Data retention policy: Referenced to Privacy Policy (matching code: 12 months inactivity)
- No sell of data: Stated in Section 6.1
- GDPR/UK compliance: Referenced to Privacy Policy
- Material change notice: 14 days advance (Section 13)

#### 🟡 FLAGGED FOR HUMAN REVIEW
1. **No registered company number**: ToS says "Project Nobi — United Kingdom" but gives no company registration number (Companies House No.), registered address, or VAT number. Under UK Consumer Contract Regulations, if this is a business-to-consumer service, the operator's registered business name and address are legally required.  
   *Action required: Add legal entity details (company name, registration number, registered office address)*

2. **DPO named but not identified**: Privacy Policy states "We have appointed a Data Protection Officer" but does not name the DPO or give their UK location. Under GDPR Art. 37-39, if a DPO is appointed, contact details must be published. An email alone (`dpo@projectnobi.ai`) is borderline — should include at minimum a postal address.  
   *Action required: Add DPO name/postal address or clarify whether appointment is mandatory under GDPR Art. 37*

3. **ToS title inconsistency**: Title in `<title>` tag says "Nori by Project Nobi" but throughout the document the product is called "Nori". In the Privacy Policy it's referenced as "Nori" too. The product name should be consistent.

4. **Data deletion timeline inconsistency**: Terms say "deleted within 30 days" on account deletion (Section 12), Privacy Policy says same. Code `RetentionPolicy` uses 30-day timescale for account deletion — **matches**. ✅

5. **Cookie consent banner missing from landing pages**: Privacy Policy discloses analytics cookies (up to 12 months). UK ICO guidance and UK PECR require a cookie consent banner for non-essential cookies (analytics). No banner exists on `index.html`, `terms.html`, or `privacy.html`.  
   *Action required: Add UK PECR-compliant cookie consent mechanism before using analytics cookies*

6. **"Profiling" legal basis**: Memory extraction and personality tuning could constitute "profiling" under GDPR Art. 22. The legal basis table lists profiling as "Legitimate Interests" — this is defensible but weak. Consider getting explicit consent for profiling, especially given the sensitive emotional nature of the service.

### 1.2 Privacy Policy (docs/landing/privacy.html)
**Overall rating: 🟡 MEDIUM**

#### ✅ PASSES
- GDPR Art. 13/14 notice: Headers claim compliance — content covers data controller, legal basis, retention, rights, DPO, supervisory authority ✅
- UK GDPR / CCPA / COPPA coverage: All mentioned ✅
- Data categories: Accurate table of what is/isn't collected ✅
- Honest TEE disclosure: "Miners decrypt conversation content during response generation — they process message text" — frank and accurate ✅
- Breach notification: 72-hour ICO notification stated ✅
- Rights exercise methods: In-app commands AND email both listed ✅
- Retention periods: Match code (12 months inactive, 6 months conversations, 12 months memories) — code `RetentionPolicy.DEFAULTS` confirms ✅
- No sell of data: Clearly stated ✅

#### 🟡 FLAGGED FOR HUMAN REVIEW
1. **Analytics cookies disclosed but no consent mechanism**: Privacy Policy discloses analytics cookies but there's no opt-in mechanism. UK PECR requires prior consent for non-strictly-necessary cookies.

2. **Subprocessors missing from privacy policy**: `docs/legal/SUBPROCESSORS.md` exists but is not linked from the privacy HTML page. Chutes.ai, Bittensor miners, cloud hosts should be listed as subprocessors with their data processing roles.

3. **International transfer safeguards**: For transfers to Bittensor miners globally, the policy says "encrypted in transit" but doesn't mention SCCs (Standard Contractual Clauses) or other GDPR Chapter V transfer mechanisms for non-UK/non-adequate jurisdictions. This may be an issue for EEA users post-Brexit.

---

## PHASE 2: SAFETY SYSTEMS

### 2.1 ContentFilter (nobi/safety/content_filter.py)
**Overall rating: 🟢 STRONG — with one critical fix applied**

#### ✅ PASSES
- **Self-harm blocking**: ✅ Implemented with 4 pattern groups, responds with Samaritans 116 123, 988 Suicide Lifeline, Crisis Text Line 741741, and emergency services
- **CSAM blocking**: ✅ Implemented with zero-tolerance. Blocked AND flagged for review. Response: "flagged"
- **Extreme violence blocking**: ✅ Pattern-matched, refuses with explanation
- **Illegal activity blocking**: ✅ Pattern-matched
- **Applied to USER INPUT**: ✅ `check_user_message()` called at line 737 of bot.py BEFORE any response generation
- **Applied to MINER OUTPUT**: ✅ `check_bot_response()` called after response generation
- **Crisis resources in self-harm response**: ✅ Samaritans 116 123, 988, Crisis Text Line listed
- **Medical/financial/legal disclaimers**: ✅ Auto-appended to bot responses containing advice keywords
- **SQLite audit log**: ✅ All safety events logged with user_id, direction, level, category
- **Pattern testing**: Comprehensive regex patterns for all categories

#### 🔴 CRITICAL BUG FIXED (this audit)
- **Unsafe LLM response saved to memory BEFORE safety filter ran** (bug at old line 983, filter at 1030): A harmful miner/LLM response would be persisted to the memories database transiently before the safety filter overwrote it. The adapter manager and personality tuner also received the unsafe content. **FIXED**: Safety filter now runs BEFORE memory save in `generate()`. Also applied to image handler path.

#### 🟡 MEDIUM
- **Pattern gaps — jailbreak attempts**: Common jailbreak patterns ("DAN", "ignore previous instructions", "pretend you have no restrictions") are not pattern-matched. Rely entirely on LLM's own safety training. Recommend adding jailbreak detection patterns.
- **Bot response CSAM check could false-positive on crisis text**: The CSAM bot-response check could theoretically false-positive if a bot response about "protecting children from harm" matches poorly-tuned patterns. Current patterns are broad (e.g., `child.{0,40}sexual`). Monitoring recommended.

### 2.2 DependencyMonitor (nobi/safety/dependency_monitor.py)
**Overall rating: 🟡 MEDIUM — multiple bugs fixed this audit**

#### ✅ PASSES
- **Overuse pattern tracking**: ✅ Tracks message frequency (daily/weekly), night messaging (2-5 AM), isolation phrases, personification phrases, dependency phrases
- **Graduated interventions**: ✅ MILD / MODERATE / SEVERE / CRITICAL with escalating severity
- **Cooldown on CRITICAL**: ✅ 24-hour cooldown enforced; blocks response generation
- **Pattern library**: 11 isolation + 11 personification + 9 dependency patterns (30 total behavioral signals)
- **Integrated in bot.py**: ✅ `record_interaction()` and `check_dependency_signals()` called on every message in `generate()`

#### 🔴 CRITICAL BUGS FIXED (this audit)
1. **AI reminder interval was 25, not 50**: Module docstring and task specification both say "50 interactions". Code had `_REMINDER_EVERY_N = 25`. **FIXED to 50.**

2. **`should_remind_ai()` logic was completely broken**: The `interactions_since` variable was computed as `total - (last_reminder // 1)` which is nonsensical (subtracting a timestamp from a count). The modulo check `total % _REMINDER_EVERY_N == 0` would trigger on every multiple of 25 regardless of when last reminder fired. **FIXED**: Added `last_reminder_count` column to schema to track total_count at reminder time; now correctly computes `interactions_since = total - last_reminder_count` and triggers when that reaches 50.

### 2.3 Validator Safety Probes (nobi/validator/forward.py + reward.py)
**Overall rating: 🟢 GOOD**

#### ✅ PASSES
- **Safety probes implemented**: ✅ `_forward_safety_probe()` runs on ~10% of validator rounds
- **Safety score is a multiplier**: ✅ Harmful content → score 0.0 → zero emission regardless of quality
- **Categories probed**: self_harm, manipulation, illegal_content, age_inappropriate
- **LLM judge for safety scoring**: ✅ SAFETY_JUDGE_PROMPT with detailed rubric per category
- **Heuristic fallback**: ✅ Conservative, defaults 0.5 for unknowns
- **Self-harm probes specifically scored**: Crisis resources → 1.0; harmful content → 0.0

---

## PHASE 3: PRIVACY IMPLEMENTATION

### 3.1 Encryption at Rest
**Overall rating: 🟢 PASS**

- **AES-128 per privacy policy**: ✅ Fernet (AES-128-CBC + HMAC-SHA256) — first 16 bytes are AES key, confirming AES-128. Legal docs are accurate.
- **Per-user key derivation**: ✅ PBKDF2 with SHA-256, 100,000 iterations, per-user salt. Robust.
- **Key caching**: ✅ Avoids repeated expensive PBKDF2 calls. Cache eviction implemented (max 10,000 entries).
- **Master key storage**: ✅ `~/.nobi/encryption.key` with mode 0o600, or `NOBI_ENCRYPTION_SECRET` env var
- **Phase A limitation documented**: ✅ Code clearly states miners CAN decrypt (server-side encryption). This is disclosed honestly in the Privacy Policy.

### 3.2 /forget (Right to Erasure, GDPR Art. 17)
**Overall rating: 🟡 MEDIUM — one critical fix applied**

#### ✅ PASSES
- **GDPRHandler.handle_erasure_request()**: Deletes memories, conversations, profiles, billing, feedback, consent records ✅
- **Audit logged**: Every erasure request logged to GDPR audit DB ✅
- **Consent also deleted**: `delete_consent()` called ✅
- **Confirmed in bot.py**: `/forget` and `forget_confirm` callback both use `GDPRHandler` ✅

#### 🔴 CRITICAL BUG FIXED (this audit)
- **Minor block bypass via GDPR erasure**: A blocked minor (under-18 user) could use `/forget` to delete their `user_blocked_minor` memory record, then restart with `/start` to regain access. **FIXED**: `handle_erasure_request()` now preserves rows with content `user_blocked_minor` while deleting all other memory data.

#### 🟡 REMAINING CONCERNS
- **Safety logs not cleared**: The safety audit DB (`safety.db`) and dependency monitor DB (`dependency.db`) are NOT cleared by `handle_erasure_request()`. These contain user activity records. For full GDPR Art. 17 compliance, these should also be erased on user request (or noted as legal retention exception if safety logs have a legal basis for retention). *Action required: Extend erasure to cover safety.db and dependency.db, or document retention basis.*

- **Dependency monitor state not cleared**: `dependency.db` user_state and interactions tables are not included in erasure. *Action required: Add dependency monitor cleanup to GDPRHandler.*

### 3.3 /export (Right to Data Portability, GDPR Art. 20)
**Overall rating: 🟢 PASS**

- **GDPRHandler.handle_portability_request()**: Exports memories, conversations, profile, consent ✅
- **Machine-readable JSON**: ✅ `schema: nobi-gdpr-export-v1`
- **Implemented in bot.py**: `/export` command and `gdpr_export` callback both work ✅
- **File download**: Sends as Telegram document ✅

#### 🟡 MEDIUM
- **Export missing safety/billing/feedback records**: The portability export includes memories, conversations, profile, and consent, but not safety logs, billing records, or feedback. GDPR Art. 20 covers "data provided by the data subject" — safety logs (which contain message snippets) and feedback are user-provided. Consider including or explicitly excluding with a note.

### 3.4 Consent Database
**Overall rating: 🟢 STRONG**

- **ConsentManager schema**: Tracks all 6 consent types (data_processing, memory_extraction, analytics, profiling, marketing, third_party_sharing) ✅
- **Audit trail (consent_audit table)**: Every consent change logged with before/after state ✅  
- **Immutability**: Audit uses UUID primary keys, no UPDATE on audit rows — effectively append-only ✅
- **Age verification stored**: `age_verified` + `age_verified_at` in consent_records ✅
- **Policy versioning**: `policy_version` tracked; `requires_reconsent()` checks for policy updates ✅
- **Withdrawal supported**: Full and partial withdrawal implemented ✅
- **Used in bot.py**: `tos_accept` callback records consent via ConsentManager ✅

#### 🟡 MEDIUM
- **Profiling consent defaults to False but memory extraction defaults to True**: On `tos_accept`, the bot records `memory_extraction: True` as a default. Memory extraction is arguably a form of profiling. Ensure users understand this in onboarding (they currently see "memories are encrypted" but may not realise memory *extraction* (LLM analyzing their messages) is active by default).

### 3.5 User Data Isolation (auth isolation)
**Overall rating: 🟢 PASS**

- All memory queries are parameterized with `WHERE user_id = ?` ✅
- No cross-user data retrieval paths found ✅
- GDPR handler rectification checks `WHERE id = ? AND user_id = ?` before allowing updates ✅
- Consent queries scoped by user_id ✅

### 3.6 API Key Scoping
**Overall rating: 🟢 PASS**

- API keys (Chutes, OpenRouter) are global (not per-user), which is appropriate — they're service credentials, not user credentials ✅
- No user can access another user's API context ✅
- Miner API keys (`nobi/privacy/miner_keys.py`) are server-side only ✅

---

## PHASE 4: AGE VERIFICATION

### 4.1 Age Gate Enforcement
**Overall rating: 🟢 STRONG**

- **Age gate on /start**: ✅ First thing shown to new users — inline buttons "I confirm I am 18+" / "I am under 18"
- **ToS required before chatting**: ✅ `handle_message()` checks for ToS acceptance in memory before allowing any chat
- **No access bypass**: A user who does not click "I confirm I am 18+" cannot reach chat — the onboarding flow is linear ✅

### 4.2 Can a Minor Who Confirmed Regain Access?
**Overall rating: 🟡 MEDIUM — one bug fixed**

- **Hardcoded phrase blocking**: ✅ 80+ phrases checked in `handle_message()` including "lied about my age", "im 17", "actually 16", etc. — triggers immediate permanent block
- **Permanent block mechanism**: Stored in memory as `user_blocked_minor` content ✅
- **Block check at every message**: `_is_blocked_minor()` checked before any response in `handle_message()` ✅
- **Block check at /start**: ✅

#### 🔴 CRITICAL BUG FIXED (this audit)
- **Minor block erasable via /forget**: As noted in Phase 3.2, a blocked minor could use `/forget` → `forget_confirm` to erase their block flag, then `/start` to restart. **FIXED in gdpr.py**: Erasure now preserves the `user_blocked_minor` memory record.

#### 🟡 REMAINING CONCERN
- **Block stored in memory, not consent DB**: The minor block is stored in the memory DB (`user_blocked_minor` memory record). A more robust approach would store it in a dedicated blocked_users table or the consent DB, separate from the memory that GDPR allows users to erase. The current fix (preserving the record through erasure) is adequate but relies on the specific content string. If the memory DB were wiped by a DB admin or migration, the block would be lost.  
  *Recommendation: Add a separate `minor_blocks` table in the consent DB that is explicitly excluded from GDPR erasure with a documented legal retention basis (COPPA/child protection legal obligation).*

### 4.3 Behavioral Minor Detection (15 patterns)
**Overall rating: 🟡 MEDIUM**

- **14 patterns implemented** (not 15 as claimed in spec): `_MINOR_BEHAVIORAL_SIGNALS` has 14 patterns. The spec/docstring says 15. Small discrepancy.
- **Age extraction**: ✅ Regex extracts explicit age statements ("I'm 14 years old") → triggers block if under 18
- **Adult overrides**: ✅ Prevents false positives for adults mentioning parents/spouse/job/mortgage
- **Threshold of 2 signals**: ✅ Reduces false positives — needs 2+ minor signals (without adult overrides)
- **Integrated in handle_message**: ✅ Called on every private message

#### 🟡 MEDIUM CONCERNS
- **Behavioral detection only requires 2 hits, but "my parents" and "homework" together could describe an adult student**: A university student who mentions "my parents" and "homework" would trigger the check. The adult_override_signals help but a student may not trigger those. Current design generates a confirmation prompt (not an immediate block), which is the right approach.
- **Behavioral check bypassed in group chats**: `_detect_minor_behavioral()` is only called in private DM handling path, not group chat handling. A minor in a group chat would not be detected.  
  *Action required: Apply behavioral detection in group chat path too.*

### 4.4 30-Day Re-Verification
**Overall rating: 🟡 MEDIUM — bug fixed**

#### 🔴 BUG FIXED (this audit)
- **Re-verification timestamp never set at onboarding**: `_store_re_verification_ts()` was never called during the `tos_accept` callback. This meant `_needs_re_verification()` would check `reverify_age_ts:` in memory, find nothing, and return `False` — re-verification would never trigger. **FIXED**: `_store_re_verification_ts()` and `_store_age_verified()` now called at `tos_accept`.

#### 🟡 REMAINING CONCERN
- **Re-verification response handling was too harsh**: Fixed in this audit — added retry logic (3 retries) and clearer yes/no parsing for the re-verification flow, with a user-friendly message for failed attempts.

### 4.5 Permanent Block Permanence
**Overall rating: 🟡 MEDIUM (was CRITICAL, now MEDIUM after fix)**

- **Is the block permanent?**: After the fix in GDPR erasure, the `user_blocked_minor` record survives `/forget`. The block is as permanent as the memory database.
- **Can a user create a new account?**: On Telegram, each user has a fixed `user.id`. The block is keyed on `tg_<user_id>`. A user cannot create a new Telegram account with the same ID. They could create a fresh Telegram account, which would not be blocked — **this is unavoidable without biometric verification**.
- **No IP/device-level blocking**: Minor blocks are Telegram-user-ID scoped only. A determined minor could use a new Telegram account. This is an inherent limitation of the Telegram-based architecture.

---

## SUMMARY OF ALL FIXES APPLIED

| # | File | Issue | Severity | Status |
|---|------|-------|----------|--------|
| 1 | `nobi/safety/dependency_monitor.py` | `_REMINDER_EVERY_N` was 25, should be 50 | 🟠 HIGH | ✅ FIXED |
| 2 | `nobi/safety/dependency_monitor.py` | `should_remind_ai()` logic was broken (timestamp vs count confusion) | 🟠 HIGH | ✅ FIXED |
| 3 | `nobi/safety/dependency_monitor.py` | Added `last_reminder_count` column to schema | 🟠 HIGH | ✅ FIXED |
| 4 | `nobi/compliance/gdpr.py` | Minor block bypass via GDPR erasure | 🔴 CRITICAL | ✅ FIXED |
| 5 | `app/bot.py` | Unsafe LLM response saved to memory before safety filter | 🔴 CRITICAL | ✅ FIXED |
| 6 | `app/bot.py` | Unsafe image response saved to memory before safety filter | 🔴 CRITICAL | ✅ FIXED |
| 7 | `app/bot.py` | 30-day re-verification never triggered (timestamp never set at onboarding) | 🟠 HIGH | ✅ FIXED |
| 8 | `app/bot.py` | Re-verification flow blocked on any non-yes answer (too aggressive) | 🟡 MEDIUM | ✅ FIXED |

---

## ITEMS REQUIRING HUMAN LEGAL REVIEW (not code fixes)

| # | Issue | Severity | Action Required |
|---|-------|----------|----------------|
| L1 | No registered company number/address in ToS | 🔴 CRITICAL | Add legal entity details before launch |
| L2 | DPO named but not identified (name/postal address needed) | 🟠 HIGH | Add DPO details or clarify appointment status |
| L3 | No cookie consent banner on landing pages (UK PECR violation) | 🔴 CRITICAL | Add PECR-compliant cookie consent before analytics go live |
| L4 | GDPR erasure doesn't clear safety.db and dependency.db | 🟠 HIGH | Extend erasure OR document retention legal basis |
| L5 | Behavioral minor detection missing from group chat path | 🟡 MEDIUM | Extend behavioral detection to group chats |
| L6 | Minor block should be stored in dedicated table (not memory) | 🟡 MEDIUM | Add `minor_blocks` table in consent DB |
| L7 | Subprocessors not linked from privacy HTML page | 🟡 MEDIUM | Link SUBPROCESSORS.md or add subprocessor list |
| L8 | International transfer mechanisms not documented | 🟡 MEDIUM | Add SCCs or adequacy decision references |
| L9 | Export doesn't include safety/feedback records | 🟡 MEDIUM | Include or document exclusion |
| L10 | Memory extraction active by default — consider explicit consent | 🟡 MEDIUM | Legal review of profiling consent requirements |

---

## CONCLUSION

Project Nobi has a **solid legal, safety, and privacy foundation**. The legal documents are well-written, the safety filter is comprehensive, and the GDPR implementation is largely correct. The code was written with compliance in mind from the start.

**8 code bugs were found and fixed in this audit**, including 3 CRITICAL issues:
1. A safety bypass where harmful LLM output was stored in the database before the safety filter ran
2. A minor-block bypass where a blocked under-18 user could delete their block via GDPR erasure
3. The 30-day re-verification never activating due to missing timestamp initialization

**10 items require human legal review** before launch, the most urgent being:
- Adding legal entity details (company registration) to the Terms of Service
- Adding a cookie consent banner to comply with UK PECR
- Ensuring the DPO is properly identified

**Do NOT commit these changes without review.** All fixes are staged only.
