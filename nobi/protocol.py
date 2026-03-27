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
        adapter_config: Per-user personality adapter config (Phase B)
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
    adapter_config: dict = {}  # Phase B: per-user personality adapter

    # === Response fields (filled by miner) ===
    response: typing.Optional[str] = None
    confidence: typing.Optional[float] = None
    memory_context: typing.Optional[typing.List[dict]] = None  # Memory entries used

    # === Phase 4: Miner specialization ===
    query_type: str = "general"  # advice | creative | technical | social | knowledge
    miner_specialization: str = ""  # Miner's declared specialty

    # === Phase 5: TEE Encryption (end-to-end privacy) ===
    # When encrypted=True, the miner receives only ciphertext — no plaintext user data.
    # Non-TEE miners see encrypted=False and continue receiving plaintext (backward compat).
    encrypted: bool = False                 # Whether payload is encrypted
    encryption_scheme: str = ""            # e.g., "aes-256-gcm-v1" or "aes-256-gcm-hpke-v1"
    encrypted_message: str = ""            # base64url: "<nonce>.<ciphertext+tag>"
    encrypted_context: str = ""            # base64url: "<nonce>.<ciphertext+tag>" (memory context)
    key_id: str = ""                       # Session key (Phase 1: plaintext b64; Phase 2: HPKE-wrapped blob)

    # === Phase 6: HPKE Key Advertisement (miner → validator) ===
    # Miner populates tee_pubkey in their response so the validator can cache it.
    # Validator uses this on subsequent queries to HPKE-wrap the session key.
    # This field is set by the miner, not the validator.
    tee_pubkey: str = ""                   # Miner's X25519 TEE public key (base64url, 44 chars)

    # === Phase 7: TEE Capability Advertisement (miner → validator) ===
    # Miners that run inside a Trusted Execution Environment advertise their
    # TEE type and provide a signed attestation report.  Validators verify
    # the report and set tee_verified=True, making the miner eligible for
    # a scoring bonus (see reward.py: TEE_BONUS).
    #
    # Workflow:
    #   1. Miner sets tee_type and tee_attestation in its response.
    #   2. Validator calls TEEAttestationVerifier.verify_from_base64().
    #   3. If verification passes, validator records tee_verified=True in the
    #      cached synapse / miner score state.
    #
    # Supported tee_type values:
    #   "amd-sev-snp"  — AMD EPYC with SEV-SNP (recommended, proven on SN4/Targon)
    #   "nvidia-cc"    — NVIDIA H100/A100 Confidential Computing mode
    #   ""  or "none"  — No TEE (backward compatible; no bonus, no penalty)
    tee_type: str = ""                     # TEE hardware type (set by miner)
    tee_attestation: str = ""              # Base64-encoded attestation report (set by miner)
    tee_verified: bool = False             # Set to True by validator after successful verification

    # === Phase 4: TEE Encrypted Response (miner → validator / API → browser) ===
    # When the miner processes an encrypted synapse, it encrypts its response too.
    # The validator decrypts this field to get plaintext for scoring.
    # Non-TEE miners leave this empty — backward compatible.
    encrypted_response: str = ""           # base64url: "<nonce>.<ciphertext+tag>" (AES-256-GCM)

    def deserialize(self) -> str:
        """Returns the response string."""
        return self.response


class VoiceRequest(bt.Synapse):
    """
    Voice message handling.

    Carries audio data for speech-to-text transcription,
    Nori response generation, and text-to-speech synthesis.
    """

    # === Request fields ===
    audio_data: str = ""        # Base64 encoded audio
    audio_format: str = "wav"   # wav | mp3 | ogg
    language: str = "en"
    user_id: str = ""

    # === Response fields (filled by miner) ===
    transcription: str = ""
    response_text: str = ""
    response_audio: str = ""    # Base64 encoded audio response

    def deserialize(self) -> str:
        return self.response_text


class ImageRequest(bt.Synapse):
    """
    Image understanding request.

    Carries image data for vision model analysis.
    Returns description, response, and extracted memories.
    """

    # === Request fields ===
    image_data: str = ""        # Base64 encoded image
    image_format: str = "jpg"   # jpg | png | gif | webp
    caption: str = ""           # User's caption/question about the image
    user_id: str = ""

    # === Response fields (filled by miner) ===
    description: str = ""       # What's in the image
    response: str = ""          # Nori's response about the image
    extracted_memories: typing.List[str] = []  # Memories extracted from the image

    def deserialize(self) -> str:
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

    # === Encryption metadata (Phase A) ===
    encrypted: bool = False  # Whether content is pre-encrypted by the sender
    encryption_version: int = 1  # Encryption protocol version for negotiation

    # === Phase B: End-to-end encrypted content ===
    encrypted_content: str = ""  # AES-encrypted memory content (miner stores as-is)
    content_hash: str = ""  # SHA-256 hash of plaintext (for dedup without decryption)

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
    return_encrypted: bool = False  # Phase B: if True, return encrypted blobs as-is

    # === Response fields (filled by miner) ===
    memories: typing.Optional[typing.List[dict]] = None
    # Each memory dict: {id, type, content, importance, tags, created_at, expires_at}
    total_count: typing.Optional[int] = None  # Total memories for this user

    def deserialize(self) -> typing.List[dict]:
        return self.memories or []


class MemoryForget(bt.Synapse):
    """
    GDPR right-to-erasure — request miners to delete ALL data for a user.

    Validators broadcast this to all miners when a user requests deletion.
    Miners MUST delete all memories, conversations, profiles, entities,
    relationships, and embeddings for the given user_id.

    This is a best-effort protocol: we broadcast the request but cannot
    verify deletion on remote miners. Compliance is trust-based.

    GDPR basis: Art. 17 — Right to Erasure ("right to be forgotten").
    Subnet 272 design: Bot triggers local wipe first, then validator
    broadcasts MemoryForget to all active miners for decentralized erasure.
    """

    # === Request fields ===
    user_id: str                            # User whose data must be deleted
    reason: str = "user_request"            # user_request | gdpr | account_deletion

    # === Response fields (filled by miner) ===
    deleted: typing.Optional[bool] = None
    items_deleted: int = 0                  # How many items (rows) were deleted

    def deserialize(self) -> bool:
        return self.deleted or False


class FederatedUpdate(bt.Synapse):
    """
    Carries federated learning weight updates with privacy-preserving model deltas.

    Raw user data never travels in this synapse — only anonymized preference signals.
    This is the core synapse for Phase C federated privacy.

    Flow:
    1. Miner generates preference signals from user interactions (locally).
    2. Miner adds differential privacy noise to the signal.
    3. Miner encrypts and sends via this synapse to the validator.
    4. Validator aggregates signals from all miners (secure aggregation).
    5. Validator returns the global update to all miners.

    Privacy guarantees:
    - No raw user data in the synapse (only anonymized preference deltas).
    - DP noise is applied before transmission.
    - Encryption for in-transit protection.
    - k-anonymity enforced at aggregation (min 5 signals).
    """

    # === Request fields (sent by miner to validator) ===
    signal_type: str = "preference"    # preference | quality | style
    encrypted_signal: str = ""         # Encrypted preference delta (JSON)
    noise_added: bool = False          # Whether DP noise has been applied
    epsilon: float = 1.0               # Privacy parameter used
    aggregation_round: int = 0         # Which round of aggregation
    num_contributions: int = 0         # How many users contributed to this signal

    # === Response fields (filled by validator) ===
    accepted: typing.Optional[bool] = None
    global_update: dict = {}           # Aggregated update to apply locally

    def deserialize(self) -> dict:
        """Returns the global update dict."""
        return self.global_update
