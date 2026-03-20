# Project Nobi — Data Retention Schedule

**Last updated:** 2026-03-20  
**Document owner:** DPO — dpo@projectnobi.ai

This document describes how long Project Nobi retains different categories of personal data, and how users can exercise their deletion rights.

---

## Summary Table

| Data Category | Retention Period | User Control |
|--------------|-----------------|--------------|
| Conversation history | Until user deletes | `/forget` command or web app |
| Memory data | Until user deletes | `/memories`, `/forget`, or web app |
| User profile | Until user deletes | `/forget` or account deletion |
| Inactive accounts | Auto-deleted after 12 months of inactivity | N/A (automatic) |
| Feedback submissions | 6 months (anonymised after 6 months) | N/A |
| API access logs | 30 days (rolling) | N/A |
| Payment data | Handled by Stripe — not stored by us | Stripe account |
| Age consent record | Until account deletion | Account deletion |

---

## Detailed Retention Policies

### 1. Conversation History
- **What:** Message text exchanged between the user and Nori
- **Retention:** Retained indefinitely while the account is active
- **Deletion:** Users can delete all conversation history using the `/forget` command (Telegram) or the "Forget Everything" button in the web app's Memories page
- **Auto-deletion:** After 12 months of account inactivity (no messages sent or received)

### 2. Memory Data
- **What:** Extracted facts, preferences, relationship data, and context that Nori remembers about the user
- **Retention:** Retained indefinitely while the account is active
- **User control:**
  - `/memories` — view all stored memories
  - `/forget` — delete all memories permanently
  - `/export` — download a copy of all memories
  - Web app → Memories page → delete individual memories or all memories
- **Auto-deletion:** After 12 months of account inactivity

### 3. User Profile
- **What:** Display name, language preference, settings, and onboarding data
- **Retention:** Retained while account is active
- **Deletion:** Deleted when the user runs `/forget` or requests full account deletion

### 4. Inactive Accounts
- **Policy:** Accounts with no activity (no messages sent or received) for 12 consecutive months will have all personal data automatically deleted
- **Notice:** Users will receive a notification (if contact information is available) 30 days before auto-deletion
- **Scope:** Conversation history, memories, user profile, and all associated data

### 5. Feedback & Support Submissions
- **What:** Bug reports, feature requests, support tickets submitted via `/feedback`, `/support`, or the web app support page
- **Retention:** Retained for 6 months in identifiable form for product improvement purposes
- **Anonymisation:** After 6 months, feedback is anonymised (user_id removed) and retained for aggregate analysis
- **Full deletion:** Available upon request to privacy@projectnobi.ai

### 6. API Access Logs
- **What:** Server-side logs of API requests (endpoint, timestamp, user_id hash, response code)
- **Retention:** 30 days rolling
- **Purpose:** Security monitoring, abuse prevention, debugging
- **Note:** Logs contain hashed identifiers, not plaintext user data

### 7. Payment Data
- **Policy:** Project Nobi does NOT store payment card numbers, CVV codes, or full billing details
- **What we store:** Stripe customer ID, subscription tier, payment status, and transaction reference (no card data)
- **Stripe retention:** Stripe retains payment data per their own retention policies (see [stripe.com/privacy](https://stripe.com/privacy))
- **User control:** Manage payment methods and history directly in your Stripe billing portal

### 8. Age Consent Record
- **What:** A record that the user confirmed they are 18+ years old at onboarding
- **Retention:** Retained for the lifetime of the account for legal compliance purposes
- **Deletion:** Deleted when the full account is deleted

---

## How to Delete Your Data

### Full Data Deletion (All Platforms)
1. **Telegram:** Send `/forget` to @ProjectNobiBot
2. **Web App:** Go to Memories → "Forget Everything" button

### Account Deletion Request
To request complete and permanent deletion of all data associated with your account, email **privacy@projectnobi.ai** with the subject "Data Deletion Request" and include your Telegram user ID or web app user ID.

We will process deletion requests within **30 days** as required by GDPR Article 17.

### Data Export (Right to Portability)
1. **Telegram:** Send `/export` to @ProjectNobiBot
2. **Web App:** Go to Memories → "Export" button
3. **Formal request:** Email privacy@projectnobi.ai for a full machine-readable export

---

## Legal Basis for Retention

| Data Category | Legal Basis | Regulation |
|--------------|-------------|------------|
| Conversation & memory data | Contract performance (service delivery) | GDPR Art. 6(1)(b) |
| Feedback & support | Legitimate interest (product improvement) | GDPR Art. 6(1)(f) |
| API logs | Legitimate interest (security) | GDPR Art. 6(1)(f) |
| Age consent record | Legal obligation (COPPA/GDPR-K compliance) | GDPR Art. 6(1)(c) |

---

## Contact

- **Privacy requests:** privacy@projectnobi.ai
- **Data Protection Officer:** dpo@projectnobi.ai
- **Response time:** Within 72 hours for acknowledgement; 30 days for resolution
