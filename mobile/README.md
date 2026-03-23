# Nori Mobile — iOS & Android App

> Your personal AI companion in your pocket. Built with Expo + React Native.

## Features

- 💬 **Chat** — Full conversation interface with typing indicators
- 🧠 **Memories** — View, search, and manage what Nori remembers about you
- 🎤 **Voice** — Send voice messages, get voice replies
- 📷 **Images** — Send photos for Nori to understand and discuss
- 🌍 **20 Languages** — Auto-detects and responds in your language
- 🔐 **Encryption** — Client-side encryption for sensitive data
- 📱 **Offline Queue** — Messages queued when offline, sent when reconnected
- 🌙 **Dark Mode** — Follows system preference
- ⚡ **Onboarding** — Smooth first-time setup flow

## Quick Start

```bash
cd mobile

# Install dependencies
npm install

# Start Expo dev server
npx expo start

# Run on specific platform
npx expo start --ios      # iOS simulator
npx expo start --android  # Android emulator
npx expo start --web      # Web browser
```

## Requirements

- Node.js 18+
- Expo CLI (`npm install -g expo-cli`)
- For iOS: macOS + Xcode (simulator) or Expo Go app on device
- For Android: Android Studio (emulator) or Expo Go app on device

## Configuration

Set the API URL in `services/api.ts`:

```typescript
const DEFAULT_BASE_URL = 'https://api.projectnobi.ai';  // Production
const TESTNET_BASE_URL = 'https://testnet.projectnobi.ai';  // Testnet
```

For local development, use:
```typescript
const DEFAULT_BASE_URL = 'http://YOUR_SERVER_IP:8042';
```

## Project Structure

```
mobile/
├── app/                      # Screens (Expo Router)
│   ├── _layout.tsx           # Root Stack layout (onboarding gate)
│   ├── onboarding.tsx        # First-time setup (fullscreen, no tabs)
│   └── (tabs)/               # Tab navigation: Chat | Memories | Settings
│       ├── _layout.tsx       # Tab bar config
│       ├── index.tsx         # Chat screen (main)
│       ├── memories.tsx      # Memory viewer
│       └── settings.tsx      # Preferences
├── components/               # Reusable UI components
│   ├── ChatBubble.tsx        # Message bubble (🔒 encryption indicator)
│   ├── MemoryCard.tsx        # Memory display card
│   ├── NoriAvatar.tsx        # Animated Nori avatar
│   └── TypingIndicator.tsx   # Animated typing dots
├── hooks/                    # React hooks
│   ├── useChat.ts            # Chat state management
│   ├── useMemory.ts          # Memory operations
│   └── useVoice.ts           # Voice recording/playback
├── lib/                      # Shared TypeScript modules (adapted from webapp)
│   ├── client-crypto.ts      # Key derivation + utils (expo-crypto)
│   ├── local-extractor.ts    # On-device regex memory extraction (pure TS)
│   └── memory-sync.ts        # AsyncStorage memory cache + server sync
├── services/                 # Backend integration
│   ├── api.ts                # API client with retry + offline queue
│   ├── auth.ts               # Anonymous auth + device ID
│   ├── encryption.ts         # Client-side AES encryption (expo-crypto)
│   ├── memory.ts             # Local memory cache
│   └── voice.ts              # TTS/STT via expo-speech + server Whisper
├── styles/
│   └── theme.ts              # Color palette, spacing, typography
├── assets/                   # App icons + splash screen
├── store/                    # App Store metadata (iOS/Android)
├── app.json                  # Expo config (bundle: ai.projectnobi.nori v0.1.0)
├── eas.json                  # EAS Build config
├── package.json
└── tsconfig.json
```

## Building for Production

### Expo EAS Build (Recommended)

```bash
# Install EAS CLI
npm install -g eas-cli

# Configure build
eas build:configure

# Build for both platforms
eas build --platform all

# Submit to stores
eas submit --platform ios
eas submit --platform android
```

### Local Build

```bash
# iOS (requires macOS + Xcode)
npx expo run:ios --configuration Release

# Android
npx expo run:android --variant release
```

## API Compatibility

The mobile app uses `/v1/` API routes. The FastAPI backend at `/root/project-nobi/api/server.py` supports both `/api/` and `/v1/` prefixes.

| Mobile Endpoint | Backend Handler |
|----------------|----------------|
| POST /v1/chat | /api/chat |
| GET /v1/memories | /api/memories |
| DELETE /v1/memories/:id | /api/memories/:id |
| POST /v1/memories/export | /api/memories/export |
| DELETE /v1/memories/all | /api/memories/all |
| GET /v1/health | /api/health |

## Links

- **Try Nori:** [@ProjectNobiBot](https://t.me/ProjectNobiBot)
- **Discord:** [discord.gg/e6StezHM](https://discord.gg/e6StezHM)
- **Website:** [projectnobi.ai](https://projectnobi.ai)
- **GitHub:** [ProjectNobi/project-nobi](https://github.com/ProjectNobi/project-nobi)
