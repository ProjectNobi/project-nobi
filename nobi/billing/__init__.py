"""
Project Nobi — Billing & Subscription System
==============================================
Manages subscription tiers, usage tracking, and Stripe integration.
Stripe is OPTIONAL — system works fully with free tier when not configured.
"""

from nobi.billing.subscription import SubscriptionManager

__all__ = ["SubscriptionManager"]
