"""
Project Nobi — Protocol
Synapse definitions for companion AI interactions on Bittensor subnet 272.
"""

import typing
import pydantic
import bittensor as bt


class CompanionQuery(bt.Synapse):
    """
    Synapse for querying a personal AI companion.

    The validator sends a user message and optional context;
    the miner returns a companion response with a confidence score.
    """

    # ── Required request fields (set by validator) ──────────────────
    user_message: str = pydantic.Field(
        ...,
        description="The user's message to the companion.",
    )
    conversation_id: str = pydantic.Field(
        default="default",
        description="Unique conversation thread identifier.",
    )
    user_profile: typing.Optional[dict] = pydantic.Field(
        default=None,
        description="Optional user profile dict (name, preferences, etc.).",
    )

    # ── Response fields (set by miner) ──────────────────────────────
    companion_response: typing.Optional[str] = pydantic.Field(
        default=None,
        description="The companion's reply to the user message.",
    )
    confidence_score: typing.Optional[float] = pydantic.Field(
        default=None,
        description="Miner's self-assessed confidence in the response (0-1).",
    )

    def deserialize(self) -> dict:
        """Return the response payload as a simple dict."""
        return {
            "companion_response": self.companion_response,
            "confidence_score": self.confidence_score,
        }


class MemorySync(bt.Synapse):
    """
    Synapse for syncing user memory state between validator and miner.
    Allows the network to coordinate long-term user context.
    """

    # ── Request fields ──────────────────────────────────────────────
    user_id: str = pydantic.Field(
        ...,
        description="Unique user identifier.",
    )
    memories: typing.Optional[typing.List[dict]] = pydantic.Field(
        default=None,
        description="List of memory dicts to sync ({key, value, timestamp}).",
    )

    # ── Response fields ─────────────────────────────────────────────
    acknowledged: typing.Optional[bool] = pydantic.Field(
        default=None,
        description="Whether the miner acknowledged the memory sync.",
    )
    memory_count: typing.Optional[int] = pydantic.Field(
        default=None,
        description="Number of memories stored by the miner for this user.",
    )

    def deserialize(self) -> dict:
        return {
            "acknowledged": self.acknowledged,
            "memory_count": self.memory_count,
        }
