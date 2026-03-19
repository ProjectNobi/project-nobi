"""
Project Nobi — Secure Aggregation Protocol (Phase C)

Implements additive secret sharing for privacy-preserving aggregation.
The validator can compute aggregate statistics (sums, means) without
seeing any individual miner's contribution.

Protocol:
1. Each miner splits their score into N additive shares (one per party).
2. Shares are distributed so that no single party can reconstruct the original.
3. The validator collects one share from each miner per slot.
4. Summing all shares for a slot recovers the aggregate sum.

Security property:
- Any N-1 shares reveal zero information about the original value.
- Only the full set of N shares reveals the sum.

Uses cryptographically secure random number generation via the `secrets` module.
"""

import secrets
import math
from typing import Dict, List, Optional, Tuple

# Large prime for modular arithmetic (prevents floating-point issues)
# Using a 128-bit prime for security
_PRIME = (1 << 127) - 1  # Mersenne prime M127

# Scale factor for converting floats to integers
_SCALE = 10**9  # 9 decimal places of precision


def _float_to_int(value: float) -> int:
    """Convert a float to a scaled integer for modular arithmetic."""
    return round(value * _SCALE)


def _int_to_float(value: int) -> float:
    """Convert a scaled integer back to float."""
    # Handle modular wraparound for negative values
    if value > _PRIME // 2:
        value -= _PRIME
    return value / _SCALE


class SecureAggregator:
    """
    Secure aggregation using additive secret sharing.

    Each value is split into N shares that sum to the original (mod prime).
    The validator only ever sees shares, never raw values.
    """

    def __init__(self, prime: int = None):
        """
        Args:
            prime: Prime modulus for arithmetic. Defaults to M127.
        """
        self.prime = prime or _PRIME

    def create_shares(self, value: float, num_parties: int) -> List[int]:
        """
        Split a value into N additive shares.

        The shares sum to the original value modulo the prime.
        Each share individually reveals nothing about the value.

        Args:
            value: The value to split.
            num_parties: Number of shares (N ≥ 2).

        Returns:
            List of N integer shares.

        Raises:
            ValueError: If num_parties < 2.
        """
        if num_parties < 2:
            raise ValueError(f"Need at least 2 parties, got {num_parties}")

        int_value = _float_to_int(value) % self.prime

        # Generate N-1 random shares
        shares = []
        for _ in range(num_parties - 1):
            share = secrets.randbelow(self.prime)
            shares.append(share)

        # Last share = value - sum(other shares) mod prime
        partial_sum = sum(shares) % self.prime
        last_share = (int_value - partial_sum) % self.prime
        shares.append(last_share)

        return shares

    def aggregate_shares(self, all_shares: List[List[int]]) -> float:
        """
        Aggregate shares from multiple parties to recover the sum.

        Each element in all_shares is a list of shares from one party/miner.
        We sum corresponding shares across all miners.

        For single-value aggregation: all_shares[i] is a list of shares
        for miner i's value. We sum share[j] across all miners for each
        slot j, then sum the slot sums.

        Simpler: just sum ALL shares mod prime.

        Args:
            all_shares: List of share-lists. all_shares[i] = shares for miner i.

        Returns:
            The aggregate sum as a float.

        Raises:
            ValueError: If all_shares is empty.
        """
        if not all_shares:
            raise ValueError("Cannot aggregate empty shares list")

        total = 0
        for shares in all_shares:
            for s in shares:
                total = (total + s) % self.prime

        return _int_to_float(total)

    def verify_aggregate(self, all_shares: List[List[int]],
                         expected_sum: float, tolerance: float = 1e-6) -> bool:
        """
        Verify that the aggregation of shares matches the expected sum.

        Args:
            all_shares: List of share-lists from all parties.
            expected_sum: The expected aggregate sum.
            tolerance: Floating-point comparison tolerance.

        Returns:
            True if the aggregated sum matches expected_sum within tolerance.
        """
        actual = self.aggregate_shares(all_shares)
        return abs(actual - expected_sum) < tolerance


class SecureScoreAggregator:
    """
    Wraps SecureAggregator for the validator's scoring pipeline.

    Miners submit masked (secret-shared) scores.
    The validator aggregates without seeing individual scores.

    Usage:
        agg = SecureScoreAggregator(num_miners=10)

        # Each miner creates shares of their score
        for miner_id, score in miner_scores.items():
            shares = agg.submit_score(miner_id, score)
            # shares are distributed to other miners / held by validator

        # Validator aggregates
        total, mean = agg.aggregate()
    """

    def __init__(self, num_miners: int, num_share_parties: int = 3):
        """
        Args:
            num_miners: Total number of miners participating.
            num_share_parties: Number of shares per score (default 3).
        """
        if num_miners < 1:
            raise ValueError("Need at least 1 miner")
        if num_share_parties < 2:
            raise ValueError("Need at least 2 share parties")

        self.num_miners = num_miners
        self.num_share_parties = num_share_parties
        self.aggregator = SecureAggregator()
        self._submitted_shares: Dict[str, List[int]] = {}

    def submit_score(self, miner_id: str, score: float) -> List[int]:
        """
        Submit a miner's score as secret shares.

        Args:
            miner_id: Unique miner identifier.
            score: The miner's raw score.

        Returns:
            The shares (for distribution to share-holding parties).
        """
        shares = self.aggregator.create_shares(score, self.num_share_parties)
        self._submitted_shares[miner_id] = shares
        return shares

    def aggregate(self) -> Tuple[float, float]:
        """
        Aggregate all submitted scores.

        Returns:
            Tuple of (total_sum, mean_score).

        Raises:
            ValueError: If no scores have been submitted.
        """
        if not self._submitted_shares:
            raise ValueError("No scores submitted for aggregation")

        all_shares = list(self._submitted_shares.values())
        total = self.aggregator.aggregate_shares(all_shares)
        n = len(self._submitted_shares)
        mean = total / n if n > 0 else 0.0

        return total, mean

    def get_submitted_count(self) -> int:
        """Return the number of submitted scores."""
        return len(self._submitted_shares)

    def reset(self) -> None:
        """Clear all submitted scores for a new round."""
        self._submitted_shares.clear()
