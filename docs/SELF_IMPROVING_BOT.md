# Nori Self-Improving Feedback Loop

**Making Nori the first self-improving AI companion on Bittensor.**

## Overview

Nori now has a growing feedback loop: when users correct her, she extracts a lesson and injects it into all future conversations. The more users chat, the smarter Nori becomes — not just for that user, but for everyone.

---

## Architecture

```
User message → detect_correction() → extract_lesson() (LLM)
                                        ↓
                              save_lesson() → SQLite nori_lessons
                                        ↓
User's next message → get_active_lessons() → injected into system prompt
```

---

## Files Created

### `nobi/feedback/__init__.py`
Module init — exports `FeedbackStore`.

### `nobi/feedback/feedback_store.py`
Core self-improvement engine. Key class:

```python
class FeedbackStore:
    def detect_correction(self, message: str) -> bool
    async def extract_lesson(self, user_message, bot_response, correction, llm_client) -> str
    def save_lesson(self, user_id, correction, lesson) -> int
    def get_active_lessons(self, limit=50) -> list
    def mark_applied(self, lesson_id: int)
    async def curate_with_llm(self, llm_client)  # periodic curation
```

### `tests/test_feedback_store.py`
42 tests covering:
- 20+ correction detection patterns
- Storage and retrieval
- Deduplication
- Fallback lesson generation
- Async extraction without LLM
- DB pruning

---

## Changes to `app/bot.py`

Three surgical additions (nothing restructured, nothing broken):

1. **Import** (line ~65):
   ```python
   from nobi.feedback import FeedbackStore
   ```

2. **Init** (in `CompanionBot.__init__`):
   ```python
   self.feedback_store = FeedbackStore(db_path="~/.nobi/feedback_lessons.db")
   self._last_response: Dict[str, str] = {}
   ```

3. **In `generate()` method** — before building the `messages` list:
   - Check if user message is a correction → async extract + save lesson
   - Inject active lessons into system prompt
   - After saving response → `self._last_response[user_id] = response`

---

## SQLite Schema

```sql
CREATE TABLE nori_lessons (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    user_id         TEXT    NOT NULL,
    correction_text TEXT    NOT NULL,
    lesson_extracted TEXT   NOT NULL,
    applied         INTEGER NOT NULL DEFAULT 0
);
```

DB path: `~/.nobi/feedback_lessons.db`

---

## Correction Detection Patterns

Detected via regex (24 patterns, case-insensitive):

| Pattern | Example |
|---------|---------|
| `no, I said...` | "no, I said tomorrow not today" |
| `that's wrong` | "that's wrong, I never told you that" |
| `I already told you` | "I already told you my name is Alex" |
| `you forgot` | "you forgot what I said about my schedule" |
| `not what I asked` | "that's not what I asked for" |
| `I meant` | "I meant next week, not this week" |
| `actually, X` | "actually, my name is Sarah not Emma" |
| `correct yourself` | "please correct yourself" |
| `you misunderstood` | "you misunderstood what I said" |
| `you already asked` | "you already asked me that question" |
| `I told you before` | "I told you that before" |
| `stop repeating` | "stop repeating yourself" |
| `you keep forgetting` | "you keep forgetting my preferences" |
| `please remember` | "please remember what I said" |
| `no, my name is` | "no, my name is Alex not Bob" |

---

## Lesson Injection into System Prompt

When lessons exist, this is appended to the system prompt at generation time:

```
== Lessons Learned from User Feedback ==
- Always verify the user's name from memory before using it.
- Never repeat a question already answered in the same conversation.
- Check user's timezone before suggesting meeting times.
- ...
```

Lessons are loaded fresh on every message (no caching), so a lesson saved in one conversation is available in the next.

---

## Periodic Curation

- **Every 100 lessons**: basic deduplication runs automatically (prunes duplicates keeping 3 per prefix)
- **`curate_with_llm()`**: full LLM-powered curation — deduplication, merging, consolidation down to ≤30 lessons. Can be triggered externally (e.g. cron job).

---

## Test Results

```
tests/test_feedback_store.py: 42 passed in 2.04s
Full suite: 1699 passed, 4 pre-existing failures (unrelated: i18n, TEE scoring)
```

The 4 pre-existing failures exist before this change and are in unrelated modules.

---

## Future Improvements

1. **Per-user vs global lessons**: Currently lessons are global (benefit all users). Could add per-user lesson filtering.
2. **Lesson scoring**: Track how often each lesson prevents future corrections (reward signal).
3. **Lesson decay**: Old lessons that haven't prevented corrections could be down-weighted.
4. **Ralph Loop integration**: Run curation cron to continuously refine the lesson library.
5. **Lesson analytics**: Dashboard showing most common correction categories.

---

## Built by

Dragon Lord (autonomous coder subagent) — 2026-03-25
Pending audit by Doraemon (main agent) before push.
