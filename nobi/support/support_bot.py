"""
Project Nobi — SupportHandler
================================
FAQ matching + smart routing for Nori support conversations.

When someone asks a question:
  1. Try to match a FAQ entry (fuzzy matching)
  2. If matched → return instant answer
  3. If not matched → save as feedback ticket, return acknowledgment
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from .feedback import FeedbackManager, FeedbackCategory

logger = logging.getLogger(__name__)

# ─── FAQ Database ────────────────────────────────────────────

FAQ_ENTRIES: List[Dict[str, Any]] = [
    {
        "id": "what_is_nobi",
        "topic": "What is Project Nobi?",
        "keywords": ["what is nobi", "what is project nobi", "what is nori", "about nobi", "about nori", "explain nobi"],
        "answer": (
            "Project Nobi is a decentralized AI companion network built on Bittensor! 🤖\n\n"
            "Nori (that's me!) is your personal AI companion who actually *remembers* you — "
            "your conversations, preferences, relationships, and life events. Unlike other AIs, "
            "your memories are AES-128 encrypted at rest. I'm powered by the "
            "Bittensor network, meaning real miners compete to give you the best AI responses. "
            "No Big Tech, no data harvesting — just a companion that genuinely knows you. 💙"
        ),
    },
    {
        "id": "how_memory_works",
        "topic": "How does Nori's memory work?",
        "keywords": ["memory", "remember", "how does memory", "memories", "forget", "learning", "remembers"],
        "answer": (
            "Nori's memory is like a semantic journal — I extract important facts from your "
            "conversations and store them in a searchable graph. 🧠\n\n"
            "When you chat with me, I automatically pick up on things like your name, your "
            "relationships, your hobbies, and how you're feeling. Before each reply, I search "
            "my memories for relevant context to make the conversation feel personal.\n\n"
            "Your memories are stored encrypted at rest. You can view, edit, or delete "
            "any memory at any time via /memories (Telegram) or the Memories page in the web app."
        ),
    },
    {
        "id": "privacy",
        "topic": "Is my data private?",
        "keywords": ["private", "privacy", "data", "secure", "security", "encrypted", "safe", "gdpr", "delete data"],
        "answer": (
            "Yes — privacy is a core priority. 🔒\n\n"
            "• All memories are AES-128 encrypted at rest (Fernet, PBKDF2 per-user keys)\n"
            "• This is server-side encryption — it protects stored data\n"
            "• Miners process conversation content to generate responses\n"
            "• We don't sell, share, or analyze your conversations\n"
            "• You can export or delete ALL your data at any time\n"
            "• Open source: anyone can audit the encryption code on GitHub\n\n"
            "End-to-end TEE encryption is code-complete and deploying to production. "
            "Browser-side memory extraction is code-complete and available in the web app."
        ),
    },
    {
        "id": "how_to_mine",
        "topic": "How do I mine on the Nobi subnet?",
        "keywords": ["mine", "mining", "miner", "subnet", "bittensor", "how to mine", "start mining", "register miner"],
        "answer": (
            "Running a miner on the Nobi subnet earns you TAO rewards for serving AI "
            "responses! ⛏️\n\n"
            "Quick start:\n"
            "1. Install Bittensor: `pip install bittensor`\n"
            "2. Create a wallet: `btcli wallet new_coldkey`\n"
            "3. Register on the subnet: `btcli subnet register --netuid <nobi_netuid>`\n"
            "4. Clone the repo and install: `pip install -e .`\n"
            "5. Start your miner: `python neurons/miner.py`\n\n"
            "Check our ROADMAP.md and the README for detailed setup instructions. "
            "Join our Telegram for miner support!"
        ),
    },
    {
        "id": "hardware_requirements",
        "topic": "What hardware do I need to mine?",
        "keywords": ["hardware", "gpu", "cpu", "ram", "specs", "requirements", "server", "compute", "min_compute"],
        "answer": (
            "Minimum hardware for mining on Nobi: 💻\n\n"
            "• CPU: 8+ cores recommended\n"
            "• RAM: 16 GB minimum, 32 GB recommended\n"
            "• GPU: Optional for basic mining; GPU (A100/H100 class) needed for top-tier inference\n"
            "• Storage: 50+ GB SSD\n"
            "• Network: Stable internet, low latency preferred\n\n"
            "Check `min_compute.yml` in the repo for the exact current requirements. "
            "Validators score miners on response speed AND quality, so better hardware = more TAO."
        ),
    },
    {
        "id": "how_to_validate",
        "topic": "How do I run a validator?",
        "keywords": ["validator", "validate", "validation", "how to validate", "run validator", "stake"],
        "answer": (
            "Validators on Nobi score miners and distribute rewards! 🏆\n\n"
            "Requirements:\n"
            "• Hold a minimum stake of TAO (check current minimum on the subnet)\n"
            "• Reliable server (24/7 uptime)\n"
            "• Register as a validator: `btcli subnet register --netuid <nobi_netuid>`\n\n"
            "Start validating:\n"
            "```\npython neurons/validator.py --wallet.name <your_wallet>\n```\n\n"
            "Validators send test prompts to miners, grade their responses for quality/speed, "
            "and emit rewards proportional to performance. See the repo for full details."
        ),
    },
    {
        "id": "pricing",
        "topic": "How much does Nori cost?",
        "keywords": ["price", "pricing", "cost", "free", "subscription", "plan", "tier", "pay", "billing", "premium"],
        "answer": (
            "Nori is free for all users! 🎉\n\n"
            "The service is funded by Bittensor network emissions and community support — "
            "no subscriptions required. Every feature, every memory, every conversation is "
            "available to everyone.\n\n"
            "Want to support the project? Run a miner or validator, or stake TAO on our subnet!"
        ),
    },
    {
        "id": "voice_features",
        "topic": "Does Nori support voice?",
        "keywords": ["voice", "speech", "talk", "tts", "audio", "speak", "listen", "stt", "voice message"],
        "answer": (
            "Yes! Nori supports voice in the Telegram bot 🎙️\n\n"
            "• Send voice messages and Nori will transcribe + respond\n"
            "• Voice responses via text-to-speech (TTS) — Nori can talk back!\n"
            "• Powered by Whisper (STT) and ElevenLabs/OpenAI TTS\n\n"
            "In the Telegram bot, just send a voice note — Nori handles the rest automatically. "
            "Voice features are available to all users — free!"
        ),
    },
    {
        "id": "language_support",
        "topic": "What languages does Nori support?",
        "keywords": ["language", "languages", "multilingual", "english", "spanish", "french", "translate", "i18n", "locale"],
        "answer": (
            "Nori speaks 20+ languages! 🌍\n\n"
            "Nori auto-detects the language you're writing in and responds in the same language. "
            "No setup needed — just chat in your preferred language.\n\n"
            "Supported languages include: English, Spanish, French, German, Portuguese, Italian, "
            "Dutch, Japanese, Korean, Chinese (Simplified & Traditional), Arabic, Hindi, Russian, "
            "Turkish, Polish, Vietnamese, Thai, Indonesian, and more.\n\n"
            "Memory extraction and personality also adapt per language."
        ),
    },
    {
        "id": "group_chat",
        "topic": "Can I use Nori in group chats?",
        "keywords": ["group", "group chat", "telegram group", "channel", "team", "shared", "multiple users"],
        "answer": (
            "Yes! Nori works great in Telegram group chats 👥\n\n"
            "• Add Nori to any Telegram group\n"
            "• Nori responds when @mentioned or when messages are directed to her\n"
            "• Group memory is separate from personal memory\n"
            "• Each user maintains their own private memory profile\n"
            "• Nori moderates the vibe — she's a great group companion!\n\n"
            "Group features are available to all users — free! Add her with: @ProjectNobiBot"
        ),
    },
    {
        "id": "delete_memories",
        "topic": "How do I delete my memories?",
        "keywords": ["delete memory", "forget", "erase", "remove memory", "clear memories", "wipe", "forget me"],
        "answer": (
            "You have full control over your memories! 🗑️\n\n"
            "Telegram:\n"
            "• Delete a specific memory: use the Memories menu\n"
            "• Delete ALL memories: send /forgetme\n\n"
            "Web App:\n"
            "• Go to the Memories page\n"
            "• Click the trash icon on any memory to delete it\n"
            "• Use 'Forget Everything' in Settings to wipe all data\n\n"
            "Deletion is permanent and immediate. We do not retain copies."
        ),
    },
    {
        "id": "self_host",
        "topic": "Can I self-host Nori?",
        "keywords": ["self host", "self-host", "host myself", "own server", "local", "docker", "deploy", "installation"],
        "answer": (
            "Absolutely — self-hosting is encouraged! 🏠\n\n"
            "Nobi is fully open-source. You can run the entire stack on your own server:\n"
            "1. Clone the repo: `git clone https://github.com/ProjectNobi/project-nobi`\n"
            "2. Install deps: `pip install -e .`\n"
            "3. Set your API keys in `.env`\n"
            "4. Run the bot: `python app/bot.py`\n"
            "5. Run the API: `python api/server.py`\n\n"
            "Full Docker support coming soon. Check the README for the latest setup guide."
        ),
    },
    {
        "id": "api_access",
        "topic": "Is there an API?",
        "keywords": ["api", "api key", "developer", "integration", "programmatic", "webhook", "rest api"],
        "answer": (
            "Yes! Nobi has a REST API for developers 🔧\n\n"
            "• Base URL: `https://api.projectnobi.ai`\n"
            "• Authentication: API keys (generate in Settings → API Keys)\n"
            "• Endpoints: /api/chat, /api/memories, /api/settings, /api/feedback\n\n"
            "API access is available on Pro and Enterprise plans. "
            "See the API docs at https://github.com/ProjectNobi/project-nobi/blob/main/docs/API_REFERENCE.md for full reference."
        ),
    },
    {
        "id": "telegram_bot",
        "topic": "How do I start with the Telegram bot?",
        "keywords": ["telegram", "bot", "start", "how to use", "getting started", "setup bot", "first time"],
        "answer": (
            "Getting started with Nori on Telegram is super easy! 📱\n\n"
            "1. Open Telegram and search for @ProjectNobiBot\n"
            "2. Hit /start\n"
            "3. That's it — just start chatting!\n\n"
            "Nori will introduce herself and start building your memory profile automatically. "
            "No configuration needed. She remembers everything from your first message."
        ),
    },
    {
        "id": "bittensor_what",
        "topic": "What is Bittensor and why does Nobi use it?",
        "keywords": ["bittensor", "tao", "decentralized", "blockchain", "subnet", "why bittensor", "what is bittensor"],
        "answer": (
            "Bittensor is a decentralized AI network where miners compete to provide the best "
            "AI services and earn TAO (the native token) as rewards. 🌐\n\n"
            "Nobi runs as a subnet on Bittensor, meaning:\n"
            "• Real people run miners providing AI compute\n"
            "• No single company controls the AI\n"
            "• Better miners earn more TAO\n"
            "• You benefit from genuine competition driving quality up\n\n"
            "It's the antithesis of Big Tech AI — open, incentivized, and permissionless."
        ),
    },
    {
        "id": "relationship_graph",
        "topic": "What is the relationship graph?",
        "keywords": ["relationship", "graph", "people", "contacts", "network", "who do i know", "connections"],
        "answer": (
            "Nori builds a relationship graph of the people in your life! 👥\n\n"
            "When you mention someone — 'my friend Sarah', 'my boss Tom', 'my mom' — Nori "
            "remembers them and the context you've shared. Over time, she builds a mental map "
            "of your relationships.\n\n"
            "This helps Nori give better advice, remember who you're talking about, and provide "
            "context-aware support. You can view your relationship graph in the web app's "
            "Memory section."
        ),
    },
    {
        "id": "proactive_messages",
        "topic": "Why is Nori messaging me first?",
        "keywords": ["proactive", "message me", "notification", "check in", "reaching out", "unprompted", "why did nori"],
        "answer": (
            "That's Nori's proactive mode — she actually checks in on you! 💙\n\n"
            "Based on patterns in your conversations (like a difficult week, an upcoming event, "
            "or something you mentioned wanting to follow up on), Nori will proactively reach out.\n\n"
            "You can control this in /settings:\n"
            "• Turn proactive messages on/off\n"
            "• Set quiet hours\n"
            "• Choose how often she checks in\n\n"
            "She's not a bot spamming you — she's checking in like a real friend would."
        ),
    },
    {
        "id": "export_data",
        "topic": "How do I export my data?",
        "keywords": ["export", "download", "backup", "portability", "my data", "gdpr export", "save data"],
        "answer": (
            "You can export all your data at any time! 📦\n\n"
            "Telegram: Use /export to get a JSON file of all your memories.\n\n"
            "Web App:\n"
            "• Go to Settings → Privacy\n"
            "• Click 'Export My Data'\n"
            "• Downloads a full JSON backup of your memories and settings\n\n"
            "Your export includes all memories, relationship graph, and settings. "
            "Format: JSON (easily readable by other tools)."
        ),
    },
    {
        "id": "open_source",
        "topic": "Is Nobi open source?",
        "keywords": ["open source", "github", "code", "license", "mit", "repository", "source code", "contribute"],
        "answer": (
            "Yes — Nobi is fully open source! 🔓\n\n"
            "• GitHub: https://github.com/ProjectNobi/project-nobi\n"
            "• License: MIT\n"
            "• Contributions welcome — PRs, issues, and ideas!\n\n"
            "We believe AI companions should be transparent and community-driven. "
            "You can inspect every line of code, run it yourself, or contribute new features."
        ),
    },
    {
        "id": "subscription_upgrade",
        "topic": "Is there a paid plan?",
        "keywords": ["upgrade", "subscribe", "subscription", "pro plan", "pay", "stripe", "billing page", "premium"],
        "answer": (
            "Nori is free for all users — no subscriptions needed! 🎉\n\n"
            "All features are available to everyone:\n"
            "• Full chat with memory\n"
            "• Voice features\n"
            "• Memory graph\n"
            "• Group chat support\n\n"
            "The service is funded by Bittensor network emissions and community support. "
            "Want to help? Run a miner, run a validator, or stake TAO on our subnet!"
        ),
    },
    {
        "id": "multiple_devices",
        "topic": "Can I use Nori on multiple devices?",
        "keywords": ["multiple devices", "sync", "device", "mobile", "desktop", "web", "cross-platform", "phone"],
        "answer": (
            "Yes! Nori syncs across all your devices automatically. 📱💻\n\n"
            "• Telegram: Works on any device with your Telegram account\n"
            "• Web App: Access at https://app.projectnobi.ai from any browser\n"
            "• Mobile: Telegram app works on iOS and Android\n\n"
            "Your memory profile is tied to your user ID, so conversations from any platform "
            "are all part of the same memory graph. Nori always remembers, regardless of "
            "where you're chatting from."
        ),
    },
    {
        "id": "response_time",
        "topic": "Why is Nori slow to respond sometimes?",
        "keywords": ["slow", "response time", "latency", "delay", "taking long", "timeout", "fast"],
        "answer": (
            "Response speed depends on a few factors: ⚡\n\n"
            "• Subnet routing: When routed through Bittensor miners, speed varies by miner performance\n"
            "• Memory search: Complex memory retrieval takes a moment\n"
            "• Model size: Larger models = better quality but slower response\n"
            "• Server load: During peak times, inference can be slower\n\n"
            "We're constantly optimizing. Pro users get priority routing to the fastest miners. "
            "If you experience persistent slowness, please use /feedback to report it!"
        ),
    },
    {
        "id": "contact_human",
        "topic": "How do I talk to a human support agent?",
        "keywords": ["human", "real person", "agent", "support team", "contact support", "speak to someone", "email"],
        "answer": (
            "I can handle most questions, but sometimes you need a real human! 🧑‍💼\n\n"
            "• Telegram: Use /feedback and choose 'complaint' — our team monitors all tickets\n"
            "• Discord: Join our community at discord.gg/e6StezHM\n"
            "• Community: Join our Telegram community group\n"
            "• GitHub Issues: For technical bugs\n\n"
            "We typically respond within 24-48 hours. For urgent issues, "
            "mark your ticket as high priority in the feedback form."
        ),
    },
    {
        "id": "safety_crisis",
        "topic": "How does Nori handle safety and crisis situations?",
        "keywords": ["safety", "crisis", "self-harm", "suicide", "dangerous", "harmful", "block"],
        "answer": (
            "Safety is built into every layer 🛡️\n\n"
            "• Content Filter: Every message is checked before AND after the AI responds. "
            "Harmful content (self-harm, violence, illegal activity) is blocked entirely — never shown to you.\n"
            "• Crisis Response: If you express distress, Nori provides crisis resources immediately "
            "(Samaritans 116 123, Crisis Text Line, local emergency services).\n"
            "• Miner Accountability: Miners that serve harmful content receive zero emission — "
            "safety is a scoring dimension, not optional.\n\n"
            "Important: Nori is an AI companion, not a therapist. For serious concerns, "
            "please contact a professional or crisis service."
        ),
    },
    {
        "id": "addiction_overuse",
        "topic": "What protections exist against overuse or addiction?",
        "keywords": ["addiction", "overuse", "dependency", "too much", "attached", "obsessed", "healthy"],
        "answer": (
            "We take this seriously. Multiple protections are in place:\n\n"
            "• Dependency Monitor: Tracks conversation patterns over time — frequency, "
            "unusual hours, emotional escalation, isolation signals.\n"
            "• Graduated Interventions: Gentle nudges → direct reminders → strong recommendations → "
            "temporary cooldown (24h) for severe cases.\n"
            "• AI Reminders: Every 50 interactions, Nori reminds you it's an AI and encourages "
            "real-world connections.\n"
            "• Rate Limits: Daily message limits prevent excessive use.\n"
            "• Emotional Disclaimers: On heavy topics, Nori suggests professional help.\n\n"
            "Real human connections are irreplaceable. Nori is here to complement them, not replace them."
        ),
    },
    {
        "id": "minors_age",
        "topic": "Is Nori safe for minors? How is the 18+ rule enforced?",
        "keywords": ["minor", "age", "18", "child", "teenager", "young", "kids", "underage"],
        "answer": (
            "Nori is for adults aged 18 and over only. Multiple enforcement layers:\n\n"
            "• Mandatory Age Gate: The first thing on signup — you cannot chat without confirming 18+.\n"
            "• Birth Year Verification: We verify age via birth year (the year is not stored, only verification status).\n"
            "• Behavioural Detection: 15 patterns detect potential minors (school mentions, "
            "'my parents' language). If 2+ signals detected, age re-confirmation is required.\n"
            "• Permanent Block: Under-18 users are permanently blocked.\n"
            "• 30-Day Re-verification: Age requirement re-confirmed periodically.\n"
            "• Adult Branding: All marketing, tone, and UX designed for adults.\n\n"
            "No system is perfect, but we do everything technically feasible to protect minors."
        ),
    },
    {
        "id": "miners_read_data",
        "topic": "Can miners read my conversations?",
        "keywords": ["miner", "read", "see", "plaintext", "data", "conversations", "privacy"],
        "answer": (
            "Honest answer: currently, yes — during processing.\n\n"
            "Storage: Your memories are encrypted at rest (AES-128, server-side). "
            "This protects stored data.\n\n"
            "During response generation: Miners process your conversation content "
            "to generate responses. This is the current reality.\n\n"
            "What we've built (code-complete, deploying):\n"
            "• TEE Encryption: Miners can only decrypt inside secure enclaves — "
            "even the operator can't read your data. 72 tests passing.\n"
            "• Browser Extraction: Raw text never leaves your browser — "
            "only encrypted embeddings sent to server. Available in web app.\n\n"
            "We won't claim 'end-to-end encrypted' until it's live for all users."
        ),
    },
    {
        "id": "harmful_miner",
        "topic": "What happens if a miner serves harmful content?",
        "keywords": ["harmful", "miner", "bad response", "inappropriate", "blocked", "penalise"],
        "answer": (
            "It gets blocked before reaching you, and the miner gets penalised.\n\n"
            "Our ContentFilter checks every response before delivery. Harmful content is "
            "replaced entirely — the original is never shown.\n\n"
            "On the incentive side: validators run adversarial safety probes as ~10% of scoring queries. "
            "Miners that fail receive a safety score of zero, applied as a multiplier to total reward. "
            "Zero safety = zero emission, regardless of response quality.\n\n"
            "Miners have a direct economic incentive to handle sensitive topics responsibly."
        ),
    },
    {
        "id": "legal_structure",
        "topic": "What is your legal structure? Do you have legal counsel?",
        "keywords": ["legal", "lawyer", "counsel", "entity", "company", "CIC", "liability", "structure", "registered"],
        "answer": (
            "We're currently operating as individuals building on testnet. "
            "No entity is registered yet, and we don't have dedicated legal counsel "
            "for AI product liability. We're transparent about this.\n\n"
            "We're evaluating entity registration in either England & Wales "
            "(Community Interest Company) or the Republic of Ireland "
            "(Company Limited by Guarantee) — both have advantages for a "
            "community-funded AI project handling personal data. Ireland offers "
            "EU GDPR/AI Act compliance; the UK offers established CIC structures.\n\n"
            "Final decision will be made with legal counsel before mainnet. "
            "Our commitment: the entity will be non-profit, community-governed, "
            "with no equity, no investors, and 100% of owner emissions burned on-chain."
        ),
    },
    {
        "id": "why_not_ads",
        "topic": "Why not just add ads, affiliate links, or monetize user data?",
        "keywords": ["ads", "advertising", "affiliate", "monetize", "data harvesting", "betterhelp", "revenue model", "sell data"],
        "answer": (
            "Because we'd lose the one thing that makes Nobi different: "
            "'your AI companion that no company can monetize or exploit.'\n\n"
            "That's not idealism — it's strategy. The AI companion market is dominated "
            "by companies that monetize users. Our competitive advantage is that we don't.\n\n"
            "The butterfly effect:\n"
            "→ Person discovers Nori — just wants an AI friend\n"
            "→ Nori works great — they tell friends\n"
            "→ Curious user asks 'what powers this?' — discovers Bittensor\n"
            "→ Some buy TAO, some become miners — network grows\n"
            "→ Media covers 'the free AI no company owns' — cycle accelerates\n\n"
            "One product. Millions of entry points to Bittensor. "
            "That's what stakers are betting on — adoption, not revenue.\n\n"
            "Wikipedia: 1.7B monthly visitors, ~$170M/year donations, 23 years, zero ads.\n"
            "Signal: 100M+ users, foundation-funded.\n"
            "Linux: 90%+ of cloud infrastructure, community-funded.\n\n"
            "These aren't charities — they're some of the most valuable projects in the world."
        ),
    },
    {
        "id": "legal_data_decentralized",
        "topic": "If it's decentralized, how do you handle legal data requests?",
        "keywords": ["legal", "decentralized", "data request", "court", "dispute", "subpoena", "GDPR request", "compliance", "controller"],
        "answer": (
            "The AI layer (miners generating responses) is decentralized. "
            "The legal/compliance layer is centralized — and always will be.\n\n"
            "Your consent records, age verification, ToS acceptance, and audit trail "
            "are stored on OUR infrastructure — not on miners. This data never touches "
            "the Bittensor subnet.\n\n"
            "This means:\n"
            "• Legal requests: we can always pull your records, regardless of network size\n"
            "• GDPR requests: handled directly by us — no miner cooperation needed\n"
            "• Audit trail: every consent change logged with timestamps, append-only\n"
            "• Dispute resolution: complete consent history via our legal API\n\n"
            "GDPR requires a data controller. That's us. Decentralization is for AI quality. "
            "Legal accountability is ours. We commit to always operating the bot/app layer "
            "and at least one validator."
        ),
    },
    {
        "id": "alpha_value",
        "topic": "No revenue means no value. Why would anyone stake on Nobi?",
        "keywords": ["revenue", "stake", "alpha", "value", "monetize", "money", "profit", "survive", "sustainable", "economics"],
        "answer": (
            "'No monetization' means no monetization FROM USERS. "
            "The subnet has real economic activity — it's the usage itself.\n\n"
            "The ALPHA demand loop:\n"
            "Millions of users chatting → millions of queries → miners needed → "
            "miners register and earn TAO for quality responses. More users = more miners needed = healthier network.\n\n"
            "The burn effect:\n"
            "We receive 18% owner emissions (mandatory). We burn 100% via burn_alpha(). "
            "Every burn reduces ALPHA supply. More users = more burns = less supply = "
            "deflationary pressure for all ALPHA holders.\n\n"
            "Miner profitability:\n"
            "Miners earn TAO for serving quality responses. Profitable mining attracts "
            "more miners joining = better quality = more reasons to stake on the subnet.\n\n"
            "If nobody stakes? Emissions stay low, miners leave, quality drops. "
            "That's the same risk every subnet faces. We're betting that millions "
            "of daily users create enough demand to sustain itself.\n\n"
            "Disclaimer: Not financial advice. Staking involves risk."
        ),
    },
    {
        "id": "every_subnet_has_revenue",
        "topic": "Every other subnet has a revenue source. Why doesn't Nobi?",
        "keywords": ["revenue source", "every subnet", "other subnets", "no revenue", "conviction", "research subnet", "benchmarking", "investors believe"],
        "answer": (
            "Not true. There are research subnets on Bittensor mainnet with zero users "
            "and zero revenue path. Benchmarking subnets. Academic subnets. They earn "
            "emissions because stakers believe in the research. Nobody asks them "
            "'where's your revenue?' or demands 10K DAU in 3 months. They're funded "
            "on conviction. That's how Bittensor is designed — for every subnet, not just Nobi.\n\n"
            "The difference: we're the only one that can point to a working product "
            "on Telegram, Discord, and web, with 1,661 passing tests and MIT-licensed "
            "code anyone can audit.\n\n"
            "If conviction-funded subnets with zero users can attract stake, a subnet "
            "with real users and a real product has a stronger case — not a weaker one.\n\n"
            "Every staker on every subnet is staking with the belief that the subnet "
            "will create value. That's not hope — that's how dTAO works."
        ),
    },
    {
        "id": "alpha_traders_hurt",
        "topic": "How do you deal with alpha traders? Won't they hurt the subnet?",
        "keywords": ["alpha trader", "trader", "dump", "sell pressure", "short term", "hurt", "speculator"],
        "answer": (
            "Alpha traders exist on every subnet — that's a Bittensor-wide reality, "
            "not a Nobi-specific problem. We can't control what traders do with the "
            "alpha token, and we don't try to.\n\n"
            "What we can control: building a product good enough that long-term stakers "
            "outweigh short-term traders.\n\n"
            "And the burn helps — every owner emission we burn via burn_alpha() reduces "
            "alpha supply permanently. More usage → more emissions → more burns → less supply. "
            "That's structural deflationary pressure that works in favour of holders, not traders.\n\n"
            "Traders come and go. Builders stay."
        ),
    },
    {
        "id": "mass_adoption_contradiction",
        "topic": "Isn't 'mass adoption' and 'users won't know about Bittensor' a contradiction?",
        "keywords": ["mass adoption", "contradiction", "users won't know", "bittensor invisible", "don't know bittensor", "don't care about bittensor", "front door"],
        "answer": (
            "Do you know what database Instagram uses? What protocol your bank runs on? "
            "What kernel your phone runs? No — but you use them every day.\n\n"
            "That's literally what mass adoption means: people use something without "
            "knowing or caring what's under the hood.\n\n"
            "If users need to understand Bittensor to use the product, it's not mass "
            "adoption — it's a developer tool.\n\n"
            "We're building the product normal people actually use. "
            "Bittensor is the engine, not the steering wheel.\n\n"
            "The butterfly effect: person discovers Nori → loves it → tells friends → "
            "curious user asks 'what powers this?' → discovers Bittensor → some buy TAO, "
            "some become miners → network grows. That's how mass adoption works. "
            "Not by explaining consensus mechanisms to grandma."
        ),
    },
    {
        "id": "tao_emissions_subsidy",
        "topic": "Aren't TAO emissions just a permanent subsidy? Who pays for it?",
        "keywords": ["emissions", "subsidy", "dilution", "inflation", "who pays", "TAO", "block reward", "bitcoin", "cost", "forever funding", "community pays"],
        "answer": (
            "This gets to the heart of why Bittensor exists.\n\n"
            "Bitcoin miners earn block rewards — funded by inflation that dilutes "
            "every holder. Nobody calls that a 'subsidy.' It's the network paying "
            "for security. Holders accept dilution because mining makes Bitcoin "
            "more valuable than the dilution costs. That's the social contract.\n\n"
            "Bittensor is the same contract, applied to AI.\n\n"
            "Bitcoin: emissions fund miners who secure the network.\n"
            "Bittensor: emissions fund miners who provide useful AI services.\n\n"
            "Every subnet receives TAO because the community stakes on them, not "
            "because they charge end users. That's how the network is designed. "
            "The mechanism IS the model.\n\n"
            "So the real question isn't 'who pays for emissions?' — it's "
            "'Is Nobi a good use of emissions compared to other subnets?'\n\n"
            "We believe bringing millions of everyday users into Bittensor — people "
            "who've never heard of TAO — makes the network more valuable than another "
            "infrastructure subnet that only serves developers. That's our thesis. "
            "The community decides via staking whether they agree."
        ),
    },
    {
        "id": "why_not_charge_like_chutes",
        "topic": "Other subnets like Chutes charge users. Why doesn't Nobi?",
        "keywords": ["chutes", "charge", "revenue", "B2B", "inference", "pay", "cost of production", "why free", "make money"],
        "answer": (
            "Different markets, different models.\n\n"
            "Chutes provides inference-as-a-service to developers and businesses "
            "who pay for API access. That's a B2B revenue model serving technical users.\n\n"
            "Nobi serves everyday consumers who chat with an AI companion. "
            "Our target users are regular people — many in developing countries — "
            "who want a private AI friend. Adding a paywall kills adoption in "
            "exactly the demographics we're building for.\n\n"
            "That said, Chutes and Nobi are complementary, not competing. "
            "A consumer-facing subnet that drives millions of inference requests "
            "and an infrastructure subnet that serves them? That's a self-evolving "
            "ecosystem. We see collaboration potential there, not conflict.\n\n"
            "Closer comparisons for our model: Wikipedia (1.7B monthly visitors, "
            "free, donation-funded), Signal (100M+ users, free, foundation-funded). "
            "Consumer products serving a public good can sustain without charging "
            "users — if the mission resonates enough to attract support.\n\n"
            "The key insight: miners pay their own server costs. We don't pay "
            "miners — Bittensor does. There's no production cost to pass on to users."
        ),
    },
    {
        "id": "staker_mev_risk",
        "topic": "Won't users who stake get dumped on by degens and leave?",
        "keywords": ["mev", "dump", "dumped", "degen", "leave", "delete", "bitter", "rug", "front-run"],
        "answer": (
            "This is a fair concern — a user loves Nori, wants to support the project, "
            "buys alpha, gets dumped on, and leaves bitter. It's happened across crypto.\n\n"
            "But here's the key: staking is never required or even encouraged for normal users. "
            "Nobi is free. The product works without any token interaction at all.\n\n"
            "Supporting Nobi doesn't mean buying alpha — it means using Nori, giving feedback, "
            "spreading the word, or donating via fiat when that's available.\n\n"
            "The staking layer is for people who understand Bittensor tokenomics and want "
            "exposure to subnet alpha. That's a different audience from the everyday user "
            "chatting with their AI companion. We deliberately keep those worlds separate — "
            "Nori never pushes users toward tokens, never gamifies staking, never creates "
            "a funnel where someone buys alpha because the app told them to.\n\n"
            "If someone who understands crypto chooses to stake, that's their informed decision. "
            "But the millions of normal users we're building for? They'll never need to touch a token."
        ),
    },
    {
        "id": "why_users_matter",
        "topic": "If subnets get stake without users, why does having users matter?",
        "keywords": ["users matter", "stake without users", "speculation", "no users", "why users", "fundamentals", "timeline", "durable"],
        "answer": (
            "Right now, subnets get stake on speculation alone — people bet on potential. "
            "That's early-stage Bittensor. But that won't last forever.\n\n"
            "As the network matures, stakers will increasingly ask: 'Does this subnet actually "
            "DO something? Does anyone use it?'\n\n"
            "When that shift happens — and it will — subnets with zero users and no revenue "
            "path lose their stake. Subnets with millions of active users don't.\n\n"
            "Today: speculation drives stake. Nobi can compete on that like anyone else.\n"
            "Tomorrow: fundamentals drive stake. Nobi is built for that world.\n\n"
            "We're not saying users = stake today. We're saying users = durable stake "
            "when the music stops for empty subnets."
        ),
    },
    {
        "id": "support_without_tokens",
        "topic": "Can I support Nobi without buying tokens?",
        "keywords": ["support without", "no tokens", "non-crypto", "help without", "fiat", "donate", "contribute", "support nobi"],
        "answer": (
            "Absolutely! You don't need to touch crypto to support Nobi:\n\n"
            "• Use Nori — every conversation proves the product works and generates "
            "real usage data that attracts stakers\n"
            "• Tell friends — word of mouth is the most powerful growth engine\n"
            "• Give feedback — report bugs, suggest features, help us improve via /feedback\n"
            "• Contribute code — Nobi is open source (MIT). PRs, issues, and ideas welcome\n"
            "• Join the community — Discord, Telegram, help answer questions\n"
            "• Run a miner — earn TAO by providing AI compute\n\n"
            "A fiat donation gateway (Stripe/Ko-fi) is on the roadmap for after mainnet launch. "
            "For now, the best support is simply using Nori and sharing it with people "
            "who'd benefit from a private AI companion."
        ),
    },
]

# ─── SupportHandler ─────────────────────────────────────────

class SupportHandler:
    """
    Manages support conversations for Nori.

    FAQ matching (fuzzy keyword-based) → instant answer
    No FAQ match → save as feedback ticket, acknowledge warmly.
    """

    # Threshold: fraction of query words that must appear in keywords
    MATCH_THRESHOLD = 0.3

    def __init__(self, feedback_manager: Optional[FeedbackManager] = None):
        self.feedback = feedback_manager or FeedbackManager()
        self._faq = FAQ_ENTRIES

    # ── Public API ────────────────────────────────────────────

    def get_faq(self) -> List[Dict[str, Any]]:
        """Return FAQ entries (id, topic, answer — no internal keywords)."""
        return [
            {"id": e["id"], "topic": e["topic"], "answer": e["answer"]}
            for e in self._faq
        ]

    def ask(
        self,
        question: str,
        user_id: str,
        platform: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Process a support question.

        Returns dict with:
          - type: 'faq' | 'ticket'
          - answer: str (for faq) or acknowledgment (for ticket)
          - faq_id: str (for faq)
          - ticket_id: str (for ticket)
        """
        if not question or not question.strip():
            return {
                "type": "error",
                "answer": "Please ask me something — I'm here to help! 😊",
            }

        match = self._match_faq(question)
        if match:
            return {
                "type": "faq",
                "faq_id": match["id"],
                "topic": match["topic"],
                "answer": match["answer"],
            }

        # No FAQ match — create a support ticket
        try:
            feedback = self.feedback.submit_feedback(
                message=question.strip(),
                user_id=user_id,
                platform=platform,
                category=FeedbackCategory.QUESTION.value,
            )
            ticket_id = feedback["id"][:8].upper()
            return {
                "type": "ticket",
                "ticket_id": feedback["id"],
                "answer": self._ticket_acknowledgment(question, ticket_id),
            }
        except Exception as e:
            logger.error("Failed to create support ticket: %s", e)
            return {
                "type": "error",
                "answer": (
                    "Hmm, I couldn't save your question right now — "
                    "please try again in a moment! 🙏"
                ),
            }

    def submit_feedback(
        self,
        message: str,
        user_id: str,
        platform: str = "unknown",
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit user feedback. Returns acknowledgment info.
        """
        feedback = self.feedback.submit_feedback(
            message=message,
            user_id=user_id,
            platform=platform,
            category=category,
        )
        ticket_id = feedback["id"][:8].upper()
        return {
            "feedback_id": feedback["id"],
            "ticket_id": ticket_id,
            "category": feedback["category"],
            "acknowledgment": self._feedback_acknowledgment(feedback["category"], ticket_id),
        }

    # ── FAQ Matching ──────────────────────────────────────────

    def _match_faq(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Fuzzy keyword matching against FAQ entries.
        Returns the best matching FAQ entry or None.
        """
        q_lower = query.lower()
        q_words = set(re.findall(r'\w+', q_lower))

        best_entry = None
        best_score = 0.0

        for entry in self._faq:
            score = 0.0
            # Direct keyword phrase matching (highest weight)
            for phrase in entry["keywords"]:
                if phrase in q_lower:
                    phrase_words = len(phrase.split())
                    score = max(score, phrase_words * 2.0)

            # Word-level matching (lower weight)
            if q_words:
                entry_words = set()
                for phrase in entry["keywords"]:
                    entry_words.update(re.findall(r'\w+', phrase))
                overlap = len(q_words & entry_words) / max(len(q_words), 1)
                score = max(score, overlap)

            if score > best_score:
                best_score = score
                best_entry = entry

        if best_score >= self.MATCH_THRESHOLD:
            return best_entry
        return None

    # ── Response generation ───────────────────────────────────

    def _feedback_acknowledgment(self, category: str, ticket_id: str) -> str:
        messages = {
            FeedbackCategory.BUG_REPORT.value: (
                f"Thanks for the bug report! 🐛 I've logged it as ticket #{ticket_id}. "
                "Our team will investigate and get back to you. Your help makes Nori better!"
            ),
            FeedbackCategory.FEATURE_REQUEST.value: (
                f"Ooh, love the idea! 💡 Saved as ticket #{ticket_id}. "
                "I'll make sure the team sees this. Feature requests like yours shape where Nori goes next!"
            ),
            FeedbackCategory.QUESTION.value: (
                f"Got your question — logged as ticket #{ticket_id}. "
                "I'll get you an answer as soon as possible! 😊"
            ),
            FeedbackCategory.COMPLAINT.value: (
                f"I'm sorry you had a bad experience. 😔 Your feedback is logged as ticket #{ticket_id}. "
                "This matters to us and I'll make sure someone looks into it promptly."
            ),
            FeedbackCategory.GENERAL_FEEDBACK.value: (
                f"Thanks for sharing! 💙 Logged as ticket #{ticket_id}. "
                "Every bit of feedback helps us make Nori better for everyone."
            ),
        }
        return messages.get(category, messages[FeedbackCategory.GENERAL_FEEDBACK.value])

    def _ticket_acknowledgment(self, question: str, ticket_id: str) -> str:
        return (
            f"I don't have an instant answer for that one, but I've logged your question as "
            f"ticket #{ticket_id}. 📋\n\n"
            "Our team will get back to you within 24-48 hours. "
            "Is there anything else I can help with in the meantime? 😊"
        )
