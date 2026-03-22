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
) -> float:
    """
    Score a miner's response.

    Phase 2 Weights:
    - Single-turn: 90% quality + 10% reliability
    - Multi-turn:  50% quality + 25% memory_integration + 15% memory_recall + 10% reliability

    Memory integration (Phase 2): checks if miner naturally weaves memories into
    responses vs just keyword-matching. Uses LLM judge when available.
    """
    if not response or not isinstance(response, str) or len(response.strip()) == 0:
        return 0.0

    # Quality score from LLM judge (includes helpfulness + coherence + personality)
    quality_score = _llm_judge(query, response, api_key)

    # Reliability score based on latency
    reliability_score = _score_reliability(latency)

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

        bt.logging.debug(
            f"Score: quality={quality_score:.2f} integration={memory_integration_score:.2f} "
            f"recall={memory_recall_score:.2f} reliability={reliability_score:.2f} → final={final:.2f}"
        )
        return final

    # Single-turn: 90% quality/personality + 10% reliability
    final = 0.90 * quality_score + 0.10 * reliability_score

    # Apply length normalization if tuning available
    if _TUNING_AVAILABLE:
        final = normalize_length_score(response, final)

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


def get_rewards(
    self,
    query: str,
    responses: List[str],
    test_type: str = "single",
    memory_keywords: List[str] = None,
    latencies: List[float] = None,
) -> np.ndarray:
    """Returns an array of rewards for the given query and responses."""
    api_key = (
        getattr(self.config.neuron, "openrouter_api_key", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )

    if latencies is None:
        latencies = [0.0] * len(responses)

    # Compute base rewards
    rewards = np.array([
        reward(
            query, response, api_key,
            test_type=test_type,
            memory_keywords=memory_keywords,
            latency=lat,
        )
        for response, lat in zip(responses, latencies)
    ])

    # Apply diversity penalties (anti-gaming: penalize identical responses)
    if _TUNING_AVAILABLE and len(responses) > 1:
        diversity_penalties = compute_diversity_penalties(responses)
        rewards = rewards * np.array(diversity_penalties)

        # Log entropy for monitoring
        entropy = compute_entropy(responses)
        if entropy < 0.3:
            bt.logging.warning(
                f"[Anti-Gaming] Low response entropy ({entropy:.2f}) — "
                "miners may be copying each other"
            )

    return rewards
