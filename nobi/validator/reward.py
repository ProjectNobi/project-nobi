# Project Nobi — Reward functions
# Phase 1: LLM-as-judge scoring
# Phase 2: Memory recall scoring — bonus for remembering user details

import os
import re
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
- Personality (0-0.3): Does the response feel warm, personal, and engaging (like a companion)?

Return ONLY a single decimal number between 0.0 and 1.0. Nothing else."""


MEMORY_JUDGE_PROMPT = """You are an AI companion quality judge. The companion was told personal details about the user in earlier messages, then asked a follow-up question. Rate how well the response uses those details.

Setup information shared with the companion:
{setup_info}

Follow-up question: {query}

Companion's response: {response}

Keywords that SHOULD appear if the companion remembered: {keywords}

Scoring:
- Memory recall (0-0.4): Does the response reference the user's details naturally?
- Helpfulness (0-0.3): Is the response helpful given what's known about the user?
- Personality (0-0.3): Does it feel personal and caring, not generic?

Return ONLY a single decimal number between 0.0 and 1.0. Nothing else."""


def reward(
    query: str,
    response: str,
    api_key: str = "",
    test_type: str = "single",
    memory_keywords: List[str] = None,
) -> float:
    """Score a miner's response. Supports single-turn and multi-turn."""
    if not response or not isinstance(response, str) or len(response.strip()) == 0:
        return 0.0

    # Base quality score from LLM or heuristic
    base_score = _llm_judge(query, response, api_key)

    # Memory bonus for multi-turn tests
    if test_type == "multi_turn" and memory_keywords:
        memory_score = _score_memory_recall(response, memory_keywords)
        # Weighted: 60% quality + 40% memory
        final = 0.6 * base_score + 0.4 * memory_score
        bt.logging.debug(f"Score breakdown: base={base_score:.2f} memory={memory_score:.2f} "
                        f"final={final:.2f}")
        return final

    return base_score


def _llm_judge(query: str, response: str, api_key: str = "") -> float:
    """Score using LLM-as-judge with Chutes + OpenRouter fallback."""
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

    # Heuristic fallback
    return _heuristic_score(query, response)


def _heuristic_score(query: str, response: str) -> float:
    """Simple heuristic scoring when no API available."""
    score = 0.0
    if len(response) >= 20:
        score += 0.3
    elif len(response) >= 5:
        score += 0.1
    if 50 <= len(response) <= 2000:
        score += 0.3
    elif len(response) > 2000:
        score += 0.1
    if len(response.split()) >= 5:
        score += 0.2
    query_words = set(query.lower().split())
    response_words = set(response.lower().split())
    if query_words & response_words:
        score += 0.2
    return min(1.0, score)


def _score_memory_recall(response: str, keywords: List[str]) -> float:
    """
    Score how well a response demonstrates memory recall.
    Checks if the response naturally includes keywords from the user's
    previously shared information.
    """
    if not keywords:
        return 0.5  # neutral if no keywords to check

    response_lower = response.lower()
    matches = 0
    for kw in keywords:
        kw_lower = kw.lower()
        # For short keywords (<=2 chars), require word boundary match
        if len(kw_lower) <= 2:
            # Use word boundary: check " kw " or "kw " at start or " kw" at end
            if re.search(r'\b' + re.escape(kw_lower) + r'\b', response_lower):
                matches += 1
        else:
            if kw_lower in response_lower:
                matches += 1

    recall_rate = matches / len(keywords)

    # Continuous scoring with tiers
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
        return 0.1  # No recall at all


def get_rewards(
    self,
    query: str,
    responses: List[str],
    test_type: str = "single",
    memory_keywords: List[str] = None,
) -> np.ndarray:
    """Returns an array of rewards for the given query and responses."""
    api_key = (
        getattr(self.config.neuron, "openrouter_api_key", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )

    return np.array([
        reward(
            query, response, api_key,
            test_type=test_type,
            memory_keywords=memory_keywords,
        )
        for response in responses
    ])
