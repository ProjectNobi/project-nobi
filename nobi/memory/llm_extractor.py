"""
Project Nobi — LLM Entity Extractor
=====================================
LLM-powered entity/relationship extraction that supplements regex patterns.

Uses Chutes or OpenRouter APIs for structured extraction.
Falls back gracefully if no API key is configured or LLM fails.
Caches recent extractions to avoid duplicate API calls.
Thread-safe via threading locks.
"""

import os
import json
import hashlib
import logging
import random
import threading
import time
from typing import Dict, List, Optional
from collections import OrderedDict

logger = logging.getLogger("nobi-llm-extractor")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Known valid types for validation
VALID_ENTITY_TYPES = frozenset({
    "person", "place", "org", "organization", "animal", "object",
    "concept", "event", "food", "activity", "language",
})

VALID_RELATIONSHIP_TYPES = frozenset({
    "is_a", "is_named", "has", "likes", "dislikes", "loves",
    "lives_in", "from", "works_at", "works_as",
    "related_to", "sibling_of", "sister_of", "brother_of",
    "parent_of", "child_of", "mother_of", "father_of",
    "friend_of", "partner_of", "married_to",
    "owns", "has_pet", "studies", "studies_at",
    "plays", "speaks", "born_on", "born_in",
    "interested_in", "member_of", "uses",
})

# Map shorthand entity types to canonical types
_ENTITY_TYPE_MAP = {
    "org": "organization",
    "organisation": "organization",
    "company": "organization",
    "location": "place",
    "city": "place",
    "country": "place",
    "pet": "animal",
    "sport": "activity",
    "game": "activity",
    "hobby": "activity",
    "drink": "food",
    "beverage": "food",
}

_EXTRACTION_PROMPT = """Extract entities and relationships from this text about a user.
Return JSON: {"entities": [{"name": "...", "type": "person|place|org|animal|food|activity|language|concept"}], "relationships": [{"source": "...", "type": "...", "target": "..."}]}
Relationship types: is_named, sister_of, brother_of, mother_of, father_of, child_of, lives_in, from, works_at, works_as, likes, loves, dislikes, has_pet, plays, speaks, studies, studies_at, married_to, partner_of, friend_of, interested_in, member_of, owns, uses, related_to, is_a
Use "user" as source when the text is about the speaker themselves.
Return ONLY valid JSON, no explanation. Return {"entities": [], "relationships": []} if nothing extractable.
Text: "{text}"
"""


class LLMEntityExtractor:
    """
    LLM-powered entity and relationship extraction.

    Supplements regex extraction with richer, more nuanced understanding.
    Falls back gracefully when LLM is unavailable.
    Thread-safe with LRU cache for deduplication.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        cache_size: int = 256,
        timeout: float = 8.0,
    ):
        """
        Initialize the LLM extractor.

        Args:
            api_key: API key for Chutes/OpenRouter. Falls back to env vars.
            model: Model name. Falls back to env var or default.
            cache_size: Max number of cached extraction results.
            timeout: API request timeout in seconds.
        """
        self.api_key = api_key or os.environ.get("CHUTES_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model or os.environ.get("CHUTES_MODEL", "deepseek-ai/DeepSeek-V3.1-TEE")
        self.timeout = timeout

        # Determine base URL from key type
        if self.api_key.startswith("sk-or-"):
            self.base_url = "https://openrouter.ai/api/v1"
        else:
            self.base_url = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")

        # Thread-safe LRU cache
        self._cache: OrderedDict[str, Dict] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        """Check if LLM extraction is available (API key + library)."""
        return bool(self.api_key) and OpenAI is not None

    def _cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()[:32]

    def _get_cached(self, text: str) -> Optional[Dict]:
        """Get cached result if available."""
        key = self._cache_key(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def _set_cached(self, text: str, result: Dict):
        """Cache an extraction result."""
        key = self._cache_key(text)
        with self._lock:
            self._cache[key] = result
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def _normalize_entity_type(self, etype: str) -> str:
        """Normalize entity type to canonical form."""
        etype = etype.strip().lower()
        if etype in _ENTITY_TYPE_MAP:
            return _ENTITY_TYPE_MAP[etype]
        if etype in VALID_ENTITY_TYPES:
            return etype
        return "concept"

    def _normalize_relationship_type(self, rtype: str) -> str:
        """Normalize relationship type to canonical form."""
        rtype = rtype.strip().lower().replace(" ", "_").replace("-", "_")
        if rtype in VALID_RELATIONSHIP_TYPES:
            return rtype
        return "related_to"

    def _validate_and_clean(self, raw: Dict) -> Dict:
        """Validate and clean LLM extraction output."""
        entities = []
        relationships = []

        raw_entities = raw.get("entities", [])
        if isinstance(raw_entities, list):
            for ent in raw_entities:
                if not isinstance(ent, dict):
                    continue
                name = str(ent.get("name", "")).strip()
                if not name or len(name) < 1 or len(name) > 100:
                    continue
                etype = self._normalize_entity_type(str(ent.get("type", "concept")))
                entities.append({"name": name, "type": etype})

        raw_rels = raw.get("relationships", [])
        if isinstance(raw_rels, list):
            for rel in raw_rels:
                if not isinstance(rel, dict):
                    continue
                source = str(rel.get("source", "")).strip()
                target = str(rel.get("target", "")).strip()
                rtype = self._normalize_relationship_type(str(rel.get("type", "related_to")))
                if source and target and len(source) <= 100 and len(target) <= 100:
                    relationships.append({"source": source, "type": rtype, "target": target})

        return {"entities": entities, "relationships": relationships}

    def extract_sync(self, text: str) -> Dict:
        """
        Synchronous entity/relationship extraction.

        Args:
            text: Text to extract from.

        Returns:
            Dict with 'entities' and 'relationships' lists.
            Returns empty lists on failure.
        """
        if not text or not text.strip():
            return {"entities": [], "relationships": []}

        # Check cache first
        cached = self._get_cached(text)
        if cached is not None:
            return cached

        if not self.is_available:
            return {"entities": [], "relationships": []}

        try:
            client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            prompt = _EXTRACTION_PROMPT.replace("{text}", text[:2000])

            # Exponential backoff with jitter on 429 responses
            # Start at 2s, max 60s, ±30% jitter
            backoff_base = 2.0
            backoff_max = 60.0
            backoff_attempt = 0
            max_retries = 5

            while True:
                try:
                    completion = client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=500,
                        temperature=0.1,
                        timeout=self.timeout,
                    )
                    break  # Success — exit retry loop
                except Exception as api_err:
                    err_str = str(api_err)
                    is_rate_limit = (
                        "429" in err_str
                        or "rate limit" in err_str.lower()
                        or "too many requests" in err_str.lower()
                    )
                    if is_rate_limit and backoff_attempt < max_retries:
                        delay = min(backoff_base * (2 ** backoff_attempt), backoff_max)
                        jitter = delay * 0.3 * (2 * random.random() - 1)  # ±30%
                        sleep_time = max(0.1, delay + jitter)
                        backoff_attempt += 1
                        logger.warning(
                            f"[LLM Extractor] Rate limited (429), retry {backoff_attempt}/{max_retries} "
                            f"in {sleep_time:.1f}s"
                        )
                        time.sleep(sleep_time)
                    else:
                        raise  # Non-429 error or exhausted retries

            raw_response = completion.choices[0].message.content.strip()

            # Handle markdown code blocks
            if raw_response.startswith("```"):
                raw_response = raw_response.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = json.loads(raw_response)
            if not isinstance(parsed, dict):
                logger.warning("[LLM Extractor] Response is not a dict")
                return {"entities": [], "relationships": []}

            result = self._validate_and_clean(parsed)
            self._set_cached(text, result)

            logger.info(
                f"[LLM Extractor] Extracted {len(result['entities'])} entities, "
                f"{len(result['relationships'])} relationships"
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"[LLM Extractor] JSON parse error: {e}")
        except Exception as e:
            logger.warning(f"[LLM Extractor] Error: {e}")

        empty = {"entities": [], "relationships": []}
        return empty

    async def extract(self, text: str) -> Dict:
        """
        Async entity/relationship extraction.
        Currently wraps sync version. Can be upgraded to async HTTP later.

        Args:
            text: Text to extract from.

        Returns:
            Dict with 'entities' and 'relationships' lists.
        """
        # For now, use sync version (OpenAI client is sync)
        # Can be upgraded to httpx async later if needed
        return self.extract_sync(text)

    def clear_cache(self):
        """Clear the extraction cache."""
        with self._lock:
            self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Current number of cached extractions."""
        with self._lock:
            return len(self._cache)


def merge_extractions(regex_result: Dict, llm_result: Dict) -> Dict:
    """
    Merge regex and LLM extraction results, deduplicating.

    Args:
        regex_result: Result from regex extraction (graph.py format).
        llm_result: Result from LLM extraction.

    Returns:
        Merged dict with deduplicated entities and relationships.
    """
    # Merge entities
    seen_entities = set()
    merged_entities = []

    # Regex entities are just names (strings)
    regex_entities = regex_result.get("entities", [])
    for ent in regex_entities:
        if isinstance(ent, str):
            key = ent.strip().lower()
            if key and key not in seen_entities:
                seen_entities.add(key)
                merged_entities.append(ent)
        elif isinstance(ent, dict):
            key = ent.get("name", "").strip().lower()
            if key and key not in seen_entities:
                seen_entities.add(key)
                merged_entities.append(ent.get("name", ""))

    # LLM entities are dicts with name/type
    llm_entities = llm_result.get("entities", [])
    for ent in llm_entities:
        if isinstance(ent, dict):
            key = ent.get("name", "").strip().lower()
            if key and key not in seen_entities:
                seen_entities.add(key)
                merged_entities.append(ent.get("name", ""))
        elif isinstance(ent, str):
            key = ent.strip().lower()
            if key and key not in seen_entities:
                seen_entities.add(key)
                merged_entities.append(ent)

    # Merge relationships
    seen_rels = set()
    merged_rels = []

    for rel_list in [regex_result.get("relationships", []), llm_result.get("relationships", [])]:
        for rel in rel_list:
            if not isinstance(rel, dict):
                continue
            source = rel.get("source", "").strip().lower()
            rtype = rel.get("type", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            key = (source, rtype, target)
            if key not in seen_rels and source and target:
                seen_rels.add(key)
                merged_rels.append(rel)

    return {"entities": merged_entities, "relationships": merged_rels}
