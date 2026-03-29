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
import tempfile
import time
from typing import Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

WHISPER_LOCAL_MODEL = os.environ.get("WHISPER_LOCAL_MODEL", "base")

HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_ASR_MODEL = os.environ.get("HF_ASR_MODEL", "openai/whisper-large-v3-turbo")
HF_API_BASE = "https://api-inference.huggingface.co/models"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "m4a", "webm", "flac"}
MAX_AUDIO_SIZE_MB = 25
SUPPORTED_LANGUAGES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh",
    "ar", "hi", "ru", "tr", "pl", "sv", "da", "no", "fi",
}

# Format validation regex — only allow safe alphanumeric format names
_SAFE_FORMAT_RE = None  # Lazy-compiled below


def _is_safe_format(fmt: str) -> bool:
    """Validate audio format is safe for use in filenames/commands."""
    return bool(fmt) and fmt.isalnum() and len(fmt) <= 10


# ─── Provider tracking (skip known-broken providers) ─────────────────────────

_provider_failures: Dict[str, float] = {}  # provider_name -> timestamp of last failure
_PROVIDER_COOLDOWN = 300  # 5 min cooldown before retrying a failed provider


def _provider_recently_failed(name: str) -> bool:
    """Check if a provider failed recently (within cooldown period)."""
    ts = _provider_failures.get(name)
    if ts is None:
        return False
    if time.monotonic() - ts > _PROVIDER_COOLDOWN:
        _provider_failures.pop(name, None)
        return False
    return True


def _mark_provider_failed(name: str):
    _provider_failures[name] = time.monotonic()


def _mark_provider_ok(name: str):
    _provider_failures.pop(name, None)


# ─── Audio conversion helpers ─────────────────────────────────────────────────

async def _convert_to_wav(audio_bytes: bytes, audio_format: str) -> Tuple[bytes, str]:
    """Convert audio bytes to WAV using ffmpeg (async, non-blocking).
    
    Returns (wav_bytes, "wav") on success, or (original_bytes, original_format) on failure.
    """
    if audio_format in ("wav", "flac", "mp3"):
        # These are well-supported natively; skip conversion
        return audio_bytes, audio_format

    if not _is_safe_format(audio_format):
        logger.warning(f"Refusing to convert unsafe format: {audio_format!r}")
        return audio_bytes, audio_format

    src_path = None
    dst_path = None
    try:
        # Create temp files with explicit, safe paths
        with tempfile.NamedTemporaryFile(
            suffix=f".{audio_format}", delete=False, prefix="nobi_stt_src_"
        ) as src:
            src.write(audio_bytes)
            src_path = src.name

        dst_path = src_path.rsplit(".", 1)[0] + ".wav"

        # Run ffmpeg asynchronously — does NOT block the event loop
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", src_path,
            "-ar", "16000", "-ac", "1",
            "-t", "300",  # Hard cap at 5 minutes to prevent abuse
            dst_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("ffmpeg conversion timed out (>30s)")
            return audio_bytes, audio_format

        if proc.returncode == 0:
            with open(dst_path, "rb") as f:
                wav_bytes = f.read()
            logger.debug(f"Converted {audio_format} → wav ({len(wav_bytes)} bytes)")
            return wav_bytes, "wav"
        else:
            stderr_text = stderr.decode(errors="replace")[:200] if stderr else ""
            logger.warning(f"ffmpeg conversion failed (rc={proc.returncode}): {stderr_text}")
    except FileNotFoundError:
        logger.debug("ffmpeg not found — sending original format to HF API")
    except Exception as e:
        logger.warning(f"Audio conversion error: {e}")
    finally:
        # Cleanup temp files (safe even if paths are None)
        for path in (src_path, dst_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
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

    Uses openai/whisper-large-v3-turbo via HF API (free tier).
    Env vars:
      HF_API_TOKEN — optional, increases rate limits
      HF_ASR_MODEL — override model (default: openai/whisper-large-v3-turbo)
    """
    if _provider_recently_failed("huggingface"):
        logger.debug("[HuggingFace STT] Skipping — recently failed (cooldown)")
        return None

    model = HF_ASR_MODEL
    url = f"{HF_API_BASE}/{model}"

    # Convert OGG/WebM to WAV for best compatibility (now async)
    payload_bytes, payload_format = await _convert_to_wav(audio_bytes, audio_format)
    content_type = _get_content_type(payload_format)

    headers = {"Content-Type": content_type}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    max_retries = 3
    timeout = httpx.Timeout(connect=10.0, read=50.0, write=10.0, pool=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(url, content=payload_bytes, headers=headers)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        logger.warning(f"[HuggingFace STT] Invalid JSON response: {resp.text[:200]}")
                        _mark_provider_failed("huggingface")
                        return None

                    # HF returns either [{"text": "..."}] or {"text": "..."}
                    if isinstance(data, list) and data:
                        text = data[0].get("text", "").strip() if isinstance(data[0], dict) else ""
                    elif isinstance(data, dict):
                        text = data.get("text", "").strip()
                    else:
                        text = ""
                    if text:
                        logger.info(f"[HuggingFace STT] Success: '{text[:80]}...' (model={model})")
                        _mark_provider_ok("huggingface")
                        return text
                    logger.warning(f"[HuggingFace STT] Empty response: {str(data)[:200]}")
                    return None

                elif resp.status_code == 503:
                    # Model is loading — wait and retry
                    try:
                        error_data = resp.json()
                        wait_time = float(error_data.get("estimated_time", 20))
                    except Exception:
                        wait_time = 20.0
                    wait_time = min(max(wait_time, 1.0), 60.0)  # clamp 1-60s
                    logger.info(
                        f"[HuggingFace STT] Model loading, waiting {wait_time:.0f}s "
                        f"(attempt {attempt+1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                elif resp.status_code == 429:
                    logger.warning("[HuggingFace STT] Rate limited (429) — falling through")
                    _mark_provider_failed("huggingface")
                    return None

                elif resp.status_code == 401:
                    logger.warning("[HuggingFace STT] Unauthorized — check HF_API_TOKEN")
                    _mark_provider_failed("huggingface")
                    return None

                else:
                    logger.warning(
                        f"[HuggingFace STT] HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    _mark_provider_failed("huggingface")
                    return None

            except httpx.TimeoutException:
                logger.warning(f"[HuggingFace STT] Timeout (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                continue
            except Exception as e:
                logger.error(f"[HuggingFace STT] Error: {e}")
                _mark_provider_failed("huggingface")
                return None

    logger.warning("[HuggingFace STT] All retries exhausted")
    _mark_provider_failed("huggingface")
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

    if _provider_recently_failed("openrouter"):
        logger.debug("[OpenRouter STT] Skipping — recently failed (cooldown)")
        return None

    url = f"{OPENROUTER_BASE}/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://projectnobi.ai",
        "X-Title": "Nobi",
    }

    # Determine filename for multipart upload
    safe_fmt = audio_format if _is_safe_format(audio_format) else "wav"
    filename = f"audio.{safe_fmt}"
    content_type = _get_content_type(audio_format)

    timeout = httpx.Timeout(connect=10.0, read=50.0, write=10.0, pool=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
            try:
                data = resp.json()
            except Exception:
                logger.warning(f"[OpenRouter STT] Invalid JSON response: {resp.text[:200]}")
                _mark_provider_failed("openrouter")
                return None

            text = ""
            if isinstance(data, dict):
                text = data.get("text", "").strip()
            if text:
                logger.info(f"[OpenRouter STT] Success: '{text[:80]}...'")
                _mark_provider_ok("openrouter")
                return text
            logger.warning(f"[OpenRouter STT] Empty response: {str(data)[:200]}")
            return None

        elif resp.status_code == 429:
            logger.warning("[OpenRouter STT] Rate limited (429)")
            _mark_provider_failed("openrouter")
            return None

        else:
            logger.warning(
                f"[OpenRouter STT] HTTP {resp.status_code}: {resp.text[:200]}"
            )
            _mark_provider_failed("openrouter")
            return None

    except httpx.TimeoutException:
        logger.warning("[OpenRouter STT] Timeout")
        _mark_provider_failed("openrouter")
        return None
    except Exception as e:
        logger.error(f"[OpenRouter STT] Error: {e}")
        _mark_provider_failed("openrouter")
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

        safe_fmt = audio_format if _is_safe_format(audio_format) else "wav"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=f".{safe_fmt}", delete=False, prefix="nobi_stt_local_"
            ) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                tmp_path = tmp.name

            result = model.transcribe(
                tmp_path,
                language=language if language in SUPPORTED_LANGUAGES else None,
                fp16=False,
            )
            text = result.get("text", "").strip()
            if text:
                logger.info(f"[Local Whisper] Success: '{text[:80]}...'")
            return text
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    except ImportError:
        logger.warning("[Local Whisper] Not installed. Install with: pip install openai-whisper")
        return None
    except Exception as e:
        logger.error(f"[Local Whisper] Error: {e}")
        return None


# ─── Health Check ─────────────────────────────────────────────────────────────

async def check_stt_health() -> Dict[str, dict]:
    """Test each STT provider and return status.
    
    Returns dict like:
      {
        "huggingface": {"available": True, "model": "openai/whisper-large-v3-turbo", "status": "ok"},
        "openrouter": {"available": True, "status": "ok"},
        "local_whisper": {"available": False, "reason": "not installed"},
      }
    """
    results: Dict[str, dict] = {}

    # Check HuggingFace
    hf_info: dict = {"model": HF_ASR_MODEL, "has_token": bool(HF_API_TOKEN)}
    try:
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {}
            if HF_API_TOKEN:
                headers["Authorization"] = f"Bearer {HF_API_TOKEN}"
            resp = await client.get(f"{HF_API_BASE}/{HF_ASR_MODEL}", headers=headers)
            if resp.status_code == 200:
                hf_info.update({"available": True, "status": "ok"})
            elif resp.status_code == 503:
                hf_info.update({"available": True, "status": "model_loading"})
            else:
                hf_info.update({"available": False, "status": f"http_{resp.status_code}"})
    except Exception as e:
        hf_info.update({"available": False, "status": str(e)[:100]})
    results["huggingface"] = hf_info

    # Check OpenRouter
    or_info: dict = {"has_key": bool(OPENROUTER_API_KEY)}
    if OPENROUTER_API_KEY:
        or_info.update({"available": True, "status": "key_configured"})
    else:
        or_info.update({"available": False, "status": "no_api_key"})
    results["openrouter"] = or_info

    # Check local Whisper
    try:
        import whisper
        results["local_whisper"] = {
            "available": True,
            "model": WHISPER_LOCAL_MODEL,
            "status": "installed",
        }
    except ImportError:
        results["local_whisper"] = {
            "available": False,
            "reason": "not installed (pip install openai-whisper)",
        }

    # Check ffmpeg
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        version_line = stdout.decode(errors="replace").split("\n")[0] if stdout else "unknown"
        results["ffmpeg"] = {"available": True, "version": version_line[:80]}
    except Exception:
        results["ffmpeg"] = {"available": False, "reason": "not found in PATH"}

    return results


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
    text = await asyncio.to_thread(_transcribe_local, audio_bytes, audio_format, language)
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
    tmp_path = None
    try:
        import whisper

        model = whisper.load_model(WHISPER_LOCAL_MODEL)

        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="nobi_stt_lang_"
        ) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()
            tmp_path = tmp.name

        audio = whisper.load_audio(tmp_path)
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
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

