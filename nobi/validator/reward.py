# Project Nobi — Reward functions
# Phase 1: LLM-as-judge scoring
# Phase 2: Memory recall + reliability scoring
#
# FAIRNESS DESIGN:
# - Heuristic fallback CAPS at 0.5 (not 1.0) — can't game without real LLM judge
# - Memory scoring uses LLM judge when available for natural integration check
# - Reliability score based on actual response latency
# - All weights documented and match INCENTIVE_MECHANISM.md

import os
import re
import time
import numpy as np
from typing import List, Optional
import bittensor as bt

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from nobi.memory.embeddings import EmbeddingEngine, get_engine
    _SEMANTIC_AVAILABLE = True
except ImportError:
    _SEMANTIC_AVAILABLE = False

try:
    from nobi.validator.tuning import (
        ScoringTuner,
        compute_diversity_penalties,
        normalize_length_score,
        score_confidence_calibration,
        compute_entropy,
    )
    _TUNING_AVAILABLE = True
except ImportError:
    _TUNING_AVAILABLE = False

# Global tuner instance (lazy init)
_tuner_instance = None


def _get_tuner() -> "ScoringTuner":
    """Get or create the global ScoringTuner instance."""
    global _tuner_instance
    if _tuner_instance is None and _TUNING_AVAILABLE:
        _tuner_instance = ScoringTuner()
    return _tuner_instance


# ─── TEE Scoring Bonus ───────────────────────────────────────────────────────
# Miners running inside a verified TEE enclave earn a bonus on top of their
# base score.  This incentivises miners to invest in TEE hardware (AMD SEV-SNP
# or NVIDIA CC) which provides stronger privacy guarantees for users.
#
# Bonus is applied AFTER base quality/reliability scoring so it cannot rescue
# low-quality responses — a miner must first produce a good response and then
# the TEE bonus multiplies up from there.
#
# AMD SEV-SNP fully-chain-verified (VCEK ECDSA validated): +10%
# AMD SEV-SNP structurally valid  (MVP, chain not yet verified): +5%
# NVIDIA CC structurally valid:  +5%
# No TEE / unverified:  no change
#
# Example: quality score 0.80 with AMD SEV-SNP chain verified → 0.80 × 1.10 = 0.88

TEE_BONUS_CHAIN_VERIFIED = 0.10   # Full VCEK chain verification
TEE_BONUS_STRUCTURAL = 0.05       # Structural validity only (MVP default)
TEE_MAX_FINAL_SCORE = 1.0         # Bonuses cannot push score above 1.0


def apply_tee_bonus(base_score: float, tee_verified: bool, chain_verified: bool = False) -> float:
    """
    Apply a TEE hardware bonus to a base miner score.

    Args:
        base_score:     Score before TEE bonus (0.0 – 1.0).
        tee_verified:   Whether the validator confirmed this miner runs in a TEE
                        (attestation report structurally valid).
        chain_verified: Whether the full VCEK certificate chain was verified
                        (requires AMD KDS network access — not available in MVP).

    Returns:
        Adjusted score, capped at TEE_MAX_FINAL_SCORE.
    """
    if not tee_verified:
        return base_score

    bonus = TEE_BONUS_CHAIN_VERIFIED if chain_verified else TEE_BONUS_STRUCTURAL
    return min(TEE_MAX_FINAL_SCORE, base_score * (1.0 + bonus))


JUDGE_PROMPT = """You are an AI response quality judge. Rate the following AI companion response on a scale of 0.0 to 1.0.

User's question: {query}

AI's response: {response}

Scoring criteria:
- Helpfulness (0-0.4): Does the response actually help the user?
- Coherence (0-0.3): Is the response well-structured and makes sense?
- Personality (0-0.3): Does the response feel warm, personal, and engaging (not robotic)?

Return ONLY a single decimal number between 0.0 and 1.0. Nothing else."""


def reward(
    query: str,
    response: str,
    api_key: str = "",
    test_type: str = "single",
    memory_keywords: List[str] = None,
    latency: float = 0.0,
    tee_verified: bool = False,
    tee_chain_verified: bool = False,
) -> float:
    """
    Score a miner's response.

    Phase 2 Weights:
    - Single-turn: 90% quality + 10% reliability
    - Multi-turn:  50% quality + 25% memory_integration + 15% memory_recall + 10% reliability

    Memory integration (Phase 2): checks if miner naturally weaves memories into
    responses vs just keyword-matching. Uses LLM judge when available.

    Phase 7 TEE Bonus:
    - tee_verified=True:  +5% bonus on final score (structural attestation)
    - tee_chain_verified=True: +10% bonus (full VCEK chain — not yet in MVP)
    """
    if not response or not isinstance(response, str) or len(response.strip()) == 0:
        return 0.0

    # Quality score from LLM judge (includes helpfulness + coherence + personality)
    quality_score = _llm_judge(query, response, api_key)

    # Reliability score based on latency
    reliability_score = _score_reliability(latency)

    # Quality floor enforcement: miners below minimum quality threshold get zero.
    # Applied to quality_score (not final) so reliability cannot rescue garbage responses.
    # Threshold from ScoringTuner.QUALITY_FLOOR (default 0.10).
    if _TUNING_AVAILABLE:
        tuner = _get_tuner()
        _quality_floor = getattr(tuner, "QUALITY_FLOOR", 0.10) if tuner else 0.10
    else:
        _quality_floor = 0.10

    if quality_score < _quality_floor:
        bt.logging.debug(
            f"[QualityFloor] quality={quality_score:.3f} < {_quality_floor} → 0.0"
        )
        return 0.0

    if test_type == "multi_turn" and memory_keywords:
        memory_recall_score = _score_memory_recall(response, memory_keywords)
        memory_integration_score = _score_memory_integration(
            query, response, memory_keywords, api_key
        )
        # Multi-turn: 50% quality + 25% integration + 15% recall + 10% reliability
        final = (0.50 * quality_score +
                 0.25 * memory_integration_score +
                 0.15 * memory_recall_score +
                 0.10 * reliability_score)

        # Apply length normalization if tuning available
        if _TUNING_AVAILABLE:
            final = normalize_length_score(response, final)

        # Phase 7: TEE bonus — applied after base scoring
        final = apply_tee_bonus(final, tee_verified, tee_chain_verified)

        bt.logging.debug(
            f"Score: quality={quality_score:.2f} integration={memory_integration_score:.2f} "
            f"recall={memory_recall_score:.2f} reliability={reliability_score:.2f} "
            f"tee_bonus={'yes' if tee_verified else 'no'} → final={final:.2f}"
        )
        return final

    # Single-turn: 90% quality/personality + 10% reliability
    final = 0.90 * quality_score + 0.10 * reliability_score

    # Apply length normalization if tuning available
    if _TUNING_AVAILABLE:
        final = normalize_length_score(response, final)

    # Phase 7: TEE bonus — applied after base scoring
    final = apply_tee_bonus(final, tee_verified, tee_chain_verified)

    return final


def _llm_judge(query: str, response: str, api_key: str = "") -> float:
    """Score using LLM-as-judge. Chutes → OpenRouter → heuristic fallback."""
    chutes_key = os.environ.get("CHUTES_API_KEY", "")
    chutes_model = os.environ.get("CHUTES_JUDGE_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

    for base_url, key, model in [
        ("https://llm.chutes.ai/v1", chutes_key, chutes_model),
        ("https://openrouter.ai/api/v1", api_key, "anthropic/claude-3.5-haiku-20241022"),
    ]:
        if not key or OpenAI is None:
            continue
        try:
            client = OpenAI(base_url=base_url, api_key=key)
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": JUDGE_PROMPT.format(
                        query=query, response=response
                    )}
                ],
                max_tokens=10,
                temperature=0.0,
                timeout=15,
            )
            score_text = completion.choices[0].message.content.strip()
            match = re.search(r'(\d+\.?\d*)', score_text)
            if match:
                return max(0.0, min(1.0, float(match.group(1))))
        except Exception as e:
            bt.logging.warning(f"[JUDGE] {base_url.split('/')[2]} failed: {e} — trying next")

    # Heuristic fallback — CAPPED at 0.5 to prevent gaming
    return _heuristic_score(query, response)


def _heuristic_score(query: str, response: str) -> float:
    """
    Simple heuristic scoring when no LLM API available.
    CAPPED at 0.5 — miners can't get top scores without real LLM judge.
    This ensures quality differentiation requires actual good responses.
    """
    score = 0.0

    # Length: meaningful responses
    word_count = len(response.split())
    if word_count >= 30:
        score += 0.15
    elif word_count >= 10:
        score += 0.10
    elif word_count >= 5:
        score += 0.05

    # Not too short, not too long
    if 100 <= len(response) <= 2000:
        score += 0.15
    elif 50 <= len(response) < 100:
        score += 0.08

    # Contains actual sentences (has periods or question marks)
    if "." in response or "?" in response or "!" in response:
        score += 0.10

    # Query relevance (shares words beyond common ones)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "to", "for",
                  "and", "or", "but", "in", "on", "at", "of", "can", "you",
                  "me", "my", "i", "it", "do", "how", "what", "why"}
    query_words = set(query.lower().split()) - stop_words
    response_words = set(response.lower().split()) - stop_words
    overlap = query_words & response_words
    if len(overlap) >= 2:
        score += 0.10
    elif len(overlap) >= 1:
        score += 0.05

    # Hard cap at 0.5 — heuristic should never give top scores
    return min(0.5, score)


def _score_memory_recall(
    response: str,
    keywords: List[str],
    use_semantic: bool = True,
    semantic_threshold: float = 0.5,
) -> float:
    """
    Score memory recall — checks if response naturally includes
    keywords from the user's previously shared information.

    When semantic matching is available, uses embedding similarity instead of
    exact keyword matching. This catches paraphrases and related concepts
    (e.g., "puppy" matching "dog", "NYC" matching "New York City").

    Falls back to keyword matching if embeddings aren't available.

    Args:
        response: The miner's response text
        keywords: Memory keywords to check for
        use_semantic: Attempt semantic matching (default True)
        semantic_threshold: Minimum similarity to count as a match (default 0.5)
    """
    if not keywords:
        return 0.5

    # Try semantic scoring first
    if use_semantic and _SEMANTIC_AVAILABLE:
        try:
            return _score_memory_recall_semantic(response, keywords, semantic_threshold)
        except Exception as e:
            bt.logging.debug(f"[Recall] Semantic scoring failed: {e}, falling back to keyword")

    # Fallback: original keyword matching
    return _score_memory_recall_keyword(response, keywords)


def _score_memory_recall_semantic(
    response: str, keywords: List[str], threshold: float = 0.3
) -> float:
    """
    Hybrid memory recall scoring: exact keyword match FIRST, then semantic for misses.
    Single-word vs full-sentence embeddings have low cosine similarity (~0.3-0.45),
    so we check exact matches first and only use embeddings for paraphrases.
    """
    import re as _re
    engine = get_engine()
    response_lower = response.lower()

    matches = 0
    total_sim = 0.0

    response_vec = engine.embed(response)
    keyword_vecs = engine.embed_batch(keywords)

    for i, kw in enumerate(keywords):
        kw_lower = kw.lower()
        # Step 1: Exact keyword match (fast, reliable)
        if kw_lower in response_lower:
            matches += 1
            total_sim += 1.0
            continue

        # Step 2: Semantic similarity for paraphrases
        sim = engine.cosine_similarity(response_vec, keyword_vecs[i])
        total_sim += max(0.0, sim)
        if sim >= threshold:
            matches += 1

    recall_rate = matches / len(keywords)
    avg_sim = total_sim / len(keywords)

    # Blend discrete recall rate (60%) with continuous avg similarity (40%)
    blended = 0.6 * recall_rate + 0.4 * avg_sim

    if blended >= 0.7:
        return 1.0
    elif blended >= 0.55:
        return 0.85
    elif blended >= 0.4:
        return 0.7
    elif blended >= 0.25:
        return 0.5
    elif blended > 0.1:
        return 0.3
    else:
        return 0.1


def _score_memory_recall_keyword(response: str, keywords: List[str]) -> float:
    """
    Original keyword-based memory recall scoring.
    Uses word boundary matching for short keywords to avoid false positives.
    """
    response_lower = response.lower()
    matches = 0
    for kw in keywords:
        kw_lower = kw.lower()
        if len(kw_lower) <= 2:
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', response_lower):
                matches += 1
        else:
            if kw_lower in response_lower:
                matches += 1

    recall_rate = matches / len(keywords)

    if recall_rate >= 0.8:
        return 1.0
    elif recall_rate >= 0.6:
        return 0.85
    elif recall_rate >= 0.4:
        return 0.7
    elif recall_rate >= 0.2:
        return 0.5
    elif recall_rate > 0:
        return 0.3
    else:
        return 0.1


def _score_memory_integration(
    query: str, response: str, memory_keywords: List[str], api_key: str = ""
) -> float:
    """
    Phase 2: Score how naturally a miner integrates memories into its response.
    - Does it reference stored info naturally (not just parroting)?
    - Does it forget something it was told (penalty)?

    Uses LLM judge when available; falls back to heuristic.
    """
    if not memory_keywords:
        return 0.5

    # Try LLM-based integration scoring
    chutes_key = os.environ.get("CHUTES_API_KEY", "")
    chutes_model = os.environ.get("CHUTES_JUDGE_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")

    if chutes_key and OpenAI is not None:
        try:
            client = OpenAI(base_url="https://llm.chutes.ai/v1", api_key=chutes_key)
            kw_str = ", ".join(memory_keywords[:8])
            prompt = (
                f"The AI was previously told these facts about the user: {kw_str}\n\n"
                f"User's question: {query}\n\n"
                f"AI's response: {response}\n\n"
                "Rate how naturally the AI uses its memory of the user (0.0 to 1.0):\n"
                "- 1.0 = Naturally references past info, feels personal and attentive\n"
                "- 0.7 = Mentions past info but a bit forced/mechanical\n"
                "- 0.4 = Barely references what it knows about the user\n"
                "- 0.1 = Completely ignores/forgets what the user told them\n"
                "Return ONLY a single decimal number."
            )
            completion = client.chat.completions.create(
                model=chutes_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
                timeout=10,
            )
            score_text = completion.choices[0].message.content.strip()
            match = re.search(r'(\d+\.?\d*)', score_text)
            if match:
                return max(0.0, min(1.0, float(match.group(1))))
        except Exception as e:
            bt.logging.debug(f"[Integration] LLM judge failed: {e}")

    # Heuristic fallback: check keyword presence + natural language signals
    response_lower = response.lower()
    matches = sum(1 for kw in memory_keywords if kw.lower() in response_lower)
    recall_rate = matches / max(len(memory_keywords), 1)

    # Bonus for natural integration signals
    natural_signals = [
        "you mentioned", "last time", "you told me", "i remember",
        "you said", "earlier you", "as you shared", "you were",
    ]
    has_natural = any(sig in response_lower for sig in natural_signals)

    base = min(0.5, recall_rate)  # Heuristic capped at 0.5
    if has_natural and recall_rate > 0.2:
        base = min(0.6, base + 0.15)

    return base


def _score_reliability(latency: float) -> float:
    """
    Score based on response latency.
    Lower latency = higher score.

    Thresholds:
      < 5s  → 1.0
      < 10s → 0.8
      < 20s → 0.6
      < 30s → 0.4
      ≥ 30s → 0.2
    """
    if latency <= 0:
        return 0.5  # Unknown latency, neutral score

    if latency < 5:
        return 1.0
    elif latency < 10:
        return 0.8
    elif latency < 20:
        return 0.6
    elif latency < 30:
        return 0.4
    else:
        return 0.2


def diversity_score(
    responses: List[str],
    similarity_threshold: float = 0.85,
    high_similarity_threshold: float = 0.95,
    diversity_bonus: float = 0.05,
) -> np.ndarray:
    """
    Miner Diversity Scoring — penalise monoculture and reward unique responses.

    Algorithm
    ---------
    1. **Response similarity detection** — char-level 3-gram Jaccard similarity
       detects near-duplicate responses; miners in duplicate pairs are penalised.
    2. **Model fingerprinting** — responses with very similar (length, vocabulary)
       buckets suggest the same underlying model; adds a compounded penalty.
    3. **Diversity bonus** — miners whose response is unique *and* substantive
       (≥ 20 words) receive a small additive score boost.

    Parameters
    ----------
    responses:
        List of raw response strings from miners.
    similarity_threshold:
        Jaccard similarity above which responses are near-duplicates.
    high_similarity_threshold:
        Stricter threshold; triggers maximum copy penalty.
    diversity_bonus:
        Additive bonus (added on top of 1.0) for unique, substantive responses.

    Returns
    -------
    np.ndarray of float multipliers, one per response, in [0.3, 1.05].
    1.0 = neutral (no penalty, no bonus).
    """
    n = len(responses)
    if n == 0:
        return np.array([], dtype=np.float32)
    if n == 1:
        return np.ones(1, dtype=np.float32)

    multipliers = np.ones(n, dtype=np.float64)

    # ── 1. Build char 3-gram sets ────────────────────────────────────────
    def _ngrams(text: str, size: int = 3) -> set:
        t = text.lower().strip()
        if len(t) < size:
            return {t} if t else set()
        return {t[i:i + size] for i in range(len(t) - size + 1)}

    def _jaccard_sim(a: set, b: set) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    ngram_sets = [_ngrams(r) for r in responses]

    copy_counts = np.zeros(n, dtype=np.int32)
    high_copy_counts = np.zeros(n, dtype=np.int32)

    for i in range(n):
        for j in range(i + 1, n):
            sim = _jaccard_sim(ngram_sets[i], ngram_sets[j])
            if sim >= similarity_threshold:
                copy_counts[i] += 1
                copy_counts[j] += 1
            if sim >= high_similarity_threshold:
                high_copy_counts[i] += 1
                high_copy_counts[j] += 1

    # ── 2. Model fingerprint — (length-bucket, vocab-bucket) ─────────────
    from collections import defaultdict as _defaultdict

    def _fp(text: str) -> tuple:
        words = text.lower().split()
        return (len(text) // 50, len(set(words)) // 5)

    fingerprints = [_fp(r) for r in responses]
    fp_counts: dict = _defaultdict(int)
    for fp in fingerprints:
        fp_counts[fp] += 1

    # ── 3. Apply penalties + bonus ────────────────────────────────────────
    for i in range(n):
        # Copy penalty
        if high_copy_counts[i] > 0:
            multipliers[i] = min(multipliers[i], 0.30)
        elif copy_counts[i] >= 2:
            multipliers[i] = min(multipliers[i], 0.50)
        elif copy_counts[i] == 1:
            multipliers[i] = min(multipliers[i], 0.70)

        # Model fingerprint penalty
        same_model_count = fp_counts[fingerprints[i]]
        if same_model_count >= max(3, n // 2):
            multipliers[i] = min(multipliers[i], 0.80)

        # Diversity bonus — unique + substantive
        if copy_counts[i] == 0 and len(responses[i].split()) >= 20:
            multipliers[i] = min(1.0 + diversity_bonus, multipliers[i] + diversity_bonus)

    mean_mult = float(np.mean(multipliers))
    penalised = int(np.sum(multipliers < 1.0))
    bt.logging.debug(
        f"[DiversityScore] n={n} penalised={penalised} mean_mult={mean_mult:.3f}"
    )
    return multipliers.astype(np.float32)


def get_rewards(
    self,
    query: str,
    responses: List[str],
    test_type: str = "single",
    memory_keywords: List[str] = None,
    latencies: List[float] = None,
    tee_verified_flags: Optional[List[bool]] = None,
    tee_chain_verified_flags: Optional[List[bool]] = None,
) -> np.ndarray:
    """
    Returns an array of rewards for the given query and responses.

    Args:
        tee_verified_flags: Per-miner TEE structural verification flags.
            If provided, must be same length as responses.
        tee_chain_verified_flags: Per-miner full VCEK chain verification flags.
            Only relevant when tee_verified_flags is provided.
    """
    api_key = (
        getattr(self.config.neuron, "openrouter_api_key", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )

    if latencies is None:
        latencies = [0.0] * len(responses)

    if tee_verified_flags is None:
        tee_verified_flags = [False] * len(responses)

    if tee_chain_verified_flags is None:
        tee_chain_verified_flags = [False] * len(responses)

    # Compute base rewards
    rewards = np.array([
        reward(
            query, response, api_key,
            test_type=test_type,
            memory_keywords=memory_keywords,
            latency=lat,
            tee_verified=tee_ok,
            tee_chain_verified=chain_ok,
        )
        for response, lat, tee_ok, chain_ok in zip(
            responses, latencies, tee_verified_flags, tee_chain_verified_flags
        )
    ])

    # Apply diversity penalties (anti-gaming: penalize identical responses)
    if _TUNING_AVAILABLE and len(responses) > 1:
        diversity_penalties = compute_diversity_penalties(responses)
        rewards = rewards * np.array(diversity_penalties)

        # Log entropy for monitoring — threshold raised for 256-neuron network
        entropy = compute_entropy(responses)
        tuner = _get_tuner()
        entropy_threshold = getattr(tuner, "LOW_ENTROPY_WARNING", 0.5) if tuner else 0.5
        if entropy < entropy_threshold:
            bt.logging.warning(
                f"[Anti-Gaming] Low response entropy ({entropy:.2f} < {entropy_threshold}) — "
                "miners may be copying each other"
            )

    # Quality floor enforcement — miners below threshold get zero
    # Prevents garbage responses from accumulating score in moving average
    if _TUNING_AVAILABLE:
        tuner = _get_tuner()
        quality_floor = getattr(tuner, "QUALITY_FLOOR", 0.10) if tuner else 0.10
    else:
        quality_floor = 0.10

    rewards = np.where(rewards < quality_floor, 0.0, rewards)

    # Apply miner diversity scoring (model fingerprint + uniqueness bonus)
    if len(responses) > 1:
        div_multipliers = diversity_score(responses)
        rewards = rewards * div_multipliers

    return rewards
