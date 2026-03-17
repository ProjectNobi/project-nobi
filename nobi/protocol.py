# Project Nobi — Protocol
# Synapse definitions for companion interactions.
# Phase 1: Keep it simple — message in, response out.

import typing
import bittensor as bt


class CompanionRequest(bt.Synapse):
    """
    Request synapse for the personal AI companion.

    Validators send this to miners with a user message.
    Miners process the message and fill in the response fields.

    Attributes:
        message: The user's message / query
        conversation_history: Recent messages for context (list of dicts with 'role' and 'content')
        user_id: Anonymous user identifier for session tracking
        preferences: User preferences (language, style, etc.)
        response: The AI companion's response (filled by miner)
        confidence: Miner's confidence in the response (0.0 to 1.0)
    """

    # === Required request fields (sent by validator) ===
    message: str

    # === Optional request fields ===
    conversation_history: typing.List[dict] = []
    user_id: str = ""
    preferences: dict = {}

    # === Response fields (filled by miner) ===
    response: typing.Optional[str] = None
    confidence: typing.Optional[float] = None

    def deserialize(self) -> str:
        """Returns the response string."""
        return self.response
