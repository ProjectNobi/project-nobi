"""
Web search skill for Nori.
Uses Desearch API (Bittensor SN22) or DuckDuckGo Instant Answers as fallback.
"""
import asyncio
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("nobi-skills-search")

DESEARCH_API_KEY = os.environ.get("DESEARCH_API_KEY", "dsr_1xzEZ8PxC4kBhC5ThE3IDv8xk1iqHo4Qv27PWOZ9")
DESEARCH_ENDPOINT = "https://api.desearch.ai"


# ── Search trigger patterns ──────────────────────────────────

_SEARCH_TRIGGER = re.compile(
    r"\b(?:search|look up|look for|find|google|who is|what is|tell me about|"
    r"what are|where is|where can i|how to|how do i|best\s+\w+\s+in|"
    r"recommend|latest|news about|top\s+\d+|list of)\b",
    re.IGNORECASE,
)

_SEARCH_PATTERNS = [
    # "search for X", "search X"
    r"(?:search|look up|look for|google|find)\s+(?:for\s+)?(.+?)(?:\?|$|\.)",
    # "tell me about X"
    r"tell me about\s+(.+?)(?:\?|$|\.)",
    # "who is X", "what is X", "where is X"
    r"(?:who|what|where)\s+(?:is|are|was|were)\s+(.+?)(?:\?|$|\.)",
    # "best beaches in Antigua", "top restaurants in Paris"
    r"(?:best|top\s+\d*|cheapest|most popular)\s+(.+?)(?:\?|$|\.)",
    # "how to X", "how do I X"
    r"how\s+(?:to|do i|can i|does one)\s+(.+?)(?:\?|$|\.)",
    # "latest news about X"
    r"(?:latest|recent|new)\s+(?:news|updates?|info)\s+(?:about|on)\s+(.+?)(?:\?|$|\.)",
    # "recommend X"
    r"recommend\s+(?:me\s+)?(.+?)(?:\?|$|\.)",
]


def detect_search_query(message: str) -> Optional[str]:
    """
    Check if message is a search query. Returns query string if detected, else None.
    """
    if not _SEARCH_TRIGGER.search(message):
        return None

    msg = message.strip()
    for pattern in _SEARCH_PATTERNS:
        m = re.search(pattern, msg, re.IGNORECASE)
        if m:
            query = m.group(1).strip().rstrip("?.,!")
            if len(query) >= 3:
                return query

    # Fallback: use the full message as query if it has a trigger word
    if _SEARCH_TRIGGER.search(message) and len(message) <= 200:
        return message.rstrip("?.,!")

    return None


async def search_web(query: str) -> str:
    """
    Search the web and return a formatted summary of top results.
    Tries Desearch API first, then falls back to DuckDuckGo.
    """
    if not query or not query.strip():
        return ""

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, _search_sync, query.strip())
        return result
    except Exception as e:
        logger.warning(f"[Search] Error for query '{query[:50]}': {e}")
        return f"[Search unavailable — could not find results for: {query}]"


def _search_sync(query: str) -> str:
    """Synchronous search — tries Desearch then DuckDuckGo."""
    # Try Desearch API first
    if DESEARCH_API_KEY:
        try:
            result = _desearch(query)
            if result:
                return result
        except Exception as e:
            logger.debug(f"[Search] Desearch failed: {e}, falling back to DDG")

    # Fallback: DuckDuckGo Instant Answers
    try:
        result = _duckduckgo(query)
        if result:
            return result
    except Exception as e:
        logger.debug(f"[Search] DDG also failed: {e}")

    return f"[Search: no results found for '{query}']"


def _desearch(query: str) -> Optional[str]:
    """Query Desearch API (Bittensor SN22 — web search)."""
    url = f"{DESEARCH_ENDPOINT}/search"
    payload = json.dumps({
        "query": query,
        "num_results": 3,
        "result_type": "links",
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {DESEARCH_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "NoriBot/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)

    # Extract results from Desearch response
    results = []
    organic = data.get("organic_results") or data.get("results") or data.get("data") or []
    if isinstance(organic, list):
        for item in organic[:3]:
            if isinstance(item, dict):
                title = item.get("title", "").strip()
                snippet = item.get("snippet", item.get("description", "")).strip()
                url_val = item.get("url", item.get("link", "")).strip()
                if title or snippet:
                    parts = []
                    if title:
                        parts.append(f"• {title}")
                    if snippet:
                        parts.append(f"  {snippet[:200]}")
                    if url_val:
                        parts.append(f"  Source: {url_val}")
                    results.append("\n".join(parts))

    if not results:
        # Try to get answer directly
        answer = data.get("answer") or data.get("abstract") or ""
        if answer:
            results.append(f"• {answer[:400]}")

    if not results:
        return None

    header = f"[Search results for: {query}]\n"
    return header + "\n\n".join(results[:3])


def _duckduckgo(query: str) -> Optional[str]:
    """Query DuckDuckGo Instant Answers API (free, no key)."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "no_redirect": "1",
        "no_html": "1",
        "skip_disambig": "1",
    })
    url = f"https://api.duckduckgo.com/?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "NoriBot/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)

    results = []

    # Main answer/abstract
    abstract = data.get("AbstractText", "").strip()
    abstract_source = data.get("AbstractSource", "")
    if abstract:
        source_note = f" (Source: {abstract_source})" if abstract_source else ""
        results.append(f"• {abstract[:400]}{source_note}")

    # Definition
    definition = data.get("Definition", "").strip()
    if definition and definition != abstract:
        results.append(f"• {definition[:300]}")

    # Instant answer
    answer = data.get("Answer", "").strip()
    if answer and answer not in (abstract, definition):
        results.append(f"• {answer[:300]}")

    # Related topics
    related = data.get("RelatedTopics", [])
    for topic in related[:2]:
        if isinstance(topic, dict):
            text = topic.get("Text", "").strip()
            if text and len(results) < 3:
                results.append(f"• {text[:200]}")

    if not results:
        return None

    header = f"[Search results for: {query}]\n"
    return header + "\n\n".join(results[:3])
