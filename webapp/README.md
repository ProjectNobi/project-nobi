# Nori Web App — Project Nobi

A warm, modern web interface for chatting with Nori, your personal AI companion on Bittensor.

## Features

- 💬 **Chat Interface** — Clean, responsive chat UI with markdown support
- 🧠 **Memories** — View, search, and manage what Nori remembers about you
- ⚙️ **Settings** — Language, voice, theme, and privacy controls
- 🌙 **Dark Mode** — System-aware with manual toggle
- 📱 **Mobile-first** — Works great on all screen sizes
- 🔒 **Privacy** — Anonymous user IDs, encrypted memory storage

## Tech Stack

- **Frontend:** Next.js 14 (App Router) + TypeScript
- **Styling:** Tailwind CSS
- **Backend:** FastAPI (Python) at `/api/`
- **Storage:** SQLite via MemoryManager (no separate DB needed)

## Quick Start

### 1. Frontend (Next.js)

```bash
cd webapp
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 2. Backend (FastAPI)

```bash
cd api
pip install fastapi uvicorn pydantic openai
python server.py
```

API runs on [http://localhost:8042](http://localhost:8042)

### 3. Environment Variables

Create `.env.local` in the webapp directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:8042
```

For the API server, set in your environment or `.env`:

```env
CHUTES_API_KEY=your_key_here
CHUTES_MODEL=deepseek-ai/DeepSeek-V3.1-TEE
NOBI_DB_PATH=~/.nobi/webapp_memories.db
NOBI_API_PORT=8042
```

## Build & Deploy

### Static Export (Vercel, Cloudflare Pages, etc.)

```bash
NEXT_OUTPUT=export npm run build
# Output in `out/` directory
```

### Docker / Server

```bash
npm run build
npm start
```

## Project Structure

```
webapp/
├── app/            # Next.js App Router pages
│   ├── page.tsx    # Landing page
│   ├── chat/       # Chat interface
│   ├── memories/   # Memory viewer
│   ├── settings/   # User settings
│   └── onboarding/ # First-time flow
├── components/     # Reusable UI components
├── hooks/          # React hooks (useChat, useMemories, useSettings)
├── lib/            # API client, types, constants
├── styles/         # Global CSS + Tailwind
└── public/         # Static assets
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message, get AI response |
| GET | `/api/memories?user_id=X` | List memories |
| DELETE | `/api/memories/{id}?user_id=X` | Delete a memory |
| POST | `/api/memories/export` | Export all memories as JSON |
| DELETE | `/api/memories/all?user_id=X` | Forget everything |
| POST | `/api/settings` | Save user preferences |
| GET | `/api/settings?user_id=X` | Get user preferences |
| GET | `/api/languages` | List supported languages |
| GET | `/api/health` | Health check |

## License

MIT — Part of [Project Nobi](https://github.com/ProjectNobi/project-nobi)
