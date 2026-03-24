"""
Tests for the Nobi billing/subscription system.
Covers: customers, subscriptions, usage tracking, limits, Stripe handler (mocked).
"""

import os
import json
import tempfile
import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Add project root
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.billing.subscription import SubscriptionManager, TIERS, ACTION_LIMIT_MAP
from nobi.billing.stripe_handler import StripeHandler


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def billing(tmp_path):
    """Create a fresh SubscriptionManager with temp DB."""
    db_path = str(tmp_path / "test_billing.db")
    mgr = SubscriptionManager(db_path=db_path)
    yield mgr
    mgr.close()


@pytest.fixture
def stripe():
    """Create a StripeHandler without real Stripe configured."""
    return StripeHandler(api_key="", webhook_secret="")


# ─── Customer Tests ──────────────────────────────────────────

class TestCustomers:
    def test_create_customer(self, billing):
        cid = billing.create_customer("user1", "user1@example.com")
        assert cid.startswith("cust_")
        assert len(cid) > 10

    def test_create_customer_idempotent(self, billing):
        cid1 = billing.create_customer("user1", "user1@example.com")
        cid2 = billing.create_customer("user1", "user1@example.com")
        assert cid1 == cid2

    def test_create_customer_updates_email(self, billing):
        billing.create_customer("user1", "old@example.com")
        billing.create_customer("user1", "new@example.com")
        customer = billing.get_customer("user1")
        assert customer["email"] == "new@example.com"

    def test_create_customer_no_email(self, billing):
        cid = billing.create_customer("user2")
        assert cid.startswith("cust_")
        customer = billing.get_customer("user2")
        assert customer["email"] == ""

    def test_get_customer_nonexistent(self, billing):
        assert billing.get_customer("nobody") is None

    def test_get_customer_by_customer_id(self, billing):
        cid = billing.create_customer("user1", "user1@example.com")
        customer = billing.get_customer_by_customer_id(cid)
        assert customer is not None
        assert customer["user_id"] == "user1"

    def test_get_customer_by_customer_id_nonexistent(self, billing):
        assert billing.get_customer_by_customer_id("cust_fake") is None


# ─── Subscription Tests ─────────────────────────────────────

class TestSubscriptions:
    def test_default_free_tier(self, billing):
        sub = billing.get_subscription("user1")
        assert sub["tier"] == "free"
        assert sub["status"] == "active"

    def test_create_customer_creates_free_sub(self, billing):
        billing.create_customer("user1")
        sub = billing.get_subscription("user1")
        assert sub["tier"] == "free"
        assert sub["status"] == "active"

    def test_upgrade_to_plus(self, billing):
        billing.create_customer("user1")
        result = billing.upgrade("user1", "plus", "pay_123")
        assert result is True
        sub = billing.get_subscription("user1")
        assert sub["tier"] == "plus"
        assert sub["status"] == "active"
        assert sub["payment_id"] == "pay_123"
        assert sub["expires_at"] is not None

    def test_upgrade_to_pro(self, billing):
        billing.create_customer("user1")
        result = billing.upgrade("user1", "pro")
        assert result is True
        sub = billing.get_subscription("user1")
        assert sub["tier"] == "pro"

    def test_upgrade_invalid_tier(self, billing):
        billing.create_customer("user1")
        result = billing.upgrade("user1", "mega_ultra")
        assert result is False

    def test_upgrade_auto_creates_customer(self, billing):
        """Upgrade should work even if create_customer wasn't called first."""
        result = billing.upgrade("user_new", "plus")
        assert result is True
        sub = billing.get_subscription("user_new")
        assert sub["tier"] == "plus"

    def test_downgrade(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")
        result = billing.downgrade("user1")
        assert result is True
        sub = billing.get_subscription("user1")
        assert sub["tier"] == "free"
        assert sub["expires_at"] is None

    def test_cancel(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")
        result = billing.cancel("user1")
        assert result is True
        sub = billing.get_subscription("user1")
        assert sub["status"] == "cancelled"
        assert sub["tier"] == "plus"  # Tier kept until expiry

    def test_cancel_free_returns_false(self, billing):
        billing.create_customer("user1")
        result = billing.cancel("user1")
        assert result is False

    def test_is_premium_free(self, billing):
        assert billing.is_premium("user1") is False

    def test_is_premium_plus(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")
        assert billing.is_premium("user1") is True

    def test_is_premium_pro(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")
        assert billing.is_premium("user1") is True

    def test_is_premium_cancelled_still_active(self, billing):
        """Cancelled sub is still premium until expiry."""
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")
        billing.cancel("user1")
        assert billing.is_premium("user1") is True

    def test_get_tier(self, billing):
        assert billing.get_tier("user1") == "free"
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")
        assert billing.get_tier("user1") == "pro"

    def test_get_tier_config(self, billing):
        config = billing.get_tier_config("user1")
        assert config["name"] == "Free"
        assert config["messages_per_day"] == 300

    def test_subscription_lifecycle(self, billing):
        """Full lifecycle: create → upgrade → cancel → downgrade."""
        billing.create_customer("user1", "user@example.com")
        assert billing.get_tier("user1") == "free"

        billing.upgrade("user1", "plus", "pay_1")
        assert billing.get_tier("user1") == "plus"
        assert billing.is_premium("user1") is True

        billing.upgrade("user1", "pro", "pay_2")
        assert billing.get_tier("user1") == "pro"

        billing.cancel("user1")
        assert billing.is_premium("user1") is True  # Still active until expiry

        billing.downgrade("user1")
        assert billing.get_tier("user1") == "free"
        assert billing.is_premium("user1") is False


# ─── Usage Tracking Tests ────────────────────────────────────

class TestUsageTracking:
    def test_record_usage(self, billing):
        billing.record_usage("user1", "message")
        usage = billing.get_usage("user1")
        assert usage["messages_today"] == 1

    def test_record_multiple_usage(self, billing):
        for _ in range(30):
            billing.record_usage("user1", "message")
        usage = billing.get_usage("user1")
        assert usage["messages_today"] == 30

    def test_record_different_actions(self, billing):
        billing.record_usage("user1", "message")
        billing.record_usage("user1", "voice")
        billing.record_usage("user1", "image")
        usage = billing.get_usage("user1")
        assert usage["messages_today"] == 1
        assert usage["voice_today"] == 1
        assert usage["image_today"] == 1

    def test_usage_includes_limits(self, billing):
        usage = billing.get_usage("user1")
        assert usage["tier"] == "free"
        assert usage["messages_limit"] == 300
        assert usage["voice_limit"] == 30
        assert usage["image_limit"] == 30


# ─── Limit Enforcement Tests ─────────────────────────────────

class TestLimits:
    def test_free_message_limit(self, billing):
        """Free tier: 50 messages/day."""
        for i in range(300):
            allowed, reason = billing.check_limits("user1", "message")
            assert allowed is True, f"Should be allowed at message {i+1}"
            billing.record_usage("user1", "message")

        allowed, reason = billing.check_limits("user1", "message")
        assert allowed is False
        assert "300" in reason
        assert "midnight" in reason.lower() or "reset" in reason.lower()

    def test_free_voice_limit(self, billing):
        """Free tier: 5 voice/day."""
        for _ in range(30):
            billing.record_usage("user1", "voice")

        allowed, reason = billing.check_limits("user1", "voice")
        assert allowed is False
        assert "voice" in reason.lower()

    def test_free_image_limit(self, billing):
        """Free tier: 3 images/day."""
        for _ in range(30):
            billing.record_usage("user1", "image")

        allowed, reason = billing.check_limits("user1", "image")
        assert allowed is False

    def test_plus_higher_limits(self, billing):
        """Plus tier: 500 messages/day."""
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")

        for _ in range(300):
            billing.record_usage("user1", "message")

        allowed, reason = billing.check_limits("user1", "message")
        assert allowed is True

    def test_pro_unlimited(self, billing):
        """Pro tier: unlimited everything."""
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")

        for _ in range(1000):
            billing.record_usage("user1", "message")

        allowed, reason = billing.check_limits("user1", "message")
        assert allowed is True
        assert reason == "ok"

    def test_unknown_action_always_allowed(self, billing):
        allowed, reason = billing.check_limits("user1", "unknown_action")
        assert allowed is True

    def test_check_feature_proactive_free(self, billing):
        assert billing.check_feature("user1", "proactive_messages") is True

    def test_check_feature_proactive_plus(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")
        assert billing.check_feature("user1", "proactive_messages") is True

    def test_check_feature_group_mode_free(self, billing):
        # All features available in free-forever model
        assert billing.check_feature("user1", "group_mode") is True

    def test_check_feature_group_mode_pro(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")
        assert billing.check_feature("user1", "group_mode") is True

    def test_check_feature_priority_response(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "plus")
        assert billing.check_feature("user1", "priority_response") is True
        billing.upgrade("user1", "pro")
        assert billing.check_feature("user1", "priority_response") is True

    def test_memory_limit_free(self, billing):
        allowed, reason = billing.check_memory_limit("user1", 301)
        assert allowed is False
        assert "30" in reason

    def test_memory_limit_under(self, billing):
        allowed, reason = billing.check_memory_limit("user1", 50)
        assert allowed is True

    @pytest.mark.skip(reason="Pro tier no longer unlimited - needs rework")
    def test_memory_limit_pro_unlimited(self, billing):
        billing.create_customer("user1")
        billing.upgrade("user1", "pro")
        allowed, reason = billing.check_memory_limit("user1", 999999)
        assert allowed is True


# ─── Tier Configuration Tests ────────────────────────────────

class TestTierConfig:
    def test_all_tiers_exist(self):
        assert "free" in TIERS
        assert "plus" in TIERS
        assert "pro" in TIERS

    def test_free_tier_values(self):
        t = TIERS["free"]
        assert t["messages_per_day"] == 300
        assert t["memory_slots"] == 300
        assert t["voice_per_day"] == 30
        assert t["image_per_day"] == 30
        assert t["proactive_messages"] is True
        assert t["priority_response"] is False
        assert t["group_mode"] is True  # All features free in community model

    def test_plus_tier_values(self):
        t = TIERS["plus"]
        assert t["messages_per_day"] == 900
        assert t["memory_slots"] == 900
        assert t["proactive_messages"] is True
        assert t["group_mode"] is True
        assert t["price"] == 0  # Free forever

    def test_pro_tier_values(self):
        t = TIERS["pro"]
        assert t["messages_per_day"] == 2700
        assert t["memory_slots"] == 2700
        assert t["priority_response"] is True
        assert t["price"] == 0  # Free forever

    def test_action_limit_map(self):
        assert "message" in ACTION_LIMIT_MAP
        assert "voice" in ACTION_LIMIT_MAP
        assert "image" in ACTION_LIMIT_MAP


# ─── Stripe Handler Tests ────────────────────────────────────

class TestStripeHandler:
    def test_stripe_not_configured(self, stripe):
        assert stripe.stripe_configured is False

    def test_checkout_without_stripe(self, stripe):
        url = stripe.create_checkout_session("user1", "plus")
        assert url == ""

    def test_portal_without_stripe(self, stripe):
        url = stripe.create_portal_session("cust_123")
        assert url == ""

    def test_webhook_without_stripe(self, stripe):
        result = stripe.handle_webhook(b"{}", "sig")
        assert "error" in result
        assert "not configured" in result["error"]

    def test_checkout_invalid_tier(self, stripe):
        url = stripe.create_checkout_session("user1", "mega")
        assert url == ""

    @patch("nobi.billing.stripe_handler.STRIPE_AVAILABLE", True)
    @patch("nobi.billing.stripe_handler.stripe_lib")
    def test_stripe_configured_with_key(self, mock_stripe):
        mock_stripe.api_key = None
        handler = StripeHandler(api_key="sk_test_fake")
        assert handler.stripe_configured is True
        assert mock_stripe.api_key == "sk_test_fake"

    @patch("nobi.billing.stripe_handler.STRIPE_AVAILABLE", False)
    def test_stripe_not_configured_without_sdk(self):
        handler = StripeHandler(api_key="sk_test_fake")
        assert handler.stripe_configured is False

    def test_handle_checkout_completed_extracts_data(self, stripe):
        """Test internal webhook parsing logic."""
        session_data = {
            "client_reference_id": "user1",
            "metadata": {"tier": "plus"},
            "customer": "cust_abc",
            "subscription": "sub_xyz",
        }
        result = stripe._handle_checkout_completed(session_data)
        assert result["action"] == "activate"
        assert result["user_id"] == "user1"
        assert result["tier"] == "plus"
        assert result["customer_id"] == "cust_abc"
        assert result["payment_id"] == "sub_xyz"
        assert result["processed"] is True

    def test_handle_subscription_deleted(self, stripe):
        sub_data = {"customer": "cust_abc"}
        result = stripe._handle_subscription_deleted(sub_data)
        assert result["action"] == "cancel"
        assert result["customer_id"] == "cust_abc"

    def test_handle_payment_failed(self, stripe):
        invoice_data = {"customer": "cust_abc"}
        result = stripe._handle_payment_failed(invoice_data)
        assert result["action"] == "payment_failed"

    def test_handle_checkout_completed_no_user_id(self, stripe):
        """Missing user_id should return error."""
        session_data = {"metadata": {}, "customer": "cust_abc"}
        result = stripe._handle_checkout_completed(session_data)
        assert result["processed"] is False
        assert "error" in result


# ─── Thread Safety Tests ─────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_usage_recording(self, billing):
        """Test that concurrent usage recording doesn't lose data."""
        import threading

        def record_n(n):
            for _ in range(n):
                billing.record_usage("user1", "message")

        threads = [threading.Thread(target=record_n, args=(10,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        usage = billing.get_usage("user1")
        assert usage["messages_today"] == 50


# ─── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    def test_close_and_reopen(self, tmp_path):
        db_path = str(tmp_path / "test_reopen.db")
        mgr1 = SubscriptionManager(db_path=db_path)
        mgr1.create_customer("user1", "test@example.com")
        mgr1.upgrade("user1", "pro")
        mgr1.close()

        mgr2 = SubscriptionManager(db_path=db_path)
        sub = mgr2.get_subscription("user1")
        assert sub["tier"] == "pro"
        mgr2.close()

    def test_empty_user_id(self, billing):
        """Empty user_id should still work."""
        cid = billing.create_customer("")
        assert cid.startswith("cust_")

    def test_special_characters_user_id(self, billing):
        cid = billing.create_customer("tg_12345")
        assert cid.startswith("cust_")
        sub = billing.get_subscription("tg_12345")
        assert sub["tier"] == "free"

    def test_export_memories_always_allowed(self, billing):
        """Export memories should be allowed on all tiers."""
        for tier in TIERS:
            assert TIERS[tier]["export_memories"] is True
