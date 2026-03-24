# Project Nobi — Subprocessor List

**Last updated:** 2026-03-20  
**Document owner:** DPO — dpo@projectnobi.ai

This document lists all third-party service providers ("subprocessors") that may process personal data on behalf of Project Nobi when you use the Nori service.

---

## What is a Subprocessor?

A subprocessor is a third-party company that Project Nobi engages to process personal data as part of delivering the Nori service. This includes companies that handle your conversation text, messages, payments, or voice data.

---

## Current Subprocessors

### 1. Chutes.ai
| Field | Details |
|-------|---------|
| **Company** | Chutes AI, Inc. |
| **Purpose** | Primary LLM inference — processes conversation text to generate Nori's responses |
| **Data Processed** | Conversation messages, system prompts |
| **Data Location** | United States |
| **DPA Status** | Data Processing Agreement in place |
| **Privacy Policy** | https://chutes.ai/privacy |

### 2. OpenRouter
| Field | Details |
|-------|---------|
| **Company** | OpenRouter, Inc. |
| **Purpose** | Backup LLM inference — used as a fallback when primary LLM is unavailable |
| **Data Processed** | Conversation messages, system prompts |
| **Data Location** | United States |
| **DPA Status** | Data Processing Agreement in place |
| **Privacy Policy** | https://openrouter.ai/privacy |

### 3. Telegram Bot API
| Field | Details |
|-------|---------|
| **Company** | Telegram FZ-LLC |
| **Purpose** | Message delivery — routes messages between users and the Nori Telegram bot |
| **Data Processed** | Message content, Telegram user IDs, timestamps |
| **Data Location** | Netherlands / United Arab Emirates |
| **DPA Status** | Covered by Telegram's standard terms |
| **Privacy Policy** | https://telegram.org/privacy |

### 4. Stripe
| Field | Details |
|-------|---------|
| **Company** | Stripe, Inc. |
| **Purpose** | Payment processing — handles subscription billing and payment data |
| **Data Processed** | Payment card details, billing address, transaction history (processed directly by Stripe — Project Nobi does NOT store card data) |
| **Data Location** | United States (with EU data transfer mechanisms) |
| **DPA Status** | Stripe Data Processing Agreement available at stripe.com/legal/dpa |
| **Privacy Policy** | https://stripe.com/privacy |

### 5. Google Text-to-Speech (gTTS)
| Field | Details |
|-------|---------|
| **Company** | Google LLC |
| **Purpose** | Text-to-speech synthesis — converts Nori's text responses to audio for voice replies |
| **Data Processed** | Nori's response text (not user messages) |
| **Data Location** | United States (Google Cloud infrastructure) |
| **DPA Status** | Covered by Google Cloud DPA |
| **Privacy Policy** | https://policies.google.com/privacy |

### 6. ElevenLabs (TTS — when configured)
| Field | Details |
|-------|---------|
| **Company** | ElevenLabs, Inc. |
| **Purpose** | Text-to-speech synthesis — voice replies for all users (no premium tiers) |
| **Data Processed** | Nori's response text |
| **Data Location** | United States |
| **DPA Status** | Data Processing Agreement available upon request |
| **Privacy Policy** | https://elevenlabs.io/privacy |
| **Status** | Optional — only active when `ELEVENLABS_API_KEY` is configured |

---

## Subprocessors Not Currently Active

The following may be used in future versions:

- **Twilio** — SMS/voice delivery (planned)
- **Sendgrid / Mailgun** — Transactional email (planned)

---

## Changes to This List

Project Nobi will update this list before engaging any new subprocessors. Users who have subscribed to our DPA notification list (dpo@projectnobi.ai) will be notified at least 10 days in advance of any new subprocessor additions.

---

## Questions

For questions about our subprocessors or data processing:
- **DPO:** dpo@projectnobi.ai
- **Privacy:** privacy@projectnobi.ai
