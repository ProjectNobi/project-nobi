"""
Project Nobi — TEE Encryption Module (Phase 1 + Phase 2)
=========================================================
End-to-end encryption for validator → miner communication.

Phase 1: AES-256-GCM per-query encryption (session key in plaintext key_id).
Phase 2: HPKE key wrapping — session key wrapped with miner's X25519 public key
         so only the miner's TEE enclave can unwrap it.

Design:
  - Per-query AES-256-GCM encryption (authenticated encryption)
  - Validator encrypts user message + memory context before sending to miner
  - Miner's TEE model decrypts inside the enclave
  - Backward compatible — non-TEE miners receive plaintext unchanged
  - Keys are per-query (ephemeral), never stored, never logged
  - No deprecated crypto: no MD5, no SHA1 for keys, no ECB mode

Phase 1 scheme: "aes-256-gcm-v1"
  - 256-bit random AES key per query
  - 96-bit random nonce (GCM standard)
  - Authentication tag verifies integrity (prevents tampering)
  - Base64url encoding for wire transport
  - Session key travels in plaintext key_id field

Phase 2 scheme: "aes-256-gcm-hpke-v1"
  - Same AES-256-GCM for the payload
  - Session key wrapped with miner's X25519 public key (ECIES-like)
  - ECIES: ephemeral X25519 ECDH + HKDF-SHA256 + AES-256-GCM
  - key_id contains the HPKE-wrapped key blob (base64url)
  - Only the miner's TEE private key can unwrap the session key

Key wrapping format (base64url-encoded in key_id):
  [32 bytes: ephemeral X25519 public key]
  [12 bytes: AES-GCM nonce]
  [48 bytes: encrypted session key + 16-byte GCM tag]
  Total: 92 bytes → 124 base64url chars

Security properties:
  - Confidentiality: AES-256-GCM (payload + key wrapping)
  - Integrity: GCM authentication tag (both layers)
  - Forward secrecy: per-query ephemeral keys — compromise of one key doesn't expose others
  - No key persistence: session keys live only for the duration of the query
  - HPKE protection: even miner operator cannot read user data, only TEE enclave can
"""

import os
import base64
import logging
from typing import Optional, Tuple

logger = logging.getLogger("nobi-tee-encryption")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes, serialization
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not available — TEE encryption disabled. "
        "Install with: pip install cryptography"
    )


# ─── Constants ───────────────────────────────────────────────────────────────

ENCRYPTION_SCHEME = "aes-256-gcm-v1"
ENCRYPTION_SCHEME_HPKE = "aes-256-gcm-hpke-v1"

KEY_SIZE_BYTES = 32    # AES-256
NONCE_SIZE_BYTES = 12  # 96-bit nonce (GCM standard)

# HPKE wire format layout
_EPHEMERAL_PUBKEY_SIZE = 32   # X25519 raw public key
_WRAP_NONCE_SIZE = 12         # AES-GCM nonce for key wrapping
_WRAPPED_KEY_SIZE = 48        # 32-byte session key + 16-byte GCM tag
_WRAPPED_BLOB_SIZE = _EPHEMERAL_PUBKEY_SIZE + _WRAP_NONCE_SIZE + _WRAPPED_KEY_SIZE  # 92 bytes

# HKDF info string — identifies the key wrapping context
_HKDF_INFO = b"nobi-key-wrap-v1"


# ─── Availability ────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if the cryptography library is available."""
    return _CRYPTO_AVAILABLE


# ─── Phase 1: AES-256-GCM payload encryption ─────────────────────────────────

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

    Phase 1: key travels in plaintext (proof-of-concept).
    Phase 2: use wrap_session_key() to HPKE-wrap before transport.
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


# ─── Phase 2: HPKE key wrapping ──────────────────────────────────────────────

def generate_tee_keypair() -> Tuple[bytes, bytes]:
    """
    Generate an X25519 keypair for TEE key wrapping.

    Miners call this at startup and advertise the public key.
    The private key stays in the TEE enclave (never logged, never transmitted).

    Returns:
        Tuple of (private_key_bytes, public_key_bytes) — each 32 bytes (raw format)

    Raises:
        RuntimeError: if cryptography library is not available
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not available — cannot generate TEE keypair")

    private_key = X25519PrivateKey.generate()
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key_bytes, public_key_bytes


def wrap_session_key(session_key: bytes, miner_public_key: bytes) -> str:
    """
    Wrap (encrypt) a session key using the miner's X25519 public key.

    Uses ECIES-like scheme: X25519 ECDH + HKDF-SHA256 + AES-256-GCM.
    Each call uses a fresh ephemeral keypair (forward secrecy).

    Wire format (92 bytes, base64url-encoded):
      [32 bytes] ephemeral X25519 public key
      [12 bytes] AES-GCM nonce for key wrapping
      [48 bytes] encrypted session key + 16-byte GCM authentication tag

    Args:
        session_key: 32-byte AES-256 session key to wrap
        miner_public_key: 32-byte raw X25519 public key (from miner's TEE keypair)

    Returns:
        base64url-encoded wrapped key blob (92 bytes → 124 chars)

    Raises:
        ValueError: if inputs have wrong lengths
        RuntimeError: if cryptography library is not available
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not available — cannot wrap session key")
    if len(session_key) != KEY_SIZE_BYTES:
        raise ValueError(f"session_key must be {KEY_SIZE_BYTES} bytes, got {len(session_key)}")
    if len(miner_public_key) != 32:
        raise ValueError(f"miner_public_key must be 32 bytes, got {len(miner_public_key)}")

    # Step 1: Generate ephemeral X25519 keypair
    ephemeral_private = X25519PrivateKey.generate()
    ephemeral_public_bytes = ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    # Step 2: ECDH with miner's public key → shared secret
    miner_pubkey_obj = X25519PublicKey.from_public_bytes(miner_public_key)
    shared_secret = ephemeral_private.exchange(miner_pubkey_obj)

    # Step 3: HKDF-SHA256 derive 32-byte wrapping key from shared secret
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE_BYTES,
        salt=None,
        info=_HKDF_INFO,
    )
    wrapping_key = hkdf.derive(shared_secret)

    # Clear shared secret from memory (best effort)
    del shared_secret

    # Step 4: AES-256-GCM encrypt the session key
    wrap_nonce = os.urandom(_WRAP_NONCE_SIZE)
    aesgcm = AESGCM(wrapping_key)
    wrapped = aesgcm.encrypt(wrap_nonce, session_key, None)
    # wrapped = ciphertext(32 bytes) + tag(16 bytes) = 48 bytes

    # Clear wrapping key from memory (best effort)
    del wrapping_key

    # Step 5: Assemble wire format and encode
    blob = ephemeral_public_bytes + wrap_nonce + wrapped
    assert len(blob) == _WRAPPED_BLOB_SIZE, f"Unexpected blob size: {len(blob)}"

    return base64.urlsafe_b64encode(blob).decode("ascii")


def unwrap_session_key(wrapped_key_b64: str, miner_private_key: bytes) -> bytes:
    """
    Unwrap (decrypt) a session key using the miner's X25519 private key.

    Only the holder of the miner's TEE private key can perform this operation.
    Call this inside the TEE enclave.

    Args:
        wrapped_key_b64: base64url-encoded wrapped key blob (from wrap_session_key)
        miner_private_key: 32-byte raw X25519 private key (miner's TEE keypair)

    Returns:
        32-byte AES-256 session key

    Raises:
        ValueError: if inputs are malformed or have wrong lengths
        cryptography.exceptions.InvalidTag: if the wrapped key was tampered with
        RuntimeError: if cryptography library is not available
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography library not available — cannot unwrap session key")
    if not wrapped_key_b64:
        raise ValueError("wrapped_key_b64 must not be empty")
    if len(miner_private_key) != 32:
        raise ValueError(f"miner_private_key must be 32 bytes, got {len(miner_private_key)}")

    # Decode the blob
    try:
        blob = base64.urlsafe_b64decode(wrapped_key_b64.encode("ascii"))
    except Exception as e:
        raise ValueError(f"Invalid base64url in wrapped_key_b64: {e}")

    if len(blob) != _WRAPPED_BLOB_SIZE:
        raise ValueError(
            f"Wrapped key blob must be {_WRAPPED_BLOB_SIZE} bytes, got {len(blob)}"
        )

    # Parse wire format
    ephemeral_public_bytes = blob[:_EPHEMERAL_PUBKEY_SIZE]
    wrap_nonce = blob[_EPHEMERAL_PUBKEY_SIZE : _EPHEMERAL_PUBKEY_SIZE + _WRAP_NONCE_SIZE]
    wrapped_and_tag = blob[_EPHEMERAL_PUBKEY_SIZE + _WRAP_NONCE_SIZE :]

    # Step 1: Reconstruct miner private key object
    miner_priv = X25519PrivateKey.from_private_bytes(miner_private_key)

    # Step 2: ECDH with ephemeral public key → shared secret
    ephemeral_pubkey_obj = X25519PublicKey.from_public_bytes(ephemeral_public_bytes)
    shared_secret = miner_priv.exchange(ephemeral_pubkey_obj)

    # Step 3: HKDF-SHA256 derive wrapping key
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE_BYTES,
        salt=None,
        info=_HKDF_INFO,
    )
    wrapping_key = hkdf.derive(shared_secret)

    # Clear shared secret (best effort)
    del shared_secret

    # Step 4: AES-256-GCM decrypt — raises InvalidTag if tampered
    aesgcm = AESGCM(wrapping_key)
    session_key = aesgcm.decrypt(wrap_nonce, wrapped_and_tag, None)

    # Clear wrapping key (best effort)
    del wrapping_key

    if len(session_key) != KEY_SIZE_BYTES:
        raise ValueError(
            f"Unwrapped session key must be {KEY_SIZE_BYTES} bytes, got {len(session_key)}"
        )

    return session_key


# ─── High-level payload encrypt/decrypt ──────────────────────────────────────

def encrypt_payload(
    message: str,
    context: str = "",
    miner_pubkey: Optional[bytes] = None,
) -> dict:
    """
    High-level: encrypt both message and context for a single synapse.

    Generates one session key and uses it to encrypt both fields.
    If miner_pubkey is provided (Phase 2), the session key is HPKE-wrapped
    with the miner's X25519 public key. Otherwise, falls back to Phase 1
    (session key in plaintext).

    Args:
        message: The user's message (required)
        context: Memory context string (optional, can be empty)
        miner_pubkey: 32-byte X25519 public key for HPKE wrapping (Phase 2).
                      If None, falls back to Phase 1 (plaintext key_id).

    Returns:
        dict with keys:
          - encrypted: True
          - encryption_scheme: "aes-256-gcm-hpke-v1" (Phase 2) or "aes-256-gcm-v1" (Phase 1)
          - encrypted_message: "<nonce>.<ciphertext>" base64url
          - encrypted_context: "<nonce>.<ciphertext>" base64url (or "" if no context)
          - key_id: HPKE-wrapped session key (Phase 2) or plaintext base64url key (Phase 1)

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

    # Phase 2: HPKE-wrap the session key if miner public key is available
    if miner_pubkey is not None:
        key_id = wrap_session_key(key, miner_pubkey)
        scheme = ENCRYPTION_SCHEME_HPKE
    else:
        # Phase 1 fallback: session key in plaintext
        key_id = encode_key(key)
        scheme = ENCRYPTION_SCHEME

    # Clear key bytes from memory (best effort in Python)
    del key

    return {
        "encrypted": True,
        "encryption_scheme": scheme,
        "encrypted_message": encrypted_message,
        "encrypted_context": encrypted_context,
        "key_id": key_id,
    }


def decrypt_payload(
    encrypted_message: str,
    encrypted_context: str,
    key_id: str,
    miner_privkey: Optional[bytes] = None,
) -> Tuple[str, str]:
    """
    High-level: decrypt both message and context from synapse fields.

    If miner_privkey is provided and key_id is an HPKE-wrapped blob (Phase 2),
    unwraps the session key first. Otherwise, decodes key directly (Phase 1).

    Auto-detects Phase 1 vs Phase 2 based on key_id length:
      - Phase 1: 44 chars (base64url of 32 bytes)
      - Phase 2: 124 chars (base64url of 92 bytes)

    Args:
        encrypted_message: "<nonce>.<ciphertext>" string from synapse
        encrypted_context: "<nonce>.<ciphertext>" string from synapse (may be empty)
        key_id: base64url-encoded key (Phase 1) or wrapped blob (Phase 2)
        miner_privkey: 32-byte X25519 private key for HPKE unwrapping (Phase 2).
                       If None, treats key_id as Phase 1 plaintext key.

    Returns:
        Tuple of (plaintext_message, plaintext_context)
        plaintext_context is "" if encrypted_context was empty

    Raises:
        ValueError: if format is wrong
        RuntimeError: if crypto unavailable or decryption fails
    """
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("TEE encryption requires the cryptography library")

    # Determine Phase 1 vs Phase 2 based on key_id length
    # Phase 1: 44 chars (base64url of 32-byte raw key)
    # Phase 2: 124 chars (base64url of 92-byte HPKE blob)
    _is_phase2 = len(key_id) > 50  # Phase 2 blobs are 124 chars, Phase 1 keys are 44

    if _is_phase2 and miner_privkey is not None:
        # Phase 2: unwrap HPKE blob with miner's private key
        try:
            key = unwrap_session_key(key_id, miner_privkey)
        except Exception as e:
            raise RuntimeError(f"HPKE key unwrapping failed: {e}") from e
    else:
        # Phase 1: decode plaintext key directly (works with or without miner_privkey)
        key = decode_key(key_id)

    # Decrypt message
    try:
        msg_nonce, msg_cipher = encrypted_message.split(".", 1)
    except ValueError:
        raise ValueError("Invalid encrypted_message format — expected 'nonce.ciphertext'")

    plaintext_message = decrypt_message(msg_nonce, msg_cipher, key)

    # Decrypt context (optional)
    plaintext_context = ""
    if encrypted_context:
        try:
            ctx_nonce, ctx_cipher = encrypted_context.split(".", 1)
        except ValueError:
            raise ValueError("Invalid encrypted_context format — expected 'nonce.ciphertext'")
        plaintext_context = decrypt_message(ctx_nonce, ctx_cipher, key)

    del key
    return plaintext_message, plaintext_context


# ─── TEE miner detection ──────────────────────────────────────────────────────

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
