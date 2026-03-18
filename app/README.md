# 🤖 Dora — Your Personal AI Companion

## Setup (2 minutes)

### 1. Create a Telegram Bot
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Name: `Dora Nobi` (or anything you like)
4. Username: `nobi_companion_bot` (must end in `bot`)
5. Copy the token

### 2. Run
```bash
# Set your token + API key
export NOBI_BOT_TOKEN="your-token-from-botfather"
export CHUTES_API_KEY="your-chutes-key"  # From chutes.ai

# Start
python3 app/bot.py
```

Or with PM2 (recommended):
```bash
NOBI_BOT_TOKEN="..." CHUTES_API_KEY="..." pm2 start python3 --name nobi-bot -- app/bot.py
```

### 3. Talk to your bot
Open Telegram → find your bot → press Start → just talk!

## Features
- **Zero setup for users** — just /start and talk
- **Persistent memory** — remembers your name, preferences, life events
- **Natural conversation** — no slash commands needed
- **Privacy controls** — /memories to see what's stored, /forget to clear

## Commands (optional — users don't need these)
| Command | What it does |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Quick guide |
| `/memories` | See what the bot remembers about you |
| `/forget` | Delete all your data |

Everything else: just type normally and chat! 💬
