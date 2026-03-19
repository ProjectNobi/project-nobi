"""
Project Nobi — Privacy-Preserving Validator Scoring (Phase C)

Wraps the validator's scoring pipeline with differential privacy.
Ensures no single user's interactions can be reverse-engineered
from the published weights.

Design:
- Each miner's raw score is noised before weight-setting.
- Privacy budget is tracked per scoring round.
- When budget is exhausted, scoring refuses to proceed (fail-safe).
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from nobi.privacy.config import PRIVACY_CONFIG
from nobi.privacy.differential import DifferentialPrivacyEngine, PrivacyAccountant
from nobi.privacy.audit import PrivacyAuditLogger


class PrivateScorer:
    """
    Privacy-preserving scorer for the validator.

    Wraps existing scoring by adding calibrated DP noise to individual
    miner scores before they are used for weight-setting on-chain.
    """

    def __init__(
        self,
        epsilon: float = None,
        sensitivity: float = None,
        total_budget: float = None,
        audit_logger: Optional[PrivacyAuditLogger] = None,
    ):
        """
        Args:
            epsilon: Per-round privacy parameter.
            sensitivity: Score sensitivity (max score change from one user).
            total_budget: Total privacy budget across all rounds.
            audit_logger: Optional audit logger for compliance.
        """
        self.epsilon = epsilon or PRIVACY_CONFIG["epsilon"]
        self.sensitivity = sensitivity or PRIVACY_CONFIG["max_signal_norm"]
        self.dp_engine = DifferentialPrivacyEngine(
            epsilon=self.epsilon, sensitivity=self.sensitivity
        )
        self.accountant = PrivacyAccountant(
            total_budget=total_budget or PRIVACY_CONFIG["privacy_budget_total"]
        )
        self.audit_logger = audit_logger
        self._round: int = 0

    def score_miners(
        self, raw_scores: Dict[str, float], epsilon: float = None
    ) -> Optional[Dict[str, float]]:
        """
        Apply differential privacy to miner scores.

        Each score is clipped and noised independently.
        The privacy budget is consumed for this round.

        Args:
            raw_scores: Dict mapping miner_uid → raw_score.
            epsilon: Privacy parameter for this round. Defaults to self.epsilon.

        Returns:
            Dict mapping miner_uid → noised_score, or None if budget exhausted.
        """
        eps = epsilon or self.epsilon

        # Check budget
        if not self.accountant.can_afford(eps):
            if self.audit_logger:
                self.audit_logger.log_data_access(
                    "system", "score_miners_rejected", "budget_exhausted"
                )
            return None

        # Consume budget
        self.accountant.consume(eps, f"score_miners_round_{self._round}")

        noised_scores = {}
        for miner_uid, raw_score in raw_scores.items():
            noised = self.dp_engine.clip_and_noise(
                raw_score, sensitivity=self.sensitivity, epsilon=eps
            )
            noised_scores[miner_uid] = noised

        # Audit logging
        if self.audit_logger:
            self.audit_logger.log_noise_addition(
                epsilon=eps,
                delta=PRIVACY_CONFIG["delta"],
                mechanism=PRIVACY_CONFIG["noise_mechanism"],
            )
            self.audit_logger.log_aggregation(
                num_signals=len(raw_scores), round_id=self._round
            )

        self._round += 1
        return noised_scores

    def normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize noised scores to [0, 1] range for weight-setting.

        Args:
            scores: Dict mapping miner_uid → noised_score.

        Returns:
            Normalized scores in [0, 1].
        """
        if not scores:
            return {}

        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)
        spread = max_val - min_val

        if spread < 1e-10:
            # All scores are essentially equal
            return {uid: 0.5 for uid in scores}

        return {uid: (v - min_val) / spread for uid, v in scores.items()}

    @property
    def budget_remaining(self) -> float:
        """Remaining privacy budget."""
        return self.accountant.remaining

    @property
    def is_budget_exhausted(self) -> bool:
        """Whether the privacy budget is exhausted."""
        return self.accountant.is_exhausted

    @property
    def current_round(self) -> int:
        """Current scoring round number."""
        return self._round
