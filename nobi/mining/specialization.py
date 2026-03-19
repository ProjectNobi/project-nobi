"""
Nobi Miner Specialization — Route queries to specialized miners.

Allows miners to declare specializations and receive query-matched bonuses.
Validators track per-miner performance by category and route accordingly.

Specializations:
  - "advice": Life coaching, decision-making, emotional support
  - "creative": Storytelling, brainstorming, artistic ideas
  - "technical": Code help, math, science explanations
  - "social": Conversation, humor, casual chat
  - "knowledge": Facts, research, learning
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

SPECIALIZATIONS = {"advice", "creative", "technical", "social", "knowledge", "general"}

SPECIALIZATION_BONUS = 0.15  # 15% bonus for matching specialization
FALLBACK_PENALTY = 0.0       # No penalty for general miners
MIN_SAMPLES_FOR_ROUTING = 5  # Minimum scored queries before routing

# ─── Query Classification Keywords ───────────────────────────────────────────

CLASSIFICATION_KEYWORDS: dict[str, list[str]] = {
    "advice": [
        "should i", "help me decide", "what do you think", "advice", "recommend",
        "feeling", "stressed", "anxious", "worried", "sad", "happy", "upset",
        "relationship", "career", "decision", "support", "encourage", "motivat",
        "cope", "deal with", "struggling", "confused", "lost", "guidance",
    ],
    "creative": [
        "write", "story", "poem", "creative", "imagine", "brainstorm", "idea",
        "fiction", "character", "plot", "song", "lyrics", "art", "design",
        "invent", "create", "compose", "draw", "paint", "novel", "script",
    ],
    "technical": [
        "code", "program", "bug", "error", "function", "algorithm", "binary search", "database",
        "python", "javascript", "api", "debug", "math", "calculate", "equation",
        "science", "physics", "chemistry", "biology", "engineering", "compute",
        "server", "deploy", "docker", "linux", "sql", "data", "machine learning",
    ],
    "social": [
        "hey", "hello", "hi", "how are you", "what's up", "lol", "haha",
        "joke", "funny", "chat", "talk", "bored", "tell me about yourself",
        "friend", "conversation", "weather", "today", "morning", "night",
        "thanks", "cool", "nice", "awesome", "great", "love it",
    ],
    "knowledge": [
        "what is", "who is", "when did", "where is", "why does", "how does",
        "explain", "define", "history", "fact", "research", "study",
        "learn", "teach", "education", "science", "theory", "concept",
        "meaning", "difference between", "compare", "summarize", "overview",
    ],
}


# ─── Query Classification ────────────────────────────────────────────────────

def classify_query(message: str) -> str:
    """
    Classify a user query into a specialization category.

    Uses keyword matching with scoring. Returns the best-matching category
    or 'general' if no clear match.

    Args:
        message: The user's message text.

    Returns:
        One of: advice, creative, technical, social, knowledge, general
    """
    if not message or not message.strip():
        return "general"

    lower_msg = message.lower().strip()
    scores: dict[str, float] = defaultdict(float)

    for category, keywords in CLASSIFICATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in lower_msg:
                # Longer keywords get higher weight (more specific)
                weight = len(keyword.split()) * 0.5 + 0.5
                scores[category] += weight

    if not scores:
        return "general"

    # Get the highest-scoring category
    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]

    # Require minimum confidence
    if best_score < 1.0:
        return "general"

    # Check if there's a clear winner (at least 50% more than runner-up)
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) > 1 and sorted_scores[0] < sorted_scores[1] * 1.5:
        return "general"

    return best_category


# ─── Miner Profile ───────────────────────────────────────────────────────────

@dataclass
class MinerProfile:
    """
    Stores a miner's declared specialization and performance metrics.

    Tracks per-category scores to enable intelligent routing.
    """

    uid: int
    hotkey: str
    specialization: str = "general"
    scores_by_category: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    total_queries: int = 0
    total_score: float = 0.0

    def add_score(self, category: str, score: float) -> None:
        """Record a score for a query category."""
        self.scores_by_category[category].append(score)
        self.total_queries += 1
        self.total_score += score

        # Keep only last 100 scores per category (sliding window)
        if len(self.scores_by_category[category]) > 100:
            self.scores_by_category[category] = self.scores_by_category[category][-100:]

    def get_category_score(self, category: str) -> float:
        """Get average score for a category."""
        scores = self.scores_by_category.get(category, [])
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def get_overall_score(self) -> float:
        """Get overall average score."""
        if self.total_queries == 0:
            return 0.0
        return self.total_score / self.total_queries

    def get_effective_score(self, query_type: str) -> float:
        """
        Get the effective score for a query type, including specialization bonus.
        """
        base_score = self.get_category_score(query_type)

        # Apply specialization bonus
        if self.specialization == query_type and self.specialization != "general":
            base_score *= (1.0 + SPECIALIZATION_BONUS)

        return base_score

    def has_enough_data(self, category: str) -> bool:
        """Check if we have enough samples for reliable routing."""
        return len(self.scores_by_category.get(category, [])) >= MIN_SAMPLES_FOR_ROUTING

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "uid": self.uid,
            "hotkey": self.hotkey,
            "specialization": self.specialization,
            "total_queries": self.total_queries,
            "overall_score": self.get_overall_score(),
            "category_scores": {
                cat: self.get_category_score(cat)
                for cat in SPECIALIZATIONS
                if self.scores_by_category.get(cat)
            },
        }


# ─── Miner Selection ─────────────────────────────────────────────────────────

def select_best_miner(
    query_type: str,
    available_miners: list[MinerProfile],
    top_k: int = 3,
) -> list[MinerProfile]:
    """
    Select the best miners for a given query type.

    Strategy:
    1. Prefer miners with matching specialization AND good scores.
    2. Fall back to highest-scoring general miners.
    3. Always return at least some miners (never block a query).

    Args:
        query_type: The classified query type (advice, creative, etc.).
        available_miners: List of available MinerProfile objects.
        top_k: Number of miners to select.

    Returns:
        Sorted list of best miners (best first), up to top_k.
    """
    if not available_miners:
        return []

    if len(available_miners) <= top_k:
        return available_miners

    # Score each miner
    scored_miners: list[tuple[float, MinerProfile]] = []

    for miner in available_miners:
        if miner.has_enough_data(query_type):
            # Use category-specific score with specialization bonus
            score = miner.get_effective_score(query_type)
        else:
            # Not enough data — use overall score
            score = miner.get_overall_score()

            # Small bonus for declared specialization match (even without data)
            if miner.specialization == query_type and query_type != "general":
                score *= 1.05

        scored_miners.append((score, miner))

    # Sort by score (highest first)
    scored_miners.sort(key=lambda x: x[0], reverse=True)

    return [miner for _, miner in scored_miners[:top_k]]


# ─── Validator Integration ────────────────────────────────────────────────────

class MinerRouter:
    """
    Manages miner profiles and routes queries to specialized miners.

    Used by validators to track and route to the best miners.
    """

    def __init__(self) -> None:
        self.miners: dict[int, MinerProfile] = {}

    def register_miner(
        self,
        uid: int,
        hotkey: str,
        specialization: str = "general",
    ) -> MinerProfile:
        """Register or update a miner's profile."""
        if specialization not in SPECIALIZATIONS:
            logger.warning(
                f"Unknown specialization '{specialization}' for UID {uid}, defaulting to general"
            )
            specialization = "general"

        if uid in self.miners:
            self.miners[uid].specialization = specialization
            self.miners[uid].hotkey = hotkey
        else:
            self.miners[uid] = MinerProfile(
                uid=uid, hotkey=hotkey, specialization=specialization
            )

        return self.miners[uid]

    def record_score(self, uid: int, query_type: str, score: float) -> None:
        """Record a miner's score for a query category."""
        if uid not in self.miners:
            logger.warning(f"Unknown miner UID {uid}, cannot record score")
            return

        self.miners[uid].add_score(query_type, score)

    def route_query(
        self,
        message: str,
        available_uids: Optional[list[int]] = None,
        top_k: int = 3,
    ) -> tuple[str, list[MinerProfile]]:
        """
        Classify a query and select the best miners.

        Args:
            message: User's message.
            available_uids: UIDs to consider (None = all registered).
            top_k: Number of miners to select.

        Returns:
            (query_type, selected_miners)
        """
        query_type = classify_query(message)

        if available_uids is not None:
            candidates = [
                self.miners[uid]
                for uid in available_uids
                if uid in self.miners
            ]
        else:
            candidates = list(self.miners.values())

        selected = select_best_miner(query_type, candidates, top_k)

        logger.info(
            f"Query type: {query_type}, selected {len(selected)} miners: "
            f"{[m.uid for m in selected]}"
        )

        return query_type, selected

    def get_miner(self, uid: int) -> Optional[MinerProfile]:
        """Get a miner's profile."""
        return self.miners.get(uid)

    def get_all_profiles(self) -> list[dict]:
        """Get all miner profiles as dicts."""
        return [m.to_dict() for m in self.miners.values()]

    def get_specialists(self, specialization: str) -> list[MinerProfile]:
        """Get all miners with a given specialization."""
        return [
            m for m in self.miners.values()
            if m.specialization == specialization
        ]

    def get_stats(self) -> dict:
        """Get routing statistics."""
        spec_counts: dict[str, int] = defaultdict(int)
        for miner in self.miners.values():
            spec_counts[miner.specialization] += 1

        return {
            "total_miners": len(self.miners),
            "specialization_distribution": dict(spec_counts),
            "avg_overall_score": (
                sum(m.get_overall_score() for m in self.miners.values()) / len(self.miners)
                if self.miners
                else 0.0
            ),
        }
