"""
Project Nobi — TEE Encryption Module (Phase 1)
===============================================
End-to-end encryption for validator → miner communication.

Design:
  - Per-query AES-256-GCM encryption (authenticated encryption)
  - Validator encrypts user message + memory context before sending to miner
  - Miner's TEE model decrypts inside the enclave
  - Backward compatible — non-TEE miners receive plaintext unchanged
  - Keys are per-query (ephemeral), never stored, never logged
  - No deprecated crypto: no MD5, no SHA1 for keys, no ECB mode

Encryption scheme: "aes-256-gcm-v1"
  - 256-bit random AES key per query
  - 96-bit random nonce (GCM standard)
  - Authentication tag verifies integrity (prevents tampering)
  - Base64url encoding for wire transport

The session key itself travels in the synapse (key_id field) for now
as a proof-of-concept. In production, the session key would be wrapped
with the miner's TEE attestation public key (HPKE/ECIES). That upgrade
is Phase 2 of the encryption roadmap.

Security properties:
  - Confidentiality: AES-256-GCM
  - Integrity: GCM authentication tag
  - Forward secrecy: per-query keys — compromise of one key doesn't expose others
  - No key persistence: keys live only for the duration of the query
"""

import os
import base64
import logging
from typing import Optional, Tuple

logger = logging.getLogger("nobi-tee-encryption")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not available — TEE encryption disabled. "
        "Install with: pip install cryptography"
    )


ENCRYPTION_SCHEME = "aes-256-gcm-v1"
KEY_SIZE_BYTES = 32   # AES-256
NONCE_SIZE_BYTES = 12  # 96-bit nonce (GCM standard)


def is_available() -> bool:
    """Return True if the cryptography library is available."""
    return _CRYPTO_AVAILABLE


def generate_session_key() -> bytes:
    """
    Generate a cryptographically random 256-bit AES key.

    Uses os.urandom (CSPRNG) for key generation.
    Each call produces a unique, independent key.
    NEVER store or log this key.
    """
    return os.urandom(KEY_SIZE_BYTES)


def encrypt_message(plaintext: str, key: bytes) -> Tuple[str, str]:
    """
    Encrypt a plaintext string using AES-256-GCM.

    Args:
        plaintext: The string to encrypt
        key: 32-byte AES-256 key (from generate_session_key())

    Returns:
        Tuple of (nonce_b64, ciphertext_b64) where:
          - nonce_b64: base64url-encoded 12-byte nonce
          - ciphertext_b64: base64url-encoded (ciphertext + 16-byte GCM tag)

    Raises:
        ValueError: if key is wrong length or crypto unavailable
        RuntimeError: if encryption fails
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not available — cannot encrypt")
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(f"Key must be {KEY_SIZE_BYTES} bytes, got {len(key)}")
    if not isinstance(plaintext, str):
        raise ValueError("plaintext must be a string")

    nonce = os.urandom(NONCE_SIZE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("ascii")
    ciphertext_b64 = base64.urlsafe_b64encode(ciphertext_with_tag).decode("ascii")

    return nonce_b64, ciphertext_b64


def decrypt_message(nonce_b64: str, ciphertext_b64: str, key: bytes) -> str:
    """
    Decrypt an AES-256-GCM encrypted message.

    Args:
        nonce_b64: base64url-encoded nonce (from encrypt_message)
        ciphertext_b64: base64url-encoded ciphertext+tag (from encrypt_message)
        key: 32-byte AES-256 key

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: if key is wrong length, or inputs are malformed
        cryptography.exceptions.InvalidTag: if authentication fails (tampered)
        RuntimeError: if crypto unavailable
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not available — cannot decrypt")
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(f"Key must be {KEY_SIZE_BYTES} bytes, got {len(key)}")
    if not nonce_b64 or not ciphertext_b64:
        raise ValueError("nonce and ciphertext must not be empty")

    nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
    ciphertext_with_tag = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))

    if len(nonce) != NONCE_SIZE_BYTES:
        raise ValueError(f"Nonce must be {NONCE_SIZE_BYTES} bytes, got {len(nonce)}")

    aesgcm = AESGCM(key)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    return plaintext_bytes.decode("utf-8")


def encode_key(key: bytes) -> str:
    """
    Encode a session key as base64url string for transport in the synapse key_id field.

    NOTE: In Phase 2, the key will be wrapped with the miner's TEE attestation
    public key. For now, the key travels in plaintext (proof-of-concept).
    This is still useful: it separates the encrypted payload from the key field,
    making the architecture ready for HPKE key wrapping in Phase 2.
    """
    return base64.urlsafe_b64encode(key).decode("ascii")


def decode_key(key_b64: str) -> bytes:
    """
    Decode a base64url-encoded session key back to bytes.

    Args:
        key_b64: base64url-encoded key string

    Returns:
        32-byte AES-256 key
    """
    key = base64.urlsafe_b64decode(key_b64.encode("ascii"))
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(f"Decoded key must be {KEY_SIZE_BYTES} bytes, got {len(key)}")
    return key


def encrypt_payload(message: str, context: str = "") -> dict:
    """
    High-level: encrypt both message and context for a single synapse.

    Generates one session key and uses it to encrypt both fields.
    Returns a dict with all fields needed to populate the encrypted
    CompanionRequest fields.

    Args:
        message: The user's message (required)
        context: Memory context string (optional, can be empty)

    Returns:
        dict with keys:
          - encrypted: True
          - encryption_scheme: "aes-256-gcm-v1"
          - encrypted_message: "<nonce>.<ciphertext>" base64url
          - encrypted_context: "<nonce>.<ciphertext>" base64url (or "" if no context)
          - key_id: base64url-encoded session key (for Phase 1 transport)

    Raises:
        RuntimeError: if crypto unavailable
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("TEE encryption requires the cryptography library")

    key = generate_session_key()

    # Encrypt message
    msg_nonce, msg_cipher = encrypt_message(message, key)
    encrypted_message = f"{msg_nonce}.{msg_cipher}"

    # Encrypt context (may be empty)
    encrypted_context = ""
    if context:
        ctx_nonce, ctx_cipher = encrypt_message(context, key)
        encrypted_context = f"{ctx_nonce}.{ctx_cipher}"

    key_id = encode_key(key)

    # Clear key bytes from memory (best effort in Python)
    # Python GC doesn't guarantee immediate clearing, but we avoid holding references
    del key

    return {
        "encrypted": True,
        "encryption_scheme": ENCRYPTION_SCHEME,
        "encrypted_message": encrypted_message,
        "encrypted_context": encrypted_context,
        "key_id": key_id,
    }


def decrypt_payload(encrypted_message: str, encrypted_context: str, key_id: str) -> Tuple[str, str]:
    """
    High-level: decrypt both message and context from synapse fields.

    Args:
        encrypted_message: "<nonce>.<ciphertext>" string from synapse
        encrypted_context: "<nonce>.<ciphertext>" string from synapse (may be empty)
        key_id: base64url-encoded session key

    Returns:
        Tuple of (plaintext_message, plaintext_context)
        plaintext_context is "" if encrypted_context was empty

    Raises:
        ValueError: if format is wrong
        RuntimeError: if crypto unavailable or decryption fails
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("TEE encryption requires the cryptography library")

    key = decode_key(key_id)

    # Decrypt message
    try:
        msg_nonce, msg_cipher = encrypted_message.split(".", 1)
    except ValueError:
        raise ValueError(f"Invalid encrypted_message format — expected 'nonce.ciphertext'")

    plaintext_message = decrypt_message(msg_nonce, msg_cipher, key)

    # Decrypt context (optional)
    plaintext_context = ""
    if encrypted_context:
        try:
            ctx_nonce, ctx_cipher = encrypted_context.split(".", 1)
        except ValueError:
            raise ValueError(f"Invalid encrypted_context format — expected 'nonce.ciphertext'")
        plaintext_context = decrypt_message(ctx_nonce, ctx_cipher, key)

    del key
    return plaintext_message, plaintext_context


def is_tee_miner(miner_model: str) -> bool:
    """
    Check if a miner's model string indicates it runs a TEE model.

    TEE models are identified by "-TEE" suffix in the model name.
    Examples: "deepseek-ai/DeepSeek-V3.1-TEE", "gpt-oss-120b-TEE"

    Args:
        miner_model: Model name string from miner config/advertisement

    Returns:
        True if the model is a known TEE model
    """
    if not miner_model:
        return False
    # TEE models have -TEE suffix (case-insensitive for robustness)
    model_upper = miner_model.upper()
    return "-TEE" in model_upper or "_TEE" in model_upper
