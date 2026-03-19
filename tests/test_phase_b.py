#!/usr/bin/env python3
"""
Phase B Tests — Encrypted synapses, per-user personality adapters
"""

import os
import sys
import json
import hashlib
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure encryption key exists
os.makedirs(os.path.expanduser("~/.nobi"), exist_ok=True)
from nobi.memory.encryption import ensure_master_secret
ensure_master_secret()


def test_protocol_fields():
    """Test that new Phase B fields exist on synapses."""
    from nobi.protocol import CompanionRequest, MemoryStore, MemoryRecall

    # CompanionRequest: adapter_config
    cr = CompanionRequest(message="hello")
    assert hasattr(cr, "adapter_config"), "CompanionRequest missing adapter_config"
    assert cr.adapter_config == {}

    # MemoryStore: encrypted_content, content_hash
    ms = MemoryStore(user_id="test")
    assert hasattr(ms, "encrypted_content"), "MemoryStore missing encrypted_content"
    assert hasattr(ms, "content_hash"), "MemoryStore missing content_hash"
    assert ms.encrypted_content == ""
    assert ms.content_hash == ""

    # MemoryRecall: return_encrypted
    mr = MemoryRecall(user_id="test")
    assert hasattr(mr, "return_encrypted"), "MemoryRecall missing return_encrypted"
    assert mr.return_encrypted == False

    print("✅ Protocol fields: PASS")


def test_encrypted_memory_store():
    """Test storing encrypted content — miner stores as-is without decrypting."""
    from nobi.memory.store import MemoryManager
    from nobi.memory.encryption import encrypt_memory

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mm = MemoryManager(db_path=db_path)
        user_id = "test_user_enc"
        plaintext = "User's secret: their birthday is January 1st"

        # Simulate bot-side encryption
        encrypted = encrypt_memory(user_id, plaintext)
        content_hash = hashlib.sha256(plaintext.encode()).hexdigest()

        # Store with encrypted_content (Phase B path)
        mid = mm.store(
            user_id=user_id,
            content="",  # No plaintext
            memory_type="fact",
            encrypted_content=encrypted,
            content_hash=content_hash,
            encryption_version=1,
        )
        assert mid, "Memory store returned empty ID"

        # Recall encrypted
        memories = mm.recall(user_id, return_encrypted=True, limit=5)
        assert len(memories) > 0, "No memories returned"
        mem = memories[0]
        assert mem["encrypted_content"] == encrypted, "Encrypted content mismatch"
        assert mem["content_hash"] == content_hash, "Content hash mismatch"
        assert mem["content"] == "", "Content should be empty when return_encrypted=True"

        print("✅ Encrypted memory store: PASS")
    finally:
        os.unlink(db_path)


def test_encrypted_memory_recall():
    """Test that return_encrypted=True returns blobs without decrypting."""
    from nobi.memory.store import MemoryManager
    from nobi.memory.encryption import encrypt_memory, decrypt_memory

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mm = MemoryManager(db_path=db_path)
        user_id = "test_user_recall"
        plaintext = "User lives in Tokyo"

        encrypted = encrypt_memory(user_id, plaintext)

        mm.store(
            user_id=user_id,
            content=plaintext,  # Also store plaintext (backward compat)
            memory_type="fact",
            encrypted_content=encrypted,
            content_hash=hashlib.sha256(plaintext.encode()).hexdigest(),
            encryption_version=1,
        )

        # Normal recall (decrypted)
        normal = mm.recall(user_id, return_encrypted=False, limit=5)
        assert len(normal) > 0
        assert normal[0]["content"] == plaintext, f"Expected plaintext, got: {normal[0]['content']}"

        # Encrypted recall
        enc = mm.recall(user_id, return_encrypted=True, limit=5)
        assert len(enc) > 0
        assert enc[0]["encrypted_content"] == encrypted
        assert enc[0]["content"] == ""  # No plaintext leaked

        # Bot can decrypt the blob
        decrypted = decrypt_memory(user_id, enc[0]["encrypted_content"])
        assert decrypted == plaintext, f"Decryption failed: {decrypted}"

        print("✅ Encrypted memory recall: PASS")
    finally:
        os.unlink(db_path)


def test_backward_compat():
    """Test that old-style MemoryStore (no encryption) still works."""
    from nobi.memory.store import MemoryManager

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mm = MemoryManager(db_path=db_path)
        user_id = "test_old_style"

        # Old-style store (just content, no encrypted_content)
        mid = mm.store(user_id=user_id, content="User likes cats", memory_type="preference")
        assert mid

        memories = mm.recall(user_id, limit=5)
        assert len(memories) > 0
        assert memories[0]["content"] == "User likes cats"

        print("✅ Backward compatibility: PASS")
    finally:
        os.unlink(db_path)


def test_adapter_default():
    """Test that new users get a default adapter config."""
    from nobi.memory.adapters import UserAdapterManager, DEFAULT_ADAPTER
    from nobi.memory.store import MemoryManager

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Need MemoryManager to create the schema first
        mm = MemoryManager(db_path=db_path)
        am = UserAdapterManager(db_path=db_path)

        config = am.get_adapter_config("new_user_123")
        assert config["tone"] == "warm"
        assert config["formality"] == 0.5
        assert config["message_count"] == 0

        print("✅ Adapter default config: PASS")
    finally:
        os.unlink(db_path)


def test_adapter_learning():
    """Test that adapter learns preferences from conversation patterns."""
    from nobi.memory.adapters import UserAdapterManager
    from nobi.memory.store import MemoryManager

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        mm = MemoryManager(db_path=db_path)
        am = UserAdapterManager(db_path=db_path)
        user_id = "learning_user"

        # Simulate casual user with lots of emoji
        casual_messages = [
            ("yo whats up bro 😂😂 lol", "haha hey! what's going on?"),
            ("nah tbh idk lmao 🤣", "haha fair enough!"),
            ("dude thats hilarious 😅👍", "ikr? so funny!"),
            ("gonna go grab food bruh", "nice, enjoy!"),
            ("lol ya that was wild 🔥🔥", "totally!"),
        ]

        for msg, resp in casual_messages:
            am.update_adapter_from_conversation(user_id, msg, resp)

        config = am.get_adapter_config(user_id)
        assert config["message_count"] == 5, f"Expected 5, got {config['message_count']}"
        assert config["formality"] < 0.45, f"Expected casual (< 0.45), got {config['formality']}"
        assert config["emoji_usage"] > 0.3, f"Expected some emoji (> 0.3), got {config['emoji_usage']}"
        assert config["humor_level"] > 0.5, f"Expected humor (> 0.5), got {config['humor_level']}"

        print("✅ Adapter learning (casual user): PASS")

        # Now test a formal user
        formal_user = "formal_user"
        formal_messages = [
            ("Could you please explain the algorithm's implementation details regarding the database architecture?",
             "Certainly. The algorithm uses..."),
            ("Thank you kindly. Furthermore, I would appreciate a detailed technical explanation.",
             "Of course. The technical details are..."),
            ("Regarding the protocol specification, could you elaborate on the encryption implementation?",
             "The protocol specifies..."),
            ("I would appreciate your analysis of the architectural implications and scalability considerations.",
             "From an architectural standpoint..."),
            ("Please provide a comprehensive technical overview of the system's distributed computing framework.",
             "The distributed framework consists of..."),
        ]

        for msg, resp in formal_messages:
            am.update_adapter_from_conversation(formal_user, msg, resp)

        config2 = am.get_adapter_config(formal_user)
        assert config2["formality"] > 0.5, f"Expected formal (> 0.5), got {config2['formality']}"
        assert config2["technical_depth"] > 0.5, f"Expected technical (> 0.5), got {config2['technical_depth']}"
        assert config2["verbosity"] >= 0.5, f"Expected verbose (>= 0.5), got {config2['verbosity']}"

        print("✅ Adapter learning (formal user): PASS")
    finally:
        os.unlink(db_path)


def test_adapter_prompt_application():
    """Test that adapter modifies system prompt differently for different users."""
    from nobi.memory.adapters import UserAdapterManager

    am = UserAdapterManager.__new__(UserAdapterManager)

    # Casual user config
    casual = {
        "tone": "warm",
        "formality": 0.2,
        "humor_level": 0.8,
        "verbosity": 0.2,
        "emoji_usage": 0.8,
        "technical_depth": 0.3,
        "topics_of_interest": ["gaming", "music"],
        "message_count": 10,
    }

    # Formal user config
    formal = {
        "tone": "professional",
        "formality": 0.85,
        "humor_level": 0.2,
        "verbosity": 0.8,
        "emoji_usage": 0.1,
        "technical_depth": 0.9,
        "topics_of_interest": ["finance", "tech"],
        "message_count": 10,
    }

    base = "You are Nori, a companion AI."

    casual_prompt = am.apply_adapter_to_prompt(base, casual)
    formal_prompt = am.apply_adapter_to_prompt(base, formal)

    assert "concise" in casual_prompt.lower() or "brief" in casual_prompt.lower(), \
        "Casual user should get concise hint"
    assert "informal" in casual_prompt.lower() or "casual" in casual_prompt.lower(), \
        "Casual user should get casual hint"
    assert "emoji" in casual_prompt.lower(), "Casual user should get emoji hint"

    assert "detailed" in formal_prompt.lower() or "elaborate" in formal_prompt.lower(), \
        "Formal user should get detailed hint"
    assert "formal" in formal_prompt.lower() or "professional" in formal_prompt.lower(), \
        "Formal user should get formal hint"
    assert "technical" in formal_prompt.lower(), "Formal user should get technical hint"

    # Prompts should be different
    assert casual_prompt != formal_prompt, "Casual and formal prompts should differ"

    # New user (< 3 messages) should get unmodified prompt
    new_user = {"message_count": 1}
    new_prompt = am.apply_adapter_to_prompt(base, new_user)
    assert new_prompt == base, "New user prompt should be unmodified"

    print("✅ Adapter prompt application: PASS")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase B Tests — Encrypted Synapses + Personality Adapters")
    print("=" * 60)

    test_protocol_fields()
    test_encrypted_memory_store()
    test_encrypted_memory_recall()
    test_backward_compat()
    test_adapter_default()
    test_adapter_learning()
    test_adapter_prompt_application()

    print("\n" + "=" * 60)
    print("🎉 ALL PHASE B TESTS PASSED!")
    print("=" * 60)
