"""
Nobi Speech-to-Text — Server-side audio transcription.

Transcription chain (in priority order):
  1. HuggingFace Inference API (primary — free tier, no GPU needed)
  2. OpenRouter Whisper API  (secondary — fallback if HF fails)
  3. Local Whisper model     (tertiary — last resort)
"""

import asyncio
import base64
import io
import logging
import os
import subprocess
import tempfile
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

WHISPER_LOCAL_MODEL = os.environ.get("WHISPER_LOCAL_MODEL", "base")

HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_ASR_MODEL = os.environ.get("HF_ASR_MODEL", "openai/whisper-large-v3")
HF_API_BASE = "https://api-inference.huggingface.co/models"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "m4a", "webm", "flac"}
MAX_AUDIO_SIZE_MB = 25
SUPPORTED_LANGUAGES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh",
    "ar", "hi", "ru", "tr", "pl", "sv", "da", "no", "fi",
}


# ─── Audio conversion helpers ─────────────────────────────────────────────────

def _convert_to_wav(audio_bytes: bytes, audio_format: str) -> Tuple[bytes, str]:
    """Convert audio bytes to WAV using ffmpeg (most reliable for HF API).
    
    Returns (wav_bytes, "wav") on success, or (original_bytes, original_format) on failure.
    """
    if audio_format in ("wav", "flac", "mp3"):
        # These are well-supported natively; skip conversion
        return audio_bytes, audio_format

    try:
        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as src:
            src.write(audio_bytes)
            src_path = src.name

        dst_path = src_path.replace(f".{audio_format}", ".wav")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", dst_path],
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0:
            with open(dst_path, "rb") as f:
                wav_bytes = f.read()
            logger.debug(f"Converted {audio_format} → wav ({len(wav_bytes)} bytes)")
            return wav_bytes, "wav"
        else:
            logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()[:200]}")
    except FileNotFoundError:
        logger.debug("ffmpeg not found — sending original format to HF API")
    except Exception as e:
        logger.warning(f"Audio conversion error: {e}")
    finally:
        # Cleanup temp files
        try:
            os.unlink(src_path)
        except Exception:
            pass
        try:
            os.unlink(dst_path)
        except Exception:
            pass

    return audio_bytes, audio_format


def _get_content_type(audio_format: str) -> str:
    """Map audio format to MIME content type."""
    mapping = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
        "flac": "audio/flac",
    }
    return mapping.get(audio_format, "audio/mpeg")


# ─── HuggingFace Inference API ────────────────────────────────────────────────

async def _transcribe_huggingface(
    audio_bytes: bytes,
    audio_format: str = "ogg",
    language: str = "en",
) -> Optional[str]:
    """Transcribe audio using HuggingFace Inference API.

    Uses openai/whisper-large-v3 via HF API (free tier).
    Env vars:
      HF_API_TOKEN — optional, increases rate limits
      HF_ASR_MODEL — override model (default: openai/whisper-large-v3)
    """
    model = HF_ASR_MODEL
    url = f"{HF_API_BASE}/{model}"

    # Convert OGG/WebM to WAV for best compatibility
    payload_bytes, payload_format = _convert_to_wav(audio_bytes, audio_format)
    content_type = _get_content_type(payload_format)

    headers = {"Content-Type": content_type}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, content=payload_bytes, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                # HF returns either [{"text": "..."}] or {"text": "..."}
                if isinstance(data, list) and data:
                    text = data[0].get("text", "").strip()
                elif isinstance(data, dict):
                    text = data.get("text", "").strip()
                else:
                    text = ""
                if text:
                    logger.info(f"[HuggingFace STT] Success: '{text[:80]}...' (model={model})")
                    return text
                logger.warning(f"[HuggingFace STT] Empty response: {data}")
                return None

            elif resp.status_code == 503:
                # Model is loading — wait and retry
                try:
                    error_data = resp.json()
                    wait_time = float(error_data.get("estimated_time", 20))
                except Exception:
                    wait_time = 20.0
                wait_time = min(wait_time, 60.0)  # cap at 60s
                logger.info(
                    f"[HuggingFace STT] Model loading, waiting {wait_time:.0f}s "
                    f"(attempt {attempt+1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
                continue

            elif resp.status_code == 429:
                logger.warning("[HuggingFace STT] Rate limited (429) — falling through to next provider")
                return None

            elif resp.status_code == 401:
                logger.warning("[HuggingFace STT] Unauthorized — check HF_API_TOKEN")
                return None

            else:
                logger.warning(
                    f"[HuggingFace STT] HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

        except httpx.TimeoutException:
            logger.warning(f"[HuggingFace STT] Timeout (attempt {attempt+1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            continue
        except Exception as e:
            logger.error(f"[HuggingFace STT] Error: {e}")
            return None

    logger.warning("[HuggingFace STT] All retries exhausted")
    return None


# ─── OpenRouter Whisper API ───────────────────────────────────────────────────

async def _transcribe_openrouter(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """Fallback: OpenAI Whisper via OpenRouter API.
    
    Uses OpenAI-compatible audio transcription endpoint.
    Requires OPENROUTER_API_KEY env var.
    """
    if not OPENROUTER_API_KEY:
        logger.debug("[OpenRouter STT] No OPENROUTER_API_KEY set — skipping")
        return None

    url = f"{OPENROUTER_BASE}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://projectnobi.ai",
        "X-Title": "Nobi",
    }

    # Determine filename for multipart upload
    filename = f"audio.{audio_format}"
    content_type = _get_content_type(audio_format)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers=headers,
                files={"file": (filename, audio_bytes, content_type)},
                data={
                    "model": "openai/whisper-1",
                    "language": language if language in SUPPORTED_LANGUAGES else "en",
                    "response_format": "json",
                },
            )

        if resp.status_code == 200:
            data = resp.json()
            text = data.get("text", "").strip()
            if text:
                logger.info(f"[OpenRouter STT] Success: '{text[:80]}...'")
                return text
            logger.warning(f"[OpenRouter STT] Empty response: {data}")
            return None

        elif resp.status_code == 429:
            logger.warning("[OpenRouter STT] Rate limited (429)")
            return None

        else:
            logger.warning(
                f"[OpenRouter STT] HTTP {resp.status_code}: {resp.text[:200]}"
            )
            return None

    except httpx.TimeoutException:
        logger.warning("[OpenRouter STT] Timeout")
        return None
    except Exception as e:
        logger.error(f"[OpenRouter STT] Error: {e}")
        return None


# ─── Local Whisper Model ──────────────────────────────────────────────────────

def _transcribe_local(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """Transcribe audio using local Whisper model (tertiary fallback)."""
    try:
        import whisper

        model = whisper.load_model(WHISPER_LOCAL_MODEL)

        with tempfile.NamedTemporaryFile(
            suffix=f".{audio_format}", delete=True
        ) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()

            result = model.transcribe(
                tmp.name,
                language=language if language in SUPPORTED_LANGUAGES else None,
                fp16=False,
            )
            text = result.get("text", "").strip()
            if text:
                logger.info(f"[Local Whisper] Success: '{text[:80]}...'")
            return text

    except ImportError:
        logger.warning("[Local Whisper] Not installed. Install with: pip install openai-whisper")
        return None
    except Exception as e:
        logger.error(f"[Local Whisper] Error: {e}")
        return None


# ─── Public API ──────────────────────────────────────────────────────────────

async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """
    Transcribe audio to text.

    Priority chain:
      1. HuggingFace Inference API (primary — free tier, no GPU)
      2. OpenRouter Whisper API    (secondary fallback)
      3. Local Whisper model       (tertiary fallback)

    Args:
        audio_bytes: Raw audio bytes.
        audio_format: Audio format (wav, mp3, ogg, etc.).
        language: Expected language code.

    Returns:
        Transcribed text or None if all methods fail.
    """
    if not audio_bytes:
        logger.warning("transcribe_audio called with empty audio_bytes")
        return None

    if audio_format not in SUPPORTED_FORMATS:
        logger.warning(f"Unsupported audio format: {audio_format}")
        return None

    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        logger.warning(f"Audio too large: {size_mb:.1f}MB (max {MAX_AUDIO_SIZE_MB}MB)")
        return None

    # 1. HuggingFace Inference API (primary)
    text = await _transcribe_huggingface(audio_bytes, audio_format, language)
    if text:
        logger.info(f"[STT] Provider=HuggingFace | {size_mb:.2f}MB {audio_format}")
        return text

    # 2. OpenRouter Whisper (secondary fallback)
    logger.info("[STT] HuggingFace failed — trying OpenRouter Whisper")
    text = await _transcribe_openrouter(audio_bytes, audio_format, language)
    if text:
        logger.info(f"[STT] Provider=OpenRouter | {size_mb:.2f}MB {audio_format}")
        return text

    # 3. Local Whisper (tertiary fallback)
    logger.info("[STT] OpenRouter failed — trying local Whisper")
    text = _transcribe_local(audio_bytes, audio_format, language)
    if text:
        logger.info(f"[STT] Provider=LocalWhisper | {size_mb:.2f}MB {audio_format}")
        return text

    logger.error("[STT] All providers failed — could not transcribe audio")
    return None


def transcribe_base64(
    audio_base64: str,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """
    Transcribe base64-encoded audio (synchronous convenience wrapper).
    For use in sync contexts — uses local Whisper only.
    """
    try:
        audio_bytes = base64.b64decode(audio_base64)
        return _transcribe_local(audio_bytes, audio_format, language)
    except Exception as e:
        logger.error(f"Base64 transcription error: {e}")
        return None


def detect_language(audio_bytes: bytes) -> Optional[str]:
    """
    Detect the language of audio content using local Whisper.
    Returns ISO 639-1 language code or None.
    """
    try:
        import whisper

        model = whisper.load_model(WHISPER_LOCAL_MODEL)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()

            audio = whisper.load_audio(tmp.name)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            detected = max(probs, key=probs.get)
            return detected
    except ImportError:
        return None
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return None
