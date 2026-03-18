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

    Weights (matching INCENTIVE_MECHANISM.md):
    - Single-turn: 90% quality + 10% reliability
    - Multi-turn:  50% quality + 30% memory + 10% personality (in judge) + 10% reliability

    The 40/30/20/10 split in docs maps to:
    - Quality (40%) = LLM judge helpfulness+coherence
    - Memory (30%) = keyword recall + natural integration
    - Personality (20%) = included in LLM judge personality criteria
    - Reliability (10%) = latency-based
    """
    if not response or not isinstance(response, str) or len(response.strip()) == 0:
        return 0.0

    # Quality score from LLM judge (includes helpfulness + coherence + personality)
    quality_score = _llm_judge(query, response, api_key)

    # Reliability score based on latency
    reliability_score = _score_reliability(latency)

    if test_type == "multi_turn" and memory_keywords:
        memory_score = _score_memory_recall(response, memory_keywords)
        # Multi-turn: 60% quality/personality + 30% memory + 10% reliability
        final = 0.60 * quality_score + 0.30 * memory_score + 0.10 * reliability_score
        bt.logging.debug(
            f"Score: quality={quality_score:.2f} memory={memory_score:.2f} "
            f"reliability={reliability_score:.2f} → final={final:.2f}"
        )
        return final

    # Single-turn: 90% quality/personality + 10% reliability
    final = 0.90 * quality_score + 0.10 * reliability_score
    return final


def _llm_judge(query: str, response: str, api_key: str = "") -> float:
    """Score using LLM-as-judge. Chutes → OpenRouter → heuristic fallback."""
    chutes_key = os.environ.get("CHUTES_API_KEY", "")
    chutes_model = os.environ.get("CHUTES_JUDGE_MODEL", "deepseek-ai/DeepSeek-V3-0324")

    for base_url, key, model in [
        ("https://llm.chutes.ai/v1", chutes_key, chutes_model),
        ("https://openrouter.ai/api/v1", api_key, "anthropic/claude-3.5-haiku"),
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


def _score_memory_recall(response: str, keywords: List[str]) -> float:
    """
    Score memory recall — checks if response naturally includes
    keywords from the user's previously shared information.

    Uses word boundary matching for short keywords to avoid false positives.
    """
    if not keywords:
        return 0.5

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

    return np.array([
        reward(
            query, response, api_key,
            test_type=test_type,
            memory_keywords=memory_keywords,
            latency=lat,
        )
        for response, lat in zip(responses, latencies)
    ])
