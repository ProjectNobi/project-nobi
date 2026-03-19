#!/usr/bin/env python3
"""Tests for Privacy Phase A: Client-Side Encryption"""

import os
import sys
import json
import tempfile
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set a test encryption secret
os.environ["NOBI_ENCRYPTION_SECRET"] = "test-secret-key-for-unit-tests-only"

from nobi.memory.encryption import (
    get_user_key,
    encrypt_memory,
    decrypt_memory,
    is_encrypted,
    ensure_master_secret,
    FERNET_PREFIX,
)
from nobi.memory.store import MemoryManager


def test_encryption_roundtrip():
    """Test 1: encrypt/decrypt roundtrip"""
    user_id = "test_user_123"
    plaintext = "User's name is Alice and she loves cats"

    encrypted = encrypt_memory(user_id, plaintext)
    assert encrypted != plaintext, "Encrypted should differ from plaintext"
    assert is_encrypted(encrypted), "Should detect as encrypted"

    decrypted = decrypt_memory(user_id, encrypted)
    assert decrypted == plaintext, f"Roundtrip failed: got '{decrypted}'"
    print("✅ Test 1: Encryption roundtrip works")


def test_per_user_keys():
    """Test that different users get different encryption"""
    text = "Same content for both users"
    enc_a = encrypt_memory("user_a", text)
    enc_b = encrypt_memory("user_b", text)
    assert enc_a != enc_b, "Different users should produce different ciphertext"

    # Each user can only decrypt their own
    dec_a = decrypt_memory("user_a", enc_a)
    assert dec_a == text
    # user_b trying to decrypt user_a's data should return raw (graceful failure)
    dec_wrong = decrypt_memory("user_b", enc_a)
    # Should return raw ciphertext (not crash)
    assert dec_wrong == enc_a, "Wrong user should get raw ciphertext back"
    print("✅ Test 2: Per-user keys work correctly")


def test_is_encrypted():
    """Test encrypted detection"""
    assert not is_encrypted("Hello world"), "Plaintext should not be detected as encrypted"
    assert not is_encrypted(""), "Empty string should not be detected as encrypted"
    assert not is_encrypted(None), "None should not be detected as encrypted"
    assert not is_encrypted("gAAAAA"), "Short prefix-only should not be detected"

    encrypted = encrypt_memory("test_user", "test content")
    assert is_encrypted(encrypted), "Fernet token should be detected"
    print("✅ Test 3: is_encrypted detection works")


def test_backward_compat():
    """Test 4: Old plaintext memories still readable"""
    plaintext = "This is an old plaintext memory"
    decrypted = decrypt_memory("any_user", plaintext)
    assert decrypted == plaintext, "Plaintext should pass through unchanged"
    print("✅ Test 4: Backward compatibility works")


def test_memory_manager_store_recall():
    """Test 5: MemoryManager encrypts on store, decrypts on recall"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=True)

        user_id = "test_user_456"
        content = "User loves hiking in the mountains"

        # Store (should encrypt)
        mid = mm.store(user_id, content, memory_type="preference", importance=0.8)

        # Verify raw DB has encrypted content
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        raw = conn.execute("SELECT content FROM memories WHERE id = ?", (mid,)).fetchone()
        assert raw["content"] != content, "Raw DB should have encrypted content"
        assert is_encrypted(raw["content"]), "Raw DB content should be a Fernet token"
        conn.close()

        # Recall (should decrypt)
        memories = mm.recall(user_id, query="hiking", limit=5)
        assert len(memories) > 0, "Should recall the memory"
        assert memories[0]["content"] == content, f"Recalled content should be decrypted: got '{memories[0]['content']}'"
        print("✅ Test 5: MemoryManager store/recall with encryption works")


def test_conversation_encryption():
    """Test 6: Conversation turns are encrypted/decrypted"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=True)

        user_id = "test_conv_user"
        msg = "I had a really great day today!"

        mm.save_conversation_turn(user_id, "user", msg)

        # Check raw DB
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        raw = conn.execute("SELECT content FROM conversations ORDER BY id DESC LIMIT 1").fetchone()
        assert raw["content"] != msg, "Raw conversation should be encrypted"
        assert is_encrypted(raw["content"]), "Raw conversation should be Fernet token"
        conn.close()

        # Get recent conversation (should decrypt)
        history = mm.get_recent_conversation(user_id, limit=5)
        assert len(history) == 1
        assert history[0]["content"] == msg, f"Conversation should be decrypted: got '{history[0]['content']}'"
        print("✅ Test 6: Conversation encryption/decryption works")


def test_export_decrypted():
    """Test 7: Export returns decrypted content"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=True)

        user_id = "export_user"
        content = "User is a software engineer from Tokyo"
        mm.store(user_id, content, memory_type="fact", importance=0.9)

        exported = mm.export_memories(user_id)
        assert "error" not in exported
        assert len(exported["memories"]) == 1
        assert exported["memories"][0]["content"] == content, "Export should have decrypted content"
        print("✅ Test 7: Export returns decrypted content")


def test_import_encrypts():
    """Test 8: Import encrypts data on import"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=True)

        user_id = "import_user"
        data = {
            "version": "nobi-memory-v2",
            "memories": [
                {
                    "content": "User speaks Japanese and English",
                    "type": "fact",
                    "importance": 0.8,
                    "tags": ["language"],
                }
            ],
        }

        imported = mm.import_memories(user_id, data)
        assert imported == 1

        # Check raw DB is encrypted
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        raw = conn.execute("SELECT content FROM memories LIMIT 1").fetchone()
        assert is_encrypted(raw["content"]), "Imported data should be encrypted in DB"
        conn.close()

        # Recall should give decrypted
        memories = mm.recall(user_id, limit=5)
        assert memories[0]["content"] == "User speaks Japanese and English"
        print("✅ Test 8: Import encrypts data correctly")


def test_encryption_disabled():
    """Test 9: encryption_enabled=False stores plaintext"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=False)

        user_id = "plain_user"
        content = "This should stay plaintext"
        mid = mm.store(user_id, content)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        raw = conn.execute("SELECT content FROM memories WHERE id = ?", (mid,)).fetchone()
        assert raw["content"] == content, "With encryption disabled, raw DB should have plaintext"
        conn.close()
        print("✅ Test 9: encryption_enabled=False works correctly")


def test_mixed_plaintext_encrypted():
    """Test 10: DB with mix of plaintext and encrypted memories works"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        # First, store some plaintext (encryption disabled)
        mm1 = MemoryManager(db_path=db_path, encryption_enabled=False)
        user_id = "mixed_user"
        mm1.store(user_id, "Old plaintext memory", memory_type="fact", importance=0.5)

        # Now enable encryption and store more
        mm2 = MemoryManager(db_path=db_path, encryption_enabled=True)
        mm2.store(user_id, "New encrypted memory", memory_type="fact", importance=0.9)

        # Recall should return both, decrypted
        memories = mm2.recall(user_id, limit=10)
        contents = [m["content"] for m in memories]
        assert "Old plaintext memory" in contents, "Old plaintext should be readable"
        assert "New encrypted memory" in contents, "New encrypted should be decrypted"
        print("✅ Test 10: Mixed plaintext/encrypted DB works")


def test_empty_content():
    """Test 11: Empty content handled gracefully"""
    result = encrypt_memory("user", "")
    assert result == "", "Empty string should return empty"
    result = decrypt_memory("user", "")
    assert result == "", "Empty string decrypt should return empty"
    print("✅ Test 11: Empty content handled gracefully")


def test_context_methods():
    """Test 12: get_context_for_prompt and get_smart_context decrypt properly"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        mm = MemoryManager(db_path=db_path, encryption_enabled=True)

        user_id = "context_user"
        mm.store(user_id, "User works at Google", memory_type="fact", importance=0.9)
        mm.save_conversation_turn(user_id, "user", "I just started at Google")
        mm.save_conversation_turn(user_id, "assistant", "That's exciting! Congrats!")

        ctx = mm.get_context_for_prompt(user_id, "tell me about work")
        assert "Google" in ctx, f"Context should contain decrypted content, got: {ctx}"

        smart_ctx = mm.get_smart_context(user_id, "work")
        assert "Google" in smart_ctx, f"Smart context should contain decrypted content, got: {smart_ctx}"
        print("✅ Test 12: Context methods decrypt properly")


if __name__ == "__main__":
    print("🔐 Running Privacy Phase A Encryption Tests\n")

    test_encryption_roundtrip()
    test_per_user_keys()
    test_is_encrypted()
    test_backward_compat()
    test_memory_manager_store_recall()
    test_conversation_encryption()
    test_export_decrypted()
    test_import_encrypts()
    test_encryption_disabled()
    test_mixed_plaintext_encrypted()
    test_empty_content()
    test_context_methods()

    print("\n🎉 All 12 tests passed! Privacy Phase A encryption is working correctly.")
