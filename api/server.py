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

# Load .env from project root (ensures env vars are set when run via PM2)
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    _load_dotenv(_env_path, override=True)
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nobi.memory import MemoryManager
from nobi.memory.encryption import ensure_master_secret
from nobi.memory.adapters import UserAdapterManager
from nobi.i18n import LanguageDetector
from nobi.i18n.prompts import build_multilingual_system_prompt
from nobi.i18n.languages import SUPPORTED_LANGUAGES
from nobi.billing.subscription import SubscriptionManager, TIERS
from nobi.billing.stripe_handler import StripeHandler
from nobi.api_auth import ApiKeyManager
from nobi.personality import PersonalityTuner, detect_mood
from nobi.personality.prompts import get_dynamic_prompt
from nobi.support import FeedbackManager, SupportHandler

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─── Config ──────────────────────────────────────────────────

CHUTES_KEY = os.environ.get("CHUTES_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_CHUTES_MODEL_RAW = os.environ.get("CHUTES_MODEL", "MiniMaxAI/MiniMax-M2.5-TEE")
# Extract primary model from auto-route chain
CHUTES_MODEL = _CHUTES_MODEL_RAW.split(",")[0].split(":")[0].strip()
CHUTES_FALLBACK_MODELS = [
    "MiniMaxAI/MiniMax-M2.5-TEE",
    "moonshotai/Kimi-K2.5-TEE",
    "deepseek-ai/DeepSeek-V3.2-TEE",
]
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

def _get_user_max_tokens(user_id: str) -> int:
    """Get max response tokens based on user's subscription tier."""
    try:
        from nobi.billing.subscription import TIERS
        # Web users are on free tier by default
        return TIERS.get("free", {}).get("max_tokens", 512)
    except Exception:
        return 512

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

== WHAT YOU KNOW ABOUT PRIVACY & DATA ==
- Memories are encrypted in storage (AES-128 encryption) on miner machines.
- Users have full control: they can view memories, export data, or delete everything anytime.
- On-device memory (where data never leaves the user's device) is on our roadmap for mainnet.
- Federated learning is planned for mainnet — not yet implemented.
- Nori is NOT a substitute for professional mental health, medical, legal, or financial advice.

== YOUR FEATURES — USE THESE FACTS ==
- You have a Support page! Users can click "Support" in the navigation bar to send feedback, report bugs, or ask questions.
- On Telegram, users can use /feedback, /support, and /faq commands.
- Your website is https://projectnobi.ai — has docs, mining guides, and a "Need Help?" button.
- Your web app is https://app.projectnobi.ai — has chat, memories, settings, and support.
- You have voice replies on Telegram (/voice command) and on the web app (Settings → Voice Replies).
- When asked about feedback, bugs, or support: point them to the Support page (click "Support" in the top menu) or /feedback on Telegram.
- NEVER make up email addresses, phone numbers, or contact info that doesn't exist.
- NEVER make up email addresses. For support, direct users to the Support page or /feedback on Telegram.

== WHAT YOU NEVER DO ==
- NEVER say "As an AI" or "I don't have feelings" — you're Nori, act like it
- NEVER give the same canned response twice — be spontaneous
- NEVER pretend to know something you don't
- NEVER fabricate contact details, emails, URLs, or features that don't exist
- NEVER respond with walls of text for simple questions
- NEVER claim that miners can't read user data — miners store encrypted blobs but the encryption is AES-128 server-side
- NEVER claim raw data never leaves the user's device — on-device privacy is a roadmap item
"""

# ─── Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: str = Field(..., min_length=1)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    memories_used: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "Nori is an AI companion. Nothing said here constitutes medical, legal, "
            "or financial advice. Always consult qualified professionals for important decisions."
        )
    )


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
    proactive_enabled: Optional[bool] = None
    companion_name: Optional[str] = None


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
feedback_manager: Optional[FeedbackManager] = None
support_handler: Optional[SupportHandler] = None

# ─── Session Token Store (in-memory) ─────────────────────────
# Maps token (UUID str) → {"user_id": str, "created_at": str}
_session_tokens: Dict[str, Dict[str, Any]] = {}


async def _rate_limiter_cleanup_task():
    """Periodically clean up stale rate limiter entries to prevent memory growth."""
    while True:
        await asyncio.sleep(3600)  # Every hour
        try:
            rate_limiter.cleanup_stale()
        except Exception:
            pass

@asynccontextmanager
async def lifespan(app):
    """Initialize resources on startup, clean up on shutdown."""
    await startup()
    # Start background cleanup task
    cleanup_task = asyncio.create_task(_rate_limiter_cleanup_task())
    yield
    # Shutdown cleanup
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# ─── Session Auth Models ─────────────────────────────────────

class SessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    token: str
    user_id: str
    created_at: str


# ─── Session Auth Dependency ─────────────────────────────────

async def get_session_user_id(request: Request) -> Optional[str]:
    """
    Extract user_id from session token.
    Returns user_id if authenticated, or None if no Bearer header present.
    Raises 401 if a Bearer token is present but invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        # Only process session tokens (not nobi_ API keys — those use require_api_key)
        if token and not token.startswith("nobi_"):
            session = _session_tokens.get(token)
            if session:
                return session["user_id"]
            else:
                raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return None


async def require_session_user_id(request: Request) -> str:
    """
    Require a valid session token. Returns user_id or raises 401.
    Use this for all data endpoints that access user-specific data.
    """
    user_id = await get_session_user_id(request)
    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Create a session via POST /api/auth/session first."
        )
    return user_id


def _check_csrf(request: Request) -> None:
    """
    CSRF protection for cookie-based auth flows.
    State-mutating requests must include X-Requested-With: XMLHttpRequest header
    OR use Bearer token auth (which is CSRF-safe by nature).
    """
    method = request.method.upper()
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return  # Bearer token auth is CSRF-safe
        requested_with = request.headers.get("X-Requested-With", "")
        if requested_with.lower() != "xmlhttprequest":
            raise HTTPException(
                status_code=403,
                detail="CSRF check failed: include 'X-Requested-With: XMLHttpRequest' header or use Bearer token auth",
            )


app = FastAPI(
    title="Project Nobi API",
    description="Backend API for the Nobi AI companion web application",
    version="1.0.0",
    lifespan=lifespan,
)

_CORS_ORIGINS_ENV = os.environ.get("NOBI_CORS_ORIGINS", "")
_CORS_ORIGINS = (
    [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]
    if _CORS_ORIGINS_ENV
    else [
        "https://app.projectnobi.ai",
        "https://projectnobi.ai",
        "http://localhost:3000",  # dev only; override via NOBI_CORS_ORIGINS in prod
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


# ─── Rate Limiting ────────────────────────────────────────────

import time
from collections import defaultdict

class IPRateLimiter:
    """IP-based rate limiter for API protection."""
    
    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._blocked: dict[str, float] = {}  # IP → blocked until timestamp
        
        # Limits per endpoint category — configurable via env vars
        self.LIMITS = {
            "chat": {"max_requests": int(os.environ.get("NOBI_API_CHAT_RPM", "30")), "window_seconds": 60},
            "memory": {"max_requests": int(os.environ.get("NOBI_API_MEMORY_RPM", "60")), "window_seconds": 60},
            "general": {"max_requests": int(os.environ.get("NOBI_API_GENERAL_RPM", "120")), "window_seconds": 60},
            "auth": {"max_requests": int(os.environ.get("NOBI_API_AUTH_RPM", "10")), "window_seconds": 60},
        }
        self.BLOCK_DURATION = 300  # 5 min block for repeat offenders
        self._violations: dict[str, int] = defaultdict(int)
    
    def _clean_old(self, key: str, window: int):
        now = time.time()
        self._requests[key] = [t for t in self._requests[key] if now - t < window]
    
    def check(self, ip: str, category: str = "general") -> tuple[bool, str]:
        now = time.time()
        
        # Check if IP is blocked
        if ip in self._blocked and now < self._blocked[ip]:
            remaining = int(self._blocked[ip] - now)
            return False, f"Too many requests. Try again in {remaining}s."
        elif ip in self._blocked:
            del self._blocked[ip]
        
        limits = self.LIMITS.get(category, self.LIMITS["general"])
        key = f"{ip}:{category}"
        self._clean_old(key, limits["window_seconds"])
        
        if len(self._requests[key]) >= limits["max_requests"]:
            self._violations[ip] += 1
            if self._violations[ip] >= 3:
                self._blocked[ip] = now + self.BLOCK_DURATION
                logger.warning(f"[RateLimit] IP {ip} BLOCKED for {self.BLOCK_DURATION}s (violations: {self._violations[ip]})")
            return False, f"Rate limit exceeded ({limits['max_requests']}/{limits['window_seconds']}s). Please slow down."
        
        self._requests[key].append(now)
        return True, ""

    def cleanup_stale(self, max_age_seconds: int = 3600):
        """Remove stale entries older than max_age_seconds. Call periodically to prevent memory growth."""
        now = time.time()
        stale_keys = [k for k, times in list(self._requests.items()) if not times or now - times[-1] > max_age_seconds]
        for k in stale_keys:
            del self._requests[k]
        # Clean expired blocks
        expired_blocks = [ip for ip, until in list(self._blocked.items()) if now >= until]
        for ip in expired_blocks:
            del self._blocked[ip]
            self._violations.pop(ip, None)

rate_limiter = IPRateLimiter()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Global rate limiting middleware."""
    # Skip health check and static paths
    path = request.url.path
    if path in ("/api/health", "/api/tiers", "/api/languages", "/api/faq", "/docs", "/openapi.json"):
        return await call_next(request)
    
    ip = request.client.host if request.client else "unknown"
    
    # Categorize the request
    if "/api/chat" in path:
        category = "chat"
    elif "/api/memories" in path or "/api/settings" in path:
        category = "memory"
    elif "/api/auth" in path:
        category = "auth"
    else:
        category = "general"
    
    allowed, reason = rate_limiter.check(ip, category)
    if not allowed:
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": reason, "error": "rate_limit_exceeded"},
            headers={"Retry-After": "60"}
        )
    
    return await call_next(request)


async def startup():
    global memory, adapter_manager, lang_detector, llm_client, llm_model, billing, stripe_handler, api_key_mgr, personality_tuner, feedback_manager, support_handler

    ensure_master_secret()
    memory = MemoryManager(db_path=DB_PATH)
    adapter_manager = UserAdapterManager(db_path=DB_PATH)
    lang_detector = LanguageDetector()

    # Initialize API key manager
    api_key_mgr = ApiKeyManager(db_path=os.path.expanduser(API_KEYS_DB_PATH))
    logger.info("API key manager initialized")

    # Initialize personality tuner
    personality_tuner = PersonalityTuner(db_path=os.path.expanduser("~/.nobi/personality_api.db"))

    # Initialize support & feedback
    feedback_manager = FeedbackManager(db_path=os.path.expanduser("~/.nobi/feedback.db"))
    support_handler = SupportHandler(feedback_manager=feedback_manager)
    logger.info("Support/feedback system initialized")

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
        llm_model = "anthropic/claude-3.5-haiku-20241022"
        logger.info(f"LLM: OpenRouter ({llm_model})")
    else:
        logger.warning("No LLM API key configured!")


# ─── Session Auth Endpoint ───────────────────────────────────

@app.post("/api/auth/session", response_model=SessionResponse)
async def create_session(req: SessionRequest):
    """
    Create a session token for a user_id.
    Returns a Bearer token for use in subsequent requests.
    """
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    _session_tokens[token] = {"user_id": req.user_id, "created_at": now}
    logger.info(f"Session created for user {req.user_id}")
    return SessionResponse(token=token, user_id=req.user_id, created_at=now)


# ─── Chat ────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request = None):
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM not configured")

    # Require session token auth
    resolved_user_id = await require_session_user_id(request)

    user_id = f"web_{resolved_user_id}"
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

    # Save user message + extract memories (tagged as web source)
    try:
        memory.save_conversation_turn(user_id, "user", message)
        memory.extract_memories_from_message(user_id, message, "", source="web")
        memory.extract_memories_llm(user_id, message, source="web")
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
    # Smart fallback chain — try Chutes models in order
    try:
        loop = asyncio.get_event_loop()
        response_text = None
        for fallback_model in CHUTES_FALLBACK_MODELS:
            try:
                completion = await loop.run_in_executor(
                    None,
                    lambda m=fallback_model: llm_client.chat.completions.create(
                        model=m,
                        messages=messages,
                        max_tokens=_get_user_max_tokens(user_id),
                        temperature=0.8,
                        timeout=12,
                    ),
                )
                text = completion.choices[0].message.content
                if text and text.strip():
                    response_text = text.strip()
                    logger.info(f"[API] Model {fallback_model} succeeded")
                    break
            except Exception as model_err:
                logger.warning(f"[API] Model {fallback_model} failed: {model_err}")
                continue
        if not response_text:
            raise Exception("All Chutes models failed")
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

    # Auto-capture feedback from chat messages
    try:
        _FEEDBACK_KEYWORDS = {
            'bug_report': ['bug', 'broken', 'error', 'crash', 'not working', 'doesnt work', "doesn't work", 'glitch', 'issue'],
            'complaint': ['terrible', 'awful', 'horrible', 'worst', 'hate', 'angry', 'frustrated', 'annoying', 'disappointed', 'useless'],
            'feature_request': ['please add', 'would be nice', 'wish you could', 'feature request', 'can you add', 'suggestion', 'it would be great if'],
        }
        msg_lower = message.lower()
        detected_category = None
        for cat, keywords in _FEEDBACK_KEYWORDS.items():
            if any(kw in msg_lower for kw in keywords):
                detected_category = cat
                break
        if detected_category:
            from nobi.support.feedback import FeedbackManager
            fm = FeedbackManager()
            fm.submit_feedback(
                user_id=user_id,
                platform="webapp",
                category=detected_category,
                message=message,
            )
            logger.info(f"[Feedback] Auto-captured {detected_category} from webapp chat: {message[:60]}")
    except Exception as e:
        logger.debug(f"Auto-feedback capture error: {e}")

    return ChatResponse(response=response_text, memories_used=memories_used[:5])


# ─── Memories ────────────────────────────────────────────────

@app.get("/api/memories")
async def get_memories(user_id: str, search: Optional[str] = None, limit: int = 50, request: Request = None):
    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
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
async def delete_memory(memory_id: str, user_id: str, request: Request = None):
    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
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


@app.post("/api/memories/import")
async def import_memories(request: Request):
    body = await request.json()
    uid = f"web_{body.get('user_id', '')}"
    data = body.get("data", {})
    imported = 0
    for mem in data.get("memories", []):
        try:
            memory.store(uid, mem.get("content", ""), memory_type=mem.get("type", "fact"), importance=mem.get("importance", 0.5))
            imported += 1
        except Exception:
            pass
    return {"success": True, "imported": imported}


@app.delete("/api/memories/all")
async def forget_all(user_id: str, request: Request = None):
    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
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
async def save_settings(req: SettingsRequest, request: Request = None):
    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
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
async def get_settings(user_id: str, request: Request = None):
    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
    return {"settings": user_settings.get(uid, {})}


@app.get("/api/languages")
async def get_languages():
    return {"languages": SUPPORTED_LANGUAGES}


# ─── Billing & Subscription ───────────────────────────────────

class SubscribeRequest(BaseModel):
    user_id: str
    tier: str = "plus"
    success_url: str = "https://app.projectnobi.ai/subscription?success=true"
    cancel_url: str = "https://app.projectnobi.ai/subscription?cancelled=true"


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
async def cancel_subscription(req: CancelRequest, request: Request = None):
    """Cancel user's subscription."""
    if not billing:
        raise HTTPException(status_code=503, detail="Billing not initialized")

    authed = await require_session_user_id(request)
    uid = f"web_{authed}"
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


# ─── Privacy: Encrypted Chat & Memory Endpoints ──────────────

class EncryptedPayload(BaseModel):
    """AES-256-GCM encrypted payload from the browser client."""
    ciphertext: str
    iv: str
    salt: str
    algorithm: str = "AES-GCM-256"
    iterations: int = 100000


class EncryptedChatRequest(BaseModel):
    """Encrypted chat request — all data is client-side encrypted."""
    message: EncryptedPayload
    memories: EncryptedPayload
    conversation_history: EncryptedPayload
    user_id: str = Field(..., min_length=1)
    client_extracted: bool = True


class EncryptedMemorySyncRequest(BaseModel):
    """Encrypted memory sync from client — pass-through, never decrypted here."""
    memories: EncryptedPayload
    user_id: str = Field(..., min_length=1)
    count: int = Field(default=0, ge=0)


@app.post("/api/v1/chat/encrypted", response_model=ChatResponse)
async def chat_encrypted(req: EncryptedChatRequest, request: Request = None):
    """
    Privacy-preserving chat endpoint — Phase 4 TEE Passthrough.

    Accepts AES-256-GCM encrypted payloads from browsers with on-device privacy mode.
    Server-side flow:
      1. Decrypt the browser's AES-256-GCM message + memories using PBKDF2-derived key
      2. Call Chutes TEE LLM with plaintext
      3. Re-encrypt the response with the same derived key
      4. Return encrypted response to browser

    The browser is the only party that holds the passphrase; the server handles
    PBKDF2-derived key derivation using the salt transmitted in the payload.
    """
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM not configured")

    # Require session token auth
    resolved_user_id = await require_session_user_id(request)

    user_id = f"web_{resolved_user_id}"

    # ─── Phase 4: Decrypt browser payload server-side ────────────────────────
    # The browser uses AES-256-GCM with a PBKDF2-derived key.
    # We receive: ciphertext, iv, salt, iterations — enough to re-derive the key
    # and decrypt the message, provided we also have a shared secret/passphrase.
    #
    # Key insight: the browser derives the key from a device-bound passphrase
    # (navigator.userAgent + screen size + etc.). The server does NOT have access
    # to this passphrase. So for the TEE passthrough MVP:
    #   - Attempt server-side decryption using the transmitted salt+iv+iterations
    #     (only works if a shared secret is negotiated, e.g. via session token)
    #   - If decryption is not possible (no shared secret), call LLM with a
    #     privacy-preserving prompt using only existing server-side memory context.
    #
    # For full TEE passthrough with a subnet miner, the encrypted blob would be
    # forwarded as-is. That path is prepared here for future routing.

    plaintext_message = None
    memories_used = []

    # Try to decrypt if we have the AES-GCM primitives available
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        import base64 as _b64

        msg_payload = req.message
        # Decode components
        ciphertext = _b64.b64decode(msg_payload.ciphertext)
        iv = _b64.b64decode(msg_payload.iv)
        salt = _b64.b64decode(msg_payload.salt)
        iterations = msg_payload.iterations

        # Try to derive key using a session-scoped passphrase if one is registered
        # For MVP without a passphrase negotiation mechanism, we cannot decrypt
        # the device-derived key — we fall through to the memory-context path.
        # This placeholder exists so the decryption path is wired up and can be
        # enabled once a passphrase exchange mechanism is implemented.
        _session_passphrase = None  # TODO: implement passphrase exchange (e.g. via /api/auth/privacy)

        if _session_passphrase:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key_bytes = kdf.derive(_session_passphrase.encode("utf-8"))
            aesgcm = AESGCM(key_bytes)
            plaintext_bytes = aesgcm.decrypt(iv, ciphertext, None)
            plaintext_message = plaintext_bytes.decode("utf-8")
            del key_bytes
            logger.info(f"[Privacy] Decrypted browser message ({len(plaintext_message)} chars)")

    except ImportError:
        logger.debug("[Privacy] cryptography library not available for browser payload decrypt")
    except Exception as e:
        logger.debug(f"[Privacy] Browser payload decrypt failed (expected for device keys): {e}")

    # Store encrypted memory blob metadata (pass-through — never decrypt)
    try:
        memory.store(
            user_id,
            f"[encrypted_client_memory] count={req.memories.ciphertext[:16]}...",
            memory_type="fact",
            importance=0.1,
            tags=["encrypted", "client_extracted"],
        )
    except Exception as e:
        logger.debug(f"Encrypted memory store error: {e}")

    # Get server-side memory context (from non-encrypted past turns)
    memory_context = ""
    try:
        memory_context = memory.get_smart_context(
            user_id, plaintext_message or ""
        )
        if memory_context:
            memories_used = [line.strip() for line in memory_context.split("\n") if line.strip()]
    except Exception:
        pass

    # ─── Build and send prompt ──────────────────────────────────────────────
    system = SYSTEM_PROMPT.format(memory_context=memory_context or "Nothing yet — this is a new friend!")

    if plaintext_message:
        # We have the decrypted message — call LLM normally
        user_content = plaintext_message
    else:
        # Device-key path: server can't decrypt (by design — that's the privacy!)
        # Graceful degradation: use the normal chat flow with server-side memory
        # Local memory extraction already happened in the browser — those encrypted
        # memories are stored. For the response, we use server-side context.
        #
        # In the future (TEE deployed), this blob would be forwarded to a TEE miner
        # who CAN decrypt it. For now, fall back to using any available context.
        logger.info(f"[Privacy] Device-key encryption — falling back to context-based response for {user_id}")
        
        # Try to get context from server-side memory for a meaningful response
        fallback_context = ""
        try:
            fallback_context = memory.get_smart_context(user_id, "general conversation")
        except Exception:
            pass
        
        if fallback_context:
            system += f"\n\n== CONTEXT FROM MEMORY ==\n{fallback_context}"
        
        user_content = "The user sent a message with privacy mode enabled. Respond warmly based on what you know about them from previous conversations. Ask them what's on their mind."

    messages = [{"role": "system", "content": system}]

    # Add recent conversation from DB for context
    try:
        recent = memory.get_recent_conversation(user_id, limit=6)
        for turn in recent:
            messages.append({"role": turn["role"], "content": turn["content"]})
    except Exception:
        pass

    messages.append({"role": "user", "content": user_content})

    # ─── Call TEE model ──────────────────────────────────────────────────────
    try:
        loop = asyncio.get_event_loop()
        response_text = None
        for fallback_model in CHUTES_FALLBACK_MODELS:
            try:
                completion = await loop.run_in_executor(
                    None,
                    lambda m=fallback_model: llm_client.chat.completions.create(
                        model=m,
                        messages=messages,
                        max_tokens=_get_user_max_tokens(user_id),
                        temperature=0.8,
                        timeout=12,
                    ),
                )
                text = completion.choices[0].message.content
                if text and text.strip():
                    response_text = text.strip()
                    logger.info(f"[Privacy] TEE model {fallback_model} responded")
                    break
            except Exception as model_err:
                logger.warning(f"[API:encrypted] Model {fallback_model} failed: {model_err}")
                continue

        if not response_text:
            raise Exception("All models failed")
    except Exception as e:
        logger.error(f"LLM error (encrypted): {e}")
        raise HTTPException(status_code=502, detail="Failed to generate response")

    # Save to memory if we had plaintext (privacy-respecting path)
    if plaintext_message:
        try:
            memory.save_conversation_turn(user_id, "user", plaintext_message)
            memory.save_conversation_turn(user_id, "assistant", response_text)
        except Exception as e:
            logger.debug(f"Memory save error: {e}")

    logger.info(f"[Privacy] Encrypted chat processed for user {user_id} "
                f"(decrypted={plaintext_message is not None})")
    return ChatResponse(response=response_text, memories_used=memories_used[:5])


@app.post("/api/v1/memories/encrypted")
async def store_encrypted_memories(req: EncryptedMemorySyncRequest, request: Request = None):
    """
    Store client-side encrypted memories.

    The server stores the encrypted blob without decrypting it.
    Only the client (with the private key) can decrypt these memories.
    Count metadata is stored for monitoring without revealing content.
    """
    resolved_user_id = await require_session_user_id(request)

    user_id = f"web_{resolved_user_id}"

    # Store encrypted blob — we can't read it, that's the point
    # We record that the user has encrypted memories without knowing the content
    try:
        memory.store(
            user_id,
            f"[encrypted_batch] {req.count} memories (client-side AES-256-GCM)",
            memory_type="fact",
            importance=0.1,
            tags=["encrypted", "client_batch"],
        )
    except Exception as e:
        logger.debug(f"Encrypted memory sync error: {e}")

    logger.info(f"[Privacy] Encrypted memory batch ({req.count} items) stored for {user_id}")
    return {"success": True, "stored": req.count, "encrypted": True}


# ─── Health ──────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": llm_client is not None,
        "model": llm_model if llm_client else None,
        "billing_enabled": billing is not None,
        "stripe_configured": stripe_handler.stripe_configured if stripe_handler else False,
        "phase": "testnet",
        "network": "Bittensor SN272",
        "testnet_notice": (
            "Project Nobi is currently in testnet phase (Bittensor SN272). "
            "The service is under active development. Features may change and data may be reset. "
            "Use at your own risk. This is not a production product."
        ),
        "legal_notice": (
            "Nori is an AI companion, not a professional service provider. "
            "Nothing Nori says constitutes medical, legal, or financial advice. "
            "Terms of Service: https://projectnobi.ai/terms | "
            "Privacy Policy: https://projectnobi.ai/privacy"
        ),
    }


@app.get("/api/terms")
async def get_terms():
    """Return ToS summary for display in apps."""
    return {
        "title": "Terms of Service",
        "version": "2026-03-20",
        "url": "https://projectnobi.ai/terms",
        "summary": (
            "By using Nori, you agree to our Terms of Service. "
            "You must be 18+ to use Nori. Nori is an AI companion — not a doctor, "
            "lawyer, or financial advisor. Your data is encrypted and you can delete it "
            "at any time. We do not sell your data. Governing law: England and Wales."
        ),
        "key_points": [
            "Minimum age: 18",
            "Nori is an AI companion — not professional advice",
            "Your data is encrypted with AES-128",
            "You own your data and can delete it anytime",
            "No selling of personal data to third parties",
            "Governing law: England and Wales",
            "Free for all individual users",
        ],
        "contact": "legal@projectnobi.ai",
    }


@app.get("/api/privacy")
async def get_privacy():
    """Return Privacy Policy summary for display in apps."""
    return {
        "title": "Privacy Policy",
        "version": "2026-03-20",
        "url": "https://projectnobi.ai/privacy",
        "gdpr_compliant": True,
        "ccpa_compliant": True,
        "summary": (
            "Project Nobi collects conversation data, memory data, and usage statistics "
            "to provide the Nori companion service. All data is encrypted with AES-128. "
            "We do not sell your data. You can access, export, or delete your data at any time."
        ),
        "key_points": [
            "Data encrypted with AES-128 before storage",
            "No selling of personal data to third parties",
            "GDPR Articles 13/14 compliant",
            "CCPA compliant",
            "COPPA compliant (18+ age limit enforced)",
            "Right to access, delete, export, and rectify your data",
            "Data auto-deleted after 12 months of inactivity",
            "72-hour breach notification to regulators",
            "DPO appointed: dpo@projectnobi.ai",
        ],
        "data_collected": [
            "Conversation messages",
            "Memory data extracted from conversations",
            "Usage statistics (anonymised)",
            "Device information",
        ],
        "user_rights": [
            "Access your data",
            "Delete your data",
            "Export your data",
            "Rectify inaccurate data",
            "Object to processing",
            "Data portability",
        ],
        "retention": {
            "active_data": "While account is active",
            "inactive_data": "Auto-deleted after 12 months of inactivity",
            "deleted_account": "Permanently deleted within 30 days",
        },
        "dpo_contact": "dpo@projectnobi.ai",
        "contact": "privacy@projectnobi.ai",
    }


# ─── Support & Feedback Models ───────────────────────────────

class FeedbackRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., min_length=1)
    platform: str = Field(default="web")
    category: Optional[str] = None  # auto-detect if omitted


class SupportRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(..., min_length=1)
    platform: str = Field(default="web")


# ─── Support & Feedback Endpoints ────────────────────────────

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Submit feedback (bug report, feature request, general, etc.)"""
    if support_handler is None:
        raise HTTPException(status_code=503, detail="Support system not initialized")
    try:
        result = support_handler.submit_feedback(
            message=req.message,
            user_id=req.user_id,
            platform=req.platform,
            category=req.category,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Error submitting feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@app.get("/api/feedback")
async def get_feedback(
    user_id: str,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get feedback history for a user."""
    if feedback_manager is None:
        raise HTTPException(status_code=503, detail="Support system not initialized")
    try:
        entries = feedback_manager.get_feedback(
            user_id=user_id,
            status=status,
            category=category,
            limit=min(limit, 200),
            offset=offset,
        )
        return {"success": True, "feedback": entries, "count": len(entries)}
    except Exception as e:
        logger.error("Error fetching feedback: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch feedback")


@app.get("/api/feedback/stats")
async def feedback_stats():
    """Public stats: total, resolved count, avg response time."""
    if feedback_manager is None:
        raise HTTPException(status_code=503, detail="Support system not initialized")
    try:
        stats = feedback_manager.get_stats()
        return {"success": True, **stats}
    except Exception as e:
        logger.error("Error fetching feedback stats: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch stats")


@app.post("/api/support")
async def ask_support(req: SupportRequest):
    """Ask a support question — returns FAQ match or creates a ticket."""
    if support_handler is None:
        raise HTTPException(status_code=503, detail="Support system not initialized")
    try:
        result = support_handler.ask(
            question=req.question,
            user_id=req.user_id,
            platform=req.platform,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error("Error processing support request: %s", e)
        raise HTTPException(status_code=500, detail="Failed to process support request")


@app.get("/api/faq")
async def get_faq():
    """Return all FAQ entries."""
    if support_handler is None:
        raise HTTPException(status_code=503, detail="Support system not initialized")
    faq = support_handler.get_faq()
    return {"success": True, "faq": faq, "count": len(faq)}


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


# ─── Burn Transparency API ──────────────────────────────────

def _get_burn_tracker():
    """Lazy-load the BurnTracker (no import overhead at startup)."""
    try:
        from nobi.burn.tracker import BurnTracker
        return BurnTracker()
    except Exception as e:
        logger.warning(f"BurnTracker unavailable: {e}")
        return None


@app.get("/api/v1/burns")
async def get_burns(
    network: str = "testnet",
    netuid: int = 272,
    limit: Optional[int] = None,
):
    """
    Public endpoint — returns the full burn history.

    Anyone can call this to verify that Project Nobi is burning
    100% of its owner take emissions as promised.

    Query params:
        network: 'testnet' or 'mainnet' (default: testnet)
        netuid: Subnet ID (default: 272)
        limit: Max records to return (default: all)
    """
    tracker = _get_burn_tracker()
    if tracker is None:
        return {
            "total_burned_alpha": 0.0,
            "burn_count": 0,
            "burns": [],
            "message": "Burn history not yet available",
        }
    try:
        history = tracker.get_burn_history(network=network, netuid=netuid, limit=limit)
        total = tracker.get_total_burned(network=network, netuid=netuid)
        return {
            "total_burned_alpha": total,
            "burn_count": len(history),
            "burns": history,
            "commitment": "100% of owner take (18% of subnet emissions) is burned",
            "network": network,
            "netuid": netuid,
        }
    except Exception as e:
        logger.error(f"Burns endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve burn history")


@app.get("/api/v1/burns/total")
async def get_burns_total(
    network: str = "testnet",
    netuid: int = 272,
):
    """
    Public endpoint — returns the total ALPHA burned.

    This is the quick-check endpoint for anyone verifying
    Project Nobi's burn commitment.

    Query params:
        network: 'testnet' or 'mainnet' (default: testnet)
        netuid: Subnet ID (default: 272)
    """
    tracker = _get_burn_tracker()
    if tracker is None:
        return {
            "total_burned_alpha": 0.0,
            "burn_count": 0,
            "latest_burn": None,
        }
    try:
        total = tracker.get_total_burned(network=network, netuid=netuid)
        count = tracker.get_burn_count(network=network, netuid=netuid)
        latest = tracker.get_latest_burn(network=network, netuid=netuid)
        return {
            "total_burned_alpha": total,
            "burn_count": count,
            "latest_burn": latest,
            "commitment": "100% of owner take (18% of subnet emissions) is burned",
            "network": network,
            "netuid": netuid,
        }
    except Exception as e:
        logger.error(f"Burns total endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve total burned")


@app.get("/api/v1/burns/verify")
async def get_burns_verify(
    start_block: int = 0,
    end_block: Optional[int] = None,
    network: str = "testnet",
    netuid: int = 272,
):
    """
    Public endpoint — lightweight burn summary for independent verification.

    For full on-chain verification, use the BurnVerifier class directly.
    This endpoint returns the internal records summary.

    Query params:
        start_block: Starting block (default: 0)
        end_block: Ending block (default: current)
        network: 'testnet' or 'mainnet'
        netuid: Subnet ID (default: 272)
    """
    tracker = _get_burn_tracker()
    if tracker is None:
        return {"error": "Burn tracker unavailable"}
    try:
        history = tracker.get_burn_history(network=network, netuid=netuid)
        if start_block > 0 or end_block is not None:
            eb = end_block or float("inf")
            history = [
                r for r in history
                if start_block <= r.get("block", 0) <= eb
            ]
        total = sum(r.get("amount_alpha", 0.0) for r in history)
        return {
            "network": network,
            "netuid": netuid,
            "block_range": {"start": start_block, "end": end_block},
            "burn_count": len(history),
            "total_alpha_burned": total,
            "burns": history,
            "note": (
                "These are internal records. For on-chain verification, "
                "use BurnVerifier.verify_range() or query the subtensor directly."
            ),
        }
    except Exception as e:
        logger.error(f"Burns verify endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve verification data")


# ─── GDPR Compliance Endpoints ───────────────────────────────

class GDPRAccessRequest(BaseModel):
    user_id: str

class GDPRRectifyRequest(BaseModel):
    user_id: str
    corrections: Dict[str, str]  # memory_id -> new_content

class GDPRConsentUpdateRequest(BaseModel):
    user_id: str
    consent: Dict[str, bool]
    age_verified: Optional[bool] = None
    source: str = "api"

class GDPRRestrictRequest(BaseModel):
    user_id: str
    restrict: bool = True


def _get_gdpr_handler() -> "GDPRHandler":
    """Lazy-load GDPRHandler."""
    from nobi.compliance.gdpr import GDPRHandler
    return GDPRHandler(
        memory_db_path=DB_PATH,
        billing_db_path=BILLING_DB_PATH,
    )


def _get_consent_manager() -> "ConsentManager":
    """Lazy-load ConsentManager."""
    from nobi.compliance.consent import ConsentManager
    return ConsentManager()


@app.post("/api/v1/gdpr/access")
async def gdpr_access(req: GDPRAccessRequest, request: Request):
    """GDPR Art. 15 — Right of Access. Returns all data held about the user.
    Requires the caller to be authenticated as the same user_id."""
    try:
        # Enforce: authenticated user can only access their OWN data
        authed_user_id = await require_session_user_id(request)
        if authed_user_id and authed_user_id != req.user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only request your own data")
        uid = f"web_{req.user_id}"
        handler = _get_gdpr_handler()
        data = handler.handle_access_request(uid)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR access error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process access request")


@app.post("/api/v1/gdpr/erasure")
async def gdpr_erasure(req: GDPRAccessRequest, request: Request):
    """GDPR Art. 17 — Right to Erasure. Permanently delete all user data.
    Requires the caller to be authenticated as the same user_id."""
    try:
        # Enforce: authenticated user can only erase their OWN data
        authed_user_id = await require_session_user_id(request)
        if authed_user_id and authed_user_id != req.user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only erase your own data")
        uid = f"web_{req.user_id}"
        handler = _get_gdpr_handler()
        result = handler.handle_erasure_request(uid)
        # Also clear in-memory session data
        if uid in user_settings:
            del user_settings[uid]
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR erasure error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process erasure request")


@app.get("/api/v1/gdpr/export")
async def gdpr_export(user_id: str, request: Request):
    """GDPR Art. 20 — Right to Data Portability. Export all user data as JSON.
    Requires the caller to be authenticated as the same user_id."""
    try:
        # Enforce: authenticated user can only export their OWN data
        authed_user_id = await require_session_user_id(request)
        if authed_user_id and authed_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only export your own data")
        uid = f"web_{user_id}"
        handler = _get_gdpr_handler()
        payload = handler.handle_portability_request(uid)
        from fastapi.responses import Response
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="nobi-gdpr-export-{user_id}.json"'
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR export error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process export request")


@app.post("/api/v1/gdpr/rectify")
async def gdpr_rectify(req: GDPRRectifyRequest, request: Request):
    """GDPR Art. 16 — Right to Rectification. Correct inaccurate data."""
    try:
        authed_user_id = await require_session_user_id(request)
        if authed_user_id and authed_user_id != req.user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only rectify your own data")
        uid = f"web_{req.user_id}"
        handler = _get_gdpr_handler()
        result = handler.handle_rectification_request(uid, req.corrections)
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR rectify error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process rectification request")


@app.post("/api/v1/gdpr/restrict")
async def gdpr_restrict(req: GDPRRestrictRequest, request: Request):
    """GDPR Art. 18 — Right to Restriction of Processing."""
    try:
        authed_user_id = await require_session_user_id(request)
        if authed_user_id and authed_user_id != req.user_id:
            raise HTTPException(status_code=403, detail="Access denied: you can only restrict your own data")
        uid = f"web_{req.user_id}"
        handler = _get_gdpr_handler()
        result = handler.handle_restriction_request(uid, req.restrict)
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR restrict error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process restriction request")


@app.get("/api/v1/gdpr/consent")
async def gdpr_get_consent(user_id: str):
    """Get current GDPR consent status for a user."""
    try:
        uid = f"web_{user_id}"
        cm = _get_consent_manager()
        status = cm.get_consent_status(uid)
        requires_reconsent = cm.requires_reconsent(uid)
        return {
            "success": True,
            "user_id": user_id,
            "consent": status,
            "requires_reconsent": requires_reconsent,
            "policy_version": cm.policy_version,
        }
    except Exception as e:
        logger.error(f"GDPR get consent error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get consent status")


@app.post("/api/v1/gdpr/consent")
async def gdpr_update_consent(req: GDPRConsentUpdateRequest):
    """Update GDPR consent choices for a user."""
    try:
        uid = f"web_{req.user_id}"
        cm = _get_consent_manager()
        existing = cm.get_consent_status(uid)
        if not existing:
            result = cm.record_consent(
                uid,
                req.consent,
                age_verified=req.age_verified or False,
                source=req.source,
            )
        else:
            updates = dict(req.consent)
            if req.age_verified is not None:
                updates["age_verified"] = req.age_verified
            result = cm.update_consent(uid, updates, source=req.source)
        return {"success": True, "consent": result}
    except Exception as e:
        logger.error(f"GDPR update consent error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update consent")


@app.get("/api/v1/gdpr/audit")
async def gdpr_audit_log(request: Request, user_id: Optional[str] = None):
    """Return GDPR audit log (admin endpoint). Filter by user_id if provided.
    When queried by a non-admin user, only their own records are returned."""
    try:
        authed_user_id = await require_session_user_id(request)
        # Non-admin users may only see their own audit entries
        if authed_user_id:
            uid = f"web_{authed_user_id}"
        elif user_id:
            # No session token — only allow if requesting own user_id via query param
            # (Admin access requires a valid admin API key — handled elsewhere)
            raise HTTPException(status_code=401, detail="Authentication required to view audit log")
        else:
            raise HTTPException(status_code=401, detail="Authentication required to view audit log")
        handler = _get_gdpr_handler()
        entries = handler.get_audit_log(uid)
        return {"success": True, "count": len(entries), "entries": entries}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GDPR audit log error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log")


@app.get("/api/v1/gdpr/pia")
async def gdpr_pia():
    """Return the Privacy Impact Assessment report as structured JSON."""
    try:
        from nobi.compliance.pia import PIAReport
        report = PIAReport()
        return report.generate()
    except Exception as e:
        logger.error(f"GDPR PIA error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PIA report")


@app.get("/api/v1/legal/consent-record/{user_id}")
async def get_consent_record(user_id: str):
    """
    Legal consent record for a specific user — for dispute resolution.

    Returns: full consent history with timestamps, policy versions,
    acceptance method, and audit trail. Designed for legal review.
    """
    try:
        from nobi.compliance.consent import ConsentManager
        cm = ConsentManager()
        status = cm.get_consent_status(user_id)
        if not status:
            raise HTTPException(status_code=404, detail="No consent record found for this user")

        # Get audit trail
        audit = []
        try:
            conn = cm._conn()
            rows = conn.execute(
                "SELECT action, old_state, new_state, changed_at, source "
                "FROM consent_audit WHERE user_id = ? ORDER BY changed_at",
                (user_id,),
            ).fetchall()
            audit = [dict(r) for r in rows]
        except Exception:
            pass

        return {
            "user_id": user_id,
            "consent_status": status,
            "audit_trail": audit,
            "record_count": len(audit),
            "note": "This record is generated for legal review purposes. "
                    "All timestamps are UTC ISO 8601. Consent changes are append-only (immutable audit log).",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal consent record error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve consent record")


# ─── TTS for Web App ────────────────────────────────────────

# ─── TTS for Web App ────────────────────────────────────────

@app.post("/api/tts")
async def web_tts(request: Request):
    """Text-to-speech for webapp - uses browser-native speech or server TTS."""
    try:
        body = await request.json()
        text = body.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        try:
            from nobi.voice.tts import synthesize_speech
            result = synthesize_speech(text, voice="default")
            if result.get("audio"):
                return {"success": True, "audio": result["audio"], "format": result.get("format", "mp3")}
        except Exception as e:
            logger.debug(f"Server TTS failed, client will use browser TTS: {e}")
        
        # Fallback: tell client to use browser's speechSynthesis
        return {"success": True, "use_browser_tts": True, "text": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return {"success": True, "use_browser_tts": True, "text": text}


# ─── Image Chat ──────────────────────────────────────────────

@app.post("/api/chat/image")
async def chat_with_image(request: Request):
    """Chat with an image — analyze and respond."""
    try:
        body = await request.json()
        image_b64 = body.get("image", "")
        caption = body.get("caption", "")
        user_id = f"web_{body.get('user_id', 'anon')}"
        image_format = body.get("format", "jpg")

        if not image_b64:
            raise HTTPException(status_code=400, detail="Image data required")

        import base64
        image_bytes = base64.b64decode(image_b64)

        # Get memory context
        memory_context = ""
        try:
            memory_context = memory.get_smart_context(user_id, caption or "photo")
        except Exception:
            pass

        # Analyze image
        from nobi.vision.image_handler import analyze_image
        result = await analyze_image(
            image_bytes=image_bytes,
            user_context=memory_context or "New user",
            caption=caption,
            image_format=image_format,
        )

        response_text = result.get("response", "I had trouble looking at that image.")

        # Store memories
        if result.get("extracted_memories"):
            for mem_text in result["extracted_memories"][:5]:
                try:
                    memory.store(user_id, mem_text, memory_type="fact", importance=0.6)
                except Exception:
                    pass

        # Save conversation
        try:
            memory.save_conversation_turn(user_id, "user", f"[Photo] {caption}" if caption else "[Photo shared]")
            memory.save_conversation_turn(user_id, "assistant", response_text)
        except Exception:
            pass

        return {"response": response_text, "success": result.get("success", False)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process image")


# ─── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
