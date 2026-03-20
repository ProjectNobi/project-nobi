"""
Project Nobi — Stripe Integration
===================================
Webhook-based Stripe payment handling.
OPTIONAL — system works fully without Stripe configured.
All Stripe calls guarded by `if self.stripe_configured`.
"""

import os
import logging
from typing import Optional, Dict

logger = logging.getLogger("nobi-stripe")

# Try importing stripe — it's optional
try:
    import stripe as stripe_lib
    STRIPE_AVAILABLE = True
except ImportError:
    stripe_lib = None
    STRIPE_AVAILABLE = False


# Stripe price IDs — set via env or defaults (would be real Stripe price IDs in production)
STRIPE_PRICES = {
    "plus": os.environ.get("STRIPE_PRICE_PLUS", "price_plus_monthly"),
    "pro": os.environ.get("STRIPE_PRICE_PRO", "price_pro_monthly"),
}


class StripeHandler:
    """
    Handles Stripe checkout sessions, webhooks, and billing portal.
    Works gracefully when Stripe is not configured.
    """

    def __init__(self, api_key: str = "", webhook_secret: str = ""):
        self.api_key = api_key or os.environ.get("STRIPE_API_KEY", "")
        self.webhook_secret = webhook_secret or os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.stripe_configured = bool(
            self.api_key and STRIPE_AVAILABLE
        )

        if self.stripe_configured:
            stripe_lib.api_key = self.api_key
            logger.info("Stripe integration configured")
        else:
            if not STRIPE_AVAILABLE:
                logger.info("Stripe SDK not installed — billing disabled (free tier only)")
            else:
                logger.info("No STRIPE_API_KEY — billing disabled (free tier only)")

    def create_checkout_session(
        self,
        user_id: str,
        tier: str,
        success_url: str = "https://app.projectnobi.ai/subscription?success=true",
        cancel_url: str = "https://app.projectnobi.ai/subscription?cancelled=true",
    ) -> str:
        """
        Create a Stripe checkout session for subscription.
        Returns the checkout URL, or empty string if Stripe not configured.
        """
        if not self.stripe_configured:
            logger.warning("Stripe not configured — cannot create checkout session")
            return ""

        if tier not in STRIPE_PRICES:
            logger.warning(f"Invalid tier for checkout: {tier}")
            return ""

        try:
            session = stripe_lib.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{
                    "price": STRIPE_PRICES[tier],
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": user_id,
                    "tier": tier,
                },
                client_reference_id=user_id,
            )
            logger.info(f"Created checkout session for {user_id} ({tier})")
            return session.url or ""
        except Exception as e:
            logger.error(f"Stripe checkout error: {e}")
            return ""

    def handle_webhook(self, payload: bytes, signature: str) -> Dict:
        """
        Process a Stripe webhook event.
        Returns dict with event type and relevant data.
        """
        if not self.stripe_configured:
            return {"error": "Stripe not configured"}

        try:
            if self.webhook_secret:
                event = stripe_lib.Webhook.construct_event(
                    payload, signature, self.webhook_secret
                )
            else:
                # Without webhook secret, parse directly (less secure, dev only)
                import json
                event = stripe_lib.Event.construct_from(
                    json.loads(payload), stripe_lib.api_key
                )
        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return {"error": f"Webhook verification failed: {e}"}

        event_type = event["type"]
        data = event["data"]["object"]
        result = {"event_type": event_type, "processed": False}

        if event_type == "checkout.session.completed":
            result.update(self._handle_checkout_completed(data))

        elif event_type == "customer.subscription.updated":
            result.update(self._handle_subscription_updated(data))

        elif event_type == "customer.subscription.deleted":
            result.update(self._handle_subscription_deleted(data))

        elif event_type == "invoice.payment_failed":
            result.update(self._handle_payment_failed(data))

        else:
            result["message"] = f"Unhandled event type: {event_type}"

        return result

    def _handle_checkout_completed(self, session) -> Dict:
        """Handle successful checkout."""
        user_id = session.get("client_reference_id") or session.get("metadata", {}).get("user_id", "")
        tier = session.get("metadata", {}).get("tier", "plus")
        customer_id = session.get("customer", "")
        subscription_id = session.get("subscription", "")

        if not user_id:
            return {"error": "No user_id in checkout session", "processed": False}

        return {
            "action": "activate",
            "user_id": user_id,
            "tier": tier,
            "customer_id": customer_id,
            "payment_id": subscription_id,
            "processed": True,
        }

    def _handle_subscription_updated(self, subscription) -> Dict:
        """Handle subscription tier change."""
        customer_id = subscription.get("customer", "")
        status = subscription.get("status", "")

        # Try to determine tier from price
        items = subscription.get("items", {}).get("data", [])
        tier = "plus"  # default
        if items:
            price_id = items[0].get("price", {}).get("id", "")
            for t, pid in STRIPE_PRICES.items():
                if price_id == pid:
                    tier = t
                    break

        return {
            "action": "update",
            "customer_id": customer_id,
            "tier": tier,
            "status": status,
            "processed": True,
        }

    def _handle_subscription_deleted(self, subscription) -> Dict:
        """Handle subscription cancellation."""
        customer_id = subscription.get("customer", "")
        return {
            "action": "cancel",
            "customer_id": customer_id,
            "processed": True,
        }

    def _handle_payment_failed(self, invoice) -> Dict:
        """Handle failed payment."""
        customer_id = invoice.get("customer", "")
        return {
            "action": "payment_failed",
            "customer_id": customer_id,
            "processed": True,
        }

    def create_portal_session(
        self,
        customer_id: str,
        return_url: str = "https://app.projectnobi.ai/subscription",
    ) -> str:
        """
        Create a Stripe billing portal session.
        Returns the portal URL, or empty string if Stripe not configured.
        """
        if not self.stripe_configured:
            return ""

        try:
            session = stripe_lib.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return session.url or ""
        except Exception as e:
            logger.error(f"Stripe portal error: {e}")
            return ""
