# Pre-Mainnet Legal Checklist — Human Review Required

**Created:** 2026-03-24 | **Source:** Full Compliance Audit
**Status:** ⏳ PENDING — Must complete ALL items before mainnet launch

---

## 🔴 CRITICAL (Must fix before launch)

### L1: No registered company number/address in ToS
- ToS says "Project Nobi — United Kingdom" but has no company registration number, registered address, or VAT number
- UK Consumer Contract Regulations require this for business-to-consumer services
- **Action:** Register CIC/CLG, add entity details to ToS and privacy policy

### L3: No cookie consent banner (UK PECR violation)
- Privacy policy discloses analytics cookies but there's no opt-in mechanism
- UK PECR requires prior consent for non-strictly-necessary cookies
- **Action:** Add PECR-compliant cookie consent banner to all landing pages, or remove analytics cookies entirely

---

## 🟠 HIGH (Should fix before launch)

### L2: DPO named but not identified
- Privacy policy mentions a DPO but gives no name or postal address
- GDPR Art. 37-39 requires DPO contact details to be published
- **Action:** Either appoint a DPO (with name + address) or clarify that a DPO is not yet formally appointed

### L4: GDPR erasure doesn't clear safety.db and dependency.db
- /forget and GDPR Art. 17 erasure clears memories, conversations, consent — but not safety monitoring or dependency tracking records
- **Action:** Either extend erasure to include these tables, OR document the legal basis for retention (legitimate interest in safety)

---

## 🟡 MEDIUM (Should fix before or shortly after launch)

### L5: Behavioral minor detection missing from group chat path
- The 15-pattern minor detection runs in DMs but not in group chats
- **Action:** Extend behavioral detection to group chat messages

### L6: Minor block should use dedicated table
- Minor blocks are stored as memory entries (fragile, could be lost)
- **Action:** Add `minor_blocks` table in consent.db for robust enforcement

### L7: Subprocessors not linked from privacy HTML page
- docs/legal/SUBPROCESSORS.md exists but isn't linked from the public privacy policy
- **Action:** Add link to subprocessor list from privacy.html, or inline the subprocessor details

### L8: International transfer mechanisms not documented
- Data is processed by miners globally but no Standard Contractual Clauses (SCCs) or adequacy decision references
- **Action:** Document transfer mechanisms for GDPR compliance

### L9: Export doesn't include safety/feedback records
- GDPR Art. 20 portability may require ALL personal data in export
- **Action:** Include safety/feedback records in export, or document the exclusion with legal basis

### L10: Memory extraction active by default — consent question
- Nori extracts memories automatically from conversations — could be classified as "profiling" under GDPR Art. 22
- **Action:** Legal review on whether explicit opt-in consent is required for automatic memory extraction

---

## Reminder Schedule
- **T-30 days before mainnet:** Review all items, prioritize L1 and L3
- **T-14 days:** Entity registration should be complete
- **T-7 days:** All CRITICAL and HIGH items must be resolved
- **T-1 day:** Final legal sign-off

## Reference
Full audit report: `docs/legal/COMPLIANCE_AUDIT_2026-03-24.md`
