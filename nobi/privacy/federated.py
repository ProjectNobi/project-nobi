"""
Project Nobi — Federated Companion Trainer (Phase C)

Federated learning for companion personality adaptation.
Based on FedAvg (McMahan et al., 2016) — Communication-Efficient Learning
of Deep Networks from Decentralized Data.

Architecture:
- Base model: shared across all miners (DeepSeek/etc via API)
- Per-user adapter: personality preferences stored as lightweight config
- Training: user interactions generate "preference signals" (not raw data)
- Aggregation: validator collects anonymized preference signals, updates global quality metrics
- Privacy: raw user data NEVER leaves the bot/client. Only preference deltas are shared.

Key design decisions:
- Signals carry NO PII: no message text, no user names, no personal details.
- Only statistical deltas: response_length_preference, formality_delta,
  topic_category distribution, quality_score.
- k-anonymity: minimum 5 signals before aggregation.
- Differential privacy noise applied before transmission.
"""

import hashlib
import math
from typing import Dict, List, Optional

import numpy as np

from nobi.privacy.config import PRIVACY_CONFIG
from nobi.privacy.differential import (
    DifferentialPrivacyEngine,
    _validate_epsilon,
    _validate_sensitivity,
)


def _hash_user_id(user_id: str, salt: str = None) -> str:
    """
    Hash a user ID for anonymization using SHA-256.

    Args:
        user_id: Raw user identifier.
        salt: Salt for hashing. Defaults to config value.

    Returns:
        Hex digest of the salted hash (first 16 chars for brevity).
    """
    if salt is None:
        salt = PRIVACY_CONFIG["user_id_salt"]
    h = hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()
    return h[:16]


def _classify_topic(message: str) -> str:
    """
    Classify a message into a topic category.

    This is a lightweight heuristic — no ML model needed.
    The actual message text is NOT stored; only the category label.

    Args:
        message: The user's message text (used locally, never transmitted).

    Returns:
        Topic category string.
    """
    categories = PRIVACY_CONFIG["topic_categories"]
    msg_lower = message.lower()

    keyword_map = {
        "tech": ["code", "program", "software", "computer", "api", "debug", "python",
                 "javascript", "server", "database", "algorithm", "machine learning"],
        "health": ["health", "doctor", "medicine", "exercise", "diet", "sleep",
                   "mental", "anxiety", "therapy", "wellness"],
        "finance": ["money", "invest", "stock", "crypto", "budget", "salary",
                    "tax", "bank", "trading", "bitcoin"],
        "education": ["learn", "study", "school", "university", "course", "exam",
                      "homework", "research", "thesis"],
        "entertainment": ["movie", "music", "game", "play", "watch", "book",
                         "show", "series", "fun", "comedy"],
        "lifestyle": ["travel", "food", "cook", "recipe", "fashion", "home",
                      "garden", "pet", "relationship"],
        "science": ["physics", "chemistry", "biology", "experiment", "theory",
                    "quantum", "space", "evolution", "climate"],
        "creative": ["write", "story", "poem", "art", "design", "creative",
                     "imagine", "draw", "paint"],
    }

    for category, keywords in keyword_map.items():
        if any(kw in msg_lower for kw in keywords):
            return category

    return "general"


def _compute_formality(text: str) -> float:
    """
    Estimate formality of text on a [-1, 1] scale.

    -1 = very informal, +1 = very formal.
    Lightweight heuristic — no ML model.

    Args:
        text: Text to analyze (used locally, never transmitted).

    Returns:
        Formality score in [-1, 1].
    """
    if not text:
        return 0.0

    informal_markers = ["lol", "omg", "btw", "idk", "tbh", "ngl", "bruh",
                        "gonna", "wanna", "gotta", "!!", "??", "haha", "lmao"]
    formal_markers = ["furthermore", "moreover", "therefore", "consequently",
                      "regarding", "pursuant", "hereby", "sincerely",
                      "respectfully", "accordingly"]

    text_lower = text.lower()
    informal_count = sum(1 for m in informal_markers if m in text_lower)
    formal_count = sum(1 for m in formal_markers if m in text_lower)

    total = informal_count + formal_count
    if total == 0:
        return 0.0

    # Score: -1 (all informal) to +1 (all formal)
    return (formal_count - informal_count) / total


class FederatedCompanionTrainer:
    """
    Federated learning for companion personality adaptation.

    Generates anonymized preference signals from user interactions,
    aggregates them using FedAvg-style weighted averaging, and
    applies differential privacy before any data leaves the client.
    """

    def __init__(self, epsilon: float = None, sensitivity: float = None):
        """
        Args:
            epsilon: Privacy parameter for DP noise on signals.
            sensitivity: Clipping bound for signal values.
        """
        self.epsilon = epsilon or PRIVACY_CONFIG["epsilon"]
        self.sensitivity = sensitivity or PRIVACY_CONFIG["max_signal_norm"]
        self.dp_engine = DifferentialPrivacyEngine(
            epsilon=self.epsilon, sensitivity=self.sensitivity
        )
        self._round_counter: int = 0

    def generate_preference_signal(
        self, user_id: str, message: str, response: str, score: float
    ) -> Dict:
        """
        Generate an anonymized preference signal from a user interaction.

        The signal captures statistical preferences WITHOUT any PII:
        - response_length_preference: normalized preference for response length
        - formality_delta: how formal the user prefers responses
        - topic_category: broad topic (no message content)
        - quality_score: user's quality rating (clipped)

        The actual message and response text are used locally for feature
        extraction but are NEVER included in the output signal.

        Args:
            user_id: Raw user identifier (hashed before inclusion).
            message: User's message (used locally only, never transmitted).
            response: AI response (used locally only, never transmitted).
            score: User quality rating (e.g., 0-1 scale).

        Returns:
            Anonymized preference signal dict.
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        # Clip score to valid range
        score = max(0.0, min(1.0, float(score)))

        # Extract features locally (text is NOT stored in signal)
        response_length = len(response) if response else 0
        # Normalize to [-1, 1]: short responses → negative, long → positive
        # Baseline: 500 chars. This is a relative preference, not absolute.
        length_pref = max(-1.0, min(1.0, (response_length - 500) / 500))

        formality = _compute_formality(message)
        topic = _classify_topic(message)

        # Map quality score to [-sensitivity, sensitivity] range centered at 0
        quality_centered = (score - 0.5) * 2.0 * self.sensitivity

        signal = {
            "user_id_hash": _hash_user_id(user_id),
            "response_length_preference": float(np.clip(
                length_pref, -self.sensitivity, self.sensitivity
            )),
            "formality_delta": float(np.clip(
                formality, -self.sensitivity, self.sensitivity
            )),
            "topic_category": topic,
            "quality_score": float(np.clip(
                quality_centered, -self.sensitivity, self.sensitivity
            )),
            "round": self._round_counter,
        }
        return signal

    def add_differential_noise(self, signal: Dict, epsilon: float = None) -> Dict:
        """
        Add calibrated Gaussian noise to a preference signal (ε-DP).

        Clips all numeric signal values to bounded sensitivity, then adds
        noise ~ N(0, σ²) where σ = sensitivity * sqrt(2*ln(1.25/δ)) / ε.

        Args:
            signal: Preference signal dict from generate_preference_signal.
            epsilon: Privacy parameter. Lower = more noise = more private.

        Returns:
            New signal dict with DP noise added. Original is not modified.
        """
        eps = epsilon or self.epsilon
        noised = dict(signal)  # shallow copy

        numeric_fields = [
            "response_length_preference",
            "formality_delta",
            "quality_score",
        ]

        for field in numeric_fields:
            if field in noised:
                noised[field] = self.dp_engine.clip_and_noise(
                    noised[field], sensitivity=self.sensitivity, epsilon=eps
                )

        noised["noise_added"] = True
        noised["epsilon"] = eps
        return noised

    def aggregate_signals(self, signals: List[Dict]) -> Optional[Dict]:
        """
        FedAvg-style aggregation of preference signals.

        Computes weighted average of preference deltas across all signals.
        Enforces k-anonymity: minimum 5 signals required.

        Args:
            signals: List of preference signal dicts.

        Returns:
            Aggregated signal dict, or None if insufficient signals.

        Raises:
            ValueError: If signals list is empty.
        """
        min_k = PRIVACY_CONFIG["min_aggregation_size"]

        if not signals:
            raise ValueError("Cannot aggregate empty signal list")

        if len(signals) < min_k:
            # k-anonymity: refuse to aggregate with too few signals
            return None

        numeric_fields = [
            "response_length_preference",
            "formality_delta",
            "quality_score",
        ]

        # Weighted average (uniform weights — FedAvg with equal data sizes)
        n = len(signals)
        aggregated = {}

        for field in numeric_fields:
            values = [s.get(field, 0.0) for s in signals]
            aggregated[field] = sum(values) / n

        # Topic distribution (histogram)
        topic_counts: Dict[str, int] = {}
        for s in signals:
            t = s.get("topic_category", "general")
            topic_counts[t] = topic_counts.get(t, 0) + 1
        total = sum(topic_counts.values())
        topic_dist = {k: v / total for k, v in topic_counts.items()} if total > 0 else {}

        aggregated["topic_distribution"] = topic_dist
        aggregated["num_contributions"] = n
        aggregated["round"] = self._round_counter

        return aggregated

    def apply_aggregated_update(
        self, current_config: Dict, aggregated_delta: Dict
    ) -> Dict:
        """
        Apply an aggregated preference delta to the global companion config.

        Uses the adapter_weight_clip to limit how much any single round
        can change the global config (stability).

        Args:
            current_config: Current global companion configuration.
            aggregated_delta: Aggregated preference delta from aggregate_signals.

        Returns:
            Updated config dict.
        """
        clip = PRIVACY_CONFIG["adapter_weight_clip"]
        updated = dict(current_config)

        # Apply numeric deltas with clipping
        for field in ["response_length_preference", "formality_delta", "quality_score"]:
            if field in aggregated_delta:
                delta = aggregated_delta[field]
                # Clip the delta
                delta = max(-clip, min(clip, delta))
                current_val = updated.get(field, 0.0)
                updated[field] = current_val + delta

        # Update topic distribution (exponential moving average)
        if "topic_distribution" in aggregated_delta:
            current_topics = updated.get("topic_distribution", {})
            new_topics = aggregated_delta["topic_distribution"]
            alpha = clip  # Learning rate = clip value
            merged = dict(current_topics)
            for topic, weight in new_topics.items():
                old = merged.get(topic, 0.0)
                merged[topic] = old * (1 - alpha) + weight * alpha
            updated["topic_distribution"] = merged

        updated["last_round"] = aggregated_delta.get("round", 0)
        return updated

    def advance_round(self) -> int:
        """Advance to the next federated round. Returns new round number."""
        self._round_counter += 1
        return self._round_counter
