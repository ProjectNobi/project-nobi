"""
Nobi Text-to-Speech — Server-side voice synthesis.

Integrates with ElevenLabs (premium) or gTTS (free fallback).
Warm, friendly, slightly playful voice for Nori.
"""

import base64
import hashlib
import io
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

CACHE_DIR = Path("/tmp/nobi_tts_cache")
MAX_CACHE_SIZE = 500  # Max cached phrases
MAX_TEXT_LENGTH = 5000  # Character limit per request


# ─── Cache ───────────────────────────────────────────────────────────────────

def _get_cache_key(text: str, voice_id: str) -> str:
    """Generate a deterministic cache key for a text+voice combo."""
    raw = f"{text}:{voice_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _get_from_cache(text: str, voice_id: str) -> Optional[bytes]:
    """Retrieve cached audio if available."""
    cache_key = _get_cache_key(text, voice_id)
    cache_path = CACHE_DIR / f"{cache_key}.mp3"
    if cache_path.exists():
        return cache_path.read_bytes()
    return None


def _save_to_cache(text: str, voice_id: str, audio_bytes: bytes) -> None:
    """Save audio to cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Evict old entries if cache is too large
        existing = list(CACHE_DIR.glob("*.mp3"))
        if len(existing) >= MAX_CACHE_SIZE:
            # Remove oldest files
            existing.sort(key=lambda f: f.stat().st_mtime)
            for old_file in existing[: len(existing) - MAX_CACHE_SIZE + 10]:
                old_file.unlink(missing_ok=True)

        cache_key = _get_cache_key(text, voice_id)
        cache_path = CACHE_DIR / f"{cache_key}.mp3"
        cache_path.write_bytes(audio_bytes)
    except Exception as e:
        logger.warning(f"TTS cache save failed: {e}")


# ─── ElevenLabs TTS ──────────────────────────────────────────────────────────

async def _generate_elevenlabs(text: str, voice_id: str) -> Optional[bytes]:
    """Generate speech using ElevenLabs API."""
    if not ELEVENLABS_API_KEY:
        return None

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.6,  # Slightly expressive
                        "similarity_boost": 0.8,
                        "style": 0.3,  # Warm and friendly
                    },
                },
            )

            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"ElevenLabs TTS failed: {response.status_code} {response.text}")
                return None
    except ImportError:
        logger.warning("httpx not installed, cannot use ElevenLabs TTS")
        return None
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        return None


# ─── gTTS Fallback ───────────────────────────────────────────────────────────

def _generate_gtts(text: str, language: str = "en") -> Optional[bytes]:
    """Generate speech using gTTS (free, offline-capable)."""
    try:
        from gtts import gTTS

        tts = gTTS(text=text, lang=language, slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()
    except ImportError:
        logger.warning("gTTS not installed. Install with: pip install gTTS")
        return None
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return None


# ─── Public API ──────────────────────────────────────────────────────────────

async def generate_speech(
    text: str,
    voice_id: Optional[str] = None,
    language: str = "en",
) -> Optional[bytes]:
    """
    Generate speech audio from text.

    Tries ElevenLabs first, falls back to gTTS.
    Returns MP3 audio bytes or None if all methods fail.

    Args:
        text: The text to synthesize.
        voice_id: ElevenLabs voice ID (optional, uses default).
        language: Language code for gTTS fallback.

    Returns:
        Audio bytes (MP3) or None.
    """
    if not text or not text.strip():
        return None

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        logger.warning(f"TTS text truncated to {MAX_TEXT_LENGTH} chars")

    effective_voice_id = voice_id or ELEVENLABS_VOICE_ID

    # Check cache first
    cached = _get_from_cache(text, effective_voice_id)
    if cached:
        logger.debug("TTS cache hit")
        return cached

    # Try ElevenLabs
    audio = await _generate_elevenlabs(text, effective_voice_id)

    # Fall back to gTTS
    if audio is None:
        audio = _generate_gtts(text, language)

    # Cache the result
    if audio:
        _save_to_cache(text, effective_voice_id, audio)

    return audio


def generate_speech_base64(
    text: str,
    voice_id: Optional[str] = None,
    language: str = "en",
) -> Optional[str]:
    """
    Synchronous wrapper — generates speech and returns base64-encoded audio.
    For use in sync contexts.
    """
    audio = _generate_gtts(text, language)
    if audio:
        return base64.b64encode(audio).decode("utf-8")
    return None


@lru_cache(maxsize=100)
def get_available_voices() -> list[dict]:
    """
    Get list of available ElevenLabs voices (cached).
    Returns empty list if ElevenLabs is not configured.
    """
    if not ELEVENLABS_API_KEY:
        return [{"id": "default", "name": "Default (gTTS)", "provider": "gtts"}]

    try:
        import httpx

        response = httpx.get(
            f"{ELEVENLABS_BASE_URL}/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY},
            timeout=10.0,
        )
        if response.status_code == 200:
            data = response.json()
            return [
                {"id": v["voice_id"], "name": v["name"], "provider": "elevenlabs"}
                for v in data.get("voices", [])
            ]
    except Exception as e:
        logger.warning(f"Failed to fetch voices: {e}")

    return [{"id": "default", "name": "Default (gTTS)", "provider": "gtts"}]
