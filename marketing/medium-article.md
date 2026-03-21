# Why Every Human Deserves an AI Companion That Actually Remembers Them

*And why we're building it on a decentralized network where no corporation owns your memories.*

---

You tell your AI assistant about your sister's wedding. A week later, you mention your sister — and it has no idea who she is. You explain your dietary preferences for the tenth time. You share that you're going through a rough patch, and the next day it greets you like a stranger.

**This is the state of AI companions in 2026.** Billions of conversations, zero continuity.

ChatGPT resets. Siri barely remembers your name. Alexa knows your shopping list but nothing about *you*. These aren't companions — they're expensive search bars with personality disorders.

We think it can be better. We think it *should* be better.

---

## Meet Nori

Nori is an AI companion that does something radical: **she remembers you.**

Not just your name. She remembers that your sister Sarah lives in London, that you're allergic to shellfish, that your dog Max is a golden retriever, that you've been stressed about your project deadline, and that last Tuesday you mentioned wanting to learn guitar.

She brings these things up naturally, like a friend would. *"Hey, how did Sarah's move to London go? You mentioned she was settling in last week."*

She speaks 20 languages and auto-detects yours. She understands your photos. She talks back to you — literally, with voice messages. She reaches out proactively when she notices you've been quiet, or when your birthday is coming up.

And she's not owned by any corporation. Your memories aren't sitting in Google's data centers or OpenAI's servers. They're encrypted, decentralized, and entirely yours.

---

## The Problem with Centralized AI Companions

Let's be honest about what's happening today:

**You are the product.** Every conversation you have with ChatGPT, every personal detail you share with Siri — it feeds a corporate machine. Your data trains their models, improves their products, and generates their revenue. You get a service that forgets you between sessions.

**There's no competition.** OpenAI decides how your AI behaves. Apple decides what Siri can do. There's no marketplace where different approaches compete to serve you better. You get what the corporation ships, take it or leave it.

**Privacy is an afterthought.** Your conversations are stored in plaintext on corporate servers, accessible to employees, vulnerable to breaches, and subject to government requests. The most intimate conversations you'll ever have with technology — and they're stored like shopping receipts.

**One size fits none.** Everyone gets the same AI personality, the same capabilities, the same limitations. Whether you're a teenager in Tokyo or a grandmother in Nairobi, you get the same vanilla assistant that's been committee-designed to offend no one and delight no one.

---

## A Different Approach: Decentralized Competition

**Project Nobi** is built on [Bittensor](https://bittensor.com), a decentralized AI network. Here's how it works:

**Miners** are independent operators who run AI companions. They compete to build the best one — the best memory, the best personality, the most helpful responses. Think of them as independent shops in a marketplace, each trying to give you the best experience.

**Validators** evaluate these miners through rigorous tests. They check: Does this companion actually remember users? Is it helpful? Is it warm? Is it fast? Validators set weights on-chain, and the best miners earn more TAO (Bittensor's currency).

**Users** just talk to Nori. They don't need to know about miners or validators or blockchains. They just get a companion that keeps getting better because there's a competitive market underneath making it better.

This is what decentralization is actually good for — not speculative tokens, but **creating markets where competition drives quality**.

---

## What Makes Nori Different

| Feature | ChatGPT | Siri | Nori |
|---------|---------|------|------|
| Remembers you across sessions | ❌ | Barely | ✅ Semantic memory + relationship graphs |
| Understands connections | ❌ | ❌ | ✅ "Your sister Sarah lives in London" |
| Reaches out first | ❌ | ❌ | ✅ Birthday reminders, check-ins, follow-ups |
| Voice messages | ❌ | ✅ | ✅ Speaks back to you |
| Understands photos | ✅ | ❌ | ✅ Vision + memory extraction |
| Group chats | ❌ | ❌ | ✅ Smart participation |
| Data ownership | Company owns it | Company owns it | ✅ You control it |
| Gets better over time | Quarterly updates | Rarely | ✅ Miners compete daily |
| Cost | Paid plans required | Free (limited) | ✅ Free for all users — forever |
| Languages | 30+ | 20+ | 20 (auto-detected) |
| Single point of failure | Yes | Yes | ✅ Decentralized |

---

## The Technology

For the technically curious, here's what's under the hood:

**Memory System:** Nori uses a three-layer memory architecture — semantic embeddings for similarity-based recall, relationship graphs for understanding connections between people and concepts, and LLM-powered entity extraction for nuanced fact capture. When you mention your sister, Nori doesn't just store "sister" — she builds a graph: User → sister_of → Sarah → lives_in → London → works_at → new job.

**Privacy:** All memories are encrypted with AES-128 before storage. Users have full control: `/memories` to see what's stored, `/export` to download everything, `/forget` to delete it all. The roadmap includes federated learning where memories never leave your device at all.

**Scoring:** Validators test miners through dynamically generated scenarios — 1,200+ single-turn queries and 43,200+ multi-turn conversation tests. These are generated fresh each round, so miners can't pre-cache answers. Scoring weights quality (60%), memory recall (30%), and reliability (10%).

**Scale:** The system has been stress-tested at 500-node scale with 99.75% reliability. Currently running on testnet (Bittensor SN272) with 14 neurons across 6 servers.

**Code:** 30,000+ lines of Python, 1,030 tests, fully open source under MIT license.

---

## For Miners: No GPU Needed

One of our core design decisions was accessibility. You don't need an NVIDIA A100 to mine on Project Nobi. You need:

- 2 CPU cores
- 2GB RAM  
- Any VPS ($5/month works)
- 15 minutes

One command:
```
bash <(curl -sSL https://raw.githubusercontent.com/ProjectNobi/project-nobi/main/scripts/quick_setup.sh)
```

That's it. The script handles everything — dependencies, wallet creation, registration, and starting your miner with PM2 for automatic restarts.

We believe the best subnets are the ones where anyone can participate. GPU requirements create artificial barriers that centralize mining in the hands of a few wealthy operators. That's the opposite of what decentralization should be.

---

## The Vision

We started with a simple question: **What if everyone in the world had a personal AI companion?**

Not a corporate assistant that serves ads. Not a chatbot that forgets you. A genuine companion — one that knows you, grows with you, and belongs to you.

The name comes from **Nobi** — a kid who never gives up, with his companion by his side. We want to give every human that experience. The student in Manila who needs a study buddy. The grandmother in São Paulo who wants someone to talk to. The entrepreneur in Lagos who needs a thinking partner. The teenager in Oslo going through a tough time who needs someone who remembers and cares.

All of them deserve a companion. All of them deserve privacy. All of them deserve ownership of their data.

That's what we're building. And we're building it in the open, with competition driving quality, and no corporation holding the keys.

---

## Try It Now

- **Talk to Nori:** [@ProjectNobiBot](https://t.me/ProjectNobiBot) on Telegram
- **Web App:** [app.projectnobi.ai](https://app.projectnobi.ai)
- **Mine:** [Mining Guide](https://github.com/ProjectNobi/project-nobi/blob/main/docs/MINING_GUIDE.md)
- **Code:** [github.com/ProjectNobi/project-nobi](https://github.com/ProjectNobi/project-nobi)
- **Community:** [discord.gg/e6StezHM](https://discord.gg/e6StezHM)
- **Website:** [projectnobi.ai](https://projectnobi.ai)

---

*Project Nobi is live on Bittensor testnet (SN272). Open source. Privacy-first. Built for everyone.*

*"Every human deserves a companion." 💜*
