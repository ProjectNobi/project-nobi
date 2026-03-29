"""
Tests for nobi/voice/stt.py — VibeVoice ASR (Phase 1)

Tests cover:
  - HuggingFace Inference API (primary provider)
  - OpenRouter Whisper API (secondary fallback)
  - Local Whisper (tertiary fallback)
  - Provider chain priority
  - Audio format handling
  - Edge cases (empty audio, 503 retry, 429 fallthrough, corrupted data)
  - Security (format validation, size limits)
  - Provider failure tracking
  - Health check
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_OGG_BYTES = b"OggS" + b"\x00" * 100   # Fake OGG header
SAMPLE_WAV_BYTES = b"RIFF" + b"\x00" * 100   # Fake WAV header
EMPTY_BYTES = b""
SAMPLE_TRANSCRIPT = "hello world this is a test"


def make_mock_response(status_code: int, json_data=None, text: str = ""):
    """Create a mock httpx Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = text
    if json_data is not None:
        mock_resp.json = MagicMock(return_value=json_data)
    else:
        mock_resp.json = MagicMock(side_effect=Exception("No JSON"))
    return mock_resp


@pytest.fixture(autouse=True)
def reset_provider_failures():
    """Reset provider failure tracking between tests."""
    from nobi.voice import stt
    stt._provider_failures.clear()
    yield
    stt._provider_failures.clear()


# ─── HuggingFace Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hf_transcribe_returns_string():
    """HF API returns transcribed text correctly."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, [{"text": SAMPLE_TRANSCRIPT}])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == SAMPLE_TRANSCRIPT


@pytest.mark.asyncio
async def test_hf_transcribe_dict_response():
    """HF API response as dict (not list) is handled."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, {"text": SAMPLE_TRANSCRIPT})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == SAMPLE_TRANSCRIPT


@pytest.mark.asyncio
async def test_hf_transcribe_handles_503_retry():
    """503 with estimated_time triggers retry after wait, then succeeds."""
    from nobi.voice import stt

    resp_503 = make_mock_response(503, {"error": "Loading", "estimated_time": 0.1})
    resp_200 = make_mock_response(200, [{"text": SAMPLE_TRANSCRIPT}])

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return resp_503
        return resp_200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == SAMPLE_TRANSCRIPT
    assert call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_hf_transcribe_handles_429_fallthrough():
    """429 rate limit returns None and marks provider failed."""
    from nobi.voice import stt

    mock_resp = make_mock_response(429, text="Too Many Requests")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None
    assert "huggingface" in stt._provider_failures


@pytest.mark.asyncio
async def test_hf_transcribe_invalid_json():
    """HF API returning non-JSON 200 is handled gracefully."""
    from nobi.voice import stt

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "not json at all"
    mock_resp.json = MagicMock(side_effect=ValueError("bad json"))

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None


@pytest.mark.asyncio
async def test_hf_transcribe_malformed_list():
    """HF returning list with non-dict items is handled."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, ["just a string"])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None


# ─── Transcription Chain Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transcribe_audio_chain_hf_wins():
    """transcribe_audio() uses HF as primary — skips other providers when HF succeeds."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value=SAMPLE_TRANSCRIPT)) as mock_hf:
        with patch.object(stt, "_transcribe_openrouter", new=AsyncMock(return_value="openrouter result")) as mock_or:
            with patch.object(stt, "_transcribe_local", return_value="local result") as mock_local:
                result = await stt.transcribe_audio(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == SAMPLE_TRANSCRIPT
    mock_hf.assert_called_once()
    mock_or.assert_not_called()
    mock_local.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_audio_chain_openrouter_fallback():
    """transcribe_audio() falls to OpenRouter when HF fails."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value=None)):
        with patch.object(stt, "_transcribe_openrouter", new=AsyncMock(return_value="openrouter result")) as mock_or:
            with patch.object(stt, "_transcribe_local", return_value="local result") as mock_local:
                result = await stt.transcribe_audio(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == "openrouter result"
    mock_or.assert_called_once()
    mock_local.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_audio_chain_local_fallback():
    """transcribe_audio() falls to local Whisper when HF and OpenRouter both fail."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value=None)):
        with patch.object(stt, "_transcribe_openrouter", new=AsyncMock(return_value=None)):
            with patch.object(stt, "_transcribe_local", return_value="local result") as mock_local:
                result = await stt.transcribe_audio(SAMPLE_WAV_BYTES, "wav", "en")

    assert result == "local result"
    mock_local.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_audio_chain_all_fail():
    """transcribe_audio() returns None when all providers fail."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value=None)):
        with patch.object(stt, "_transcribe_openrouter", new=AsyncMock(return_value=None)):
            with patch.object(stt, "_transcribe_local", return_value=None):
                result = await stt.transcribe_audio(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None


# ─── Audio Format Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audio_format_ogg():
    """OGG format is accepted and passed through the chain."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value=SAMPLE_TRANSCRIPT)) as mock_hf:
        result = await stt.transcribe_audio(SAMPLE_OGG_BYTES, "ogg", "en")

    assert result == SAMPLE_TRANSCRIPT
    call_args = mock_hf.call_args
    assert call_args[0][1] == "ogg" or call_args.args[1] == "ogg"


@pytest.mark.asyncio
async def test_audio_format_unsupported():
    """Unsupported audio format returns None immediately."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value="text")) as mock_hf:
        result = await stt.transcribe_audio(SAMPLE_WAV_BYTES, "xyz", "en")

    assert result is None
    mock_hf.assert_not_called()


# ─── Edge Case Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_transcribe_empty_audio():
    """Empty audio bytes returns None without calling any provider."""
    from nobi.voice import stt

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value="text")) as mock_hf:
        result = await stt.transcribe_audio(EMPTY_BYTES, "wav", "en")

    assert result is None
    mock_hf.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_oversized_audio():
    """Audio exceeding MAX_AUDIO_SIZE_MB returns None."""
    from nobi.voice import stt

    oversized = b"\x00" * (26 * 1024 * 1024)  # 26MB

    with patch.object(stt, "_transcribe_huggingface", new=AsyncMock(return_value="text")) as mock_hf:
        result = await stt.transcribe_audio(oversized, "wav", "en")

    assert result is None
    mock_hf.assert_not_called()


@pytest.mark.asyncio
async def test_hf_transcribe_empty_text_in_response():
    """HF response with empty text string falls through (returns None)."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, [{"text": ""}])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None


@pytest.mark.asyncio
async def test_transcribe_whitespace_only_audio():
    """Whitespace-only transcriptions are treated as empty."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, [{"text": "   \n  "}])

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt._convert_to_wav", new=AsyncMock(return_value=(SAMPLE_WAV_BYTES, "wav"))):
            result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")

    assert result is None


# ─── OpenRouter Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_openrouter_no_key_skips():
    """OpenRouter provider returns None when OPENROUTER_API_KEY not set."""
    from nobi.voice import stt

    original = stt.OPENROUTER_API_KEY
    try:
        stt.OPENROUTER_API_KEY = ""
        result = await stt._transcribe_openrouter(SAMPLE_WAV_BYTES, "wav", "en")
    finally:
        stt.OPENROUTER_API_KEY = original

    assert result is None


@pytest.mark.asyncio
async def test_openrouter_success():
    """OpenRouter returns transcribed text on 200."""
    from nobi.voice import stt

    mock_resp = make_mock_response(200, {"text": SAMPLE_TRANSCRIPT})

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)

    original = stt.OPENROUTER_API_KEY
    try:
        stt.OPENROUTER_API_KEY = "test-key-123"
        with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
            result = await stt._transcribe_openrouter(SAMPLE_WAV_BYTES, "wav", "en")
    finally:
        stt.OPENROUTER_API_KEY = original

    assert result == SAMPLE_TRANSCRIPT


# ─── Security Tests ───────────────────────────────────────────────────────────

def test_format_validation():
    """Format validation rejects dangerous strings."""
    from nobi.voice.stt import _is_safe_format

    assert _is_safe_format("wav") is True
    assert _is_safe_format("ogg") is True
    assert _is_safe_format("mp3") is True
    assert _is_safe_format("") is False
    assert _is_safe_format("../../../etc/passwd") is False
    assert _is_safe_format("wav; rm -rf /") is False
    assert _is_safe_format("a" * 20) is False  # too long


# ─── Provider Tracking Tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provider_cooldown_skips_recently_failed():
    """Provider that recently failed is skipped during cooldown."""
    from nobi.voice import stt

    stt._mark_provider_failed("huggingface")

    # Should be skipped (returns None immediately)
    result = await stt._transcribe_huggingface(SAMPLE_WAV_BYTES, "wav", "en")
    assert result is None


@pytest.mark.asyncio
async def test_provider_cooldown_expires():
    """Provider cooldown expires and allows retrying."""
    from nobi.voice import stt
    import time

    stt._provider_failures["huggingface"] = time.monotonic() - 400  # 400s ago, > 300s cooldown

    assert stt._provider_recently_failed("huggingface") is False


# ─── Health Check Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_returns_dict():
    """check_stt_health returns expected structure."""
    from nobi.voice import stt

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("nobi.voice.stt.httpx.AsyncClient", return_value=mock_client):
        with patch("nobi.voice.stt.asyncio.create_subprocess_exec", new=AsyncMock(side_effect=FileNotFoundError)):
            result = await stt.check_stt_health()

    assert "huggingface" in result
    assert "openrouter" in result
    assert "local_whisper" in result
    assert "ffmpeg" in result
    assert isinstance(result["huggingface"]["available"], bool)


# ─── Conversion Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_convert_wav_passthrough():
    """WAV format is passed through without conversion."""
    from nobi.voice.stt import _convert_to_wav

    result_bytes, result_fmt = await _convert_to_wav(SAMPLE_WAV_BYTES, "wav")
    assert result_bytes == SAMPLE_WAV_BYTES
    assert result_fmt == "wav"


@pytest.mark.asyncio
async def test_convert_unsafe_format_rejected():
    """Unsafe format strings are rejected by conversion."""
    from nobi.voice.stt import _convert_to_wav

    result_bytes, result_fmt = await _convert_to_wav(b"data", "../../../hack")
    assert result_bytes == b"data"
    assert result_fmt == "../../../hack"  # Returned unchanged, not executed
