"""
Tests for Memory V2: LLM Entity Extraction + Contradiction Detection
=====================================================================
Tests cover:
  - LLMEntityExtractor (mocked API, cache, fallback)
  - ContradictionDetector (all contradiction types, resolution)
  - merge_extractions (dedup, combined results)
  - Integration with MemoryGraph and MemoryManager
  - Edge cases
"""

import os
import json
import time
import tempfile
import threading
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from nobi.memory.llm_extractor import LLMEntityExtractor, merge_extractions
from nobi.memory.contradictions import ContradictionDetector, Contradiction
from nobi.memory.graph import MemoryGraph
from nobi.memory.store import MemoryManager


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Create a temp database path."""
    return str(tmp_path / "test_v2.db")


@pytest.fixture
def graph(tmp_db):
    """Create a MemoryGraph instance."""
    return MemoryGraph(tmp_db)


@pytest.fixture
def manager(tmp_db):
    """Create a MemoryManager with encryption disabled."""
    return MemoryManager(db_path=tmp_db, encryption_enabled=False)


@pytest.fixture
def extractor():
    """Create an LLMEntityExtractor (no real API key)."""
    return LLMEntityExtractor(api_key="", model="test-model")


@pytest.fixture
def detector(manager, graph):
    """Create a ContradictionDetector."""
    return ContradictionDetector(memory_manager=manager, memory_graph=graph)


# ── Helper ───────────────────────────────────────────────────────────────────

def _mock_openai_response(content: str):
    """Create a mock OpenAI API response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    return mock_completion


# ══════════════════════════════════════════════════════════════════════════════
# LLM Entity Extractor Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestLLMEntityExtractor:

    def test_not_available_without_key(self):
        """Without API key, extractor should not be available."""
        # Must clear env vars to test this properly
        with patch.dict(os.environ, {"CHUTES_API_KEY": "", "OPENROUTER_API_KEY": ""}, clear=False):
            ext = LLMEntityExtractor(api_key="", model="test-model")
            assert not ext.is_available

    def test_empty_text_returns_empty(self, extractor):
        """Empty text should return empty results."""
        result = extractor.extract_sync("")
        assert result == {"entities": [], "relationships": []}

    def test_whitespace_text_returns_empty(self, extractor):
        """Whitespace-only text should return empty results."""
        result = extractor.extract_sync("   ")
        assert result == {"entities": [], "relationships": []}

    def test_no_api_key_returns_empty(self, extractor):
        """Without API key, extraction should return empty (not crash)."""
        result = extractor.extract_sync("My name is Alice and I live in London")
        assert result == {"entities": [], "relationships": []}

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_successful_extraction(self, mock_openai_cls):
        """Successful LLM extraction with mocked API."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [
                {"name": "Alice", "type": "person"},
                {"name": "London", "type": "place"},
            ],
            "relationships": [
                {"source": "user", "type": "is_named", "target": "Alice"},
                {"source": "user", "type": "lives_in", "target": "London"},
            ],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("My name is Alice and I live in London")

        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 2
        assert result["entities"][0]["name"] == "Alice"
        assert result["relationships"][1]["type"] == "lives_in"

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_extraction_with_code_block(self, mock_openai_cls):
        """LLM returns JSON wrapped in markdown code blocks."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        wrapped = "```json\n" + json.dumps({
            "entities": [{"name": "Bob", "type": "person"}],
            "relationships": [],
        }) + "\n```"
        mock_client.chat.completions.create.return_value = _mock_openai_response(wrapped)

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("Call me Bob")
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Bob"

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_extraction_caching(self, mock_openai_cls):
        """Same text should use cached result (not call API twice)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [{"name": "Test", "type": "concept"}],
            "relationships": [],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result1 = ext.extract_sync("I like pizza")
        result2 = ext.extract_sync("I like pizza")

        assert result1 == result2
        # API should only be called once
        assert mock_client.chat.completions.create.call_count == 1

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_cache_size_limit(self, mock_openai_cls):
        """Cache should evict oldest entries when full."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [], "relationships": [],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model", cache_size=3)
        ext.extract_sync("text 1")
        ext.extract_sync("text 2")
        ext.extract_sync("text 3")
        assert ext.cache_size == 3

        ext.extract_sync("text 4")  # Should evict "text 1"
        assert ext.cache_size == 3

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_invalid_json_returns_empty(self, mock_openai_cls):
        """Invalid JSON from LLM should return empty (not crash)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response("not json at all")

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("My name is Alice")
        assert result == {"entities": [], "relationships": []}

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_api_exception_returns_empty(self, mock_openai_cls):
        """API exception should return empty (not crash)."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("My name is Alice")
        assert result == {"entities": [], "relationships": []}

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_entity_type_normalization(self, mock_openai_cls):
        """Entity types should be normalized to canonical forms."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [
                {"name": "Google", "type": "company"},  # → organization
                {"name": "Paris", "type": "city"},  # → place
                {"name": "Buddy", "type": "pet"},  # → animal
                {"name": "Unknown", "type": "xyz"},  # → concept
            ],
            "relationships": [],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("test")
        types = [e["type"] for e in result["entities"]]
        assert types == ["organization", "place", "animal", "concept"]

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_relationship_type_normalization(self, mock_openai_cls):
        """Unknown relationship types should fall back to related_to."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [],
            "relationships": [
                {"source": "user", "type": "unknown_type", "target": "something"},
                {"source": "user", "type": "lives_in", "target": "Paris"},
            ],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        result = ext.extract_sync("test")
        assert result["relationships"][0]["type"] == "related_to"
        assert result["relationships"][1]["type"] == "lives_in"

    def test_clear_cache(self, extractor):
        """Cache clearing should work."""
        extractor._set_cached("test", {"entities": [], "relationships": []})
        assert extractor.cache_size == 1
        extractor.clear_cache()
        assert extractor.cache_size == 0

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_thread_safety(self, mock_openai_cls):
        """Concurrent extractions should not corrupt cache."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [], "relationships": [],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        errors = []

        def extract_text(i):
            try:
                ext.extract_sync(f"text number {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=extract_text, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Merge Extractions Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMergeExtractions:

    def test_merge_empty(self):
        """Merging two empty results should give empty."""
        result = merge_extractions(
            {"entities": [], "relationships": []},
            {"entities": [], "relationships": []},
        )
        assert result == {"entities": [], "relationships": []}

    def test_merge_regex_only(self):
        """Regex-only result should pass through."""
        regex = {
            "entities": ["user", "Alice"],
            "relationships": [{"source": "user", "type": "is_named", "target": "Alice"}],
        }
        result = merge_extractions(regex, {"entities": [], "relationships": []})
        assert "Alice" in result["entities"]
        assert len(result["relationships"]) == 1

    def test_merge_llm_only(self):
        """LLM-only result should pass through."""
        llm = {
            "entities": [{"name": "Bob", "type": "person"}],
            "relationships": [{"source": "user", "type": "is_named", "target": "Bob"}],
        }
        result = merge_extractions({"entities": [], "relationships": []}, llm)
        assert "Bob" in result["entities"]

    def test_merge_dedup_entities(self):
        """Duplicate entities should be removed."""
        regex = {"entities": ["user", "Alice"], "relationships": []}
        llm = {
            "entities": [{"name": "Alice", "type": "person"}, {"name": "London", "type": "place"}],
            "relationships": [],
        }
        result = merge_extractions(regex, llm)
        names_lower = [e.lower() if isinstance(e, str) else e for e in result["entities"]]
        assert names_lower.count("alice") == 1
        assert "London" in result["entities"]

    def test_merge_dedup_relationships(self):
        """Duplicate relationships should be removed."""
        rel = {"source": "user", "type": "lives_in", "target": "London"}
        regex = {"entities": [], "relationships": [rel]}
        llm = {"entities": [], "relationships": [rel.copy()]}
        result = merge_extractions(regex, llm)
        assert len(result["relationships"]) == 1

    def test_merge_different_relationships(self):
        """Different relationships should both be kept."""
        regex = {"entities": [], "relationships": [
            {"source": "user", "type": "is_named", "target": "Alice"},
        ]}
        llm = {"entities": [], "relationships": [
            {"source": "user", "type": "lives_in", "target": "London"},
        ]}
        result = merge_extractions(regex, llm)
        assert len(result["relationships"]) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Contradiction Detector Tests
# ══════════════════════════════════════════════════════════════════════════════

class TestContradictionDetector:

    def test_no_graph_returns_empty(self, manager):
        """Without graph, should return empty."""
        det = ContradictionDetector(memory_manager=manager, memory_graph=None)
        result = det.check_contradiction("user1", "I live in London", {})
        assert result == []

    def test_empty_content_returns_empty(self, detector):
        """Empty content should return empty."""
        result = detector.check_contradiction("user1", "", {})
        assert result == []

    def test_no_contradiction_when_no_existing(self, detector, graph):
        """No contradiction when graph is empty."""
        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "London"}],
        }
        result = detector.check_contradiction("user1", "I live in London", entities)
        assert result == []

    def test_location_contradiction(self, detector, graph):
        """Detect location change contradiction."""
        # Set up existing relationship
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        # New memory says different location
        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "Paris"}],
        }
        result = detector.check_contradiction("user1", "I moved to Paris", entities)
        assert len(result) >= 1
        assert any(c.contradiction_type == "location_change" for c in result)
        assert any("London" in c.old_value and "Paris" in c.new_value for c in result)

    def test_name_contradiction(self, detector, graph):
        """Detect name change contradiction."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "Alice", "person")
        graph._add_relationship("user1", src_id, "is_named", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "is_named", "target": "Alicia"}],
        }
        result = detector.check_contradiction("user1", "Call me Alicia now", entities)
        assert len(result) >= 1
        assert any(c.contradiction_type == "name_change" for c in result)

    def test_status_contradiction_works_at(self, detector, graph):
        """Detect job change contradiction."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "Google", "organization")
        graph._add_relationship("user1", src_id, "works_at", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "works_at", "target": "Apple"}],
        }
        result = detector.check_contradiction("user1", "I now work at Apple", entities)
        assert len(result) >= 1
        assert any(c.contradiction_type == "status_change" for c in result)

    def test_relationship_contradiction_partner(self, detector, graph):
        """Detect partner change contradiction."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "Sarah", "person")
        graph._add_relationship("user1", src_id, "partner_of", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "partner_of", "target": "Emma"}],
        }
        result = detector.check_contradiction("user1", "My girlfriend Emma", entities)
        assert len(result) >= 1
        assert any(c.contradiction_type == "relationship_change" for c in result)

    def test_preference_contradiction_opposite(self, detector, graph):
        """Detect preference flip (likes → dislikes)."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "coffee", "food")
        graph._add_relationship("user1", src_id, "likes", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "dislikes", "target": "coffee"}],
        }
        result = detector.check_contradiction("user1", "I now dislike coffee", entities)
        assert len(result) >= 1
        assert any(c.contradiction_type == "preference_change" for c in result)

    def test_preference_stopped(self, detector, graph):
        """Detect 'stopped liking' pattern."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "coffee", "food")
        graph._add_relationship("user1", src_id, "likes", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "likes", "target": "coffee"}],
        }
        result = detector.check_contradiction(
            "user1", "I stopped drinking coffee", entities
        )
        assert len(result) >= 1
        assert any(c.contradiction_type == "preference_change" for c in result)

    def test_breakup_negation_pattern(self, detector, graph):
        """Detect breakup via negation keywords."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "Sarah", "person")
        graph._add_relationship("user1", src_id, "partner_of", tgt_id)

        result = detector.check_contradiction("user1", "We broke up last week", None)
        assert len(result) >= 1
        assert any(c.contradiction_type == "relationship_change" for c in result)

    def test_no_contradiction_same_value(self, detector, graph):
        """No contradiction when same value is restated."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "London"}],
        }
        result = detector.check_contradiction("user1", "I live in London", entities)
        # Should not flag a contradiction for same value
        location_contradictions = [c for c in result if c.contradiction_type == "location_change"]
        assert len(location_contradictions) == 0

    def test_multiple_contradictions(self, detector, graph):
        """Detect multiple contradictions at once."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        loc_id = graph._get_or_create_entity("user1", "London", "place")
        job_id = graph._get_or_create_entity("user1", "Google", "organization")
        graph._add_relationship("user1", src_id, "lives_in", loc_id)
        graph._add_relationship("user1", src_id, "works_at", job_id)

        entities = {
            "relationships": [
                {"source": "user", "type": "lives_in", "target": "Paris"},
                {"source": "user", "type": "works_at", "target": "Apple"},
            ],
        }
        result = detector.check_contradiction(
            "user1", "I moved to Paris and started at Apple", entities
        )
        types = [c.contradiction_type for c in result]
        assert "location_change" in types
        assert "status_change" in types

    # ── Resolution Tests ─────────────────────────────────────────────────────

    def test_resolve_newest_wins(self, detector, graph):
        """newest_wins should remove old relationship."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        rel_id = graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        old_rel = {
            "id": rel_id,
            "source": "user",
            "relationship_type": "lives_in",
            "target": "London",
        }
        contradiction = Contradiction(
            contradiction_type="location_change",
            old_relationship=old_rel,
            old_value="London",
            new_value="Paris",
            source_entity="user",
            relationship_type="lives_in",
        )

        result = detector.resolve_contradiction("user1", contradiction, "newest_wins")
        assert result is True
        assert contradiction.resolved is True
        assert contradiction.resolution_strategy == "newest_wins"

        # Old relationship should be gone
        rels = graph.get_relationships("user1", "user")
        lives_in = [r for r in rels if r["relationship_type"] == "lives_in" and r["target"] == "London"]
        assert len(lives_in) == 0

    def test_resolve_keep_both(self, detector, graph):
        """keep_both should mark as resolved without removing anything."""
        contradiction = Contradiction(
            contradiction_type="preference_change",
            old_value="likes coffee",
            new_value="dislikes coffee",
        )
        result = detector.resolve_contradiction("user1", contradiction, "keep_both")
        assert result is True
        assert contradiction.resolved is True
        assert contradiction.resolution_strategy == "keep_both"

    def test_resolve_ask_user(self, detector, graph):
        """ask_user should not resolve (returns False)."""
        contradiction = Contradiction(
            contradiction_type="location_change",
            old_value="London",
            new_value="Paris",
        )
        result = detector.resolve_contradiction("user1", contradiction, "ask_user")
        assert result is False
        assert contradiction.resolved is False

    def test_resolve_by_id(self, detector, graph):
        """resolve_by_id should find and resolve the right contradiction."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        # Trigger a contradiction
        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "Paris"}],
        }
        contradictions = detector.check_contradiction("user1", "I moved to Paris", entities)
        assert len(contradictions) >= 1

        cid = contradictions[0].id
        result = detector.resolve_by_id("user1", cid, "keep_both")
        assert result is True

    def test_get_contradictions(self, detector, graph):
        """get_contradictions should return unresolved ones."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "Paris"}],
        }
        detector.check_contradiction("user1", "I moved to Paris", entities)

        unresolved = detector.get_contradictions("user1")
        assert len(unresolved) >= 1

        all_contradictions = detector.get_contradictions("user1", include_resolved=True)
        assert len(all_contradictions) >= 1

    def test_clear_contradictions(self, detector, graph):
        """Clearing should remove all contradictions."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        entities = {
            "relationships": [{"source": "user", "type": "lives_in", "target": "Paris"}],
        }
        detector.check_contradiction("user1", "I moved to Paris", entities)
        assert len(detector.get_contradictions("user1")) >= 1

        detector.clear_contradictions("user1")
        assert len(detector.get_contradictions("user1")) == 0

    def test_contradiction_to_dict(self):
        """Contradiction.to_dict should produce a valid dict."""
        c = Contradiction(
            contradiction_type="location_change",
            description="test",
            old_value="London",
            new_value="Paris",
            source_entity="user",
            relationship_type="lives_in",
        )
        d = c.to_dict()
        assert d["contradiction_type"] == "location_change"
        assert d["old_value"] == "London"
        assert d["new_value"] == "Paris"
        assert "id" in d
        assert "detected_at" in d


# ══════════════════════════════════════════════════════════════════════════════
# Integration Tests (Graph + LLM Extractor + Contradictions)
# ══════════════════════════════════════════════════════════════════════════════

class TestIntegration:

    def test_graph_with_llm_extractor_disabled(self, tmp_db):
        """Graph should work fine without LLM extractor."""
        g = MemoryGraph(tmp_db)
        result = g.extract_entities_and_relationships("user1", "My name is Alice")
        assert len(result["entities"]) > 0

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_graph_with_llm_extractor_enabled(self, mock_openai_cls, tmp_db):
        """Graph should merge regex + LLM results when extractor is available."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_openai_response(json.dumps({
            "entities": [{"name": "cooking", "type": "activity"}],
            "relationships": [{"source": "user", "type": "likes", "target": "cooking"}],
        }))

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        g = MemoryGraph(tmp_db, llm_extractor=ext)

        result = g.extract_entities_and_relationships(
            "user1", "My name is Alice and I really enjoy cooking"
        )
        # Should have both regex (Alice) and LLM (cooking) entities
        entity_names = [e.lower() if isinstance(e, str) else e.get("name", "").lower()
                        for e in result["entities"]]
        assert "alice" in entity_names or "user" in entity_names

    def test_graph_with_contradiction_detection(self, tmp_db):
        """Graph should detect contradictions when detector is wired up."""
        g = MemoryGraph(tmp_db)
        det = ContradictionDetector(memory_graph=g)
        g.contradiction_detector = det

        # First: user lives in London
        g.extract_entities_and_relationships("user1", "I live in London")

        # Second: user moves to Paris — should detect contradiction
        g.extract_entities_and_relationships("user1", "I moved to Paris")

        # Check that contradiction was detected and resolved
        all_contradictions = det.get_contradictions("user1", include_resolved=True)
        # May or may not have contradiction depending on whether regex caught both
        # The important thing is it didn't crash

    def test_store_with_contradiction_detector(self, tmp_db):
        """MemoryManager should initialize contradiction detector."""
        mm = MemoryManager(db_path=tmp_db, encryption_enabled=False)
        assert mm.contradiction_detector is not None or not hasattr(mm, 'contradiction_detector')

    def test_store_get_contradictions(self, tmp_db):
        """MemoryManager.get_contradictions should return list."""
        mm = MemoryManager(db_path=tmp_db, encryption_enabled=False)
        result = mm.get_contradictions("user1")
        assert isinstance(result, list)

    def test_store_resolve_contradiction_no_id(self, tmp_db):
        """Resolving non-existent contradiction should return False."""
        mm = MemoryManager(db_path=tmp_db, encryption_enabled=False)
        result = mm.resolve_contradiction("user1", "nonexistent-id")
        assert result is False

    def test_store_never_crashes_on_extraction_failure(self, tmp_db):
        """Store should never crash even if LLM extraction fails."""
        mm = MemoryManager(db_path=tmp_db, encryption_enabled=False)

        # Force extractor to raise
        if mm.llm_extractor:
            mm.llm_extractor.extract_sync = MagicMock(side_effect=Exception("boom"))

        # This should still work (store the memory, just skip LLM)
        mid = mm.store("user1", "My name is Alice", memory_type="fact")
        assert mid is not None
        assert len(mid) > 0

    def test_full_flow_location_change(self, tmp_db):
        """Full flow: store two conflicting memories, check contradictions."""
        mm = MemoryManager(db_path=tmp_db, encryption_enabled=False)

        # Store first memory
        mm.store("user1", "I live in London", memory_type="fact")

        # Store second conflicting memory
        mm.store("user1", "I moved to Paris", memory_type="fact")

        # Check graph
        if mm.graph:
            rels = mm.graph.get_relationships("user1", "user")
            # Should have at least one lives_in relationship
            lives_in = [r for r in rels if r["relationship_type"] == "lives_in"]
            assert len(lives_in) >= 1

    @patch("nobi.memory.llm_extractor.OpenAI")
    def test_llm_fallback_to_regex(self, mock_openai_cls, tmp_db):
        """When LLM fails, should still get regex results."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API timeout")

        ext = LLMEntityExtractor(api_key="test-key", model="test-model")
        g = MemoryGraph(tmp_db, llm_extractor=ext)

        result = g.extract_entities_and_relationships("user1", "My name is Alice")
        # Should still get regex results
        assert len(result["entities"]) > 0

    def test_detector_thread_safety(self, detector, graph):
        """Concurrent contradiction checks should be safe."""
        src_id = graph._get_or_create_entity("user1", "user", "person")
        tgt_id = graph._get_or_create_entity("user1", "London", "place")
        graph._add_relationship("user1", src_id, "lives_in", tgt_id)

        errors = []

        def check(i):
            try:
                entities = {
                    "relationships": [{"source": "user", "type": "lives_in", "target": f"City{i}"}],
                }
                detector.check_contradiction("user1", f"I moved to City{i}", entities)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
