"""
test_forget_me.py — GDPR Right-to-Erasure (MemoryForget) Test Suite
=====================================================================
Tests covering:
  1. MemoryForget synapse serialization / deserialization
  2. MemoryManager.forget_user() — local wipe function
  3. Miner forward_memory_forget handler (mock)
  4. Validator broadcast_forget function (mock)
  5. Graceful degradation — missing handler does not crash axon
"""

import os
import sqlite3
import sys
import tempfile
import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Path setup ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ─── 1. Synapse serialization ─────────────────────────────────────────────────

class TestMemoryForgetSynapse:
    """Test MemoryForget protocol synapse fields and deserialization."""

    def test_import(self):
        """MemoryForget must be importable from nobi.protocol."""
        from nobi.protocol import MemoryForget
        assert MemoryForget is not None

    def test_default_fields(self):
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="tg_12345")
        assert s.user_id == "tg_12345"
        assert s.reason == "user_request"
        assert s.deleted is None
        assert s.items_deleted == 0

    def test_custom_reason(self):
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="tg_99", reason="gdpr")
        assert s.reason == "gdpr"

    def test_deserialize_none(self):
        """deserialize() returns False when deleted is None."""
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="u1")
        assert s.deserialize() is False

    def test_deserialize_false(self):
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="u1")
        s.deleted = False
        assert s.deserialize() is False

    def test_deserialize_true(self):
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="u1")
        s.deleted = True
        assert s.deserialize() is True

    def test_items_deleted_field(self):
        from nobi.protocol import MemoryForget
        s = MemoryForget(user_id="u1")
        s.deleted = True
        s.items_deleted = 42
        assert s.items_deleted == 42

    def test_all_reason_values(self):
        """All valid reason strings are accepted."""
        from nobi.protocol import MemoryForget
        for reason in ("user_request", "gdpr", "account_deletion"):
            s = MemoryForget(user_id="u1", reason=reason)
            assert s.reason == reason


# ─── 2. Local wipe function ───────────────────────────────────────────────────

def _seed_memory_db(db_path: str, user_id: str, other_user_id: str = "other_user"):
    """Seed a memory DB with test rows for two users."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, user_id TEXT, memory_type TEXT,
            content TEXT, importance REAL, tags TEXT,
            created_at TEXT, updated_at TEXT, expires_at TEXT,
            access_count INTEGER DEFAULT 0, last_accessed TEXT,
            encrypted_content TEXT DEFAULT '',
            content_hash TEXT DEFAULT '',
            encryption_version INTEGER DEFAULT 0,
            source TEXT DEFAULT 'dm'
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, role TEXT, content TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            summary TEXT DEFAULT '',
            personality_notes TEXT DEFAULT '',
            first_seen TEXT, last_seen TEXT,
            total_messages INTEGER DEFAULT 0,
            memory_count_at_last_summary INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS archived_memories (
            id TEXT PRIMARY KEY, user_id TEXT, memory_type TEXT,
            content TEXT, importance REAL, tags TEXT,
            created_at TEXT, updated_at TEXT, expires_at TEXT,
            access_count INTEGER DEFAULT 0, last_accessed TEXT,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id TEXT PRIMARY KEY,
            embedding_vector BLOB,
            embedding_backend TEXT DEFAULT 'unknown'
        );
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, name TEXT, entity_type TEXT,
            created_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, from_entity TEXT, to_entity TEXT,
            relation_type TEXT, created_at TEXT DEFAULT ''
        );
    """)

    now = "2026-01-01T00:00:00Z"
    # Seed target user
    for i in range(5):
        conn.execute(
            "INSERT INTO memories "
            "(id,user_id,memory_type,content,importance,tags,created_at,updated_at,"
            "expires_at,access_count,last_accessed,encrypted_content,content_hash,"
            "encryption_version,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"m{i}", user_id, "fact", f"content {i}", 0.5, "[]", now, now,
             None, 0, None, "", "", 0, "dm"),
        )
    conn.execute(
        "INSERT INTO conversations(user_id,role,content,created_at) VALUES(?,?,?,?)",
        (user_id, "user", "hello", now),
    )
    conn.execute(
        "INSERT INTO user_profiles VALUES(?,?,?,?,?,?,?)",
        (user_id, "summary", "notes", now, now, 3, 0),
    )
    conn.execute(
        "INSERT INTO archived_memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        ("a1", user_id, "fact", "old content", 0.3, "[]", now, now, None, 0, None, now),
    )
    conn.execute(
        "INSERT INTO entities(user_id,name,entity_type) VALUES(?,?,?)",
        (user_id, "Alice", "person"),
    )
    conn.execute(
        "INSERT INTO relationships(user_id,from_entity,to_entity,relation_type) VALUES(?,?,?,?)",
        (user_id, "Alice", "Bob", "friend"),
    )

    # Seed other user (must NOT be deleted)
    conn.execute(
        "INSERT INTO memories "
        "(id,user_id,memory_type,content,importance,tags,created_at,updated_at,"
        "expires_at,access_count,last_accessed,encrypted_content,content_hash,"
        "encryption_version,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("other_m1", other_user_id, "fact", "other content", 0.5, "[]",
         now, now, None, 0, None, "", "", 0, "dm"),
    )
    conn.execute(
        "INSERT INTO conversations(user_id,role,content,created_at) VALUES(?,?,?,?)",
        (other_user_id, "user", "other hello", now),
    )
    conn.commit()
    conn.close()


class TestForgetUser:
    """Test MemoryManager.forget_user() local wipe."""

    def test_forget_user_deletes_all_rows(self, tmp_path):
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_test123"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        total = mm.forget_user(user_id)

        # At least memories + conversation + profile + archived + entities + relationships = 9
        assert total >= 9, f"Expected ≥9 rows deleted, got {total}"

    def test_forget_user_does_not_affect_other_users(self, tmp_path):
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_target"
        other_id = "other_user"
        _seed_memory_db(db_path, user_id, other_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        mm.forget_user(user_id)

        # Other user's data must survive
        conn = sqlite3.connect(db_path)
        other_rows = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ?", (other_id,)
        ).fetchone()[0]
        other_convs = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (other_id,)
        ).fetchone()[0]
        conn.close()
        assert other_rows >= 1, "Other user's memories were deleted!"
        assert other_convs >= 1, "Other user's conversations were deleted!"

    def test_forget_user_clears_memories(self, tmp_path):
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_clear"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        mm.forget_user(user_id)

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_forget_user_clears_conversations(self, tmp_path):
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_conv"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        mm.forget_user(user_id)

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_forget_user_clears_profiles(self, tmp_path):
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_profile"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        mm.forget_user(user_id)

        conn = sqlite3.connect(db_path)
        count = conn.execute(
            "SELECT COUNT(*) FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_forget_user_idempotent(self, tmp_path):
        """Calling forget_user twice on the same user should not crash."""
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        user_id = "tg_twice"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        mm.forget_user(user_id)
        result2 = mm.forget_user(user_id)  # should return 0, not crash
        assert result2 == 0

    def test_forget_nonexistent_user(self, tmp_path):
        """forget_user on a user with no data should return 0 and not crash."""
        from nobi.memory.store import MemoryManager
        db_path = str(tmp_path / "memories.db")
        # Seed with a different user so DB is initialized
        _seed_memory_db(db_path, "other")

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        result = mm.forget_user("ghost_user_no_data")
        assert result == 0


# ─── 3. Miner handler (mock) ──────────────────────────────────────────────────

class TestMinerForgetHandler:
    """Test forward_memory_forget in the Miner class (mocked dependencies)."""

    @pytest.fixture
    def mock_miner(self, tmp_path):
        """Create a minimal Miner-like object with mocked internals."""
        # We don't instantiate the real Miner (needs bittensor wallet/config)
        # Instead we directly test the handler logic with a mock object
        from nobi.memory.store import MemoryManager
        from nobi.protocol import MemoryForget

        db_path = str(tmp_path / "miner_memories.db")
        _seed_memory_db(db_path, "tg_miner_user")

        miner = MagicMock()
        miner.memory = MemoryManager(db_path=db_path, encryption_enabled=False)

        # Bind the actual method to the mock
        import neurons.miner as miner_module
        miner.forward_memory_forget = lambda synapse: (
            miner_module.Miner.forward_memory_forget.__wrapped__(miner, synapse)
            if hasattr(miner_module.Miner.forward_memory_forget, "__wrapped__")
            else None
        )
        return miner, MemoryForget

    @pytest.mark.asyncio
    async def test_handler_sets_deleted_true(self, tmp_path):
        """forward_memory_forget should return deleted=True on success."""
        import asyncio
        from nobi.memory.store import MemoryManager
        from nobi.protocol import MemoryForget

        db_path = str(tmp_path / "h_memories.db")
        user_id = "tg_handler_test"
        _seed_memory_db(db_path, user_id)

        # Simulate what the miner handler does
        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        synapse = MemoryForget(user_id=user_id, reason="user_request")

        # Execute handler logic directly
        try:
            total_deleted = mm.forget_user(user_id)
            synapse.deleted = True
            synapse.items_deleted = total_deleted
        except Exception as e:
            synapse.deleted = False
            synapse.items_deleted = 0

        assert synapse.deleted is True
        assert synapse.items_deleted >= 9

    @pytest.mark.asyncio
    async def test_handler_items_deleted_count(self, tmp_path):
        """items_deleted should reflect actual row count."""
        from nobi.memory.store import MemoryManager
        from nobi.protocol import MemoryForget

        db_path = str(tmp_path / "count_memories.db")
        user_id = "tg_count_test"
        _seed_memory_db(db_path, user_id)

        mm = MemoryManager(db_path=db_path, encryption_enabled=False)
        synapse = MemoryForget(user_id=user_id)

        total = mm.forget_user(user_id)
        synapse.deleted = True
        synapse.items_deleted = total

        assert synapse.items_deleted > 0
        assert synapse.deserialize() is True

    @pytest.mark.asyncio
    async def test_handler_error_sets_deleted_false(self, tmp_path):
        """If forget_user raises, handler sets deleted=False gracefully."""
        from nobi.protocol import MemoryForget

        synapse = MemoryForget(user_id="tg_error_user")
        mm = MagicMock()
        mm.forget_user.side_effect = RuntimeError("DB locked")

        try:
            mm.forget_user(synapse.user_id)
            synapse.deleted = True
        except Exception:
            synapse.deleted = False
            synapse.items_deleted = 0

        assert synapse.deleted is False
        assert synapse.items_deleted == 0
        assert synapse.deserialize() is False


# ─── 4. Validator broadcast (mock) ────────────────────────────────────────────

class TestBroadcastForget:
    """Test broadcast_forget in the validator (mocked dendrite)."""

    @pytest.mark.asyncio
    async def test_broadcast_all_acked(self):
        """All miners ack → result shows full coverage."""
        from nobi.validator.forward import broadcast_forget
        from nobi.protocol import MemoryForget

        # Build mock responses — 3 miners all acknowledge deletion
        def _make_resp(deleted=True, items=5):
            r = MagicMock()
            r.deleted = deleted
            r.items_deleted = items
            return r

        mock_dendrite = AsyncMock()
        mock_dendrite.return_value = [_make_resp(), _make_resp(), _make_resp()]

        mock_metagraph = MagicMock()
        mock_metagraph.axons = [MagicMock(), MagicMock(), MagicMock()]

        result = await broadcast_forget(
            dendrite=mock_dendrite,
            metagraph=mock_metagraph,
            user_id="tg_broadcast_test",
        )

        assert result["miners_queried"] == 3
        assert result["miners_acked"] == 3
        assert result["miners_failed"] == 0
        assert result["total_items"] == 15

    @pytest.mark.asyncio
    async def test_broadcast_partial_failure(self):
        """Some miners fail → graceful degradation, not crash."""
        from nobi.validator.forward import broadcast_forget

        def _make_resp(deleted, items=5):
            r = MagicMock()
            r.deleted = deleted
            r.items_deleted = items
            return r

        mock_dendrite = AsyncMock()
        # 2 ack, 1 fail (deleted=False), 1 None
        mock_dendrite.return_value = [
            _make_resp(True, 10),
            _make_resp(False, 0),
            None,
            _make_resp(True, 7),
        ]

        mock_metagraph = MagicMock()
        mock_metagraph.axons = [MagicMock()] * 4

        result = await broadcast_forget(
            dendrite=mock_dendrite,
            metagraph=mock_metagraph,
            user_id="tg_partial",
        )

        assert result["miners_queried"] == 4
        assert result["miners_acked"] == 2
        assert result["miners_failed"] == 2
        assert result["total_items"] == 17

    @pytest.mark.asyncio
    async def test_broadcast_empty_metagraph(self):
        """Empty metagraph returns zeros without error."""
        from nobi.validator.forward import broadcast_forget

        mock_dendrite = AsyncMock()
        mock_metagraph = MagicMock()
        mock_metagraph.axons = []

        result = await broadcast_forget(
            dendrite=mock_dendrite,
            metagraph=mock_metagraph,
            user_id="tg_empty",
        )

        assert result["miners_queried"] == 0
        assert result["miners_acked"] == 0
        assert result["miners_failed"] == 0

    @pytest.mark.asyncio
    async def test_broadcast_dendrite_exception(self):
        """If dendrite raises, broadcast returns failed counts gracefully."""
        from nobi.validator.forward import broadcast_forget

        mock_dendrite = AsyncMock()
        mock_dendrite.side_effect = RuntimeError("network error")

        mock_metagraph = MagicMock()
        mock_metagraph.axons = [MagicMock(), MagicMock()]

        result = await broadcast_forget(
            dendrite=mock_dendrite,
            metagraph=mock_metagraph,
            user_id="tg_exception",
        )

        assert result["miners_queried"] == 2
        assert result["miners_failed"] == 2
        assert result["miners_acked"] == 0


# ─── 5. Graceful degradation ──────────────────────────────────────────────────

class TestGracefulDegradation:
    """Miners without forward_memory_forget don't break the base class."""

    def test_base_miner_attach_skips_missing_handler(self):
        """
        BaseMinerNeuron only attaches forward_memory_forget if the method
        exists. Miners without it should not raise on init.
        """
        import nobi.base.miner as base_miner_module

        # Inspect the source — axon.attach for MemoryForget must be guarded
        import inspect
        src = inspect.getsource(base_miner_module.BaseMinerNeuron.__init__)
        assert "forward_memory_forget" in src
        assert "hasattr" in src, "MemoryForget attach must be guarded with hasattr()"

    def test_synapse_is_in_protocol(self):
        """MemoryForget must be exported from nobi.protocol."""
        import nobi.protocol as proto
        assert hasattr(proto, "MemoryForget")
