"""
Tests for Project Nobi — Phase 5: TEE Encryption Module
========================================================

Tests:
  1. Encryption/decryption roundtrip (single message)
  2. Encryption/decryption roundtrip (message + context)
  3. Empty context handling
  4. Tamper detection (GCM authentication tag)
  5. Wrong key raises exception
  6. Key generation is random (no key reuse)
  7. Encrypted payload format validity
  8. CompanionRequest protocol fields
  9. Backward compatibility (encrypted=False still works)
  10. decrypt_payload error handling
  11. is_tee_miner detection
  12. encode_key / decode_key roundtrip
  13. Validator _build_synapse_for_miner function
  14. Miner forward with encrypted synapse (mock)
  15. Full integration: encrypt → decrypt → verify
"""

import base64
import os
import pytest

# ─── Module availability guard ───────────────────────────────────────────────

from nobi.privacy.tee_encryption import (
    is_available,
    generate_session_key,
    encrypt_message,
    decrypt_message,
    encode_key,
    decode_key,
    encrypt_payload,
    decrypt_payload,
    is_tee_miner,
    KEY_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    ENCRYPTION_SCHEME,
)


# ─── 1. Basic roundtrip ───────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    """Encrypting and decrypting a message returns the original plaintext."""
    key = generate_session_key()
    plaintext = "Hello, this is a secret user message!"
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)
    recovered = decrypt_message(nonce_b64, cipher_b64, key)
    assert recovered == plaintext


def test_encrypt_decrypt_unicode():
    """Roundtrip works with Unicode characters."""
    key = generate_session_key()
    plaintext = "こんにちは！こんばんは 🌙 Привет мир"
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)
    recovered = decrypt_message(nonce_b64, cipher_b64, key)
    assert recovered == plaintext


def test_encrypt_decrypt_empty_string():
    """Roundtrip works with empty string."""
    key = generate_session_key()
    plaintext = ""
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)
    recovered = decrypt_message(nonce_b64, cipher_b64, key)
    assert recovered == plaintext


def test_encrypt_decrypt_long_message():
    """Roundtrip works with a long message (simulating full conversation history)."""
    key = generate_session_key()
    plaintext = "A" * 10000 + " with some context" + "B" * 5000
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)
    recovered = decrypt_message(nonce_b64, cipher_b64, key)
    assert recovered == plaintext


# ─── 2. High-level payload encrypt/decrypt ───────────────────────────────────

def test_encrypt_payload_message_only():
    """encrypt_payload works with message only (no context)."""
    payload = encrypt_payload("Tell me about your day", "")
    assert payload["encrypted"] is True
    assert payload["encryption_scheme"] == ENCRYPTION_SCHEME
    assert payload["encrypted_message"] != ""
    assert payload["encrypted_context"] == ""  # empty context → empty string
    assert payload["key_id"] != ""


def test_encrypt_payload_with_context():
    """encrypt_payload encrypts both message and context."""
    payload = encrypt_payload(
        "How are you?",
        "User's name is Alice. She works as a teacher. Loves cats."
    )
    assert payload["encrypted"] is True
    assert payload["encrypted_message"] != ""
    assert payload["encrypted_context"] != ""
    assert payload["key_id"] != ""


def test_decrypt_payload_roundtrip_with_context():
    """decrypt_payload recovers original message and context."""
    message = "What's the weather like today?"
    context = "User is in London. Prefers metric units. Has umbrella 🌂."
    payload = encrypt_payload(message, context)
    recovered_msg, recovered_ctx = decrypt_payload(
        payload["encrypted_message"],
        payload["encrypted_context"],
        payload["key_id"],
    )
    assert recovered_msg == message
    assert recovered_ctx == context


def test_decrypt_payload_no_context():
    """decrypt_payload returns empty string for context when none was encrypted."""
    message = "Just a message, no context"
    payload = encrypt_payload(message, "")
    recovered_msg, recovered_ctx = decrypt_payload(
        payload["encrypted_message"],
        payload["encrypted_context"],
        payload["key_id"],
    )
    assert recovered_msg == message
    assert recovered_ctx == ""


# ─── 3. Tamper detection ─────────────────────────────────────────────────────

def test_tamper_detection_message():
    """Modifying the ciphertext raises an exception (GCM auth tag fails)."""
    from cryptography.exceptions import InvalidTag
    key = generate_session_key()
    plaintext = "Secret message that must not be tampered"
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)

    # Flip a byte in the ciphertext
    ciphertext_bytes = base64.urlsafe_b64decode(cipher_b64.encode("ascii"))
    tampered = bytearray(ciphertext_bytes)
    tampered[10] ^= 0xFF  # Flip bits at position 10
    tampered_b64 = base64.urlsafe_b64encode(bytes(tampered)).decode("ascii")

    with pytest.raises((InvalidTag, Exception)):
        decrypt_message(nonce_b64, tampered_b64, key)


def test_tamper_detection_nonce():
    """Modifying the nonce raises an exception."""
    from cryptography.exceptions import InvalidTag
    key = generate_session_key()
    plaintext = "Another secret message"
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key)

    # Flip bytes in nonce
    nonce_bytes = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
    tampered_nonce = bytearray(nonce_bytes)
    tampered_nonce[0] ^= 0xFF
    tampered_nonce_b64 = base64.urlsafe_b64encode(bytes(tampered_nonce)).decode("ascii")

    with pytest.raises((InvalidTag, Exception)):
        decrypt_message(tampered_nonce_b64, cipher_b64, key)


# ─── 4. Wrong key ────────────────────────────────────────────────────────────

def test_wrong_key_raises():
    """Decrypting with a different key raises an exception."""
    from cryptography.exceptions import InvalidTag
    key1 = generate_session_key()
    key2 = generate_session_key()
    assert key1 != key2  # keys must differ

    plaintext = "Top secret user message"
    nonce_b64, cipher_b64 = encrypt_message(plaintext, key1)

    with pytest.raises((InvalidTag, Exception)):
        decrypt_message(nonce_b64, cipher_b64, key2)


# ─── 5. Key generation properties ────────────────────────────────────────────

def test_key_is_correct_size():
    """Generated keys are exactly 32 bytes (AES-256)."""
    key = generate_session_key()
    assert len(key) == KEY_SIZE_BYTES == 32


def test_keys_are_unique():
    """Each call to generate_session_key produces a unique key."""
    keys = {generate_session_key() for _ in range(100)}
    # All 100 keys should be unique
    assert len(keys) == 100


def test_nonce_is_correct_size():
    """Generated nonces are exactly 12 bytes (96-bit, GCM standard)."""
    key = generate_session_key()
    nonce_b64, _ = encrypt_message("test", key)
    nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
    assert len(nonce) == NONCE_SIZE_BYTES == 12


def test_nonces_are_unique():
    """Each encryption call uses a different nonce."""
    key = generate_session_key()
    nonces = set()
    for _ in range(50):
        nonce_b64, _ = encrypt_message("same message", key)
        nonces.add(nonce_b64)
    assert len(nonces) == 50  # All nonces unique


# ─── 6. Key encode/decode ─────────────────────────────────────────────────────

def test_encode_decode_key_roundtrip():
    """encode_key + decode_key preserves exact key bytes."""
    key = generate_session_key()
    encoded = encode_key(key)
    assert isinstance(encoded, str)
    decoded = decode_key(encoded)
    assert decoded == key


def test_decode_key_wrong_length_raises():
    """decode_key raises if encoded key has wrong length."""
    bad_key = base64.urlsafe_b64encode(b"too-short").decode("ascii")
    with pytest.raises(ValueError):
        decode_key(bad_key)


# ─── 7. Invalid input handling ────────────────────────────────────────────────

def test_encrypt_wrong_key_length_raises():
    """encrypt_message raises ValueError if key is wrong length."""
    with pytest.raises(ValueError):
        encrypt_message("test", b"tooshort")


def test_decrypt_wrong_key_length_raises():
    """decrypt_message raises ValueError if key is wrong length."""
    with pytest.raises(ValueError):
        decrypt_message("nonce", "cipher", b"tooshort")


def test_decrypt_empty_inputs_raise():
    """decrypt_message raises ValueError if nonce or ciphertext is empty."""
    key = generate_session_key()
    with pytest.raises(ValueError):
        decrypt_message("", "someciphertext", key)
    with pytest.raises(ValueError):
        decrypt_message("somenonce", "", key)


def test_decrypt_payload_bad_format():
    """decrypt_payload raises ValueError if format is not 'nonce.ciphertext'."""
    payload = encrypt_payload("test message", "")
    with pytest.raises(ValueError):
        # Corrupt the format — remove the dot separator
        decrypt_payload(
            "nodot_here_at_all",
            payload["encrypted_context"],
            payload["key_id"],
        )


# ─── 8. Protocol fields ───────────────────────────────────────────────────────

def test_companion_request_encrypted_fields_default():
    """CompanionRequest has correct defaults for encrypted fields."""
    from nobi.protocol import CompanionRequest
    req = CompanionRequest(message="hello")
    assert req.encrypted is False
    assert req.encryption_scheme == ""
    assert req.encrypted_message == ""
    assert req.encrypted_context == ""
    assert req.key_id == ""


def test_companion_request_encrypted_fields_set():
    """CompanionRequest accepts encrypted fields correctly."""
    from nobi.protocol import CompanionRequest
    payload = encrypt_payload("secret user message", "Alice likes coffee")
    req = CompanionRequest(
        message="[encrypted]",
        user_id="user_123",
        encrypted=payload["encrypted"],
        encryption_scheme=payload["encryption_scheme"],
        encrypted_message=payload["encrypted_message"],
        encrypted_context=payload["encrypted_context"],
        key_id=payload["key_id"],
    )
    assert req.encrypted is True
    assert req.encryption_scheme == ENCRYPTION_SCHEME
    assert req.encrypted_message != ""
    assert req.key_id != ""


def test_companion_request_serialize_deserialize():
    """CompanionRequest encrypted fields survive serialization (dict roundtrip)."""
    from nobi.protocol import CompanionRequest
    payload = encrypt_payload("user message", "context data")
    req = CompanionRequest(
        message="[encrypted]",
        encrypted=True,
        encryption_scheme=payload["encryption_scheme"],
        encrypted_message=payload["encrypted_message"],
        encrypted_context=payload["encrypted_context"],
        key_id=payload["key_id"],
    )
    # Verify fields are all strings (JSON-serializable)
    assert isinstance(req.encrypted_message, str)
    assert isinstance(req.encrypted_context, str)
    assert isinstance(req.key_id, str)
    assert isinstance(req.encryption_scheme, str)

    # Decrypt from the synapse fields
    msg, ctx = decrypt_payload(req.encrypted_message, req.encrypted_context, req.key_id)
    assert msg == "user message"
    assert ctx == "context data"


# ─── 9. Backward compatibility ────────────────────────────────────────────────

def test_backward_compat_plaintext_synapse():
    """Non-encrypted CompanionRequest (encrypted=False) works as before."""
    from nobi.protocol import CompanionRequest
    req = CompanionRequest(
        message="Plain hello world",
        user_id="user_456",
        query_type="general",
    )
    assert req.encrypted is False
    assert req.message == "Plain hello world"
    assert req.encrypted_message == ""


def test_backward_compat_response_field():
    """CompanionRequest.response and deserialize() still work."""
    from nobi.protocol import CompanionRequest
    req = CompanionRequest(message="hello")
    req.response = "Hi there!"
    assert req.deserialize() == "Hi there!"


# ─── 10. is_tee_miner ────────────────────────────────────────────────────────

def test_is_tee_miner_positive_cases():
    """is_tee_miner returns True for known TEE model names."""
    assert is_tee_miner("deepseek-ai/DeepSeek-V3.1-TEE") is True
    assert is_tee_miner("gpt-oss-120b-TEE") is True
    assert is_tee_miner("moonshotai/Kimi-K2.5-TEE") is True
    assert is_tee_miner("some-model-TEE") is True
    assert is_tee_miner("MODEL_TEE") is True  # underscore variant


def test_is_tee_miner_negative_cases():
    """is_tee_miner returns False for non-TEE models."""
    assert is_tee_miner("deepseek-ai/DeepSeek-V3.0") is False
    assert is_tee_miner("gpt-4") is False
    assert is_tee_miner("") is False
    assert is_tee_miner("claude-3-sonnet") is False
    assert is_tee_miner("mistral-7b") is False


# ─── 11. Validator helper ─────────────────────────────────────────────────────

def test_build_synapse_creates_encrypted_synapse():
    """_build_synapse_for_miner returns an encrypted synapse when crypto is available."""
    from nobi.validator.forward import _build_synapse_for_miner
    synapse = _build_synapse_for_miner(
        query="What are you thinking about?",
        user_id="user_test_123",
        query_type="general",
    )
    if is_available():
        assert synapse.encrypted is True
        assert synapse.encryption_scheme == ENCRYPTION_SCHEME
        assert synapse.encrypted_message != ""
        assert synapse.key_id != ""
        # Plaintext message field should be the marker, not the real query
        assert synapse.message == "[encrypted]"
    else:
        # Fallback to plaintext
        assert synapse.encrypted is False
        assert synapse.message == "What are you thinking about?"


def test_build_synapse_with_context():
    """_build_synapse_for_miner encrypts context when provided."""
    from nobi.validator.forward import _build_synapse_for_miner
    synapse = _build_synapse_for_miner(
        query="How's it going?",
        user_id="user_ctx_test",
        query_type="social",
        context="User is called Bob. Works at a bakery.",
    )
    if is_available():
        assert synapse.encrypted is True
        assert synapse.encrypted_context != ""
    else:
        assert synapse.encrypted is False


def test_build_synapse_decryptable():
    """Synapse built by _build_synapse_for_miner can be decrypted to original query."""
    from nobi.validator.forward import _build_synapse_for_miner
    query = "What's the meaning of life?"
    context = "User likes philosophy and tea."
    synapse = _build_synapse_for_miner(query=query, user_id="u1", query_type="knowledge",
                                        context=context)
    if not is_available():
        pytest.skip("cryptography library not available")

    msg, ctx = decrypt_payload(
        synapse.encrypted_message,
        synapse.encrypted_context,
        synapse.key_id,
    )
    assert msg == query
    assert ctx == context


# ─── 12. End-to-end integration ──────────────────────────────────────────────

def test_full_encrypt_decrypt_pipeline():
    """
    Full pipeline test: validator encrypts → synapse fields → miner decrypts.

    Simulates what happens in the actual validator→miner flow:
    1. Validator encrypts using encrypt_payload
    2. Payload is set in CompanionRequest fields
    3. Miner receives synapse, detects encrypted=True
    4. Miner decrypts using decrypt_payload
    5. Recovered message matches original
    """
    from nobi.protocol import CompanionRequest

    original_message = "My name is Alice and I've been feeling anxious about my new job"
    original_context = "User: Alice, 28, software engineer. Started new role 2 weeks ago."

    # Validator side: encrypt
    payload = encrypt_payload(original_message, original_context)
    synapse = CompanionRequest(
        message="[encrypted]",
        user_id="user_alice",
        query_type="advice",
        encrypted=payload["encrypted"],
        encryption_scheme=payload["encryption_scheme"],
        encrypted_message=payload["encrypted_message"],
        encrypted_context=payload["encrypted_context"],
        key_id=payload["key_id"],
    )

    # Miner side: receive synapse, decrypt
    assert synapse.encrypted is True
    recovered_msg, recovered_ctx = decrypt_payload(
        synapse.encrypted_message,
        synapse.encrypted_context,
        synapse.key_id,
    )

    # Verify exact match
    assert recovered_msg == original_message
    assert recovered_ctx == original_context


def test_different_queries_produce_different_ciphertext():
    """Each encrypt_payload call produces unique ciphertext (no determinism)."""
    message = "Same message"
    context = "Same context"
    payload1 = encrypt_payload(message, context)
    payload2 = encrypt_payload(message, context)

    # Different keys
    assert payload1["key_id"] != payload2["key_id"]
    # Different ciphertexts
    assert payload1["encrypted_message"] != payload2["encrypted_message"]


def test_encryption_scheme_constant():
    """Encryption scheme is consistently set."""
    payload = encrypt_payload("test", "")
    assert payload["encryption_scheme"] == "aes-256-gcm-v1"
    assert payload["encryption_scheme"] == ENCRYPTION_SCHEME


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2: HPKE Key Wrapping Tests
# ═════════════════════════════════════════════════════════════════════════════

from nobi.privacy.tee_encryption import (
    generate_tee_keypair,
    wrap_session_key,
    unwrap_session_key,
    ENCRYPTION_SCHEME_HPKE,
)


# ─── 1. Keypair generation ───────────────────────────────────────────────────

def test_generate_tee_keypair_sizes():
    """generate_tee_keypair returns exactly 32 bytes for each key."""
    priv, pub = generate_tee_keypair()
    assert len(priv) == 32, f"Private key must be 32 bytes, got {len(priv)}"
    assert len(pub) == 32, f"Public key must be 32 bytes, got {len(pub)}"


def test_generate_tee_keypair_uniqueness():
    """Each call to generate_tee_keypair produces unique keys."""
    priv1, pub1 = generate_tee_keypair()
    priv2, pub2 = generate_tee_keypair()
    assert priv1 != priv2, "Private keys must be unique"
    assert pub1 != pub2, "Public keys must be unique"


def test_generate_tee_keypair_types():
    """generate_tee_keypair returns bytes objects."""
    priv, pub = generate_tee_keypair()
    assert isinstance(priv, bytes)
    assert isinstance(pub, bytes)


def test_keypair_private_not_equal_public():
    """Private key and public key are different (sanity check)."""
    priv, pub = generate_tee_keypair()
    assert priv != pub, "Private key and public key must differ"


# ─── 2. HPKE wrap/unwrap roundtrip ──────────────────────────────────────────

def test_wrap_unwrap_roundtrip():
    """wrap_session_key + unwrap_session_key recovers the original session key."""
    priv, pub = generate_tee_keypair()
    session_key = generate_session_key()

    wrapped = wrap_session_key(session_key, pub)
    recovered = unwrap_session_key(wrapped, priv)

    assert recovered == session_key


def test_wrap_output_is_string():
    """wrap_session_key returns a string."""
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)
    assert isinstance(wrapped, str)


def test_wrap_output_is_base64url():
    """wrap_session_key output is valid base64url."""
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)
    # Should decode without error
    decoded = base64.urlsafe_b64decode(wrapped.encode("ascii"))
    assert len(decoded) == 92  # 32 + 12 + 48


def test_wrap_produces_unique_blobs():
    """Each wrap_session_key call produces a unique blob (ephemeral keys)."""
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped1 = wrap_session_key(session_key, pub)
    wrapped2 = wrap_session_key(session_key, pub)
    assert wrapped1 != wrapped2, "Each wrap must use a different ephemeral key"


def test_wrap_unwrap_multiple_keys():
    """wrap/unwrap works correctly for multiple independent keypairs."""
    for _ in range(5):
        priv, pub = generate_tee_keypair()
        session_key = generate_session_key()
        wrapped = wrap_session_key(session_key, pub)
        recovered = unwrap_session_key(wrapped, priv)
        assert recovered == session_key


# ─── 3. Wrong private key rejection ─────────────────────────────────────────

def test_wrong_private_key_fails():
    """unwrap_session_key fails when using the wrong private key."""
    from cryptography.exceptions import InvalidTag
    priv1, pub1 = generate_tee_keypair()
    priv2, _pub2 = generate_tee_keypair()
    session_key = generate_session_key()

    wrapped = wrap_session_key(session_key, pub1)  # wrapped for priv1

    with pytest.raises((InvalidTag, Exception)):
        unwrap_session_key(wrapped, priv2)  # try to unwrap with priv2


def test_wrong_private_key_zero_bytes_fails():
    """unwrap_session_key fails with zeroed private key."""
    from cryptography.exceptions import InvalidTag
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)

    wrong_priv = bytes(32)  # all zeros
    with pytest.raises((InvalidTag, Exception)):
        unwrap_session_key(wrapped, wrong_priv)


# ─── 4. Tamper detection on wrapped key ─────────────────────────────────────

def test_tamper_wrapped_key_ephemeral_pubkey():
    """Tampering with the ephemeral public key in the blob causes failure."""
    from cryptography.exceptions import InvalidTag
    priv, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)

    # Flip a byte in the ephemeral public key section (first 32 bytes)
    blob = bytearray(base64.urlsafe_b64decode(wrapped.encode("ascii")))
    blob[5] ^= 0xFF
    tampered = base64.urlsafe_b64encode(bytes(blob)).decode("ascii")

    with pytest.raises((InvalidTag, Exception)):
        unwrap_session_key(tampered, priv)


def test_tamper_wrapped_key_nonce():
    """Tampering with the nonce section causes failure."""
    from cryptography.exceptions import InvalidTag
    priv, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)

    # Flip a byte in the nonce section (bytes 32-43)
    blob = bytearray(base64.urlsafe_b64decode(wrapped.encode("ascii")))
    blob[35] ^= 0xFF
    tampered = base64.urlsafe_b64encode(bytes(blob)).decode("ascii")

    with pytest.raises((InvalidTag, Exception)):
        unwrap_session_key(tampered, priv)


def test_tamper_wrapped_key_ciphertext():
    """Tampering with the ciphertext+tag section causes failure."""
    from cryptography.exceptions import InvalidTag
    priv, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)

    # Flip a byte in the wrapped key section (bytes 44-91)
    blob = bytearray(base64.urlsafe_b64decode(wrapped.encode("ascii")))
    blob[50] ^= 0xFF
    tampered = base64.urlsafe_b64encode(bytes(blob)).decode("ascii")

    with pytest.raises((InvalidTag, Exception)):
        unwrap_session_key(tampered, priv)


def test_tamper_truncated_blob_fails():
    """Truncated wrapped key blob raises ValueError."""
    priv, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)

    blob = base64.urlsafe_b64decode(wrapped.encode("ascii"))
    truncated = base64.urlsafe_b64encode(blob[:50]).decode("ascii")

    with pytest.raises(ValueError):
        unwrap_session_key(truncated, priv)


# ─── 5. Full pipeline with HPKE ─────────────────────────────────────────────

def test_full_hpke_pipeline():
    """Full pipeline: keygen → encrypt with HPKE → decrypt with HPKE → plaintext matches."""
    priv, pub = generate_tee_keypair()
    message = "Ultra secret user message — only TEE can read this"
    context = "User context: Alice, prefers metric units"

    # Validator side: encrypt with HPKE
    payload = encrypt_payload(message, context, miner_pubkey=pub)

    assert payload["encrypted"] is True
    assert payload["encryption_scheme"] == ENCRYPTION_SCHEME_HPKE

    # Miner TEE side: decrypt with private key
    recovered_msg, recovered_ctx = decrypt_payload(
        payload["encrypted_message"],
        payload["encrypted_context"],
        payload["key_id"],
        miner_privkey=priv,
    )

    assert recovered_msg == message
    assert recovered_ctx == context


def test_hpke_payload_scheme_is_hpke():
    """encrypt_payload with miner_pubkey sets HPKE scheme."""
    _, pub = generate_tee_keypair()
    payload = encrypt_payload("test", "ctx", miner_pubkey=pub)
    assert payload["encryption_scheme"] == ENCRYPTION_SCHEME_HPKE
    assert payload["encryption_scheme"] == "aes-256-gcm-hpke-v1"


def test_hpke_key_id_is_longer():
    """Phase 2 key_id (wrapped blob) is longer than Phase 1 (raw key)."""
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()

    phase1_key_id = encode_key(session_key)
    wrapped = wrap_session_key(session_key, pub)

    assert len(wrapped) > len(phase1_key_id)
    # Phase 1: 44 chars (32 bytes → base64url), Phase 2: 124 chars (92 bytes → base64url)
    assert len(phase1_key_id) == 44
    assert len(wrapped) == 124


# ─── 6. Backward compatibility: Phase 1 still works ─────────────────────────

def test_phase1_encrypt_payload_no_pubkey():
    """encrypt_payload without miner_pubkey uses Phase 1 scheme."""
    payload = encrypt_payload("test message", "context")
    assert payload["encryption_scheme"] == ENCRYPTION_SCHEME
    assert payload["encryption_scheme"] == "aes-256-gcm-v1"


def test_phase1_decrypt_payload_no_privkey():
    """decrypt_payload without miner_privkey works for Phase 1 payloads."""
    message = "backward compatible message"
    context = "backward compatible context"
    payload = encrypt_payload(message, context)  # Phase 1, no pubkey
    recovered_msg, recovered_ctx = decrypt_payload(
        payload["encrypted_message"],
        payload["encrypted_context"],
        payload["key_id"],
        miner_privkey=None,  # Phase 1 fallback
    )
    assert recovered_msg == message
    assert recovered_ctx == context


def test_phase1_decrypt_payload_with_privkey_succeeds():
    """Phase 1 key_id (44 chars) auto-detected and decoded even when privkey is provided."""
    priv, _pub = generate_tee_keypair()
    payload = encrypt_payload("test message", "")  # Phase 1, short key_id

    # With the auto-detect fix, Phase 1 key + miner_privkey should work
    # (falls back to Phase 1 decode instead of trying HPKE unwrap)
    msg, ctx = decrypt_payload(
        payload["encrypted_message"],
        payload["encrypted_context"],
        payload["key_id"],
        miner_privkey=priv,
    )
    assert msg == "test message"


def test_both_phases_same_payload_encryption():
    """Both Phase 1 and Phase 2 use the same AES-256-GCM for the payload."""
    priv, pub = generate_tee_keypair()
    message = "same message"
    context = "same context"

    payload_p1 = encrypt_payload(message, context)            # Phase 1
    payload_p2 = encrypt_payload(message, context, miner_pubkey=pub)  # Phase 2

    # Both are encrypted
    assert payload_p1["encrypted"] is True
    assert payload_p2["encrypted"] is True

    # Both can be decrypted to the same plaintext
    msg1, ctx1 = decrypt_payload(
        payload_p1["encrypted_message"],
        payload_p1["encrypted_context"],
        payload_p1["key_id"],
    )
    msg2, ctx2 = decrypt_payload(
        payload_p2["encrypted_message"],
        payload_p2["encrypted_context"],
        payload_p2["key_id"],
        miner_privkey=priv,
    )
    assert msg1 == msg2 == message
    assert ctx1 == ctx2 == context


# ─── 7. MinerKeyManager tests ────────────────────────────────────────────────

import tempfile
import shutil
from nobi.privacy.miner_keys import MinerKeyManager


def test_miner_key_manager_create():
    """MinerKeyManager creates a keypair on first run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        assert len(manager.get_public_key_bytes()) == 32
        assert len(manager.get_private_key()) == 32


def test_miner_key_manager_pubkey_b64():
    """MinerKeyManager.get_public_key_b64() returns a valid base64url string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        pub_b64 = manager.get_public_key_b64()
        assert isinstance(pub_b64, str)
        # 32 bytes → 44 chars in base64url (with padding)
        decoded = base64.urlsafe_b64decode(pub_b64.encode("ascii"))
        assert len(decoded) == 32


def test_miner_key_manager_save_and_load():
    """MinerKeyManager persists keypair to disk and reloads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager1 = MinerKeyManager(key_dir=tmpdir)
        pub1 = manager1.get_public_key_bytes()
        priv1 = manager1.get_private_key()

        # Create a second instance — should load from disk
        manager2 = MinerKeyManager(key_dir=tmpdir)
        pub2 = manager2.get_public_key_bytes()
        priv2 = manager2.get_private_key()

        assert pub1 == pub2, "Public key must be consistent across loads"
        assert priv1 == priv2, "Private key must be consistent across loads"


def test_miner_key_manager_consistent_keys():
    """MinerKeyManager returns the same keys each call within a session."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        assert manager.get_public_key_bytes() == manager.get_public_key_bytes()
        assert manager.get_private_key() == manager.get_private_key()


def test_miner_key_manager_key_files_exist():
    """MinerKeyManager creates key files on disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        assert manager.public_key_exists()
        import pathlib
        key_dir = pathlib.Path(tmpdir)
        assert (key_dir / "tee_private.key").exists()
        assert (key_dir / "tee_public.key").exists()


def test_miner_key_manager_file_permissions():
    """Private key file has restrictive permissions (0600)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        import pathlib, stat
        priv_path = pathlib.Path(tmpdir) / "tee_private.key"
        mode = stat.S_IMODE(os.stat(priv_path).st_mode)
        assert mode == 0o600, f"Private key file must be 0600, got {oct(mode)}"


def test_miner_key_manager_rotate():
    """MinerKeyManager.rotate_keypair() generates new keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        pub1 = manager.get_public_key_bytes()
        priv1 = manager.get_private_key()

        manager.rotate_keypair()

        pub2 = manager.get_public_key_bytes()
        priv2 = manager.get_private_key()

        assert pub1 != pub2, "Rotated public key must differ"
        assert priv1 != priv2, "Rotated private key must differ"


def test_miner_key_manager_wrap_unwrap_integration():
    """MinerKeyManager keys work with wrap_session_key/unwrap_session_key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MinerKeyManager(key_dir=tmpdir)
        session_key = generate_session_key()

        wrapped = wrap_session_key(session_key, manager.get_public_key_bytes())
        recovered = unwrap_session_key(wrapped, manager.get_private_key())

        assert recovered == session_key


# ─── 8. Mixed scenario tests ─────────────────────────────────────────────────

def test_mixed_miners_hpke_and_plaintext():
    """Validators can send HPKE to some miners and plaintext to others."""
    priv, pub = generate_tee_keypair()
    message = "Test message for mixed scenario"

    # Miner A: HPKE-capable
    payload_a = encrypt_payload(message, "", miner_pubkey=pub)
    assert payload_a["encryption_scheme"] == ENCRYPTION_SCHEME_HPKE
    msg_a, _ = decrypt_payload(
        payload_a["encrypted_message"], payload_a["encrypted_context"],
        payload_a["key_id"], miner_privkey=priv
    )
    assert msg_a == message

    # Miner B: No HPKE (Phase 1 fallback)
    payload_b = encrypt_payload(message, "")
    assert payload_b["encryption_scheme"] == ENCRYPTION_SCHEME
    msg_b, _ = decrypt_payload(
        payload_b["encrypted_message"], payload_b["encrypted_context"],
        payload_b["key_id"]
    )
    assert msg_b == message


def test_hpke_payload_not_decryptable_without_privkey():
    """An HPKE-wrapped payload cannot be decrypted without the miner private key."""
    priv, pub = generate_tee_keypair()
    other_priv, _other_pub = generate_tee_keypair()
    message = "Secret message"

    payload = encrypt_payload(message, "", miner_pubkey=pub)

    # Correct private key works
    msg, _ = decrypt_payload(
        payload["encrypted_message"], payload["encrypted_context"],
        payload["key_id"], miner_privkey=priv
    )
    assert msg == message

    # Wrong private key fails
    from cryptography.exceptions import InvalidTag
    with pytest.raises((InvalidTag, Exception)):
        decrypt_payload(
            payload["encrypted_message"], payload["encrypted_context"],
            payload["key_id"], miner_privkey=other_priv
        )


def test_protocol_tee_pubkey_field_default():
    """CompanionRequest has tee_pubkey field defaulting to empty string."""
    from nobi.protocol import CompanionRequest
    req = CompanionRequest(message="hello")
    assert hasattr(req, "tee_pubkey")
    assert req.tee_pubkey == ""


def test_protocol_tee_pubkey_field_set():
    """CompanionRequest tee_pubkey field can be set and retrieved."""
    from nobi.protocol import CompanionRequest
    _, pub = generate_tee_keypair()
    pub_b64 = base64.urlsafe_b64encode(pub).decode("ascii")
    req = CompanionRequest(message="test")
    req.tee_pubkey = pub_b64
    assert req.tee_pubkey == pub_b64


def test_full_hpke_end_to_end_with_key_manager():
    """
    Full end-to-end test with MinerKeyManager simulating the real flow:
    1. Miner starts up → MinerKeyManager generates/loads keypair
    2. Miner advertises public key (tee_pubkey field in response)
    3. Validator caches the public key
    4. Validator encrypts next query with HPKE using cached key
    5. Miner receives encrypted synapse, uses private key to unwrap
    6. Miner decrypts message → plaintext matches original
    """
    from nobi.protocol import CompanionRequest

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Miner starts up
        miner_keys = MinerKeyManager(key_dir=tmpdir)

        # Step 2: Miner advertises public key
        advertised_pubkey_b64 = miner_keys.get_public_key_b64()
        assert len(advertised_pubkey_b64) == 44  # base64url of 32 bytes

        # Step 3: Validator caches the key
        cached_pub_bytes = base64.urlsafe_b64decode(advertised_pubkey_b64.encode("ascii"))

        # Step 4: Validator builds HPKE-encrypted synapse
        original_message = "What's the meaning of life?"
        original_context = "User is a philosophy student"
        payload = encrypt_payload(original_message, original_context, miner_pubkey=cached_pub_bytes)

        synapse = CompanionRequest(
            message="[encrypted]",
            user_id="user_e2e_test",
            encrypted=payload["encrypted"],
            encryption_scheme=payload["encryption_scheme"],
            encrypted_message=payload["encrypted_message"],
            encrypted_context=payload["encrypted_context"],
            key_id=payload["key_id"],
        )

        # Verify it's Phase 2
        assert synapse.encryption_scheme == ENCRYPTION_SCHEME_HPKE

        # Step 5+6: Miner receives synapse, unwraps and decrypts
        recovered_msg, recovered_ctx = decrypt_payload(
            synapse.encrypted_message,
            synapse.encrypted_context,
            synapse.key_id,
            miner_privkey=miner_keys.get_private_key(),
        )

        assert recovered_msg == original_message
        assert recovered_ctx == original_context


def test_wrap_session_key_invalid_pubkey_length():
    """wrap_session_key raises ValueError for invalid pubkey length."""
    session_key = generate_session_key()
    with pytest.raises(ValueError):
        wrap_session_key(session_key, b"tooshort")


def test_unwrap_session_key_empty_input():
    """unwrap_session_key raises ValueError for empty input."""
    priv, _ = generate_tee_keypair()
    with pytest.raises(ValueError):
        unwrap_session_key("", priv)


def test_unwrap_session_key_invalid_privkey_length():
    """unwrap_session_key raises ValueError for invalid private key length."""
    _, pub = generate_tee_keypair()
    session_key = generate_session_key()
    wrapped = wrap_session_key(session_key, pub)
    with pytest.raises(ValueError):
        unwrap_session_key(wrapped, b"wrong_length")
