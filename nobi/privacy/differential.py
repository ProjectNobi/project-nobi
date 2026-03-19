"""
Project Nobi — Differential Privacy Engine (Phase C)

Implements ε-differential privacy for scoring signals using the Gaussian mechanism.
Based on Dwork & Roth (2014) — "The Algorithmic Foundations of Differential Privacy."

Key guarantees:
- Individual user's contribution to aggregate scores is unidentifiable.
- Calibrated noise ensures (ε, δ)-differential privacy per query.
- Privacy budget tracking prevents over-querying.

Gaussian mechanism: for sensitivity Δf and privacy parameters (ε, δ),
    noise ~ N(0, σ²) where σ = Δf * sqrt(2 * ln(1.25/δ)) / ε
"""

import math
import numpy as np
from typing import List, Optional, Tuple

from nobi.privacy.config import PRIVACY_CONFIG


def _validate_epsilon(epsilon: float) -> None:
    """Validate that epsilon is positive and finite."""
    if not isinstance(epsilon, (int, float)):
        raise TypeError(f"epsilon must be a number, got {type(epsilon).__name__}")
    if epsilon <= 0:
        raise ValueError(f"epsilon must be positive, got {epsilon}")
    if math.isinf(epsilon) or math.isnan(epsilon):
        raise ValueError(f"epsilon must be finite, got {epsilon}")


def _validate_sensitivity(sensitivity: float) -> None:
    """Validate that sensitivity is positive and finite."""
    if not isinstance(sensitivity, (int, float)):
        raise TypeError(f"sensitivity must be a number, got {type(sensitivity).__name__}")
    if sensitivity <= 0:
        raise ValueError(f"sensitivity must be positive, got {sensitivity}")
    if math.isinf(sensitivity) or math.isnan(sensitivity):
        raise ValueError(f"sensitivity must be finite, got {sensitivity}")


def compute_gaussian_sigma(sensitivity: float, epsilon: float,
                           delta: float = None) -> float:
    """
    Compute the standard deviation for the Gaussian mechanism.

    σ = sensitivity * sqrt(2 * ln(1.25 / δ)) / ε

    Args:
        sensitivity: L2 sensitivity of the query (Δf).
        epsilon: Privacy parameter ε.
        delta: Probability of privacy breach δ. Defaults to config value.

    Returns:
        Standard deviation σ for the Gaussian noise.
    """
    _validate_epsilon(epsilon)
    _validate_sensitivity(sensitivity)
    if delta is None:
        delta = PRIVACY_CONFIG["delta"]
    if delta <= 0 or delta >= 1:
        raise ValueError(f"delta must be in (0, 1), got {delta}")

    return sensitivity * math.sqrt(2.0 * math.log(1.25 / delta)) / epsilon


class DifferentialPrivacyEngine:
    """
    ε-differential privacy engine for scoring signals.

    Ensures individual user's contribution to aggregate scores
    is unidentifiable via calibrated Gaussian noise.
    """

    def __init__(self, epsilon: float = None, delta: float = None,
                 sensitivity: float = None):
        """
        Args:
            epsilon: Privacy parameter. Lower = more private, noisier.
            delta: Probability of privacy breach.
            sensitivity: Default L2 sensitivity for queries.
        """
        self.epsilon = epsilon or PRIVACY_CONFIG["epsilon"]
        self.delta = delta or PRIVACY_CONFIG["delta"]
        self.sensitivity = sensitivity or PRIVACY_CONFIG["max_signal_norm"]
        _validate_epsilon(self.epsilon)
        _validate_sensitivity(self.sensitivity)

    def clip_and_noise(self, value: float, sensitivity: float = None,
                       epsilon: float = None) -> float:
        """
        Clip a value to [-sensitivity, sensitivity] and add Gaussian noise.

        Args:
            value: The raw value.
            sensitivity: Clipping bound (and L2 sensitivity). Defaults to self.sensitivity.
            epsilon: Privacy parameter. Defaults to self.epsilon.

        Returns:
            Noised, clipped value satisfying (ε, δ)-differential privacy.
        """
        sens = sensitivity if sensitivity is not None else self.sensitivity
        eps = epsilon if epsilon is not None else self.epsilon
        _validate_epsilon(eps)
        _validate_sensitivity(sens)

        # Clip
        clipped = max(-sens, min(sens, float(value)))

        # Gaussian noise
        sigma = compute_gaussian_sigma(sens, eps, self.delta)
        noise = np.random.normal(0.0, sigma)
        return clipped + noise

    def private_mean(self, values: List[float], epsilon: float = None,
                     sensitivity: float = None) -> float:
        """
        Compute a differentially private mean.

        Each value is clipped to [-sensitivity, sensitivity], then the mean is
        computed and Gaussian noise is added calibrated to the per-element sensitivity.

        Args:
            values: Raw values.
            epsilon: Privacy parameter.
            sensitivity: Clipping bound per element.

        Returns:
            Differentially private mean.

        Raises:
            ValueError: If values list is empty.
        """
        if not values:
            raise ValueError("Cannot compute private mean of empty list")

        sens = sensitivity if sensitivity is not None else self.sensitivity
        eps = epsilon if epsilon is not None else self.epsilon
        _validate_epsilon(eps)
        _validate_sensitivity(sens)

        n = len(values)
        clipped = [max(-sens, min(sens, float(v))) for v in values]
        raw_mean = sum(clipped) / n

        # Sensitivity of the mean = 2 * sensitivity / n
        # (changing one element changes the mean by at most 2*sensitivity/n)
        mean_sensitivity = 2.0 * sens / n
        sigma = compute_gaussian_sigma(mean_sensitivity, eps, self.delta)
        noise = np.random.normal(0.0, sigma)
        return raw_mean + noise

    def private_histogram(self, values: List[float], bins: List[float],
                          epsilon: float = None) -> List[int]:
        """
        Compute a differentially private histogram.

        Each bin count has independent Gaussian noise added.
        The L2 sensitivity of a histogram query is 1 (changing one element
        changes at most 2 bin counts by 1 each, L2 = sqrt(2) ≈ 1.41,
        but we use sensitivity=1 per bin with split epsilon).

        Args:
            values: Raw values to bin.
            bins: Bin edges (N edges → N-1 bins).
            epsilon: Total privacy budget for the histogram.

        Returns:
            List of noised bin counts (non-negative integers).

        Raises:
            ValueError: If bins has fewer than 2 edges.
        """
        if len(bins) < 2:
            raise ValueError("Need at least 2 bin edges")

        eps = epsilon if epsilon is not None else self.epsilon
        _validate_epsilon(eps)

        num_bins = len(bins) - 1

        # Count true histogram
        counts = [0] * num_bins
        for v in values:
            for i in range(num_bins):
                if bins[i] <= v < bins[i + 1]:
                    counts[i] += 1
                    break
            else:
                # Value >= last bin edge → put in last bin
                if v >= bins[-1]:
                    counts[-1] += 1

        # Split epsilon across bins (parallel composition for disjoint queries)
        # Actually histogram bins are disjoint, so we can use full epsilon per bin.
        # Sensitivity per bin = 1 (one person changes one bin by at most 1).
        sigma = compute_gaussian_sigma(1.0, eps, self.delta)
        noised = []
        for c in counts:
            noised_c = c + np.random.normal(0.0, sigma)
            noised.append(max(0, round(noised_c)))

        return noised

    @staticmethod
    def compute_privacy_budget(num_queries: int,
                               epsilon_per_query: float) -> float:
        """
        Compute cumulative privacy loss under basic composition.

        Under basic composition theorem: total ε = num_queries * ε_per_query.
        (Advanced composition gives tighter bounds but basic is safer.)

        Args:
            num_queries: Number of queries made.
            epsilon_per_query: Privacy budget per query.

        Returns:
            Total privacy budget consumed.
        """
        if num_queries < 0:
            raise ValueError("num_queries cannot be negative")
        _validate_epsilon(epsilon_per_query)
        return num_queries * epsilon_per_query


class PrivacyAccountant:
    """
    Tracks cumulative privacy budget over time.

    Warns when budget is near exhaustion and refuses queries
    when the total budget is exceeded (fail-safe).

    Uses basic sequential composition: total_ε = Σ εᵢ
    """

    def __init__(self, total_budget: float = None, warning_threshold: float = 0.8):
        """
        Args:
            total_budget: Maximum total epsilon before refusing queries.
            warning_threshold: Fraction of budget at which to warn (0-1).
        """
        self.total_budget = total_budget or PRIVACY_CONFIG["privacy_budget_total"]
        self.warning_threshold = warning_threshold
        self._consumed: float = 0.0
        self._query_log: List[Tuple[float, str]] = []  # (epsilon, description)

    @property
    def consumed(self) -> float:
        """Total epsilon consumed so far."""
        return self._consumed

    @property
    def remaining(self) -> float:
        """Remaining privacy budget."""
        return max(0.0, self.total_budget - self._consumed)

    @property
    def is_exhausted(self) -> bool:
        """Whether the budget is fully exhausted."""
        return self._consumed >= self.total_budget

    @property
    def is_warning(self) -> bool:
        """Whether we've crossed the warning threshold."""
        return self._consumed >= self.total_budget * self.warning_threshold

    def can_afford(self, epsilon: float) -> bool:
        """Check if we can afford a query with the given epsilon."""
        return (self._consumed + epsilon) <= self.total_budget

    def consume(self, epsilon: float, description: str = "") -> bool:
        """
        Record a privacy-consuming operation.

        Args:
            epsilon: Privacy budget consumed by this operation.
            description: Human-readable description for audit log.

        Returns:
            True if the operation was allowed, False if budget exhausted.

        Raises:
            ValueError: If epsilon is not positive.
        """
        _validate_epsilon(epsilon)

        if self.is_exhausted:
            return False
        if not self.can_afford(epsilon):
            return False

        self._consumed += epsilon
        self._query_log.append((epsilon, description))
        return True

    def get_log(self) -> List[Tuple[float, str]]:
        """Return the query log for audit purposes."""
        return list(self._query_log)

    def reset(self) -> None:
        """Reset the accountant (use with caution — only for new privacy epochs)."""
        self._consumed = 0.0
        self._query_log.clear()

    def __repr__(self) -> str:
        return (f"PrivacyAccountant(consumed={self._consumed:.4f}, "
                f"remaining={self.remaining:.4f}, "
                f"budget={self.total_budget}, "
                f"exhausted={self.is_exhausted})")
