"""
Nobi Speech-to-Text — Server-side audio transcription.

Uses local Whisper model for transcription.
Chutes.ai does not currently offer a Whisper/STT endpoint.
Supports multiple languages and audio formats.
"""

import base64
import io
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────


WHISPER_LOCAL_MODEL = os.environ.get("WHISPER_LOCAL_MODEL", "base")  # For local

SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "m4a", "webm", "flac"}
MAX_AUDIO_SIZE_MB = 25  # OpenAI Whisper limit
SUPPORTED_LANGUAGES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "ja", "ko", "zh",
    "ar", "hi", "ru", "tr", "pl", "sv", "da", "no", "fi",
}


# ─── OpenAI Whisper API ──────────────────────────────────────────────────────

async def _transcribe_chutes(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """Transcribe audio using Chutes.ai STT endpoint (not yet available)."""
    logger.warning("STT disabled: no Chutes Whisper endpoint available. Using local Whisper fallback.")
    return None


# ─── Local Whisper Model ──────────────────────────────────────────────────────

def _transcribe_local(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """Transcribe audio using local Whisper model."""
    try:
        import whisper

        model = whisper.load_model(WHISPER_LOCAL_MODEL)

        # Write to temp file (Whisper needs a file path)
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

            return result.get("text", "").strip()
    except ImportError:
        logger.warning(
            "Local whisper not installed. Install with: pip install openai-whisper"
        )
        return None
    except Exception as e:
        logger.error(f"Local Whisper error: {e}")
        return None


# ─── Public API ──────────────────────────────────────────────────────────────

async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language: str = "en",
) -> Optional[str]:
    """
    Transcribe audio to text.

    Tries OpenAI Whisper API first, falls back to local model.

    Args:
        audio_bytes: Raw audio bytes.
        audio_format: Audio format (wav, mp3, ogg, etc.).
        language: Expected language code.

    Returns:
        Transcribed text or None if all methods fail.
    """
    # Validate format
    if audio_format not in SUPPORTED_FORMATS:
        logger.warning(f"Unsupported audio format: {audio_format}")
        return None

    # Check size
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        logger.warning(f"Audio too large: {size_mb:.1f}MB (max {MAX_AUDIO_SIZE_MB}MB)")
        return None

    if not audio_bytes:
        return None

    # Try Chutes API first (currently unavailable — falls back to local)
    text = await _transcribe_chutes(audio_bytes, audio_format, language)

    # Fall back to local
    if text is None:
        text = _transcribe_local(audio_bytes, audio_format, language)

    if text:
        logger.info(f"Transcribed {size_mb:.1f}MB {audio_format}: {text[:100]}...")

    return text


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

            # Load audio and detect language
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
