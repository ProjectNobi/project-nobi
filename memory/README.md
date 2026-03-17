# Project Nobi — Memory Protocol

Persistent memory system for personal AI companions on Bittensor subnet 272.

## Overview

The memory protocol enables companions to remember users across conversations — their name, preferences, life events, and conversation history. This creates a more personal and continuous relationship between users and their AI companion.

## Architecture

### Components

1. **MemoryManager** — Singleton manager for all user memories
   - Thread-safe concurrent access
   - Lazy loading of user memory files
   - Graceful degradation on errors

2. **UserMemory** — Per-user memory storage
   - Conversation history (per conversation_id)
   - User facts (name, preferences, location, etc.)
   - JSON file-based persistence

3. **Fact Extractor** — Pattern-based fact extraction
   - Extracts facts from natural conversation
   - No LLM needed — simple regex patterns
   - Auto-learns user information

### Storage Format

Each user gets a JSON file: `memory/data/{user_id}.json`

```json
{
  "user_id": "user_12345",
  "created_at": 1234567890.0,
  "updated_at": 1234567890.0,
  "facts": {
    "name": {
      "value": "James",
      "updated_at": 1234567890.0
    },
    "location": {
      "value": "London",
      "updated_at": 1234567890.0
    },
    "likes": {
      "value": "pizza; coding; sci-fi movies",
      "updated_at": 1234567890.0
    }
  },
  "conversations": {
    "conv_abc123": [
      {
        "role": "user",
        "content": "Hi, I'm James",
        "timestamp": 1234567890.0
      },
      {
        "role": "assistant",
        "content": "Hi James! Nice to meet you!",
        "timestamp": 1234567891.0
      }
    ]
  }
}
```

## API Usage

### Basic Usage

```python
from memory import MemoryManager

# Get the singleton instance
memory = MemoryManager()

# Add a message to conversation history
memory.add_message(
    conversation_id="conv_123",
    role="user",
    content="Hi, I'm James",
    user_id="user_james"
)

# Get conversation history (for LLM context)
history = memory.get_history("conv_123", max_turns=10, user_id="user_james")
# Returns: [{"role": "user", "content": "Hi, I'm James"}, ...]

# Store a user fact
memory.set_user_fact("user_james", "name", "James")

# Get all facts about a user
facts = memory.get_user_facts("user_james")
# Returns: {"name": "James", "location": "London", ...}

# Get a text summary
summary = memory.summarize_user("user_james")
# Returns: "Name: James | Location: London | Likes: pizza"

# Extract facts from conversation
memory.extract_facts_from_message(
    user_id="user_james",
    user_message="I love pizza and coding",
    assistant_response="That's great! Pizza is delicious."
)
# Automatically extracts and stores: likes = "pizza; coding"
```

### Integration with Miner

The miner automatically uses persistent memory:

1. **Load user context** — Before generating response:
   - Load user facts and conversation history
   - Inject into system prompt

2. **Store conversation** — After generating response:
   - Save user message and assistant response
   - Extract and store new facts

3. **Greet returning users** — If we know the user's name:
   - Greet them warmly on first message of new conversation

## Fact Extraction

The fact extractor recognizes these patterns:

### Name
- "I'm [name]"
- "I am [name]"
- "my name is [name]"
- "call me [name]"

### Preferences (Positive)
- "I love/like/enjoy [thing]"
- "my favorite is [thing]"
- "I'm into [thing]"

### Preferences (Negative)
- "I hate/dislike/don't like [thing]"
- "I can't stand [thing]"

### Life Events
- "I got [promotion/job/married/divorced/...]"
- "I have a [pet/child/baby/...]"
- "I recently [event]"

### Location
- "I live in [place]"
- "I am from [place]"
- "I was born in [place]"

### Occupation
- "I work as [job]"
- "I am a [job]"

## Thread Safety

All operations are thread-safe:
- `MemoryManager` uses a global lock for lazy loading
- `UserMemory` uses a per-user lock for file I/O
- Miners can serve concurrent requests safely

## Error Handling

The system degrades gracefully:
- If memory load fails → returns empty memory
- If memory save fails → logs warning, continues
- If fact extraction fails → logs warning, still responds
- Miner never crashes due to memory errors

## Testing

Test the memory module standalone:

```bash
# Test fact extractor
python3 -m memory.fact_extractor

# Test memory manager
python3 -c "
from memory import MemoryManager
m = MemoryManager()
m.add_message('test', 'user', 'Hi, I am James', user_id='test_user')
m.add_message('test', 'assistant', 'Hi James!', user_id='test_user')
print(m.get_history('test', user_id='test_user'))
print(m.get_user_facts('test_user'))
"
```

## Future Enhancements

- **Semantic memory search** — Use embeddings for similarity search
- **Memory importance scoring** — Keep important memories, prune trivial ones
- **Cross-conversation patterns** — Detect recurring topics/interests
- **Memory sync across miners** — Share user memory via MemorySync synapse
- **Privacy controls** — User-controlled memory deletion/export

## Design Principles

1. **Simple & Robust** — No database, just JSON files
2. **Privacy-First** — Each user's data is isolated
3. **Thread-Safe** — Works with concurrent mining requests
4. **Graceful Degradation** — Never crash due to memory errors
5. **No External Dependencies** — Only stdlib + Bittensor

---

Built for Project Nobi — Personal AI Companions on Bittensor 🤖
