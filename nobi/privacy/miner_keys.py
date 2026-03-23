"""
Project Nobi — Miner TEE Key Manager (Phase 2)
===============================================
Manages the X25519 keypair used for HPKE key wrapping.

Miners generate a keypair on first run and persist it to disk.
The public key is advertised to validators so they can wrap session keys.
The private key stays on the miner's machine (ideally inside the TEE enclave).

Storage:
  - Directory: ~/.nobi/tee_keys/  (created with 0700 permissions)
  - Private key: ~/.nobi/tee_keys/tee_private.key  (raw 32 bytes, chmod 0600)
  - Public key:  ~/.nobi/tee_keys/tee_public.key   (raw 32 bytes, chmod 0644)

Security notes:
  - Private key file is chmod 0600 — only the miner process can read it
  - Key material is NEVER logged
  - On first run, a fresh keypair is generated
  - On subsequent runs, the existing keypair is loaded (stable identity)
"""

import os
import base64
import logging
from pathlib import Path

logger = logging.getLogger("nobi-miner-keys")

# Default key storage directory
_DEFAULT_KEY_DIR = os.path.expanduser("~/.nobi/tee_keys")
_PRIVATE_KEY_FILE = "tee_private.key"
_PUBLIC_KEY_FILE = "tee_public.key"


class MinerKeyManager:
    """
    Manages the miner's X25519 TEE keypair for HPKE key wrapping.

    Usage:
        manager = MinerKeyManager()
        pubkey_b64 = manager.get_public_key_b64()   # advertise to validators
        privkey = manager.get_private_key()          # use for unwrapping inside TEE
    """

    def __init__(self, key_dir: str = None):
        """
        Initialize the key manager.

        If keys exist on disk, they are loaded.
        If not, a new keypair is generated and saved.

        Args:
            key_dir: Directory to store key files. Defaults to ~/.nobi/tee_keys/
        """
        self._key_dir = Path(key_dir or _DEFAULT_KEY_DIR)
        self._private_key_path = self._key_dir / _PRIVATE_KEY_FILE
        self._public_key_path = self._key_dir / _PUBLIC_KEY_FILE

        self._private_key_bytes: bytes = b""
        self._public_key_bytes: bytes = b""

        self._load_or_generate()

    def _load_or_generate(self) -> None:
        """Load existing keypair from disk, or generate a new one."""
        if self._private_key_path.exists() and self._public_key_path.exists():
            self._load_keypair()
        else:
            self._generate_and_save_keypair()

    def _generate_and_save_keypair(self) -> None:
        """Generate a fresh X25519 keypair and save to disk."""
        from nobi.privacy.tee_encryption import generate_tee_keypair
        logger.info(f"Generating new TEE keypair in {self._key_dir}")

        private_key_bytes, public_key_bytes = generate_tee_keypair()

        # Create directory with restrictive permissions (owner-only)
        self._key_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._key_dir, 0o700)

        # Write private key — chmod 0600 (owner read/write only)
        self._private_key_path.write_bytes(private_key_bytes)
        os.chmod(self._private_key_path, 0o600)

        # Write public key — chmod 0644 (readable by others)
        self._public_key_path.write_bytes(public_key_bytes)
        os.chmod(self._public_key_path, 0o644)

        self._private_key_bytes = private_key_bytes
        self._public_key_bytes = public_key_bytes

        logger.info(
            f"TEE keypair generated — public key: {self.get_public_key_b64()[:16]}..."
        )

    def _load_keypair(self) -> None:
        """Load existing keypair from disk."""
        try:
            private_key_bytes = self._private_key_path.read_bytes()
            public_key_bytes = self._public_key_path.read_bytes()

            if len(private_key_bytes) != 32:
                raise ValueError(
                    f"Private key file has wrong size: {len(private_key_bytes)} bytes (expected 32)"
                )
            if len(public_key_bytes) != 32:
                raise ValueError(
                    f"Public key file has wrong size: {len(public_key_bytes)} bytes (expected 32)"
                )

            self._private_key_bytes = private_key_bytes
            self._public_key_bytes = public_key_bytes
            logger.info(
                f"Loaded TEE keypair from {self._key_dir} — "
                f"public key: {self.get_public_key_b64()[:16]}..."
            )
        except Exception as e:
            logger.error(f"Failed to load TEE keypair: {e} — regenerating")
            self._generate_and_save_keypair()

    def get_public_key_bytes(self) -> bytes:
        """
        Return the raw 32-byte X25519 public key.

        This can be passed directly to wrap_session_key().
        """
        return self._public_key_bytes

    def get_public_key_b64(self) -> str:
        """
        Return the base64url-encoded public key for advertisement.

        Validators store this and use it to wrap session keys via HPKE.
        This is safe to transmit, log (the public key only), and store.
        """
        return base64.urlsafe_b64encode(self._public_key_bytes).decode("ascii")

    def get_private_key(self) -> bytes:
        """
        Return the raw 32-byte X25519 private key.

        USE ONLY INSIDE TEE ENCLAVE for unwrapping session keys.
        NEVER log, transmit, or store this value beyond the enclave.
        """
        return self._private_key_bytes

    def rotate_keypair(self) -> None:
        """
        Generate a fresh keypair, replacing the existing one.

        Call this to rotate the miner's TEE keys. Note: validators will
        need to re-learn the new public key before HPKE wrapping works again.
        In the interim, validators fall back to Phase 1 (plaintext key_id).
        """
        logger.info("Rotating TEE keypair")
        self._generate_and_save_keypair()

    def public_key_exists(self) -> bool:
        """Return True if key files exist on disk."""
        return self._private_key_path.exists() and self._public_key_path.exists()

    def __repr__(self) -> str:
        return (
            f"MinerKeyManager(key_dir={self._key_dir}, "
            f"pubkey={self.get_public_key_b64()[:8]}...)"
        )
