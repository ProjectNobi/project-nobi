# Project Nobi — Public API Reference

## Overview

The Nobi Public API lets third-party developers integrate with Nori, the AI companion, including chat, memory management, relationship graphs, and voice features.

**Base URL:** `https://api.projectnobi.ai` (or your self-hosted instance)

**API Version:** v1

---

## Authentication

All public API endpoints require an API key passed via the `Authorization` header:

```
Authorization: Bearer nobi_your_api_key_here
```

### Getting an API Key

1. Create your first key via the admin dashboard, or
2. Use an existing key to create additional keys via `POST /v1/api/keys`

### Key Format

API keys follow the format: `nobi_` + 32 hex characters

Example: `nobi_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6`

> **Security:** Store your API key securely. It is shown only once at creation time. We store only the SHA-256 hash — lost keys cannot be recovered.

---

## Rate Limits

| Tier | Requests/Day | Description |
|------|-------------|-------------|
| Free | 100 | Default tier for new keys |
| Plus | 1,000 | For growing projects |
| Pro  | 10,000 | For production apps |

When rate limited, the API returns `429 Too Many Requests` with a descriptive message.

---

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad request — invalid parameters |
| 401 | Unauthorized — missing, invalid, or revoked API key |
| 404 | Not found — resource doesn't exist |
| 422 | Validation error — missing required fields |
| 429 | Rate limit exceeded |
| 500 | Server error |
| 502 | LLM provider error |
| 503 | Service not configured/available |

Error response format:
```json
{
  "detail": "Description of the error"
}
```

---

## Endpoints

### Chat

#### `POST /v1/api/chat`

Chat with Nori. Uses the authenticated user's memory context for personalized responses.

**Request:**
```json
{
  "message": "Hey Nori, what did we talk about last time?",
  "conversation_history": []
}
```

**Response:**
```json
{
  "response": "Hey! Last time you mentioned you were working on...",
  "memories_used": ["Likes programming", "Works on AI projects"]
}
```

**curl:**
```bash
curl -X POST https://api.projectnobi.ai/v1/api/chat \
  -H "Authorization: Bearer nobi_your_key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Nori!"}'
```

**Python:**
```python
import requests

resp = requests.post(
    "https://api.projectnobi.ai/v1/api/chat",
    headers={"Authorization": "Bearer nobi_your_key"},
    json={"message": "Hello Nori!"}
)
print(resp.json()["response"])
```

**JavaScript:**
```javascript
const resp = await fetch("https://api.projectnobi.ai/v1/api/chat", {
  method: "POST",
  headers: {
    "Authorization": "Bearer nobi_your_key",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ message: "Hello Nori!" }),
});
const data = await resp.json();
console.log(data.response);
```

---

### Memories

#### `GET /v1/api/memories`

List memories for the authenticated user.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| search | string | null | Search query to filter memories |
| limit | int | 50 | Max number of results |

**Response:**
```json
{
  "memories": [
    {
      "id": "uuid-here",
      "memory_type": "fact",
      "content": "User enjoys hiking",
      "importance": 0.8,
      "tags": ["hobby", "outdoor"],
      "created_at": "2026-03-20T07:00:00+00:00",
      "updated_at": "2026-03-20T07:00:00+00:00"
    }
  ],
  "count": 1
}
```

**curl:**
```bash
curl "https://api.projectnobi.ai/v1/api/memories?limit=10" \
  -H "Authorization: Bearer nobi_your_key"
```

---

#### `POST /v1/api/memories`

Store a new memory.

**Request:**
```json
{
  "content": "User's favorite color is blue",
  "memory_type": "fact",
  "importance": 0.7,
  "tags": ["preference"]
}
```

**Response:**
```json
{
  "success": true,
  "memory": {
    "id": "uuid-here",
    "memory_type": "fact",
    "content": "User's favorite color is blue",
    "importance": 0.7,
    "tags": ["preference"],
    "created_at": "2026-03-20T07:00:00+00:00",
    "updated_at": "2026-03-20T07:00:00+00:00"
  }
}
```

---

#### `DELETE /v1/api/memories/{id}`

Delete a specific memory by ID.

**Response:**
```json
{
  "success": true,
  "message": "Memory deleted"
}
```

---

### Relationship Graph

#### `GET /v1/api/graph`

Get the full relationship graph for the authenticated user.

**Response:**
```json
{
  "success": true,
  "graph": {
    "entities": [...],
    "relationships": [...]
  }
}
```

---

#### `GET /v1/api/graph/context`

Get natural language graph context relevant to a query.

**Query Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | The query to get context for |

**Response:**
```json
{
  "success": true,
  "context": "User knows Alice from work. Alice is a software engineer..."
}
```

**curl:**
```bash
curl "https://api.projectnobi.ai/v1/api/graph/context?query=Alice" \
  -H "Authorization: Bearer nobi_your_key"
```

---

### Voice

#### `POST /v1/api/voice/transcribe`

Transcribe audio to text.

**Request:**
```json
{
  "audio": "<base64-encoded-audio>",
  "language": "en"
}
```

**Response:**
```json
{
  "success": true,
  "text": "Hello, how are you?",
  "language": "en"
}
```

---

#### `POST /v1/api/voice/synthesize`

Convert text to speech.

**Request:**
```json
{
  "text": "Hello, I'm Nori!",
  "voice": "default"
}
```

**Response:**
```json
{
  "success": true,
  "audio": "<base64-encoded-audio>",
  "format": "mp3"
}
```

---

### Key Management

#### `POST /v1/api/keys`

Create a new API key (inherits the tier of the authenticating key).

**Request:**
```json
{
  "name": "my-production-key"
}
```

**Response:**
```json
{
  "success": true,
  "key": {
    "key": "nobi_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "key_prefix": "a1b2c3d4e5f6",
    "name": "my-production-key"
  }
}
```

> **Important:** The full key is only returned at creation time. Save it securely!

---

#### `GET /v1/api/keys`

List all API keys for the authenticated user (metadata only, no raw keys).

**Response:**
```json
{
  "success": true,
  "keys": [
    {
      "key_prefix": "a1b2c3d4e5f6",
      "name": "my-production-key",
      "tier": "free",
      "created_at": "2026-03-20T07:00:00+00:00",
      "last_used": "2026-03-20T08:30:00+00:00",
      "revoked": false
    }
  ]
}
```

---

#### `DELETE /v1/api/keys/{key_prefix}`

Revoke an API key by its prefix.

**Response:**
```json
{
  "success": true,
  "message": "Key a1b2c3d4e5f6... revoked"
}
```

---

#### `GET /v1/api/keys/usage`

Get usage statistics for the authenticating API key.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| days | int | 30 | Number of days to look back |

**Response:**
```json
{
  "success": true,
  "usage": {
    "total_requests": 142,
    "requests_today": 23,
    "period_days": 30,
    "by_endpoint": {
      "/v1/api/chat": 100,
      "/v1/api/memories": 42
    }
  }
}
```

---

## Quick Start

### Python

```python
import requests

API_KEY = "nobi_your_key_here"
BASE = "https://api.projectnobi.ai"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Chat
resp = requests.post(f"{BASE}/v1/api/chat", headers=HEADERS, json={"message": "Hi!"})
print(resp.json()["response"])

# Store a memory
requests.post(f"{BASE}/v1/api/memories", headers=HEADERS, json={
    "content": "Loves hiking in the mountains",
    "memory_type": "fact",
    "importance": 0.8,
    "tags": ["hobby"]
})

# List memories
memories = requests.get(f"{BASE}/v1/api/memories", headers=HEADERS).json()
print(f"Found {memories['count']} memories")

# Check usage
usage = requests.get(f"{BASE}/v1/api/keys/usage", headers=HEADERS).json()
print(f"Requests today: {usage['usage']['requests_today']}")
```

### JavaScript / Node.js

```javascript
const API_KEY = "nobi_your_key_here";
const BASE = "https://api.projectnobi.ai";
const headers = {
  "Authorization": `Bearer ${API_KEY}`,
  "Content-Type": "application/json",
};

// Chat
const chatResp = await fetch(`${BASE}/v1/api/chat`, {
  method: "POST",
  headers,
  body: JSON.stringify({ message: "Hi!" }),
});
console.log((await chatResp.json()).response);

// List memories
const memResp = await fetch(`${BASE}/v1/api/memories`, { headers });
const memories = await memResp.json();
console.log(`Found ${memories.count} memories`);
```

### curl

```bash
# Set your key
export NOBI_KEY="nobi_your_key_here"

# Chat
curl -X POST https://api.projectnobi.ai/v1/api/chat \
  -H "Authorization: Bearer $NOBI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'

# List memories
curl https://api.projectnobi.ai/v1/api/memories \
  -H "Authorization: Bearer $NOBI_KEY"

# Create a new API key
curl -X POST https://api.projectnobi.ai/v1/api/keys \
  -H "Authorization: Bearer $NOBI_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-key"}'

# Check usage
curl https://api.projectnobi.ai/v1/api/keys/usage \
  -H "Authorization: Bearer $NOBI_KEY"
```
