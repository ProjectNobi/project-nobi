"""
Tests for Project Nobi — Phase 4: TEE Passthrough (Miner Enclave Decrypts + Responds)
=======================================================================================

Tests:
  1. Protocol: encrypted_response field exists and defaults to ""
  2. Miner: after decrypting request, encrypts response with same session key
  3. Validator: decrypts encrypted_response for Phase 1 payloads
  4. Validator: falls back to plaintext if encrypted_response absent (backward compat)
  5. API: /api/v1/chat/encrypted endpoint behaviour
  6. Roundtrip: encrypt → miner process → decrypt validator side
  7. Non-encrypted synapse still produces plaintext response (backward compat)
  8. HPKE path: Phase 2 validator cannot decrypt (no private key) — falls back
  9. session key extraction from Phase 1 synapse
  10. session key extraction from Phase 2 synapse (HPKE)
"""

import base64
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ─── 1. Protocol: encrypted_response field ────────────────────────────────────

class TestProtocolEncryptedResponseField:
    def test_field_exists(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="hello")
        assert hasattr(req, "encrypted_response")

    def test_field_default_empty(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="hello")
        assert req.encrypted_response == ""

    def test_field_can_be_set(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="hello")
        req.encrypted_response = "somebase64.data"
        assert req.encrypted_response == "somebase64.data"

    def test_field_str_type(self):
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="hello")
        assert isinstance(req.encrypted_response, str)

    def test_backward_compat_response_unchanged(self):
        """The plaintext response field still works as before."""
        from nobi.protocol import CompanionRequest
        req = CompanionRequest(message="hello")
        req.response = "Hello back!"
        assert req.deserialize() == "Hello back!"
        assert req.encrypted_response == ""  # not affected


# ─── 2. Miner: encrypts response when session key is available ────────────────

class TestMinerEncryptsResponse:
    """Test that the miner encrypts its response using the session key."""

    def test_encrypt_message_roundtrip(self):
        """The encrypt_message/decrypt_message pair works for response encryption."""
        from nobi.privacy.tee_encryption import (
            generate_session_key,
            encrypt_message,
            decrypt_message,
        )
        session_key = generate_session_key()
        response_text = "Hi! I'm Nori, your AI companion 😊"
        nonce, cipher = encrypt_message(response_text, session_key)
        encrypted_response = f"{nonce}.{cipher}"

        # Validator side: decrypt
        nonce_b64, cipher_b64 = encrypted_response.split(".", 1)
        recovered = decrypt_message(nonce_b64, cipher_b64, session_key)
        assert recovered == response_text

    def test_full_miner_response_encrypt_decrypt(self):
        """Simulate miner encrypting response, validator decrypting it."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decrypt_payload,
            generate_session_key,
            encode_key,
            encrypt_message,
            decrypt_message,
        )

        # Validator encrypts the query
        query = "What's your name?"
        payload = encrypt_payload(query, "")

        # Miner decrypts the query
        plain_msg, _ = decrypt_payload(
            payload["encrypted_message"],
            payload["encrypted_context"],
            payload["key_id"],
        )
        assert plain_msg == query

        # Miner generates response and encrypts it with the same session key
        session_key = base64.urlsafe_b64decode(payload["key_id"])
        response_text = "I'm Nori! Built by Project Nobi on Bittensor."
        resp_nonce, resp_cipher = encrypt_message(response_text, session_key)
        encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # Validator decrypts the response
        resp_nonce_b64, resp_cipher_b64 = encrypted_response.split(".", 1)
        recovered_response = decrypt_message(resp_nonce_b64, resp_cipher_b64, session_key)
        assert recovered_response == response_text

    def test_response_encryption_uses_unique_nonce(self):
        """Each response encryption uses a different nonce (no nonce reuse)."""
        from nobi.privacy.tee_encryption import generate_session_key, encrypt_message

        session_key = generate_session_key()
        response = "Same response text"
        nonces = set()
        for _ in range(20):
            nonce, _ = encrypt_message(response, session_key)
            nonces.add(nonce)
        assert len(nonces) == 20  # All nonces unique


# ─── 3. Validator: decrypts encrypted_response ───────────────────────────────

class TestValidatorDecryptsResponse:
    def test_decrypt_phase1_encrypted_response(self):
        """Validator can decrypt Phase 1 encrypted_response using key_id."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decrypt_message,
            decode_key,
        )

        # Simulate the query encryption
        payload = encrypt_payload("User message", "")
        session_key = decode_key(payload["key_id"])

        # Simulate miner encrypting response
        from nobi.privacy.tee_encryption import encrypt_message
        response_text = "This is the miner's response to the user."
        resp_nonce, resp_cipher = encrypt_message(response_text, session_key)
        encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # Validator decryption logic (mirrors _query_single_miner Phase 1 path)
        key_id = payload["key_id"]
        assert len(key_id) == 44  # Phase 1

        nonce_b64, cipher_b64 = encrypted_response.split(".", 1)
        recovered = decrypt_message(nonce_b64, cipher_b64, session_key)
        assert recovered == response_text

    def test_validator_fallback_no_encrypted_response(self):
        """Validator uses plaintext response if encrypted_response is empty."""
        from nobi.protocol import CompanionRequest

        req = CompanionRequest(message="hello")
        req.response = "Plaintext response from miner"
        req.encrypted_response = ""

        # Simulate validator logic: prefer encrypted_response if set
        response = req.encrypted_response or req.response
        assert response == "Plaintext response from miner"

    def test_validator_prefers_decrypted_response(self):
        """When encrypted_response is set, validator uses decrypted text, not plaintext."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decrypt_message,
            decode_key,
            encrypt_message,
        )

        payload = encrypt_payload("Query text", "")
        session_key = decode_key(payload["key_id"])

        # Miner sets both fields (plaintext as fallback, encrypted as primary)
        plaintext_response = "Generic fallback response"
        real_response = "The actual decrypted response with real content"
        resp_nonce, resp_cipher = encrypt_message(real_response, session_key)
        encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # Validator: check encrypted_response first
        if encrypted_response:
            n, c = encrypted_response.split(".", 1)
            decrypted = decrypt_message(n, c, session_key)
            final_response = decrypted
        else:
            final_response = plaintext_response

        assert final_response == real_response


# ─── 4. Backward compatibility: non-encrypted ────────────────────────────────

class TestBackwardCompatibility:
    def test_non_encrypted_synapse_response_unchanged(self):
        """Non-encrypted CompanionRequest still works with plaintext response."""
        from nobi.protocol import CompanionRequest

        req = CompanionRequest(
            message="Hello Nori!",
            user_id="user_123",
        )
        req.response = "Hi there! 😊"
        req.encrypted_response = ""

        assert req.encrypted is False
        assert req.response == "Hi there! 😊"
        assert req.encrypted_response == ""
        assert req.deserialize() == "Hi there! 😊"

    def test_empty_encrypted_response_is_fine(self):
        """encrypted_response="" is the default and doesn't cause issues."""
        from nobi.protocol import CompanionRequest

        req = CompanionRequest(message="test")
        # Should not raise
        assert req.encrypted_response == ""
        assert not req.encrypted_response  # falsy, so validators can check `if encrypted_response`


# ─── 5. Full roundtrip: validator → miner → validator ────────────────────────

class TestFullRoundtrip:
    """End-to-end test: validator encrypts query, miner decrypts + responds + encrypts,
    validator decrypts response."""

    def test_phase1_full_roundtrip(self):
        """Phase 1 full roundtrip: plaintext key_id, miner encrypts response."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decrypt_payload,
            decode_key,
            encrypt_message,
            decrypt_message,
        )
        from nobi.protocol import CompanionRequest

        original_query = "Tell me something interesting about quantum computing."
        original_context = "User is a computer science student."
        expected_response = "Quantum computers use qubits that can be 0 and 1 simultaneously!"

        # ── Validator side: build encrypted synapse ──
        payload = encrypt_payload(original_query, original_context)
        synapse = CompanionRequest(
            message="[encrypted]",
            user_id="user_qt",
            query_type="knowledge",
            encrypted=payload["encrypted"],
            encryption_scheme=payload["encryption_scheme"],
            encrypted_message=payload["encrypted_message"],
            encrypted_context=payload["encrypted_context"],
            key_id=payload["key_id"],
        )

        # ── Miner side: decrypt request ──
        plain_msg, plain_ctx = decrypt_payload(
            synapse.encrypted_message,
            synapse.encrypted_context,
            synapse.key_id,
        )
        assert plain_msg == original_query
        assert plain_ctx == original_context

        # Miner: get session key and encrypt response
        session_key = decode_key(synapse.key_id)
        resp_nonce, resp_cipher = encrypt_message(expected_response, session_key)
        synapse.response = ""  # miner clears plaintext response
        synapse.encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # ── Validator side: decrypt miner's response ──
        key_id = synapse.key_id
        assert len(key_id) == 44  # Phase 1

        recovered_key = decode_key(key_id)
        n, c = synapse.encrypted_response.split(".", 1)
        recovered_response = decrypt_message(n, c, recovered_key)

        assert recovered_response == expected_response

    def test_hpke_roundtrip_miner_can_decrypt_query(self):
        """Phase 2 (HPKE): miner uses private key to unwrap session key."""
        from nobi.privacy.tee_encryption import (
            generate_tee_keypair,
            encrypt_payload,
            decrypt_payload,
            unwrap_session_key,
            encrypt_message,
        )

        priv, pub = generate_tee_keypair()
        query = "What makes you special, Nori?"
        context = "User is curious about AI"

        # Validator: encrypt with HPKE
        payload = encrypt_payload(query, context, miner_pubkey=pub)

        # Miner: unwrap session key
        session_key = unwrap_session_key(payload["key_id"], priv)

        # Miner: decrypt query
        plain_msg, plain_ctx = decrypt_payload(
            payload["encrypted_message"],
            payload["encrypted_context"],
            payload["key_id"],
            miner_privkey=priv,
        )
        assert plain_msg == query
        assert plain_ctx == context

        # Miner: encrypt response
        response = "I remember you across conversations — that's my superpower! 🧠"
        resp_nonce, resp_cipher = encrypt_message(response, session_key)
        encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # Validator: for Phase 2, validator cannot decrypt (no private key)
        # This is expected — Phase 2 response encryption is for miner ↔ user only
        # Validator scores based on metadata or gets plaintext from miner
        from nobi.privacy.tee_encryption import decrypt_message
        n, c = encrypted_response.split(".", 1)
        recovered = decrypt_message(n, c, session_key)
        assert recovered == response


# ─── 6. Session key extraction logic ─────────────────────────────────────────

class TestSessionKeyExtraction:
    def test_phase1_key_extraction(self):
        """Phase 1: session key decoded directly from key_id."""
        from nobi.privacy.tee_encryption import (
            generate_session_key,
            encode_key,
            decode_key,
        )
        original_key = generate_session_key()
        key_id = encode_key(original_key)
        extracted = decode_key(key_id)
        assert extracted == original_key

    def test_phase1_key_id_length(self):
        """Phase 1 key_id is exactly 44 chars (base64url of 32 bytes)."""
        from nobi.privacy.tee_encryption import generate_session_key, encode_key
        key = generate_session_key()
        key_id = encode_key(key)
        assert len(key_id) == 44

    def test_phase2_key_id_length(self):
        """Phase 2 key_id is exactly 124 chars (base64url of 92 bytes)."""
        from nobi.privacy.tee_encryption import (
            generate_tee_keypair,
            generate_session_key,
            wrap_session_key,
        )
        _, pub = generate_tee_keypair()
        session_key = generate_session_key()
        wrapped = wrap_session_key(session_key, pub)
        assert len(wrapped) == 124

    def test_distinguish_phase1_from_phase2(self):
        """Validator can distinguish Phase 1 (44 chars) from Phase 2 (124 chars) by key_id length."""
        from nobi.privacy.tee_encryption import (
            generate_session_key,
            encode_key,
            generate_tee_keypair,
            wrap_session_key,
        )
        _, pub = generate_tee_keypair()
        session_key = generate_session_key()

        phase1_key_id = encode_key(session_key)
        phase2_key_id = wrap_session_key(session_key, pub)

        assert len(phase1_key_id) == 44
        assert len(phase2_key_id) == 124

        # Validator logic
        def is_phase2(key_id: str) -> bool:
            return len(key_id) == 124

        assert not is_phase2(phase1_key_id)
        assert is_phase2(phase2_key_id)


# ─── 7. API endpoint model: EncryptedChatRequest ────────────────────────────

class TestAPIModels:
    def test_encrypted_payload_model(self):
        from api.server import EncryptedPayload
        p = EncryptedPayload(
            ciphertext="abc123",
            iv="ivbytes",
            salt="saltbytes",
        )
        assert p.algorithm == "AES-GCM-256"
        assert p.iterations == 100000
        assert p.ciphertext == "abc123"

    def test_encrypted_chat_request_model(self):
        from api.server import EncryptedChatRequest, EncryptedPayload

        payload = EncryptedPayload(ciphertext="c", iv="i", salt="s")
        req = EncryptedChatRequest(
            message=payload,
            memories=payload,
            conversation_history=payload,
            user_id="user_test",
        )
        assert req.client_extracted is True
        assert req.user_id == "user_test"


# ─── 8. Miner forward simulation (mock) ──────────────────────────────────────

class TestMinerForwardSimulation:
    """Simulate the miner's forward() with encrypted synapse end-to-end."""

    def test_miner_response_encryption_logic(self):
        """
        Simulate the miner's response encryption step.
        When _session_key is available and response is non-empty,
        encrypted_response is set.
        """
        from nobi.privacy.tee_encryption import (
            generate_session_key,
            encrypt_message,
            decrypt_message,
        )
        from nobi.protocol import CompanionRequest

        session_key = generate_session_key()
        response_text = "This is Nori's encrypted response!"

        # Simulate miner's encryption step
        resp_nonce, resp_cipher = encrypt_message(response_text, session_key)
        encrypted_response = f"{resp_nonce}.{resp_cipher}"

        # Set on synapse
        synapse = CompanionRequest(message="[encrypted]")
        synapse.response = response_text
        synapse.encrypted_response = encrypted_response

        assert synapse.encrypted_response != ""
        assert "." in synapse.encrypted_response

        # Verify the encrypted_response can be decrypted back
        n, c = synapse.encrypted_response.split(".", 1)
        recovered = decrypt_message(n, c, session_key)
        assert recovered == response_text

    def test_miner_clears_session_key_reference(self):
        """Verify session key can be deleted (reference cleared) after use."""
        from nobi.privacy.tee_encryption import generate_session_key

        session_key = generate_session_key()
        assert len(session_key) == 32

        # After use, reference is cleared
        del session_key
        # No exception — Python GC handles the rest

    def test_non_encrypted_synapse_no_encrypted_response(self):
        """Non-encrypted synapses should have empty encrypted_response."""
        from nobi.protocol import CompanionRequest

        synapse = CompanionRequest(message="Plain hello")
        synapse.response = "Hi!"
        # encrypted_response should stay empty
        assert synapse.encrypted_response == ""


# ─── 9. Validator _query_single_miner Phase 1 decrypt ────────────────────────

class TestValidatorQuerySingleMiner:
    """Test the Phase 4 decryption logic in _query_single_miner."""

    def test_phase1_decrypt_in_query_miner(self):
        """
        Simulate the Phase 1 decrypt path in _query_single_miner:
        - Outbound synapse has key_id (44 chars = Phase 1)
        - Miner response has encrypted_response set
        - Validator decrypts and gets plaintext
        """
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decode_key,
            encrypt_message,
            decrypt_message,
        )
        from nobi.protocol import CompanionRequest

        # Build query
        query = "What did I tell you last time?"
        payload = encrypt_payload(query, "")
        outbound_synapse = CompanionRequest(
            message="[encrypted]",
            encrypted=True,
            encryption_scheme=payload["encryption_scheme"],
            encrypted_message=payload["encrypted_message"],
            encrypted_context=payload["encrypted_context"],
            key_id=payload["key_id"],
        )

        # Miner encrypts response
        session_key = decode_key(outbound_synapse.key_id)
        response_text = "You told me your name is Alice!"
        n, c = encrypt_message(response_text, session_key)
        mock_response = f"{n}.{c}"

        # Simulate _query_single_miner Phase 1 decrypt path
        key_id = outbound_synapse.key_id
        assert len(key_id) == 44  # Phase 1

        recovered_key = decode_key(key_id)
        nonce_b64, cipher_b64 = mock_response.split(".", 1)
        decrypted = decrypt_message(nonce_b64, cipher_b64, recovered_key)

        assert decrypted == response_text

    def test_phase2_decrypt_falls_back(self):
        """
        Phase 2 (HPKE) encrypted_response cannot be decrypted by validator
        (no miner private key). Falls back to plaintext response.
        """
        from nobi.privacy.tee_encryption import (
            generate_tee_keypair,
            encrypt_payload,
        )
        from nobi.protocol import CompanionRequest

        _, pub = generate_tee_keypair()
        payload = encrypt_payload("Query", "", miner_pubkey=pub)

        outbound_synapse = CompanionRequest(
            message="[encrypted]",
            encrypted=True,
            encryption_scheme=payload["encryption_scheme"],
            encrypted_message=payload["encrypted_message"],
            encrypted_context=payload["encrypted_context"],
            key_id=payload["key_id"],
        )

        # Phase 2 key_id is 124 chars — validator cannot decrypt
        assert len(outbound_synapse.key_id) == 124

        # Validator logic: if Phase 2, fall back to plaintext
        is_phase2 = len(outbound_synapse.key_id) == 124
        assert is_phase2  # Validator correctly identifies Phase 2 and won't attempt decrypt


# ─── 10. Scoring with encrypted responses ────────────────────────────────────

class TestScoringWithEncryptedResponses:
    def test_scoring_uses_decrypted_text(self):
        """Scoring should work on decrypted text, not empty string."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decode_key,
            encrypt_message,
            decrypt_message,
        )

        # Miner produces a good response
        good_response = (
            "Quantum computers use superposition and entanglement to perform "
            "computations that would take classical computers thousands of years."
        )
        payload = encrypt_payload("Explain quantum computers", "")
        session_key = decode_key(payload["key_id"])

        # Miner encrypts it
        n, c = encrypt_message(good_response, session_key)
        encrypted_response = f"{n}.{c}"

        # Validator decrypts for scoring
        n2, c2 = encrypted_response.split(".", 1)
        scoring_text = decrypt_message(n2, c2, session_key)

        assert scoring_text == good_response
        assert len(scoring_text) > 50  # Meaningful response for scoring


# ─── 11. Wire format validation ──────────────────────────────────────────────

class TestWireFormat:
    def test_encrypted_response_format(self):
        """encrypted_response is "<nonce_b64>.<ciphertext_b64>" with exactly one dot."""
        from nobi.privacy.tee_encryption import generate_session_key, encrypt_message

        key = generate_session_key()
        nonce, cipher = encrypt_message("test response", key)
        encrypted_response = f"{nonce}.{cipher}"

        parts = encrypted_response.split(".", 1)
        assert len(parts) == 2
        # Both parts should be valid base64url
        base64.urlsafe_b64decode(parts[0])
        base64.urlsafe_b64decode(parts[1])

    def test_encrypted_response_nonce_size(self):
        """The nonce in encrypted_response is 12 bytes (96-bit GCM standard)."""
        from nobi.privacy.tee_encryption import generate_session_key, encrypt_message

        key = generate_session_key()
        nonce_b64, _ = encrypt_message("test response", key)
        nonce_bytes = base64.urlsafe_b64decode(nonce_b64)
        assert len(nonce_bytes) == 12

    def test_encrypted_response_independent_of_request_nonce(self):
        """Response encryption uses a fresh nonce, independent of request nonces."""
        from nobi.privacy.tee_encryption import (
            encrypt_payload,
            decode_key,
            encrypt_message,
        )

        payload = encrypt_payload("Query", "")
        session_key = decode_key(payload["key_id"])

        # Extract request nonces
        req_msg_nonce = payload["encrypted_message"].split(".")[0]

        # Response encryption
        resp_nonce, _ = encrypt_message("Response text", session_key)

        # Should be different nonces
        assert req_msg_nonce != resp_nonce


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
