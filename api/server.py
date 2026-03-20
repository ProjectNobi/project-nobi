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

from fastapi import FastAPI, HTTPException, Request, Header, Depends
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
from nobi.billing.subscription import SubscriptionManager, TIERS
from nobi.billing.stripe_handler import StripeHandler
from nobi.api_auth import ApiKeyManager
from nobi.personality import PersonalityTuner, detect_mood
from nobi.personality.prompts import get_dynamic_prompt

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─── Config ──────────────────────────────────────────────────

CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CHUTES_MODEL = os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")
DB_PATH = os.environ.get("NOBI_DB_PATH", "~/.nobi/webapp_memories.db")
BILLING_DB_PATH = os.environ.get("NOBI_BILLING_DB_PATH", "~/.nobi/billing.db")
API_PORT = int(os.environ.get("NOBI_API_PORT", "8042"))
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
API_KEYS_DB_PATH = os.environ.get("NOBI_API_KEYS_DB_PATH", "~/.nobi/api_keys.db")

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

from contextlib import asynccontextmanager

# ─── Global State ────────────────────────────────────────────

memory: Optional[MemoryManager] = None
adapter_manager: Optional[UserAdapterManager] = None
lang_detector: Optional[LanguageDetector] = None
llm_client: Optional[Any] = None
llm_model: str = CHUTES_MODEL
user_settings: Dict[str, Dict[str, Any]] = {}  # In-memory settings cache
billing: Optional[SubscriptionManager] = None
stripe_handler: Optional[StripeHandler] = None
api_key_mgr: Optional[ApiKeyManager] = None
personality_tuner: Optional[PersonalityTuner] = None


@asynccontextmanager
async def lifespan(app):
    """Initialize resources on startup, clean up on shutdown."""
    await startup()
    yield
    # Shutdown cleanup (if needed in future)


app = FastAPI(
    title="Project Nobi API",
    description="Backend API for the Nobi AI companion web application",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def startup():
    global memory, adapter_manager, lang_detector, llm_client, llm_model, billing, stripe_handler, api_key_mgr, personality_tuner

    ensure_master_secret()
    memory = MemoryManager(db_path=DB_PATH)
    adapter_manager = UserAdapterManager(db_path=DB_PATH)
    lang_detector = LanguageDetector()

    # Initialize API key manager
    api_key_mgr = ApiKeyManager(db_path=os.path.expanduser(API_KEYS_DB_PATH))
    logger.info("API key manager initialized")

    # Initialize personality tuner
    personality_tuner = PersonalityTuner(db_path=os.path.expanduser("~/.nobi/personality_api.db"))

    # Initialize billing
    billing = SubscriptionManager(db_path=BILLING_DB_PATH)
    stripe_handler = StripeHandler(api_key=STRIPE_API_KEY, webhook_secret=STRIPE_WEBHOOK_SECRET)
    logger.info(f"Billing initialized (stripe={'enabled' if stripe_handler.stripe_configured else 'disabled'})")

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

    # Detect mood and build system prompt with personality tuning
    user_mood = detect_mood(message)
    system = SYSTEM_PROMPT.format(memory_context=memory_context or "Nothing yet — this is a new friend!")
    mood_prompt = get_dynamic_prompt(user_id, message, user_mood)
    system = system + "\n\n== PERSONALITY TUNING ==\n" + mood_prompt
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

    # Record personality metrics (best-effort)
    try:
        if personality_tuner:
            personality_tuner.analyze_conversation(message, response_text)
    except Exception as e:
        logger.debug(f"Personality metrics error: {e}")

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


# ─── Billing & Subscription ───────────────────────────────────

class SubscribeRequest(BaseModel):
    user_id: str
    tier: str = "plus"
    success_url: str = "https://nobi.ai/subscription?success=true"
    cancel_url: str = "https://nobi.ai/subscription?cancelled=true"


class CancelRequest(BaseModel):
    user_id: str


@app.post("/api/subscribe")
async def subscribe(req: SubscribeRequest):
    """Create a Stripe checkout session for subscription."""
    if not billing or not stripe_handler:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    if req.tier not in ("plus", "pro"):
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'plus' or 'pro'.")

    if not stripe_handler.stripe_configured:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Subscriptions are not available yet.",
        )

    user_id = f"web_{req.user_id}"
    billing.create_customer(user_id)

    checkout_url = stripe_handler.create_checkout_session(
        user_id=user_id,
        tier=req.tier,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
    )

    if not checkout_url:
        raise HTTPException(status_code=502, detail="Failed to create checkout session")

    return {"checkout_url": checkout_url}


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    if not billing or not stripe_handler:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    if not stripe_handler.stripe_configured:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    result = stripe_handler.handle_webhook(payload, signature)

    if "error" in result:
        logger.warning(f"Webhook error: {result['error']}")
        raise HTTPException(status_code=400, detail=result["error"])

    if not result.get("processed"):
        return {"status": "ignored", "event_type": result.get("event_type")}

    action = result.get("action")

    if action == "activate":
        user_id = result["user_id"]
        tier = result["tier"]
        payment_id = result.get("payment_id", "")
        billing.upgrade(user_id, tier, payment_id)
        logger.info(f"Webhook: activated {tier} for {user_id}")

    elif action == "update":
        customer_id = result.get("customer_id")
        customer = billing.get_customer_by_customer_id(customer_id) if customer_id else None
        if customer:
            billing.upgrade(customer["user_id"], result["tier"])
            logger.info(f"Webhook: updated tier for {customer['user_id']}")

    elif action == "cancel":
        customer_id = result.get("customer_id")
        customer = billing.get_customer_by_customer_id(customer_id) if customer_id else None
        if customer:
            billing.downgrade(customer["user_id"])
            logger.info(f"Webhook: cancelled for {customer['user_id']}")

    elif action == "payment_failed":
        customer_id = result.get("customer_id")
        customer = billing.get_customer_by_customer_id(customer_id) if customer_id else None
        if customer:
            logger.warning(f"Webhook: payment failed for {customer['user_id']}")

    return {"status": "ok", "action": action}


@app.get("/api/subscription")
async def get_subscription(user_id: str):
    """Get user's subscription status."""
    if not billing:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    uid = f"web_{user_id}"
    sub = billing.get_subscription(uid)
    tier_config = TIERS.get(sub["tier"], TIERS["free"])

    return {
        "subscription": sub,
        "tier_config": tier_config,
        "is_premium": billing.is_premium(uid),
    }


@app.post("/api/subscription/cancel")
async def cancel_subscription(req: CancelRequest):
    """Cancel user's subscription."""
    if not billing:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    uid = f"web_{req.user_id}"
    success = billing.cancel(uid)

    if not success:
        raise HTTPException(status_code=400, detail="No active paid subscription to cancel")

    return {"success": True, "message": "Subscription cancelled. You'll keep access until the end of your billing period."}


@app.get("/api/usage")
async def get_usage(user_id: str):
    """Get user's usage stats."""
    if not billing:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    uid = f"web_{user_id}"
    usage = billing.get_usage(uid)
    return {"usage": usage}


@app.get("/api/tiers")
async def get_tiers():
    """Get all available subscription tiers."""
    return {"tiers": TIERS}


# ─── Public API — Auth Dependency ─────────────────────────────

async def require_api_key(authorization: str = Header(...)) -> dict:
    """
    Extract and validate API key from Authorization header.
    Expected format: "Bearer nobi_..."
    Returns key info dict on success, raises 401/403 on failure.
    """
    if not api_key_mgr:
        raise HTTPException(status_code=503, detail="API key service not initialized")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header. Expected: Bearer nobi_...")

    api_key = authorization[7:].strip()
    if not api_key.startswith("nobi_"):
        raise HTTPException(status_code=401, detail="Invalid API key format. Keys must start with nobi_")

    key_info = api_key_mgr.validate_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Check rate limit
    allowed, reason = api_key_mgr.check_rate_limit(api_key)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    # Attach raw key for usage recording
    key_info["_raw_key"] = api_key
    return key_info


# ─── Public API — Chat ───────────────────────────────────────

class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


@app.post("/v1/api/chat")
async def public_chat(req: PublicChatRequest, key_info: dict = Depends(require_api_key)):
    """Chat with Nori via the public API."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/chat")

    chat_req = ChatRequest(
        message=req.message,
        user_id=key_info["user_id"],
        conversation_history=req.conversation_history,
    )
    return await chat(chat_req)


# ─── Public API — Memories ───────────────────────────────────

class PublicMemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    memory_type: str = "fact"
    importance: float = 0.5
    tags: List[str] = Field(default_factory=list)


@app.get("/v1/api/memories")
async def public_list_memories(
    search: Optional[str] = None,
    limit: int = 50,
    key_info: dict = Depends(require_api_key),
):
    """List memories via the public API."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/memories")
    return await get_memories(key_info["user_id"], search, limit)


@app.post("/v1/api/memories")
async def public_store_memory(req: PublicMemoryRequest, key_info: dict = Depends(require_api_key)):
    """Store a new memory via the public API."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/memories")

    uid = f"web_{key_info['user_id']}"
    try:
        mem_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(req.tags) if req.tags else "[]"
        conn = memory._conn
        conn.execute(
            """INSERT INTO memories (id, user_id, memory_type, content, importance, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (mem_id, uid, req.memory_type, req.content, req.importance, tags_json, now, now),
        )
        conn.commit()
        return {
            "success": True,
            "memory": {
                "id": mem_id,
                "memory_type": req.memory_type,
                "content": req.content,
                "importance": req.importance,
                "tags": req.tags,
                "created_at": now,
                "updated_at": now,
            },
        }
    except Exception as e:
        logger.error(f"Public store memory error: {e}")
        raise HTTPException(status_code=500, detail="Failed to store memory")


@app.delete("/v1/api/memories/{memory_id}")
async def public_delete_memory(memory_id: str, key_info: dict = Depends(require_api_key)):
    """Delete a memory via the public API."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/memories")
    return await delete_memory(memory_id, key_info["user_id"])


# ─── Public API — Graph ─────────────────────────────────────

@app.get("/v1/api/graph")
async def public_get_graph(key_info: dict = Depends(require_api_key)):
    """Get the relationship graph for the authenticated user."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/graph")

    uid = f"web_{key_info['user_id']}"
    try:
        from nobi.memory.graph import MemoryGraph
        graph = MemoryGraph(db_path=DB_PATH)
        data = graph.export_graph(uid)
        return {"success": True, "graph": data}
    except Exception as e:
        logger.error(f"Graph export error: {e}")
        return {"success": True, "graph": {"entities": [], "relationships": []}}


@app.get("/v1/api/graph/context")
async def public_get_graph_context(
    query: str,
    key_info: dict = Depends(require_api_key),
):
    """Get graph context for a query."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/graph/context")

    uid = f"web_{key_info['user_id']}"
    try:
        from nobi.memory.graph import MemoryGraph
        graph = MemoryGraph(db_path=DB_PATH)
        context = graph.get_context(uid, query)
        return {"success": True, "context": context}
    except Exception as e:
        logger.error(f"Graph context error: {e}")
        return {"success": True, "context": ""}


# ─── Public API — Voice ──────────────────────────────────────

@app.post("/v1/api/voice/transcribe")
async def public_transcribe(request: Request, key_info: dict = Depends(require_api_key)):
    """Transcribe audio to text."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/voice/transcribe")

    try:
        from nobi.voice.stt import transcribe_audio
        body = await request.json()
        audio_data = body.get("audio", "")
        language = body.get("language", "en")
        result = transcribe_audio(audio_data, language=language)
        return {"success": True, "text": result.get("text", ""), "language": result.get("language", language)}
    except Exception as e:
        logger.error(f"Transcribe error: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")


@app.post("/v1/api/voice/synthesize")
async def public_synthesize(request: Request, key_info: dict = Depends(require_api_key)):
    """Synthesize text to speech."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/voice/synthesize")

    try:
        from nobi.voice.tts import synthesize_speech
        body = await request.json()
        text = body.get("text", "")
        voice = body.get("voice", "default")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        result = synthesize_speech(text, voice=voice)
        return {"success": True, "audio": result.get("audio", ""), "format": result.get("format", "mp3")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synthesize error: {e}")
        raise HTTPException(status_code=500, detail="Speech synthesis failed")


# ─── Public API — Key Management ─────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str = "default"


@app.post("/v1/api/keys")
async def public_create_key(req: CreateKeyRequest, key_info: dict = Depends(require_api_key)):
    """Create a new API key for the authenticated user."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/keys")

    # New keys inherit the tier of the creating key
    result = api_key_mgr.create_key(
        user_id=key_info["user_id"],
        name=req.name,
        tier=key_info["tier"],
    )
    return {"success": True, "key": result}


@app.get("/v1/api/keys")
async def public_list_keys(key_info: dict = Depends(require_api_key)):
    """List all API keys for the authenticated user."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/keys")

    keys = api_key_mgr.list_keys(key_info["user_id"])
    return {"success": True, "keys": keys}


@app.delete("/v1/api/keys/{key_prefix}")
async def public_revoke_key(key_prefix: str, key_info: dict = Depends(require_api_key)):
    """Revoke an API key by its prefix."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/keys")

    revoked = api_key_mgr.revoke_key_by_prefix(key_prefix)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key not found or already revoked")
    return {"success": True, "message": f"Key {key_prefix}... revoked"}


@app.get("/v1/api/keys/usage")
async def public_key_usage(days: int = 30, key_info: dict = Depends(require_api_key)):
    """Get usage statistics for the authenticated API key."""
    api_key_mgr.record_usage(key_info["_raw_key"], "/v1/api/keys/usage")

    usage = api_key_mgr.get_usage_by_hash(key_info["key_hash"], days=days)
    return {"success": True, "usage": usage}


# ─── Health ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": llm_client is not None,
        "model": llm_model if llm_client else None,
        "billing_enabled": billing is not None,
        "stripe_configured": stripe_handler.stripe_configured if stripe_handler else False,
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
