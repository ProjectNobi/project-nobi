"""
Project Nobi — Self-Improving Feedback Loop
============================================
Detects user corrections, extracts lessons, and injects them
into Nori's system prompt — making Nori the first self-improving
AI companion on Bittensor.
"""

from .feedback_store import FeedbackStore

__all__ = ["FeedbackStore"]
