# Privacy Policy

**Effective Date:** March 20, 2026  
**Last Updated:** March 20, 2026

---

> **The short version:** Your data is encrypted, you own it, and you can delete it anytime. We don't sell your data. Ever.

---

This Privacy Policy explains how Project Nobi ("Project Nobi", "we", "us", or "our") collects, uses, stores, and protects your personal data when you use the Nori AI companion service ("the Service") through any of our platforms.

This policy is provided in compliance with:
- **GDPR** (EU General Data Protection Regulation 2016/679), Articles 13 and 14
- **CCPA** (California Consumer Privacy Act 2018)
- **COPPA** (Children's Online Privacy Protection Act)
- **UK GDPR** (as incorporated into UK law by the Data Protection Act 2018)

---

## 1. Data Controller

Project Nobi is the data controller for personal data processed through the Nori service.

**Contact:**  
Project Nobi  
United Kingdom  
Email: privacy@projectnobi.ai  
DPO Email: dpo@projectnobi.ai

If you are in the EU/EEA, you also have the right to lodge a complaint with your local supervisory authority. In the UK, this is the Information Commissioner's Office (ICO) at ico.org.uk.

---

## 2. What Data We Collect

We collect data in the following categories:

### 2.1 Data You Provide Directly
| Data Category | Examples | Purpose |
|---|---|---|
| Account information | Display name, email address | Account creation and communication |
| Conversation content | Text messages, voice transcriptions, image descriptions | Providing the companion service |
| Memory data | Facts, preferences, events Nori extracts from conversations | Personalisation and continuity |
| Feedback and support | Bug reports, feature requests, support tickets | Service improvement |
| Payment information | Billing address, last 4 digits of card (Stripe handles full card data) | Payment processing |

### 2.2 Data Collected Automatically
| Data Category | Examples | Purpose |
|---|---|---|
| Usage statistics | Features used, session length, message frequency | Service improvement and analytics |
| Device information | Device type, operating system, app version | Compatibility and debugging |
| Technical data | IP address (hashed), error logs, API response times | Security and performance monitoring |
| Cookies and local storage | Session tokens, preferences, consent flags | Authentication and user experience |

### 2.3 Data We Do NOT Collect
- Full payment card numbers (handled exclusively by Stripe)
- Audio recordings (voice messages are transcribed; the audio is not permanently stored)
- Original images (images are analysed for conversational context; originals are not permanently stored)
- Location data (we do not request or store GPS coordinates)
- Contacts or address book data

---

## 3. Legal Basis for Processing (GDPR)

Under GDPR, we process your data on the following legal bases:

| Processing Activity | Legal Basis |
|---|---|
| Providing the companion service | **Contract** (Art. 6(1)(b)) — necessary to perform the service you requested |
| Memory storage and personalisation | **Contract** (Art. 6(1)(b)) — core feature of the service |
| Payment processing | **Contract** (Art. 6(1)(b)) — necessary to process your subscription |
| Safety filtering and abuse prevention | **Legitimate interests** (Art. 6(1)(f)) — protecting users and the platform |
| Service analytics and improvement | **Legitimate interests** (Art. 6(1)(f)) — improving service quality |
| Marketing communications | **Consent** (Art. 6(1)(a)) — only with your explicit opt-in |
| Legal compliance | **Legal obligation** (Art. 6(1)(c)) — where required by law |
| Special category data (health-related conversations) | **Explicit consent** (Art. 9(2)(a)) — you initiate these conversations |

---

## 4. How We Use Your Data

We use your data to:

1. **Provide the service** — process your messages and generate AI responses
2. **Enable memory** — store and retrieve personal context to make Nori feel like a real companion
3. **Personalise your experience** — adapt Nori's tone, topics, and responses to you over time
4. **Process payments** — manage your subscription and billing
5. **Improve service quality** — analyse usage patterns and fix issues (using anonymised/aggregated data)
6. **Ensure safety** — detect and prevent abuse, illegal content, and harmful interactions
7. **Communicate with you** — send service updates, receipts, and responses to your enquiries
8. **Legal compliance** — fulfil our obligations under applicable law

**We do NOT:**
- Sell your personal data to third parties
- Use your personal conversations to train AI models without your explicit opt-in consent
- Share your data for advertising or marketing by third parties
- Use your data for automated decision-making with legal or similarly significant effects without your knowledge

---

## 5. Data Storage and Security

### 5.1 Encryption
All conversation data and memory data is encrypted using **AES-128 encryption** before storage. Encryption keys are derived from your account credentials using PBKDF2 key derivation and are never stored in plaintext.

Data in transit is protected using TLS 1.3.

### 5.2 Decentralised Storage (Bittensor Network)
Nori operates on the Bittensor decentralised AI network. When you send a message:
- Your message may be processed by network participants ("miners") to generate AI responses
- Data transmitted to miners is encrypted and does not include your personal identity (name, email, or account details)
- Miners see only the conversation context necessary to generate a response
- Memory data stored at rest is encrypted; miners store encrypted blobs they cannot casually read

We take reasonable steps to ensure that miners participating in the network meet appropriate standards, but as a decentralised network, we cannot guarantee the security practices of every individual miner node.

### 5.3 Infrastructure Security
- Data at rest: AES-128 encryption
- Data in transit: TLS 1.3
- Access controls: Role-based access with principle of least privilege
- Monitoring: Automated security monitoring and alerting
- Backups: Regular encrypted backups with tested restore procedures

---

## 6. Data Sharing

We share your data only in the following limited circumstances:

| Recipient | Purpose | Safeguards |
|---|---|---|
| **Stripe** | Payment processing | Stripe Privacy Policy; PCI-DSS compliant; data processing agreement in place |
| **Bittensor miners** | AI response generation | Encrypted data only; no PII transmitted; pseudonymous identifiers |
| **Cloud infrastructure providers** | Hosting and storage | Data processing agreements; encrypted data |
| **Legal authorities** | Compliance with legal obligations | Only when required by law, court order, or to protect safety |

**We do not share your data with:**
- Advertising networks
- Data brokers
- Social media platforms
- Any third party for marketing purposes

---

## 7. Your Rights

### 7.1 Rights Under GDPR (EU/UK residents)
You have the following rights regarding your personal data:

- **Right of Access (Art. 15)** — Request a copy of all personal data we hold about you
- **Right to Rectification (Art. 16)** — Request correction of inaccurate data
- **Right to Erasure / "Right to be Forgotten" (Art. 17)** — Request deletion of your data
- **Right to Restriction of Processing (Art. 18)** — Request we limit how we use your data
- **Right to Data Portability (Art. 20)** — Request your data in a machine-readable format
- **Right to Object (Art. 21)** — Object to processing based on legitimate interests
- **Rights related to automated decision-making (Art. 22)** — Not to be subject to solely automated decisions with significant effects

### 7.2 Rights Under CCPA (California residents)
California residents have the right to:
- Know what personal information is collected and how it is used
- Delete personal information (subject to certain exceptions)
- Opt out of the "sale" of personal information (we do not sell personal information)
- Non-discrimination for exercising your privacy rights

### 7.3 How to Exercise Your Rights
- **In-app:** Use `/memories`, `/forget`, `/export` on Telegram, or the Settings page in the web app
- **By email:** Contact privacy@projectnobi.ai with subject "Privacy Rights Request"
- **Response time:** We will respond within 30 days (extendable by a further 60 days for complex requests with notice)
- **Verification:** We may ask you to verify your identity before processing requests

---

## 8. Data Retention

| Data Category | Retention Period |
|---|---|
| Active account data (conversations, memories) | Retained while your account is active |
| Inactive account data | Automatically deleted after **12 months of inactivity** |
| Deleted account data | Permanently deleted within **30 days** of account deletion request |
| Payment records | Retained for **7 years** for accounting and legal compliance |
| Safety and abuse logs | Retained for **12 months** for security purposes |
| Anonymous analytics | Retained for **12 months** then permanently deleted |
| Support tickets | Retained for **24 months** then anonymised |

When you request data deletion (e.g., via `/forget`), we initiate deletion immediately and complete purging from all systems within 30 days.

---

## 9. Children's Privacy

### 9.1 Age Requirements
- **United States:** Nori is not directed to children under 13. We do not knowingly collect personal information from children under 13 (COPPA compliance).
- **European Union / EEA:** We require users to be at least 16 years of age (GDPR Art. 8 compliance).
- **Other jurisdictions:** We comply with local digital consent age requirements.

### 9.2 Parental Controls
If you are a parent or guardian and believe your child has provided us with personal information without your consent:
1. Contact us immediately at privacy@projectnobi.ai
2. We will verify the report and delete the child's account and all associated data within 5 business days
3. We will notify you of the deletion

### 9.3 Age Verification
We use self-declaration for age verification. When accounts are found to belong to underage users, we terminate the account and delete all data.

---

## 10. Cookie Policy

### 10.1 What We Use
We use the following types of storage:

| Type | Purpose | Duration |
|---|---|---|
| **Essential cookies** | Authentication, session management | Session or up to 30 days |
| **Preference storage (localStorage)** | Theme preference, language, consent flags | Persistent until cleared |
| **Analytics cookies** | Anonymous usage analytics | Up to 12 months |

### 10.2 We Do NOT Use
- Advertising or tracking cookies
- Third-party cookies for profiling
- Fingerprinting or cross-site tracking

### 10.3 Managing Cookies
You can control cookies through your browser settings. Disabling essential cookies may affect your ability to use the service. Our web app respects the "Do Not Track" (DNT) browser signal.

---

## 11. International Data Transfers

Project Nobi is based in the United Kingdom. If you access the service from outside the UK, your data may be transferred to and processed in the UK.

For users in the European Economic Area (EEA):
- Transfers to the UK are covered by the UK Adequacy Decision adopted by the European Commission
- Any transfers to third countries are protected by appropriate safeguards (Standard Contractual Clauses where applicable)

For data transferred to Bittensor network miners who may be located globally:
- All data transmitted is encrypted (AES-128)
- No personally identifiable information is included in transmissions

---

## 12. Data Breach Procedures

In the event of a personal data breach:

1. **Internal response** — We will contain and investigate the breach immediately
2. **Risk assessment** — We will assess the likelihood and severity of the risk to your rights and freedoms
3. **Regulatory notification** — If the breach is likely to result in a risk to your rights and freedoms, we will notify the relevant supervisory authority (ICO in the UK) within **72 hours** of becoming aware, as required by GDPR Art. 33
4. **User notification** — If the breach is likely to result in a **high risk** to your rights and freedoms, we will notify you directly without undue delay, describing: what happened, the likely consequences, and the measures taken to address it
5. **Remediation** — We will take all reasonable steps to mitigate any damage

To report a suspected data breach or security vulnerability, contact: security@projectnobi.ai

---

## 13. Data Protection Officer (DPO)

We have appointed a Data Protection Officer to oversee our GDPR compliance.

**DPO Contact:**  
Email: dpo@projectnobi.ai  
Subject line: "DPO Enquiry"

---

## 14. Changes to This Policy

We may update this Privacy Policy from time to time. When we make material changes:

- We will update the "Last Updated" date at the top of this policy
- We will notify you via email (if provided) or prominent notice in the app
- For significant changes affecting your rights, we will provide at least 14 days' notice
- Where legally required, we will seek your renewed consent

The most current version of this policy is always available at projectnobi.ai/privacy. We encourage you to review this policy periodically.

---

## 15. Contact Us

For any privacy-related questions, requests, or concerns:

**General Privacy Enquiries:**  
Email: privacy@projectnobi.ai

**Data Protection Officer:**  
Email: dpo@projectnobi.ai

**Security Issues:**  
Email: security@projectnobi.ai

**Supervisory Authority (UK):**  
Information Commissioner's Office  
Wycliffe House, Water Lane, Wilmslow, Cheshire SK9 5AF  
Tel: 0303 123 1113  
Web: ico.org.uk

---

*This Privacy Policy was last updated on March 20, 2026. It complies with GDPR Articles 13 and 14, UK GDPR, CCPA, and COPPA.*
