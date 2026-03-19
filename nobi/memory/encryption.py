"""
Project Nobi — Memory Encryption (Privacy Phase A)
====================================================
Client-side encryption for user memories.

Phase A: Encryption at rest — miners store encrypted blobs in SQLite.
The miner CAN decrypt (it has the master secret). Protection is against
casual data exposure (reading the SQLite file directly).

Full protection (miner can't decrypt) comes in Phase B/C.

Uses:
  - Fernet (AES-128-CBC + HMAC-SHA256) — industry standard
  - PBKDF2 with 100,000 iterations for per-user key derivation
  - Master secret from NOBI_ENCRYPTION_SECRET env var
"""

import os
import base64
import hashlib
import logging

logger = logging.getLogger("nobi-encryption")

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography library not installed — encryption disabled. "
        "Install with: pip install cryptography"
    )


# Fernet tokens always start with 'gAAAAA' (base64-encoded version byte 0x80)
FERNET_PREFIX = "gAAAAA"


def _get_master_secret() -> str:
    """
    Get the master encryption secret from environment.
    Falls back to reading from ~/.nobi/encryption.key if env not set.
    """
    secret = os.environ.get("NOBI_ENCRYPTION_SECRET", "")
    if secret:
        return secret

    # Try reading from key file
    key_path = os.path.expanduser("~/.nobi/encryption.key")
    if os.path.exists(key_path):
        try:
            with open(key_path, "r") as f:
                secret = f.read().strip()
            if secret:
                # Cache in env for subsequent calls
                os.environ["NOBI_ENCRYPTION_SECRET"] = secret
                return secret
        except Exception as e:
            logger.warning(f"Failed to read encryption key file: {e}")

    return ""


def generate_master_secret() -> str:
    """
    Generate a new master secret and save to ~/.nobi/encryption.key.
    Returns the generated secret.
    """
    secret = Fernet.generate_key().decode("utf-8")

    key_dir = os.path.expanduser("~/.nobi")
    os.makedirs(key_dir, exist_ok=True)
    key_path = os.path.join(key_dir, "encryption.key")

    try:
        with open(key_path, "w") as f:
            f.write(secret)
        # Restrict permissions (owner read/write only)
        os.chmod(key_path, 0o600)
        logger.info(f"Generated new encryption secret → {key_path}")
    except Exception as e:
        logger.error(f"Failed to save encryption key: {e}")

    os.environ["NOBI_ENCRYPTION_SECRET"] = secret
    return secret


def ensure_master_secret() -> str:
    """
    Ensure a master secret exists. Generate one if needed.
    Returns the secret string.
    """
    secret = _get_master_secret()
    if not secret:
        if not CRYPTO_AVAILABLE:
            logger.warning("Cannot generate secret — cryptography library not installed")
            return ""
        secret = generate_master_secret()
    return secret


def get_user_key(user_id: str) -> "Fernet | None":
    """
    Derive a per-user Fernet encryption key.

    Key derivation: PBKDF2(master_secret + user_id, salt=sha256(user_id), iterations=100000)
    The result is a 32-byte key, base64-encoded for Fernet.

    Returns None if encryption is unavailable.
    """
    if not CRYPTO_AVAILABLE:
        return None

    master_secret = _get_master_secret()
    if not master_secret:
        return None

    try:
        # Salt derived from user_id hash (deterministic per user)
        salt = hashlib.sha256(user_id.encode("utf-8")).digest()

        # Key material = master_secret + user_id
        key_material = (master_secret + user_id).encode("utf-8")

        # PBKDF2 derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = kdf.derive(key_material)

        # Fernet requires url-safe base64 encoded 32-byte key
        fernet_key = base64.urlsafe_b64encode(derived_key)
        return Fernet(fernet_key)

    except Exception as e:
        logger.error(f"Key derivation failed for user {user_id}: {e}")
        return None


def encrypt_memory(user_id: str, plaintext: str) -> str:
    """
    Encrypt a memory string for a specific user.

    Returns base64-encoded Fernet token string.
    If encryption fails, returns the original plaintext with a warning.
    """
    if not plaintext:
        return plaintext

    fernet = get_user_key(user_id)
    if fernet is None:
        logger.debug("Encryption unavailable — returning plaintext")
        return plaintext

    try:
        token = fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")
    except Exception as e:
        logger.warning(f"Encryption failed for user {user_id}: {e}")
        return plaintext


def decrypt_memory(user_id: str, ciphertext: str) -> str:
    """
    Decrypt a memory string for a specific user.

    If decryption fails (wrong key, corrupted data, or plaintext input),
    returns the raw data with a warning log. Never crashes.
    """
    if not ciphertext:
        return ciphertext

    # If it's not encrypted, return as-is (backward compatibility)
    if not is_encrypted(ciphertext):
        return ciphertext

    fernet = get_user_key(user_id)
    if fernet is None:
        logger.warning(f"Decryption unavailable for user {user_id} — returning raw data")
        return ciphertext

    try:
        plaintext = fernet.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken:
        logger.warning(f"Decryption failed (invalid token) for user {user_id} — returning raw data")
        return ciphertext
    except Exception as e:
        logger.warning(f"Decryption error for user {user_id}: {e} — returning raw data")
        return ciphertext


def is_encrypted(text: str) -> bool:
    """
    Detect if a string is a Fernet-encrypted token.

    Fernet tokens are base64url-encoded and always start with 'gAAAAA'
    (version byte 0x80 followed by timestamp bytes).
    """
    if not text or not isinstance(text, str):
        return False

    # Quick prefix check
    if not text.startswith(FERNET_PREFIX):
        return False

    # Fernet tokens are always a specific structure:
    # version (1 byte) + timestamp (8 bytes) + IV (16 bytes) + ciphertext (>=16 bytes) + HMAC (32 bytes)
    # Minimum base64 length: ceil((1+8+16+16+32)/3)*4 = 100 chars minimum
    if len(text) < 100:
        return False

    # Verify it's valid base64url
    try:
        base64.urlsafe_b64decode(text.encode("utf-8"))
        return True
    except Exception:
        return False
