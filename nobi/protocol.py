# Project Nobi — Protocol
# Synapse definitions for companion interactions.
# Phase 1: Message in, response out
# Phase 2: Memory protocol — persistent conversation memory per user

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
        memory_context: Memory entries the miner used to generate the response
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
    memory_context: typing.Optional[typing.List[dict]] = None  # Memory entries used

    def deserialize(self) -> str:
        """Returns the response string."""
        return self.response


class MemoryStore(bt.Synapse):
    """
    Store a memory entry for a user.

    Validators send this after a conversation turn to instruct miners
    to persist important information about the user.

    Memory types:
      - "fact": A factual detail about the user (name, preferences, etc.)
      - "event": Something that happened (user got a job, had a birthday)
      - "preference": User preference (likes cats, prefers formal tone)
      - "context": Ongoing context (working on a project, studying for exam)
      - "emotion": Emotional state or pattern (stressed about work lately)
    """

    # === Request fields ===
    user_id: str
    memory_type: str = "fact"  # fact | event | preference | context | emotion
    content: str = ""  # The memory content to store
    importance: float = 0.5  # 0.0 to 1.0, how important this memory is
    tags: typing.List[str] = []  # Searchable tags
    expires_at: typing.Optional[str] = None  # ISO datetime, None = permanent

    # === Encryption metadata ===
    encrypted: bool = False  # Whether content is pre-encrypted by the sender
    encryption_version: int = 1  # Encryption protocol version for negotiation

    # === Response fields (filled by miner) ===
    stored: typing.Optional[bool] = None
    memory_id: typing.Optional[str] = None  # Unique ID for the stored memory

    def deserialize(self) -> bool:
        return self.stored or False


class MemoryRecall(bt.Synapse):
    """
    Recall memories for a user.

    Validators send this to check if miners properly stored and can retrieve
    user memories. Used for scoring memory fidelity.

    The query can be:
      - A natural language query ("What does the user do for work?")
      - A tag-based query (tags=["work", "career"])
      - A type filter (memory_type="preference")
    """

    # === Request fields ===
    user_id: str
    query: str = ""  # Natural language query
    memory_type: typing.Optional[str] = None  # Filter by type
    tags: typing.List[str] = []  # Filter by tags
    limit: int = 10  # Max memories to return

    # === Response fields (filled by miner) ===
    memories: typing.Optional[typing.List[dict]] = None
    # Each memory dict: {id, type, content, importance, tags, created_at, expires_at}
    total_count: typing.Optional[int] = None  # Total memories for this user

    def deserialize(self) -> typing.List[dict]:
        return self.memories or []
