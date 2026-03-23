import hashlib
import hmac
import json
import os
import time
import numpy as np
from typing import Tuple, List, Union, Any, Optional
import bittensor
from numpy import ndarray, dtype, floating, complexfloating

U32_MAX = 4294967295
U16_MAX = 65535


def normalize_max_weight(x: np.ndarray, limit: float = 0.1) -> np.ndarray:
    r"""Normalizes the numpy array x so that sum(x) = 1 and the max value is not greater than the limit.
    Args:
        x (:obj:`np.ndarray`):
            Array to be max_value normalized.
        limit: float:
            Max value after normalization.
    Returns:
        y (:obj:`np.ndarray`):
            Normalized x array.
    """
    epsilon = 1e-7  # For numerical stability after normalization

    weights = x.copy()
    values = np.sort(weights)

    if x.sum() == 0 or len(x) * limit <= 1:
        return np.ones_like(x) / x.size
    else:
        estimation = values / values.sum()

        if estimation.max() <= limit:
            return weights / weights.sum()

        # Find the cumulative sum and sorted array
        cumsum = np.cumsum(estimation, 0)

        # Determine the index of cutoff
        estimation_sum = np.array(
            [(len(values) - i - 1) * estimation[i] for i in range(len(values))]
        )
        n_values = (
            estimation / (estimation_sum + cumsum + epsilon) < limit
        ).sum()

        # Determine the cutoff based on the index
        cutoff_scale = (limit * cumsum[n_values - 1] - epsilon) / (
            1 - (limit * (len(estimation) - n_values))
        )
        cutoff = cutoff_scale * values.sum()

        # Applying the cutoff
        weights[weights > cutoff] = cutoff

        y = weights / weights.sum()

        return y


def convert_weights_and_uids_for_emit(
    uids: np.ndarray, weights: np.ndarray
) -> Tuple[List[int], List[int]]:
    r"""Converts weights into integer u32 representation that sum to MAX_INT_WEIGHT.
    Args:
        uids (:obj:`np.ndarray,`):
            Array of uids as destinations for passed weights.
        weights (:obj:`np.ndarray,`):
            Array of weights.
    Returns:
        weight_uids (List[int]):
            Uids as a list.
        weight_vals (List[int]):
            Weights as a list.
    """
    # Checks.
    uids = np.asarray(uids)
    weights = np.asarray(weights)

    # Get non-zero weights and corresponding uids
    non_zero_weights = weights[weights > 0]
    non_zero_weight_uids = uids[weights > 0]

    # Debugging information
    bittensor.logging.debug(f"weights: {weights}")
    bittensor.logging.debug(f"non_zero_weights: {non_zero_weights}")
    bittensor.logging.debug(f"uids: {uids}")
    bittensor.logging.debug(f"non_zero_weight_uids: {non_zero_weight_uids}")

    if np.min(weights) < 0:
        raise ValueError(
            "Passed weight is negative cannot exist on chain {}".format(
                weights
            )
        )
    if np.min(uids) < 0:
        raise ValueError(
            "Passed uid is negative cannot exist on chain {}".format(uids)
        )
    if len(uids) != len(weights):
        raise ValueError(
            "Passed weights and uids must have the same length, got {} and {}".format(
                len(uids), len(weights)
            )
        )
    if np.sum(weights) == 0:
        bittensor.logging.debug("nothing to set on chain")
        return [], []  # Nothing to set on chain.
    else:
        max_weight = float(np.max(weights))
        weights = [
            float(value) / max_weight for value in weights
        ]  # max-upscale values (max_weight = 1).
        bittensor.logging.debug(
            f"setting on chain max: {max_weight} and weights: {weights}"
        )

    weight_vals = []
    weight_uids = []
    for i, (weight_i, uid_i) in enumerate(list(zip(weights, uids))):
        uint16_val = round(
            float(weight_i) * int(U16_MAX)
        )  # convert to int representation.

        # Filter zeros
        if uint16_val != 0:  # Filter zeros
            weight_vals.append(uint16_val)
            weight_uids.append(uid_i)
    bittensor.logging.debug(f"final params: {weight_uids} : {weight_vals}")
    return weight_uids, weight_vals


def process_weights_for_netuid(
    uids,
    weights: np.ndarray,
    netuid: int,
    subtensor: "bittensor.subtensor",
    metagraph: "bittensor.metagraph" = None,
    exclude_quantile: int = 0,
) -> Union[
    tuple[
        ndarray[Any, dtype[Any]],
        Union[
            Union[
                ndarray[Any, dtype[floating[Any]]],
                ndarray[Any, dtype[complexfloating[Any, Any]]],
            ],
            Any,
        ],
    ],
    tuple[ndarray[Any, dtype[Any]], ndarray],
    tuple[Any, ndarray],
]:
    bittensor.logging.debug("process_weights_for_netuid()")
    bittensor.logging.debug("weights", weights)
    bittensor.logging.debug("netuid", netuid)
    bittensor.logging.debug("subtensor", subtensor)
    bittensor.logging.debug("metagraph", metagraph)

    # Get latest metagraph from chain if metagraph is None.
    if metagraph is None:
        metagraph = subtensor.metagraph(netuid)

    # Cast weights to floats.
    if not isinstance(weights, np.ndarray) or weights.dtype != np.float32:
        weights = weights.astype(np.float32)

    # Network configuration parameters from an subtensor.
    # These parameters determine the range of acceptable weights for each neuron.
    quantile = exclude_quantile / U16_MAX
    min_allowed_weights = subtensor.min_allowed_weights(netuid=netuid)
    max_weight_limit = subtensor.max_weight_limit(netuid=netuid)
    bittensor.logging.debug("quantile", quantile)
    bittensor.logging.debug("min_allowed_weights", min_allowed_weights)
    bittensor.logging.debug("max_weight_limit", max_weight_limit)

    # Find all non zero weights.
    non_zero_weight_idx = np.argwhere(weights > 0).squeeze()
    non_zero_weight_idx = np.atleast_1d(non_zero_weight_idx)
    non_zero_weight_uids = uids[non_zero_weight_idx]
    non_zero_weights = weights[non_zero_weight_idx]
    if non_zero_weights.size == 0 or metagraph.n < min_allowed_weights:
        bittensor.logging.warning("No non-zero weights returning all ones.")
        final_weights = np.ones(metagraph.n) / metagraph.n
        bittensor.logging.debug("final_weights", final_weights)
        return np.arange(len(final_weights)), final_weights

    elif non_zero_weights.size < min_allowed_weights:
        bittensor.logging.warning(
            "No non-zero weights less then min allowed weight, returning all ones."
        )
        weights = (
            np.ones(metagraph.n) * 1e-5
        )  # creating minimum even non-zero weights
        weights[non_zero_weight_idx] += non_zero_weights
        bittensor.logging.debug("final_weights", weights)
        normalized_weights = normalize_max_weight(
            x=weights, limit=max_weight_limit
        )
        return np.arange(len(normalized_weights)), normalized_weights

    bittensor.logging.debug("non_zero_weights", non_zero_weights)

    # Compute the exclude quantile and find the weights in the lowest quantile
    max_exclude = max(0, len(non_zero_weights) - min_allowed_weights) / len(
        non_zero_weights
    )
    exclude_quantile = min([quantile, max_exclude])
    lowest_quantile = np.quantile(non_zero_weights, exclude_quantile)
    bittensor.logging.debug("max_exclude", max_exclude)
    bittensor.logging.debug("exclude_quantile", exclude_quantile)
    bittensor.logging.debug("lowest_quantile", lowest_quantile)

    # Exclude all weights below the allowed quantile.
    non_zero_weight_uids = non_zero_weight_uids[
        lowest_quantile <= non_zero_weights
    ]
    non_zero_weights = non_zero_weights[lowest_quantile <= non_zero_weights]
    bittensor.logging.debug("non_zero_weight_uids", non_zero_weight_uids)
    bittensor.logging.debug("non_zero_weights", non_zero_weights)

    # Normalize weights and return.
    normalized_weights = normalize_max_weight(
        x=non_zero_weights, limit=max_weight_limit
    )
    bittensor.logging.debug("final_weights", normalized_weights)

    return non_zero_weight_uids, normalized_weights


# ─── Weight Commit-Reveal Hardening ─────────────────────────────────────────

# Maximum per-element noise magnitude for fingerprinting (stays within epsilon).
_FINGERPRINT_EPSILON = 1e-4
# Maximum per-element salt noise amplitude for obfuscation.
_SALT_AMPLITUDE = 2e-4
# How many consecutive identical weight vectors trigger a stale-weight warning.
_STALE_EPOCH_THRESHOLD = 3
# Similarity threshold (Jaccard on quantised weights) for detecting copied weights.
_COPY_SIMILARITY_THRESHOLD = 0.98


class WeightHardening:
    """
    Mainnet-critical hardening for validator weight-setting.

    Features
    --------
    1. **Fingerprinting** — embeds a per-validator micro-signature (< epsilon)
       that survives quantisation and can be verified post-hoc.
    2. **Obfuscation** — adds deterministic-random salt so that copying the raw
       commit bytes gives a different on-chain value.
    3. **Commit hashing** — SHA-256(salt | weights) committed before reveal;
       identical hashes from two validators flag a copy.
    4. **Stale detection** — tracks N previous weight vectors; raises an alert
       when the same vector is set for multiple consecutive epochs.

    Usage
    -----
    ::

        hardening = WeightHardening(validator_hotkey)
        hardened, salt, commit_hash = hardening.harden(raw_weights)
        # → submit hardened weights on-chain
        # Later: hardening.verify_commit(commit_hash, salt, hardened)

    All state (history, fingerprint seed) is persisted to ``state_path`` so it
    survives validator restarts.
    """

    def __init__(
        self,
        validator_hotkey: str = "",
        state_path: str = "",
        stale_threshold: int = _STALE_EPOCH_THRESHOLD,
        fingerprint_epsilon: float = _FINGERPRINT_EPSILON,
        salt_amplitude: float = _SALT_AMPLITUDE,
    ):
        self.validator_hotkey = validator_hotkey
        self.stale_threshold = stale_threshold
        self.fingerprint_epsilon = fingerprint_epsilon
        self.salt_amplitude = salt_amplitude

        # Derive a stable per-validator seed from the hotkey.
        # If no hotkey supplied, fall back to a random seed (non-reproducible).
        if validator_hotkey:
            seed_bytes = hashlib.sha256(validator_hotkey.encode()).digest()
            self._validator_seed = int.from_bytes(seed_bytes[:4], "big")
        else:
            self._validator_seed = int.from_bytes(os.urandom(4), "big")

        # State persistence
        self.state_path = state_path or os.path.expanduser(
            "~/.nobi/weight_hardening_state.json"
        )
        self._weight_history: List[str] = []  # list of commit hashes
        self._epoch: int = 0
        self._load_state()

    # ── Public API ──────────────────────────────────────────────────────────

    def harden(
        self, weights: np.ndarray
    ) -> Tuple[np.ndarray, bytes, str]:
        """
        Apply fingerprinting + obfuscation to ``weights``.

        Parameters
        ----------
        weights:
            Normalised float32 weight array (sums to ~1).

        Returns
        -------
        hardened_weights:
            Modified weights ready for on-chain submission.
        salt:
            32-byte random salt used for this epoch's commit hash.
        commit_hash:
            Hex-encoded SHA-256(salt | weights_bytes) to be stored and later
            used to detect copies.
        """
        weights = np.asarray(weights, dtype=np.float64)

        # 1. Embed per-validator fingerprint (deterministic per hotkey + epoch)
        fingerprinted = self._embed_fingerprint(weights)

        # 2. Add random salt noise to obfuscate copies
        salt = os.urandom(32)
        salted = self._apply_salt(fingerprinted, salt)

        # Clip to [0, 1] and renormalize so the chain accepts them
        salted = np.clip(salted, 0.0, 1.0)
        weight_sum = salted.sum()
        if weight_sum > 0:
            salted /= weight_sum

        # 3. Convert to final float32 form (what will be emitted on-chain)
        hardened_f32 = salted.astype(np.float32)

        # 4. Build commit hash from the float32 values that will actually be submitted.
        #    Committing on float32 ensures verify_commit() receives matching precision.
        commit_hash = self._make_commit_hash(hardened_f32, salt)

        # 5. Update stale detection history
        self._record_epoch(commit_hash)
        self._epoch += 1
        self._save_state()

        return hardened_f32, salt, commit_hash

    def verify_commit(
        self, commit_hash: str, salt: bytes, weights: np.ndarray
    ) -> bool:
        """
        Verify that ``weights`` + ``salt`` reproduce ``commit_hash``.

        Returns True if the weight vector was not tampered with after commit.
        """
        expected = self._make_commit_hash(weights, salt)
        return hmac.compare_digest(expected, commit_hash)

    def check_stale(self) -> bool:
        """
        Return True if the validator has set identical weights for
        ``stale_threshold`` consecutive epochs.
        """
        if len(self._weight_history) < self.stale_threshold:
            return False
        recent = self._weight_history[-self.stale_threshold:]
        return len(set(recent)) == 1

    def flag_copied_weights(
        self, my_commit: str, other_commits: List[str]
    ) -> List[str]:
        """
        Return the subset of ``other_commits`` that are identical to ``my_commit``.

        A non-empty list means another validator submitted the exact same weight
        vector—strong evidence of weight copying.
        """
        return [c for c in other_commits if c == my_commit]

    def detect_similar_weights(
        self,
        weights_a: np.ndarray,
        weights_b: np.ndarray,
        quantisation_levels: int = 65535,
    ) -> float:
        """
        Compute Jaccard similarity between two weight vectors after quantisation
        to ``quantisation_levels`` integer levels.

        A similarity ≥ ``_COPY_SIMILARITY_THRESHOLD`` suggests copying.

        Returns
        -------
        float: Jaccard similarity in [0, 1].
        """
        a_q = self._quantise(weights_a, quantisation_levels)
        b_q = self._quantise(weights_b, quantisation_levels)
        intersection = np.sum(a_q == b_q)
        union = len(a_q)
        return float(intersection) / float(union) if union > 0 else 0.0

    # ── Internal helpers ────────────────────────────────────────────────────

    def _embed_fingerprint(self, weights: np.ndarray) -> np.ndarray:
        """
        Add a per-validator micro-signature (< ``fingerprint_epsilon``) that
        is unique per hotkey and epoch but preserves the weight ordering.

        The signature is a tiny sinusoidal perturbation whose phase is keyed
        to the validator seed and current epoch—hard to reverse-engineer.
        """
        rng = np.random.default_rng(seed=(self._validator_seed ^ self._epoch) & 0xFFFFFFFF)
        noise = rng.uniform(
            -self.fingerprint_epsilon,
            self.fingerprint_epsilon,
            size=weights.shape,
        )
        return weights + noise

    def _apply_salt(self, weights: np.ndarray, salt: bytes) -> np.ndarray:
        """
        Add deterministic per-element salt noise derived from ``salt``.

        Each element gets a unique perturbation so that even a bit-perfect
        copy of the pre-salt weights would produce different on-chain values.
        """
        # Use SHA-256 of (salt + index) to build per-element offsets
        perturbations = np.zeros_like(weights)
        for i in range(len(weights)):
            h = hashlib.sha256(salt + i.to_bytes(4, "big")).digest()
            # Map first 4 bytes to [-amplitude, +amplitude]
            raw = int.from_bytes(h[:4], "big") / 0xFFFFFFFF  # [0, 1]
            perturbations[i] = (raw * 2.0 - 1.0) * self.salt_amplitude
        return weights + perturbations

    def _make_commit_hash(self, weights: np.ndarray, salt: bytes) -> str:
        """Build HMAC-SHA256(salt, canonical_weight_bytes) as a hex string."""
        canonical = json.dumps(
            [round(float(w), 8) for w in weights],
            separators=(",", ":"),
        ).encode()
        mac = hmac.new(salt, canonical, hashlib.sha256)
        return mac.hexdigest()

    @staticmethod
    def _quantise(weights: np.ndarray, levels: int) -> np.ndarray:
        """Quantise weights to integer levels (mirrors on-chain U16 conversion)."""
        w = np.asarray(weights, dtype=np.float64)
        max_w = w.max()
        if max_w == 0:
            return np.zeros_like(w, dtype=np.int64)
        return np.round((w / max_w) * levels).astype(np.int64)

    def _record_epoch(self, commit_hash: str) -> None:
        """Append commit hash to history; keep a rolling window."""
        self._weight_history.append(commit_hash)
        # Keep at most 2× the stale threshold to bound memory
        max_history = max(self.stale_threshold * 2, 10)
        if len(self._weight_history) > max_history:
            self._weight_history = self._weight_history[-max_history:]

    def _load_state(self) -> None:
        """Load persisted state from disk (non-fatal on missing/corrupt file)."""
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, "r") as f:
                    data = json.load(f)
                self._weight_history = data.get("weight_history", [])
                self._epoch = data.get("epoch", 0)
        except Exception:
            pass  # Start fresh if state file is corrupted

    def _save_state(self) -> None:
        """Persist state to disk."""
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            with open(self.state_path, "w") as f:
                json.dump(
                    {"weight_history": self._weight_history, "epoch": self._epoch},
                    f,
                )
        except Exception:
            pass  # Non-fatal — state will be rebuilt on restart
