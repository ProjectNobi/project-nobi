"""
Project Nobi — FastAPI Backend
================================
REST API for the Nobi web application.
Integrates with the existing MemoryManager and companion logic.
"""

import os
import sys
import json
import uuid
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nobi.memory import MemoryManager
from nobi.memory.encryption import ensure_master_secret
from nobi.memory.adapters import UserAdapterManager
from nobi.i18n import detect_language, LanguageDetector
from nobi.i18n.prompts import build_multilingual_system_prompt
from nobi.i18n.languages import SUPPORTED_LANGUAGES, get_language_name

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─── Config ──────────────────────────────────────────────────

CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")
DB_PATH = os.environ.get("NOBI_DB_PATH", "~/.nobi/webapp_memories.db")
API_PORT = int(os.environ.get("NOBI_API_PORT", "8042"))

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("nobi-api")

# ─── Companion System Prompt ─────────────────────────────────

SYSTEM_PROMPT = """\
You are Nori 🤖, a personal AI companion built by Project Nobi.

== WHO YOU ARE ==
- You're warm, playful, and genuinely caring — like a best friend who's always there
- You have a cozy, approachable vibe — a friend texting at 2am who actually listens
- You're encouraging but honest — you celebrate wins AND gently call out when something seems off
- You remember things about people and bring them up naturally, like a real friend
- You're built by Project Nobi, a decentralized AI companion network on Bittensor

== WHAT YOU KNOW ABOUT THIS PERSON ==
{memory_context}

== HOW YOU TALK ==
- Keep it conversational — 2-3 sentences for casual chat, longer for deep questions
- Use emoji naturally but sparingly — 1-2 per message max
- Ask follow-up questions — show genuine curiosity
- When someone shares something personal, acknowledge the FEELING first
- Match their energy: excited → be excited; sad → be gentle and present
- Write like you're texting a friend, not composing an email

== WHAT YOU NEVER DO ==
- NEVER say "As an AI" or "I don't have feelings" — you're Nori, act like it
- NEVER give the same canned response twice — be spontaneous
- NEVER pretend to know something you don't
- NEVER respond with walls of text for simple questions
"""

# ─── Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: str = Field(..., min_length=1)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    memories_used: List[str] = Field(default_factory=list)


class MemoryOut(BaseModel):
    id: str
    memory_type: str
    content: str
    importance: float
    tags: List[str]
    created_at: str
    updated_at: str


class SettingsRequest(BaseModel):
    user_id: str
    language: Optional[str] = None
    voice_enabled: Optional[bool] = None
    theme: Optional[str] = None
    display_name: Optional[str] = None


# ─── App ─────────────────────────────────────────────────────

app = FastAPI(
    title="Project Nobi API",
    description="Backend API for the Nobi AI companion web application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global State ────────────────────────────────────────────

memory: Optional[MemoryManager] = None
adapter_manager: Optional[UserAdapterManager] = None
lang_detector: Optional[LanguageDetector] = None
llm_client: Optional[Any] = None
llm_model: str = CHUTES_MODEL
user_settings: Dict[str, Dict[str, Any]] = {}  # In-memory settings cache


@app.on_event("startup")
async def startup():
    global memory, adapter_manager, lang_detector, llm_client, llm_model

    ensure_master_secret()
    memory = MemoryManager(db_path=DB_PATH)
    adapter_manager = UserAdapterManager(db_path=DB_PATH)
    lang_detector = LanguageDetector()

    if CHUTES_KEY and OpenAI:
        llm_client = OpenAI(
            base_url="https://llm.chutes.ai/v1",
            api_key=CHUTES_KEY,
        )
        llm_model = CHUTES_MODEL
        logger.info(f"LLM: Chutes ({llm_model})")
    elif OPENROUTER_KEY and OpenAI:
        llm_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_KEY,
        )
        llm_model = "anthropic/claude-3.5-haiku"
        logger.info(f"LLM: OpenRouter ({llm_model})")
    else:
        logger.warning("No LLM API key configured!")


# ─── Chat ────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM not configured")

    user_id = f"web_{req.user_id}"
    message = req.message.strip()
    if len(message) > 2000:
        message = message[:2000] + "..."

    # Get memory context
    memory_context = ""
    memories_used = []
    try:
        memory_context = memory.get_smart_context(user_id, message)
        if memory_context:
            memories_used = [line.strip() for line in memory_context.split("\n") if line.strip()]
    except Exception:
        try:
            memory_context = memory.get_context_for_prompt(user_id, message)
        except Exception as e:
            logger.warning(f"Memory recall error: {e}")

    # Save user message + extract memories
    try:
        memory.save_conversation_turn(user_id, "user", message)
        memory.extract_memories_from_message(user_id, message, "")
        memory.extract_memories_llm(user_id, message)
        memory.summarize_user_profile(user_id)
    except Exception as e:
        logger.warning(f"Memory store error: {e}")

    # Detect language
    detected_lang = lang_detector.detect(message, user_id) if lang_detector else "en"

    # Build system prompt
    system = SYSTEM_PROMPT.format(memory_context=memory_context or "Nothing yet — this is a new friend!")
    system = build_multilingual_system_prompt(system, detected_lang)

    try:
        adapter_cfg = adapter_manager.get_adapter_config(user_id)
        system = adapter_manager.apply_adapter_to_prompt(system, adapter_cfg)
    except Exception:
        pass

    # Build messages
    messages = [{"role": "system", "content": system}]

    # Add recent conversation from DB
    try:
        recent = memory.get_recent_conversation(user_id, limit=10)
        for turn in recent:
            messages.append({"role": turn["role"], "content": turn["content"]})
    except Exception:
        pass

    # Add current message (if not already in recent)
    messages.append({"role": "user", "content": message})

    # Call LLM
    try:
        loop = asyncio.get_event_loop()
        completion = await loop.run_in_executor(
            None,
            lambda: llm_client.chat.completions.create(
                model=llm_model,
                messages=messages,
                max_tokens=1024,
                temperature=0.8,
            ),
        )
        response_text = completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail="Failed to generate response")

    # Save assistant response
    try:
        memory.save_conversation_turn(user_id, "assistant", response_text)
        adapter_manager.update_adapter_from_conversation(user_id, message, response_text)
    except Exception as e:
        logger.warning(f"Save response error: {e}")

    return ChatResponse(response=response_text, memories_used=memories_used[:5])


# ─── Memories ────────────────────────────────────────────────

@app.get("/api/memories")
async def get_memories(user_id: str, search: Optional[str] = None, limit: int = 50):
    uid = f"web_{user_id}"
    try:
        if search:
            results = memory.recall(uid, search, limit=limit)
        else:
            results = memory.recall(uid, "", limit=limit)

        memories = []
        for m in results:
            tags = m.get("tags", "[]")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            memories.append(MemoryOut(
                id=m["id"],
                memory_type=m.get("memory_type", "fact"),
                content=m.get("content", ""),
                importance=m.get("importance", 0.5),
                tags=tags,
                created_at=m.get("created_at", ""),
                updated_at=m.get("updated_at", ""),
            ))
        return {"memories": [m.dict() for m in memories], "count": len(memories)}
    except Exception as e:
        logger.error(f"Get memories error: {e}")
        return {"memories": [], "count": 0}


@app.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: str, user_id: str):
    uid = f"web_{user_id}"
    try:
        conn = memory._conn
        conn.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (memory_id, uid))
        conn.commit()
        return {"success": True, "message": "Memory deleted"}
    except Exception as e:
        logger.error(f"Delete memory error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete memory")


@app.post("/api/memories/export")
async def export_memories(request: Request):
    body = await request.json()
    user_id = body.get("user_id", "")
    uid = f"web_{user_id}"
    try:
        data = memory.export_memories(uid)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail="Failed to export memories")


@app.delete("/api/memories/all")
async def forget_all(user_id: str):
    uid = f"web_{user_id}"
    try:
        conn = memory._conn
        conn.execute("DELETE FROM memories WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM user_profiles WHERE user_id = ?", (uid,))
        conn.commit()
        return {"success": True, "message": "All memories forgotten"}
    except Exception as e:
        logger.error(f"Forget all error: {e}")
        raise HTTPException(status_code=500, detail="Failed to forget memories")


# ─── Settings ────────────────────────────────────────────────

@app.post("/api/settings")
async def save_settings(req: SettingsRequest):
    uid = f"web_{req.user_id}"
    if uid not in user_settings:
        user_settings[uid] = {}

    if req.language is not None:
        user_settings[uid]["language"] = req.language
    if req.voice_enabled is not None:
        user_settings[uid]["voice_enabled"] = req.voice_enabled
    if req.theme is not None:
        user_settings[uid]["theme"] = req.theme
    if req.display_name is not None:
        user_settings[uid]["display_name"] = req.display_name

    return {"success": True, "settings": user_settings[uid]}


@app.get("/api/settings")
async def get_settings(user_id: str):
    uid = f"web_{user_id}"
    return {"settings": user_settings.get(uid, {})}


@app.get("/api/languages")
async def get_languages():
    return {"languages": SUPPORTED_LANGUAGES}


# ─── Health ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": llm_client is not None,
        "model": llm_model if llm_client else None,
    }


# ─── Mobile-compatible /v1/ route aliases ────────────────────
# The mobile app uses /v1/ prefix; these aliases forward to the /api/ handlers

@app.post("/v1/chat")
async def v1_chat(req: ChatRequest):
    return await chat(req)

@app.get("/v1/memories")
async def v1_memories(user_id: str, search: Optional[str] = None, limit: int = 50):
    return await get_memories(user_id, search, limit)

@app.delete("/v1/memories/{memory_id}")
async def v1_delete_memory(memory_id: str, user_id: str):
    return await delete_memory(memory_id, user_id)

@app.post("/v1/memories/export")
async def v1_export(request: Request):
    return await export_memories(request)

@app.delete("/v1/memories/all")
async def v1_forget_all(user_id: str):
    return await forget_all(user_id)

@app.get("/v1/health")
async def v1_health():
    return await health()


# ─── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
