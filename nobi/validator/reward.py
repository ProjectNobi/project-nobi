# Project Nobi — Reward functions
# Phase 1: Simple LLM-as-judge scoring

import os
import numpy as np
from typing import List
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


def reward(query: str, response: str, api_key: str = "") -> float:
    """
    Score a miner's response using LLM-as-judge.
    Falls back to simple heuristic if no API key or on error.
    """
    if not response or not isinstance(response, str) or len(response.strip()) == 0:
        return 0.0

    # Try LLM-as-judge if we have an API key
    if api_key and OpenAI is not None:
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            completion = client.chat.completions.create(
                model="anthropic/claude-3.5-haiku",
                messages=[
                    {"role": "user", "content": JUDGE_PROMPT.format(query=query, response=response)}
                ],
                max_tokens=10,
                temperature=0.0,
            )
            score_text = completion.choices[0].message.content.strip()
            score = float(score_text)
            return max(0.0, min(1.0, score))
        except Exception as e:
            bt.logging.warning(f"LLM-as-judge failed, using heuristic: {e}")

    # Fallback: Simple heuristic scoring
    score = 0.0

    # Length check: responses should be meaningful (at least 20 chars)
    if len(response) >= 20:
        score += 0.3
    elif len(response) >= 5:
        score += 0.1

    # Not too short, not too long
    if 50 <= len(response) <= 2000:
        score += 0.3
    elif len(response) > 2000:
        score += 0.1

    # Contains actual words (not just special chars)
    word_count = len(response.split())
    if word_count >= 5:
        score += 0.2

    # Response relates to query (very basic check — shares words)
    query_words = set(query.lower().split())
    response_words = set(response.lower().split())
    if len(query_words & response_words) > 0:
        score += 0.2

    return min(1.0, score)


def get_rewards(
    self,
    query: str,
    responses: List[str],
) -> np.ndarray:
    """
    Returns an array of rewards for the given query and responses.
    """
    api_key = getattr(self.config.neuron, "openrouter_api_key", "") or os.environ.get("OPENROUTER_API_KEY", "")

    return np.array([
        reward(query, response, api_key) for response in responses
    ])
