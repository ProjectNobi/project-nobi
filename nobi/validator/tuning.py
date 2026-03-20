# Project Nobi — Scoring Weight Tuner
# Dragon Lord 🐉 — Task 5: Miner Scoring Weight Tuning
#
# Tracks score distributions, detects gaming, suggests optimal weights,
# and provides leaderboard/analytics for validator operators.

import os
import sqlite3
import time
import math
import statistics
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


class ScoringTuner:
    """
    Analyzes miner scoring patterns and suggests weight optimizations.
    
    Tracks per-round scores (quality, memory, reliability, final) in a
    SQLite database and provides analytics:
    - Score distribution analysis
    - Differentiation detection (are miners actually being separated?)
    - Weight suggestion based on component variance
    - Gaming detection (score spikes, identical responses, copying)
    - Leaderboard
    """

    # Default scoring weights (must match reward.py)
    DEFAULT_WEIGHTS = {
        "single": {"quality": 0.90, "reliability": 0.10},
        "multi_turn": {"quality": 0.50, "memory": 0.40, "reliability": 0.10},
    }

    # Thresholds
    LOW_DIFFERENTIATION_STD = 0.05   # Below this, scores are too similar
    SPIKE_THRESHOLD = 2.5            # Z-score for spike detection
    SIMILARITY_THRESHOLD = 0.02      # Scores closer than this are "identical"
    MIN_ROUNDS_FOR_ANALYSIS = 5      # Need at least this many rounds

    def __init__(self, db_path: str = "~/.nobi/scoring_history.db"):
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the scoring history database."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid INTEGER NOT NULL,
                    round_type TEXT NOT NULL,
                    quality REAL NOT NULL,
                    memory REAL NOT NULL DEFAULT 0.0,
                    reliability REAL NOT NULL,
                    final REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    round_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scores_uid ON scores(uid)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scores_timestamp ON scores(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scores_round_id ON scores(round_id)
            """)
            conn.commit()
        finally:
            conn.close()

    def record_score(
        self,
        uid: int,
        round_type: str,
        quality: float,
        memory: float,
        reliability: float,
        final: float,
        round_id: str = None,
    ):
        """Record a score for a miner in a given round."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO scores (uid, round_type, quality, memory, reliability, final, timestamp, round_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, round_type, quality, memory, reliability, final, time.time(), round_id),
            )
            conn.commit()
        finally:
            conn.close()

    def record_scores_batch(self, records: List[Dict]):
        """Record multiple scores in a single transaction."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT INTO scores (uid, round_type, quality, memory, reliability, final, timestamp, round_id)
                   VALUES (:uid, :round_type, :quality, :memory, :reliability, :final, :timestamp, :round_id)""",
                [
                    {
                        "uid": r["uid"],
                        "round_type": r["round_type"],
                        "quality": r["quality"],
                        "memory": r.get("memory", 0.0),
                        "reliability": r["reliability"],
                        "final": r["final"],
                        "timestamp": r.get("timestamp", time.time()),
                        "round_id": r.get("round_id"),
                    }
                    for r in records
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def get_score_distribution(self, last_n_rounds: int = 100) -> dict:
        """
        Get score distribution statistics for recent rounds.
        
        Returns:
            dict with keys: count, mean, std, min, max, median, p25, p75
            for each score component (quality, memory, reliability, final).
        """
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT quality, memory, reliability, final FROM scores
                   ORDER BY timestamp DESC LIMIT ?""",
                (last_n_rounds,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {
                "count": 0,
                "quality": self._empty_stats(),
                "memory": self._empty_stats(),
                "reliability": self._empty_stats(),
                "final": self._empty_stats(),
            }

        quality_vals = [r[0] for r in rows]
        memory_vals = [r[1] for r in rows]
        reliability_vals = [r[2] for r in rows]
        final_vals = [r[3] for r in rows]

        return {
            "count": len(rows),
            "quality": self._compute_stats(quality_vals),
            "memory": self._compute_stats(memory_vals),
            "reliability": self._compute_stats(reliability_vals),
            "final": self._compute_stats(final_vals),
        }

    def analyze_differentiation(self) -> dict:
        """
        Analyze whether miners are actually being differentiated by scores.
        
        Returns:
            dict with:
            - is_differentiated: bool — True if scoring separates miners well
            - final_std: float — standard deviation of final scores
            - component_stds: dict — std of each component
            - dominant_component: str or None — which component dominates variance
            - recommendation: str — human-readable suggestion
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get per-miner average final scores
            rows = conn.execute(
                """SELECT uid, AVG(final) as avg_final, AVG(quality) as avg_q,
                          AVG(memory) as avg_m, AVG(reliability) as avg_r,
                          COUNT(*) as cnt
                   FROM scores
                   GROUP BY uid
                   HAVING cnt >= 2"""
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < 2:
            return {
                "is_differentiated": False,
                "final_std": 0.0,
                "component_stds": {},
                "dominant_component": None,
                "recommendation": "Not enough data (need scores from at least 2 miners with 2+ rounds each).",
                "miner_count": len(rows),
            }

        final_avgs = [r[1] for r in rows]
        quality_avgs = [r[2] for r in rows]
        memory_avgs = [r[3] for r in rows]
        reliability_avgs = [r[4] for r in rows]

        final_std = statistics.stdev(final_avgs) if len(final_avgs) > 1 else 0.0
        component_stds = {
            "quality": statistics.stdev(quality_avgs) if len(quality_avgs) > 1 else 0.0,
            "memory": statistics.stdev(memory_avgs) if len(memory_avgs) > 1 else 0.0,
            "reliability": statistics.stdev(reliability_avgs) if len(reliability_avgs) > 1 else 0.0,
        }

        # Find dominant component
        dominant = max(component_stds, key=component_stds.get) if any(v > 0 for v in component_stds.values()) else None

        is_diff = final_std > self.LOW_DIFFERENTIATION_STD

        # Build recommendation
        if not is_diff:
            rec = (
                f"Poor differentiation (std={final_std:.4f} < {self.LOW_DIFFERENTIATION_STD}). "
                "Miners score too similarly. Consider increasing weight on the most variable component "
                f"({dominant}) or adding new scoring dimensions."
            )
        elif dominant and component_stds[dominant] > 3 * min(v for v in component_stds.values() if v > 0):
            rec = (
                f"Scoring is dominated by '{dominant}' (std={component_stds[dominant]:.4f}). "
                "Consider rebalancing weights to include other dimensions."
            )
        else:
            rec = f"Good differentiation (std={final_std:.4f}). Weights are balanced."

        return {
            "is_differentiated": is_diff,
            "final_std": final_std,
            "component_stds": component_stds,
            "dominant_component": dominant,
            "recommendation": rec,
            "miner_count": len(rows),
        }

    def suggest_weights(self) -> dict:
        """
        Suggest optimal scoring weights based on observed score data.
        
        Logic:
        - Components with higher variance contribute more to differentiation
        - Weights should be proportional to each component's ability to separate miners
        - Constrained: weights sum to 1.0, each weight >= 0.05
        
        Returns:
            dict with suggested weights per round_type and reasoning.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT uid, round_type, AVG(quality), AVG(memory), AVG(reliability)
                   FROM scores GROUP BY uid, round_type"""
            ).fetchall()
        finally:
            conn.close()

        if len(rows) < 3:
            return {
                "suggested": self.DEFAULT_WEIGHTS.copy(),
                "reasoning": "Not enough data to suggest weights. Using defaults.",
                "data_points": len(rows),
            }

        # Group by round_type
        by_type = defaultdict(lambda: {"quality": [], "memory": [], "reliability": []})
        for uid, rt, q, m, r in rows:
            by_type[rt]["quality"].append(q)
            by_type[rt]["memory"].append(m)
            by_type[rt]["reliability"].append(r)

        suggested = {}
        reasoning = []

        for rt, components in by_type.items():
            variances = {}
            for comp, vals in components.items():
                if len(vals) > 1:
                    variances[comp] = statistics.variance(vals)
                else:
                    variances[comp] = 0.0

            # Skip memory for single-turn
            if rt == "single":
                variances.pop("memory", None)

            total_var = sum(variances.values())
            if total_var == 0:
                suggested[rt] = self.DEFAULT_WEIGHTS.get(rt, {"quality": 0.9, "reliability": 0.1})
                reasoning.append(f"{rt}: No variance detected, using defaults.")
                continue

            # Proportional weights with minimum floor
            min_weight = 0.05
            raw_weights = {k: max(min_weight, v / total_var) for k, v in variances.items()}
            weight_sum = sum(raw_weights.values())
            normalized = {k: round(v / weight_sum, 2) for k, v in raw_weights.items()}

            # Fix rounding to sum to 1.0
            diff = round(1.0 - sum(normalized.values()), 2)
            if diff != 0:
                max_key = max(normalized, key=normalized.get)
                normalized[max_key] = round(normalized[max_key] + diff, 2)

            suggested[rt] = normalized
            var_str = ", ".join(f"{k}={v:.4f}" for k, v in variances.items())
            reasoning.append(f"{rt}: variances [{var_str}] → weights {normalized}")

        return {
            "suggested": suggested,
            "reasoning": "; ".join(reasoning),
            "data_points": len(rows),
        }

    def get_leaderboard(self, limit: int = 20) -> list:
        """
        Get top miners ranked by average final score.
        
        Returns:
            list of dicts with uid, avg_final, avg_quality, avg_memory,
            avg_reliability, round_count.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT uid, AVG(final) as avg_final, AVG(quality) as avg_q,
                          AVG(memory) as avg_m, AVG(reliability) as avg_r,
                          COUNT(*) as cnt
                   FROM scores
                   GROUP BY uid
                   ORDER BY avg_final DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "rank": i + 1,
                "uid": row[0],
                "avg_final": round(row[1], 4),
                "avg_quality": round(row[2], 4),
                "avg_memory": round(row[3], 4),
                "avg_reliability": round(row[4], 4),
                "round_count": row[5],
            }
            for i, row in enumerate(rows)
        ]

    def detect_gaming(self) -> list:
        """
        Detect suspicious scoring patterns that may indicate gaming.
        
        Checks:
        1. Score spikes — sudden jumps in a miner's score (z-score based)
        2. Identical scores — miners consistently scoring the exact same
        3. Perfect scores — miners with suspiciously perfect track records
        4. Score clustering — groups of miners with near-identical scores
        
        Returns:
            list of dicts with type, uid(s), details, severity.
        """
        alerts = []
        conn = sqlite3.connect(self.db_path)
        try:
            # 1. Score spikes per miner
            miners = conn.execute(
                "SELECT DISTINCT uid FROM scores"
            ).fetchall()

            for (uid,) in miners:
                scores = conn.execute(
                    "SELECT final, timestamp FROM scores WHERE uid = ? ORDER BY timestamp",
                    (uid,),
                ).fetchall()
                if len(scores) < self.MIN_ROUNDS_FOR_ANALYSIS:
                    continue

                finals = [s[0] for s in scores]
                mean = statistics.mean(finals)
                std = statistics.stdev(finals) if len(finals) > 1 else 0.0

                if std > 0:
                    for i, (score, ts) in enumerate(scores):
                        z = (score - mean) / std
                        if z > self.SPIKE_THRESHOLD:
                            alerts.append({
                                "type": "score_spike",
                                "uid": uid,
                                "details": f"Score {score:.4f} is {z:.1f} std devs above mean {mean:.4f}",
                                "severity": "high" if z > 3.5 else "medium",
                                "score": score,
                                "z_score": round(z, 2),
                            })

            # 2. Perfect scores
            for (uid,) in miners:
                row = conn.execute(
                    """SELECT AVG(final), COUNT(*), MIN(final), MAX(final) 
                       FROM scores WHERE uid = ?""",
                    (uid,),
                ).fetchone()
                avg, cnt, min_s, max_s = row
                if cnt >= self.MIN_ROUNDS_FOR_ANALYSIS and avg > 0.95 and min_s > 0.9:
                    alerts.append({
                        "type": "perfect_scores",
                        "uid": uid,
                        "details": f"Avg={avg:.4f}, min={min_s:.4f} over {cnt} rounds — suspiciously perfect",
                        "severity": "high",
                    })

            # 3. Score clustering — groups of miners with near-identical averages
            miner_avgs = conn.execute(
                """SELECT uid, AVG(final) as avg_f FROM scores
                   GROUP BY uid HAVING COUNT(*) >= 3
                   ORDER BY avg_f"""
            ).fetchall()

            if len(miner_avgs) >= 2:
                clusters = []
                current_cluster = [miner_avgs[0]]
                for i in range(1, len(miner_avgs)):
                    if abs(miner_avgs[i][1] - current_cluster[-1][1]) < self.SIMILARITY_THRESHOLD:
                        current_cluster.append(miner_avgs[i])
                    else:
                        if len(current_cluster) >= 3:
                            clusters.append(current_cluster)
                        current_cluster = [miner_avgs[i]]
                if len(current_cluster) >= 3:
                    clusters.append(current_cluster)

                for cluster in clusters:
                    uids = [c[0] for c in cluster]
                    avg_score = statistics.mean([c[1] for c in cluster])
                    alerts.append({
                        "type": "score_cluster",
                        "uids": uids,
                        "details": f"{len(uids)} miners clustered at avg score {avg_score:.4f}",
                        "severity": "medium",
                    })

        finally:
            conn.close()

        return alerts

    def get_miner_history(self, uid: int, limit: int = 50) -> list:
        """Get score history for a specific miner."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT round_type, quality, memory, reliability, final, timestamp
                   FROM scores WHERE uid = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (uid, limit),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "round_type": r[0],
                "quality": r[1],
                "memory": r[2],
                "reliability": r[3],
                "final": r[4],
                "timestamp": r[5],
            }
            for r in rows
        ]

    def get_round_scores(self, round_id: str) -> list:
        """Get all scores from a specific round."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT uid, round_type, quality, memory, reliability, final
                   FROM scores WHERE round_id = ?
                   ORDER BY final DESC""",
                (round_id,),
            ).fetchall()
        finally:
            conn.close()

        return [
            {"uid": r[0], "round_type": r[1], "quality": r[2],
             "memory": r[3], "reliability": r[4], "final": r[5]}
            for r in rows
        ]

    def cleanup_old_data(self, days: int = 30):
        """Remove score data older than N days."""
        cutoff = time.time() - (days * 86400)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM scores WHERE timestamp < ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()

    # --- Internal helpers ---

    @staticmethod
    def _compute_stats(values: list) -> dict:
        """Compute statistics for a list of values."""
        if not values:
            return ScoringTuner._empty_stats()
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "mean": round(statistics.mean(values), 4),
            "std": round(statistics.stdev(values), 4) if n > 1 else 0.0,
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "median": round(statistics.median(values), 4),
            "p25": round(sorted_vals[max(0, n // 4 - 1)], 4) if n >= 4 else round(sorted_vals[0], 4),
            "p75": round(sorted_vals[min(n - 1, 3 * n // 4)], 4) if n >= 4 else round(sorted_vals[-1], 4),
        }

    @staticmethod
    def _empty_stats() -> dict:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0,
                "median": 0.0, "p25": 0.0, "p75": 0.0}


# --- Response diversity and anti-gaming scoring functions ---

def check_response_diversity(responses: list, threshold: float = 0.85) -> list:
    """
    Check for near-identical responses across miners.
    
    Returns a list of (i, j, similarity) tuples where similarity > threshold.
    Uses character-level n-gram Jaccard similarity for efficiency.
    """
    if len(responses) < 2:
        return []

    duplicates = []
    # Pre-compute n-gram sets
    ngram_sets = [_char_ngrams(r, 3) for r in responses]

    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            if not ngram_sets[i] or not ngram_sets[j]:
                continue
            sim = _jaccard(ngram_sets[i], ngram_sets[j])
            if sim > threshold:
                duplicates.append((i, j, round(sim, 4)))

    return duplicates


def compute_diversity_penalties(responses: list, threshold: float = 0.85) -> list:
    """
    Compute per-response diversity penalty scores.
    
    Miners giving near-identical responses to others get penalized.
    Returns a list of penalty multipliers (1.0 = no penalty, 0.0 = full penalty).
    """
    n = len(responses)
    if n < 2:
        return [1.0] * n

    penalties = [1.0] * n
    duplicates = check_response_diversity(responses, threshold)

    # Count how many duplicates each response is involved in
    dup_counts = defaultdict(int)
    for i, j, sim in duplicates:
        dup_counts[i] += 1
        dup_counts[j] += 1

    for idx, count in dup_counts.items():
        # Penalty increases with number of duplicates
        # 1 duplicate = 0.7x, 2 = 0.5x, 3+ = 0.3x
        if count >= 3:
            penalties[idx] = 0.3
        elif count >= 2:
            penalties[idx] = 0.5
        else:
            penalties[idx] = 0.7

    return penalties


def normalize_length_score(response: str, base_score: float, optimal_range: tuple = (50, 1500)) -> float:
    """
    Apply length normalization to a score.
    
    Penalizes artificially long responses (padding) and very short responses.
    Optimal range is character count.
    
    Returns adjusted score.
    """
    if not response:
        return 0.0

    length = len(response.strip())
    min_len, max_len = optimal_range

    if length < 10:
        return base_score * 0.2  # Almost empty
    elif length < min_len:
        # Linearly scale up from 0.5 to 1.0
        factor = 0.5 + 0.5 * (length / min_len)
        return base_score * factor
    elif length <= max_len:
        return base_score  # Sweet spot
    else:
        # Gradually penalize excess length
        excess_ratio = (length - max_len) / max_len
        penalty = max(0.5, 1.0 - 0.2 * excess_ratio)
        return base_score * penalty


def score_confidence_calibration(response: str, is_correct: bool = True) -> float:
    """
    Score confidence calibration.
    
    Responses that express high certainty about incorrect information
    get penalized more than uncertain wrong answers.
    
    Returns a multiplier (0.5 to 1.0).
    """
    high_confidence_phrases = [
        "i'm absolutely certain", "i'm 100% sure", "without a doubt",
        "definitely", "absolutely", "i guarantee", "there's no question",
        "i'm positive that", "undoubtedly", "certainly",
    ]

    hedging_phrases = [
        "i think", "i believe", "i'm not sure", "it might be",
        "possibly", "perhaps", "it seems like", "from what i know",
        "i could be wrong", "approximately",
    ]

    response_lower = response.lower()

    has_high_confidence = any(p in response_lower for p in high_confidence_phrases)
    has_hedging = any(p in response_lower for p in hedging_phrases)

    if is_correct:
        # Correct + confident = good, correct + hedging = slightly less good
        if has_high_confidence:
            return 1.0
        elif has_hedging:
            return 0.95
        return 1.0
    else:
        # Wrong + confident = bad, wrong + hedging = less bad
        if has_high_confidence:
            return 0.5  # Big penalty for confident and wrong
        elif has_hedging:
            return 0.8  # Smaller penalty — at least they hedged
        return 0.7  # Default penalty for incorrect


def compute_entropy(responses: list) -> float:
    """
    Compute Shannon entropy of responses to measure diversity.
    
    Low entropy = responses are too similar (possible gaming).
    High entropy = good diversity.
    
    Returns normalized entropy (0.0 to 1.0).
    """
    if len(responses) < 2:
        return 1.0

    # Use first 200 chars as a fingerprint for bucketing
    fingerprints = [r[:200].lower().strip() for r in responses if r]
    if not fingerprints:
        return 0.0

    # Count frequency of similar fingerprints
    buckets = defaultdict(int)
    for fp in fingerprints:
        # Simple hash bucket
        bucket_key = _simple_hash(fp)
        buckets[bucket_key] += 1

    # Shannon entropy
    n = len(fingerprints)
    entropy = 0.0
    for count in buckets.values():
        p = count / n
        if p > 0:
            entropy -= p * math.log2(p)

    # Normalize by max possible entropy
    max_entropy = math.log2(n) if n > 1 else 1.0
    return round(entropy / max_entropy, 4) if max_entropy > 0 else 0.0


# --- Internal helpers ---

def _char_ngrams(text: str, n: int = 3) -> set:
    """Generate character n-grams from text."""
    text = text.lower().strip()
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def _jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _simple_hash(text: str, bucket_size: int = 100) -> str:
    """Create a simple hash bucket for text (for entropy calculation)."""
    # Use word-level features for bucketing
    words = sorted(set(text.split()))[:10]
    return " ".join(words)
