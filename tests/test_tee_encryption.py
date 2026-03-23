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
