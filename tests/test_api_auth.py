"""
Tests for API key authentication system.
Covers key management, validation, rate limiting, usage tracking,
hashing security, and endpoint auth middleware.
"""

import os
import sys
import json
import time
import hashlib
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

# Add project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from nobi.api_auth.keys import ApiKeyManager, _hash_key, _generate_key, _key_prefix, RATE_LIMITS, KEY_PREFIX


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_api_keys.db")


@pytest.fixture
def mgr(db_path):
    m = ApiKeyManager(db_path=db_path)
    yield m
    m.close()


# ── Key Generation Tests ─────────────────────────────────────────────────────

class TestKeyGeneration:
    def test_generate_key_format(self):
        """Keys must start with nobi_ prefix."""
        key = _generate_key()
        assert key.startswith("nobi_")

    def test_generate_key_length(self):
        """Keys must be nobi_ + 32 hex chars = 37 chars total."""
        key = _generate_key()
        assert len(key) == 37  # 5 (nobi_) + 32

    def test_generate_key_hex_part(self):
        """Hex part must be valid hex."""
        key = _generate_key()
        hex_part = key[5:]
        int(hex_part, 16)  # Should not raise

    def test_generate_key_uniqueness(self):
        """Two generated keys must be different."""
        k1 = _generate_key()
        k2 = _generate_key()
        assert k1 != k2

    def test_key_prefix_extraction(self):
        """Key prefix should be first 12 chars after nobi_."""
        key = "nobi_a1b2c3d4e5f6g7h8i9j0k1l2m3n4"
        prefix = _key_prefix(key)
        assert prefix == "a1b2c3d4e5f6"

    def test_key_prefix_no_nobi(self):
        """Key prefix for non-nobi keys returns first 12 chars."""
        prefix = _key_prefix("randomkey12345678")
        assert prefix == "randomkey123"


# ── Key Hashing Security Tests ───────────────────────────────────────────────

class TestKeyHashing:
    def test_hash_is_sha256(self):
        """Hashed key must be SHA-256."""
        key = "nobi_abcdef1234567890abcdef1234567890"
        expected = hashlib.sha256(key.encode("utf-8")).hexdigest()
        assert _hash_key(key) == expected

    def test_hash_length(self):
        """SHA-256 hash must be 64 hex chars."""
        h = _hash_key("nobi_test")
        assert len(h) == 64

    def test_raw_key_not_stored(self, mgr):
        """Raw key must NEVER be stored in the database."""
        result = mgr.create_key("user1", "mykey", "free")
        raw_key = result["key"]

        # Check the database directly
        rows = mgr._conn.execute("SELECT * FROM api_keys").fetchall()
        for row in rows:
            row_dict = dict(row)
            for col, val in row_dict.items():
                if isinstance(val, str):
                    assert raw_key not in val, f"Raw key found in column {col}!"

    def test_hash_stored_instead(self, mgr):
        """Key hash must be stored in the database."""
        result = mgr.create_key("user1", "mykey", "free")
        raw_key = result["key"]
        expected_hash = _hash_key(raw_key)

        row = mgr._conn.execute("SELECT key_hash FROM api_keys").fetchone()
        assert row["key_hash"] == expected_hash

    def test_different_keys_different_hashes(self):
        """Different keys must produce different hashes."""
        h1 = _hash_key("nobi_aaaa")
        h2 = _hash_key("nobi_bbbb")
        assert h1 != h2


# ── Key Creation Tests ───────────────────────────────────────────────────────

class TestKeyCreation:
    def test_create_key_returns_raw_key(self, mgr):
        """create_key must return the raw key."""
        result = mgr.create_key("user1")
        assert result["key"].startswith("nobi_")

    def test_create_key_returns_prefix(self, mgr):
        result = mgr.create_key("user1")
        assert len(result["key_prefix"]) == 12

    def test_create_key_returns_name(self, mgr):
        result = mgr.create_key("user1", name="production")
        assert result["name"] == "production"

    def test_create_key_default_name(self, mgr):
        result = mgr.create_key("user1")
        assert result["name"] == "default"

    def test_create_key_invalid_tier(self, mgr):
        with pytest.raises(ValueError, match="Invalid tier"):
            mgr.create_key("user1", tier="ultra")

    def test_create_multiple_keys(self, mgr):
        k1 = mgr.create_key("user1", name="key1")
        k2 = mgr.create_key("user1", name="key2")
        assert k1["key"] != k2["key"]
        assert k1["key_prefix"] != k2["key_prefix"]


# ── Key Validation Tests ─────────────────────────────────────────────────────

class TestKeyValidation:
    def test_validate_valid_key(self, mgr):
        result = mgr.create_key("user1", "test", "free")
        info = mgr.validate_key(result["key"])
        assert info is not None
        assert info["user_id"] == "user1"
        assert info["name"] == "test"
        assert info["tier"] == "free"

    def test_validate_invalid_key(self, mgr):
        info = mgr.validate_key("nobi_invalidkey00000000000000000000")
        assert info is None

    def test_validate_wrong_prefix(self, mgr):
        info = mgr.validate_key("wrong_prefix")
        assert info is None

    def test_validate_empty_key(self, mgr):
        info = mgr.validate_key("")
        assert info is None

    def test_validate_none_key(self, mgr):
        info = mgr.validate_key(None)
        assert info is None

    def test_validate_updates_last_used(self, mgr):
        result = mgr.create_key("user1")
        info = mgr.validate_key(result["key"])
        assert info["last_used"] is not None


# ── Key Revocation Tests ─────────────────────────────────────────────────────

class TestKeyRevocation:
    def test_revoke_valid_key(self, mgr):
        result = mgr.create_key("user1")
        assert mgr.revoke_key(result["key"]) is True

    def test_revoked_key_invalid(self, mgr):
        result = mgr.create_key("user1")
        mgr.revoke_key(result["key"])
        assert mgr.validate_key(result["key"]) is None

    def test_revoke_invalid_key(self, mgr):
        assert mgr.revoke_key("nobi_doesnotexist000000000000000000") is False

    def test_double_revoke(self, mgr):
        result = mgr.create_key("user1")
        assert mgr.revoke_key(result["key"]) is True
        assert mgr.revoke_key(result["key"]) is False  # Already revoked

    def test_revoke_by_prefix(self, mgr):
        result = mgr.create_key("user1")
        prefix = result["key_prefix"]
        assert mgr.revoke_key_by_prefix(prefix) is True
        assert mgr.validate_key(result["key"]) is None


# ── Key Listing Tests ────────────────────────────────────────────────────────

class TestKeyListing:
    def test_list_keys_empty(self, mgr):
        keys = mgr.list_keys("user1")
        assert keys == []

    def test_list_keys_returns_metadata(self, mgr):
        mgr.create_key("user1", "mykey", "plus")
        keys = mgr.list_keys("user1")
        assert len(keys) == 1
        assert keys[0]["name"] == "mykey"
        assert keys[0]["tier"] == "plus"
        assert "key" not in keys[0]  # Raw key must NOT be in listing

    def test_list_keys_multiple_users(self, mgr):
        mgr.create_key("user1", "k1")
        mgr.create_key("user2", "k2")
        assert len(mgr.list_keys("user1")) == 1
        assert len(mgr.list_keys("user2")) == 1


# ── Usage Tracking Tests ────────────────────────────────────────────────────

class TestUsageTracking:
    def test_record_usage(self, mgr):
        result = mgr.create_key("user1")
        mgr.record_usage(result["key"], "/v1/api/chat")
        usage = mgr.get_usage(result["key"], days=1)
        assert usage["total_requests"] == 1

    def test_usage_by_endpoint(self, mgr):
        result = mgr.create_key("user1")
        mgr.record_usage(result["key"], "/v1/api/chat")
        mgr.record_usage(result["key"], "/v1/api/chat")
        mgr.record_usage(result["key"], "/v1/api/memories")
        usage = mgr.get_usage(result["key"], days=1)
        assert usage["by_endpoint"]["/v1/api/chat"] == 2
        assert usage["by_endpoint"]["/v1/api/memories"] == 1

    def test_usage_today_count(self, mgr):
        result = mgr.create_key("user1")
        mgr.record_usage(result["key"], "/v1/api/chat")
        usage = mgr.get_usage(result["key"], days=1)
        assert usage["requests_today"] >= 1

    def test_get_usage_by_hash(self, mgr):
        result = mgr.create_key("user1")
        mgr.record_usage(result["key"], "/v1/api/chat")
        key_hash = _hash_key(result["key"])
        usage = mgr.get_usage_by_hash(key_hash, days=1)
        assert usage["total_requests"] == 1


# ── Rate Limiting Tests ──────────────────────────────────────────────────────

class TestRateLimiting:
    def test_within_limit(self, mgr):
        result = mgr.create_key("user1", tier="free")
        allowed, reason = mgr.check_rate_limit(result["key"])
        assert allowed is True
        assert "OK" in reason

    def test_rate_limit_tiers(self):
        """All tiers must be defined."""
        assert "free" in RATE_LIMITS
        assert "plus" in RATE_LIMITS
        assert "pro" in RATE_LIMITS
        assert RATE_LIMITS["free"] == 100
        assert RATE_LIMITS["plus"] == 1000
        assert RATE_LIMITS["pro"] == 10000

    def test_exceed_free_limit(self, mgr):
        result = mgr.create_key("user1", tier="free")
        # Record 100 requests (the limit)
        for _ in range(100):
            mgr.record_usage(result["key"], "/v1/api/chat")
        allowed, reason = mgr.check_rate_limit(result["key"])
        assert allowed is False
        assert "Rate limit exceeded" in reason

    def test_invalid_key_rate_limit(self, mgr):
        allowed, reason = mgr.check_rate_limit("nobi_invalid00000000000000000000000")
        assert allowed is False
        assert "Invalid" in reason


# ── FastAPI Endpoint Auth Tests ──────────────────────────────────────────────

class TestEndpointAuth:
    """Test the require_api_key dependency via the FastAPI test client."""

    @pytest.fixture
    def client(self, db_path):
        """Create a test client with api_key_mgr initialized."""
        # We need to import and configure the app
        import importlib
        from fastapi.testclient import TestClient

        # Patch the api_key_mgr in server module
        import api.server as server_module
        server_module.api_key_mgr = ApiKeyManager(db_path=db_path)

        # Create a simple test endpoint if needed — we test via /v1/api/keys
        client = TestClient(server_module.app)
        yield client, server_module.api_key_mgr
        server_module.api_key_mgr.close()

    def test_missing_auth_header(self, client):
        c, _ = client
        resp = c.get("/v1/api/keys")
        assert resp.status_code == 422  # Missing required header

    def test_invalid_bearer_format(self, client):
        c, _ = client
        resp = c.get("/v1/api/keys", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_invalid_key_prefix(self, client):
        c, _ = client
        resp = c.get("/v1/api/keys", headers={"Authorization": "Bearer invalid_key"})
        assert resp.status_code == 401

    def test_nonexistent_key(self, client):
        c, _ = client
        resp = c.get("/v1/api/keys", headers={"Authorization": "Bearer nobi_00000000000000000000000000000000"})
        assert resp.status_code == 401

    def test_valid_key_list(self, client):
        c, mgr = client
        result = mgr.create_key("testuser", "test", "free")
        resp = c.get("/v1/api/keys", headers={"Authorization": f"Bearer {result['key']}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["keys"]) >= 1

    def test_create_key_endpoint(self, client):
        c, mgr = client
        result = mgr.create_key("testuser", "admin", "pro")
        resp = c.post(
            "/v1/api/keys",
            json={"name": "new-key"},
            headers={"Authorization": f"Bearer {result['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["key"]["key"].startswith("nobi_")
        assert data["key"]["name"] == "new-key"

    def test_revoke_key_endpoint(self, client):
        c, mgr = client
        k1 = mgr.create_key("testuser", "admin", "pro")
        k2 = mgr.create_key("testuser", "to-revoke", "free")
        prefix = k2["key_prefix"]
        resp = c.delete(
            f"/v1/api/keys/{prefix}",
            headers={"Authorization": f"Bearer {k1['key']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_usage_endpoint(self, client):
        c, mgr = client
        result = mgr.create_key("testuser", "test", "free")
        resp = c.get(
            "/v1/api/keys/usage",
            headers={"Authorization": f"Bearer {result['key']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "usage" in data

    def test_revoked_key_rejected(self, client):
        c, mgr = client
        k1 = mgr.create_key("testuser", "main", "pro")
        k2 = mgr.create_key("testuser", "temp", "free")
        mgr.revoke_key(k2["key"])
        resp = c.get("/v1/api/keys", headers={"Authorization": f"Bearer {k2['key']}"})
        assert resp.status_code == 401


# ── Database Schema Tests ────────────────────────────────────────────────────

class TestDatabaseSchema:
    def test_tables_created(self, mgr):
        tables = mgr._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "api_keys" in table_names
        assert "api_usage" in table_names

    def test_fresh_db_no_keys(self, mgr):
        rows = mgr._conn.execute("SELECT COUNT(*) as cnt FROM api_keys").fetchone()
        assert rows["cnt"] == 0
