"""
Nobi Image Understanding — Analyze images and extract memories.

Sends images to vision models (GPT-4V, Claude Vision, or free alternatives via Chutes).
Extracts meaningful memories from images without storing the images themselves.
"""

import base64
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

CHUTES_API_KEY = os.environ.get("CHUTES_API_KEY", "")
CHUTES_API_URL = os.environ.get(
    "CHUTES_API_URL", "https://llm.chutes.ai/v1"
)

# Load backup Chutes keys for vision retry (429/503 key rotation)
_CHUTES_KEYS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "chutes_keys.txt"
)
_CHUTES_BACKUP_KEYS: list = []
try:
    if os.path.exists(_CHUTES_KEYS_PATH):
        with open(_CHUTES_KEYS_PATH) as f:
            _CHUTES_BACKUP_KEYS = [k.strip() for k in f if k.strip().startswith("cpk_")]
except Exception:
    pass

SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_IMAGE_SIZE_MB = 10
MAX_DESCRIPTION_LENGTH = 500


# ─── System Prompt ────────────────────────────────────────────────────────────

NORI_VISION_PROMPT = """You are Nori, a warm and caring AI companion. 
You're looking at an image shared by your friend. 

Respond naturally:
1. Describe what you see briefly and warmly
2. If you notice anything personal (pets, people, places, food), mention it with genuine interest
3. Extract any facts worth remembering about the user

Format your response as:
DESCRIPTION: [Brief warm description of the image]
RESPONSE: [Your natural, friendly response to the user about this image]
MEMORIES: [Comma-separated list of facts to remember, or "none" if nothing notable]

Example:
DESCRIPTION: A fluffy orange cat sleeping on a blue couch
RESPONSE: Oh my gosh, what a beautiful cat! 🐱 They look so peaceful! What's their name?
MEMORIES: User has an orange cat, cat sleeps on blue couch
"""


# ─── Vision Model Providers ──────────────────────────────────────────────────

async def _analyze_with_chutes(
    image_base64: str,
    image_format: str,
    caption: str,
    user_context: str,
) -> Optional[str]:
    """Analyze image using Chutes.ai (free vision models)."""
    if not CHUTES_API_KEY:
        return None

    try:
        import httpx

        messages = [
            {"role": "system", "content": NORI_VISION_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_format};base64,{image_base64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": f"User says: {caption}\n\nContext: {user_context}"
                        if caption
                        else f"User shared this image.\n\nContext: {user_context}",
                    },
                ],
            },
        ]

        # Fast path: try smaller model first (faster TTFT), then larger
        # 3 keys per model max to keep total time under 15s
        vision_models = [
            "Qwen/Qwen2.5-VL-32B-Instruct",      # Smaller, faster
            "Qwen/Qwen3-VL-235B-A22B-Instruct",   # Larger, slower but more capable
        ]

        # Build key rotation list: primary + up to 2 backups (3 total per model)
        api_keys = [CHUTES_API_KEY]
        for bk in _CHUTES_BACKUP_KEYS:
            if bk != CHUTES_API_KEY and bk not in api_keys:
                api_keys.append(bk)
            if len(api_keys) >= 3:
                break

        async with httpx.AsyncClient(timeout=20.0) as client:
            for model in vision_models:
                for key in api_keys:
                    try:
                        response = await client.post(
                            f"{CHUTES_API_URL}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": model,
                                "messages": messages,
                                "max_tokens": 300,
                                "temperature": 0.7,
                            },
                        )

                        if response.status_code == 200:
                            data = response.json()
                            logger.info(f"Chutes Vision OK: {model}")
                            return data["choices"][0]["message"]["content"]
                        elif response.status_code == 429:
                            logger.warning(f"Chutes Vision {model}: 429, rotating key...")
                            continue
                        elif response.status_code in (503, 502):
                            logger.warning(f"Chutes Vision {model}: {response.status_code}, next model...")
                            break
                        else:
                            logger.error(f"Chutes Vision {model}: {response.status_code}")
                            break
                    except httpx.TimeoutException:
                        logger.warning(f"Chutes Vision {model}: timeout, next model...")
                        break
                    except Exception as model_err:
                        logger.warning(f"Chutes Vision {model}: {model_err}")
                        break

            logger.error("All Chutes vision models/keys exhausted")
            return None
    except ImportError:
        logger.warning("httpx not installed for Chutes Vision")
        return None
    except Exception as e:
        logger.error(f"Chutes Vision error: {e}")
        return None


# ─── Response Parsing ─────────────────────────────────────────────────────────

def _parse_vision_response(
    raw_response: str,
) -> tuple[str, str, list[str]]:
    """
    Parse the structured vision model response.

    Returns:
        (description, response, extracted_memories)
    """
    description = ""
    response = ""
    memories: list[str] = []

    # Extract DESCRIPTION
    desc_match = re.search(
        r"DESCRIPTION:\s*(.+?)(?=RESPONSE:|$)", raw_response, re.DOTALL | re.IGNORECASE
    )
    if desc_match:
        description = desc_match.group(1).strip()

    # Extract RESPONSE
    resp_match = re.search(
        r"RESPONSE:\s*(.+?)(?=MEMORIES:|$)", raw_response, re.DOTALL | re.IGNORECASE
    )
    if resp_match:
        response = resp_match.group(1).strip()

    # Extract MEMORIES
    mem_match = re.search(r"MEMORIES:\s*(.+?)$", raw_response, re.DOTALL | re.IGNORECASE)
    if mem_match:
        mem_text = mem_match.group(1).strip()
        if mem_text.lower() != "none":
            memories = [m.strip() for m in mem_text.split(",") if m.strip()]

    # Fallback: if parsing failed, use the whole response
    if not description and not response:
        response = raw_response.strip()
        description = raw_response[:MAX_DESCRIPTION_LENGTH].strip()

    return description, response, memories


# ─── Public API ──────────────────────────────────────────────────────────────

async def analyze_image(
    image_bytes: bytes,
    user_context: str = "",
    caption: str = "",
    image_format: str = "jpg",
) -> dict:
    """
    Analyze an image and generate a response + extracted memories.

    Args:
        image_bytes: Raw image bytes.
        user_context: Context about the user (previous memories, preferences).
        caption: User's caption or question about the image.
        image_format: Image format (jpg, png, etc.).

    Returns:
        Dict with keys: description, response, extracted_memories, success
    """
    result = {
        "description": "",
        "response": "I wasn't able to look at that image right now. Could you describe it to me? 😊",
        "extracted_memories": [],
        "success": False,
    }

    # Validate format
    if image_format.lower() not in SUPPORTED_FORMATS:
        result["response"] = f"Sorry, I can't process {image_format} images yet. Try JPG or PNG!"
        return result

    # Check size
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        result["response"] = f"That image is a bit large ({size_mb:.1f}MB). Could you send a smaller version?"
        return result

    # Resize large images to reduce payload and speed up processing
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        # Resize if larger than 1024px on any side
        max_dim = 1024
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            buf = io.BytesIO()
            save_fmt = "JPEG" if image_format.lower() in ("jpg", "jpeg") else "PNG"
            img.save(buf, format=save_fmt, quality=80)
            image_bytes = buf.getvalue()
            image_format = "jpeg" if save_fmt == "JPEG" else "png"
            logger.info(f"Image resized to {img.size}, {len(image_bytes)} bytes")
    except ImportError:
        pass  # PIL not available, send as-is
    except Exception as e:
        logger.debug(f"Image resize skipped: {e}")

    # Encode to base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Chutes only — no centralized providers
    raw_response = await _analyze_with_chutes(
        image_base64, image_format, caption, user_context
    )

    if raw_response is None:
        logger.warning("All vision providers failed")
        return result

    # Parse the response
    description, response, memories = _parse_vision_response(raw_response)

    return {
        "description": description[:MAX_DESCRIPTION_LENGTH],
        "response": response,
        "extracted_memories": memories,
        "success": True,
    }


def analyze_image_sync(
    image_bytes: bytes,
    user_context: str = "",
    caption: str = "",
    image_format: str = "jpg",
) -> dict:
    """
    Synchronous wrapper for image analysis.
    Uses a simple description fallback when async is not available.
    """
    return {
        "description": "Image received (async analysis not available)",
        "response": "I can see you sent an image! Let me take a closer look when I'm fully set up. 😊",
        "extracted_memories": [],
        "success": False,
    }
