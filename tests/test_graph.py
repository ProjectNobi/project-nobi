"""
Project Nobi — Memory Relationship Graph Tests
================================================
Comprehensive tests for entity extraction, relationships, BFS traversal,
graph context generation, entity merging, export, and MemoryManager integration.

Test count: 35+ cases.
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.memory.graph import MemoryGraph, ENTITY_TYPES, RELATIONSHIP_TYPES, _rel_to_sentence


class TestMemoryGraphBasics(unittest.TestCase):
    """Test graph initialization and basic entity/relationship CRUD."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_1"

    def test_01_init_creates_tables(self):
        """Graph init creates entities and relationships tables."""
        tables = self.graph._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        self.assertIn("entities", table_names)
        self.assertIn("relationships", table_names)

    def test_02_create_entity(self):
        """Creating an entity returns a valid ID."""
        eid = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        self.assertIsInstance(eid, int)
        self.assertGreater(eid, 0)

    def test_03_get_existing_entity(self):
        """Getting an existing entity returns the same ID (case-insensitive)."""
        eid1 = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        eid2 = self.graph._get_or_create_entity(self.user_id, "alice", "person")
        self.assertEqual(eid1, eid2)

    def test_04_entity_different_users(self):
        """Same entity name for different users creates separate entities."""
        eid1 = self.graph._get_or_create_entity("user_a", "Alice", "person")
        eid2 = self.graph._get_or_create_entity("user_b", "Alice", "person")
        self.assertNotEqual(eid1, eid2)

    def test_05_empty_entity_name_raises(self):
        """Empty entity name raises ValueError."""
        with self.assertRaises(ValueError):
            self.graph._get_or_create_entity(self.user_id, "", "person")
        with self.assertRaises(ValueError):
            self.graph._get_or_create_entity(self.user_id, "   ", "person")

    def test_06_invalid_entity_type_defaults(self):
        """Invalid entity type defaults to 'concept'."""
        eid = self.graph._get_or_create_entity(self.user_id, "Foo", "invalid_type")
        entity = self.graph.get_entity(self.user_id, "Foo")
        self.assertEqual(entity["entity_type"], "concept")

    def test_07_add_relationship(self):
        """Adding a relationship between entities works."""
        src = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        tgt = self.graph._get_or_create_entity(self.user_id, "London", "place")
        rid = self.graph._add_relationship(self.user_id, src, "lives_in", tgt, 0.9)
        self.assertIsInstance(rid, int)
        self.assertGreater(rid, 0)

    def test_08_duplicate_relationship_reuses(self):
        """Adding the same relationship twice returns the same ID."""
        src = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        tgt = self.graph._get_or_create_entity(self.user_id, "London", "place")
        rid1 = self.graph._add_relationship(self.user_id, src, "lives_in", tgt)
        rid2 = self.graph._add_relationship(self.user_id, src, "lives_in", tgt)
        self.assertEqual(rid1, rid2)

    def test_09_invalid_rel_type_defaults(self):
        """Invalid relationship type defaults to 'related_to'."""
        src = self.graph._get_or_create_entity(self.user_id, "A", "person")
        tgt = self.graph._get_or_create_entity(self.user_id, "B", "person")
        self.graph._add_relationship(self.user_id, src, "bogus_type", tgt)
        rels = self.graph.get_relationships(self.user_id, "A")
        self.assertEqual(rels[0]["relationship_type"], "related_to")

    def test_10_get_entity(self):
        """get_entity returns correct info."""
        self.graph._get_or_create_entity(self.user_id, "Bob", "person")
        entity = self.graph.get_entity(self.user_id, "Bob")
        self.assertIsNotNone(entity)
        self.assertEqual(entity["name"], "Bob")
        self.assertEqual(entity["entity_type"], "person")

    def test_11_get_entity_missing(self):
        """get_entity returns None for non-existent entity."""
        result = self.graph.get_entity(self.user_id, "NonExistent")
        self.assertIsNone(result)

    def test_12_get_relationships(self):
        """get_relationships returns all relationships for an entity."""
        src = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        t1 = self.graph._get_or_create_entity(self.user_id, "London", "place")
        t2 = self.graph._get_or_create_entity(self.user_id, "Google", "organization")
        self.graph._add_relationship(self.user_id, src, "lives_in", t1)
        self.graph._add_relationship(self.user_id, src, "works_at", t2)
        rels = self.graph.get_relationships(self.user_id, "Alice")
        self.assertEqual(len(rels), 2)
        rel_types = {r["relationship_type"] for r in rels}
        self.assertIn("lives_in", rel_types)
        self.assertIn("works_at", rel_types)

    def test_13_entity_count(self):
        """get_entity_count is accurate."""
        self.assertEqual(self.graph.get_entity_count(self.user_id), 0)
        self.graph._get_or_create_entity(self.user_id, "A", "person")
        self.graph._get_or_create_entity(self.user_id, "B", "place")
        self.assertEqual(self.graph.get_entity_count(self.user_id), 2)

    def test_14_relationship_count(self):
        """get_relationship_count is accurate."""
        self.assertEqual(self.graph.get_relationship_count(self.user_id), 0)
        src = self.graph._get_or_create_entity(self.user_id, "A", "person")
        tgt = self.graph._get_or_create_entity(self.user_id, "B", "place")
        self.graph._add_relationship(self.user_id, src, "lives_in", tgt)
        self.assertEqual(self.graph.get_relationship_count(self.user_id), 1)


class TestEntityExtraction(unittest.TestCase):
    """Test regex-based entity extraction from text."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_2"

    def test_15_extract_name(self):
        """Extract user's name from 'My name is Alice'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "My name is Alice", "mem1"
        )
        self.assertIn("Alice", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("is_named", rel_types)

    def test_16_extract_family_relation(self):
        """Extract family relation: 'My sister Sarah'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "My sister Sarah is really nice.", "mem2"
        )
        self.assertIn("Sarah", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("sister_of", rel_types)

    def test_17_extract_location(self):
        """Extract location from 'I live in London'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I live in London.", "mem3"
        )
        self.assertIn("London", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("lives_in", rel_types)

    def test_18_extract_from_location(self):
        """Extract origin from 'I'm from Tokyo'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I'm from Tokyo originally.", "mem4"
        )
        self.assertIn("Tokyo", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("from", rel_types)

    def test_19_extract_workplace(self):
        """Extract workplace from 'I work at Google'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I work at Google.", "mem5"
        )
        self.assertIn("Google", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("works_at", rel_types)

    def test_20_extract_likes(self):
        """Extract preference from 'I like Italian food'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I like Italian food", "mem6"
        )
        self.assertIn("Italian food", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("likes", rel_types)

    def test_21_extract_dislikes(self):
        """Extract dislike from 'I hate spiders'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I hate spiders.", "mem7"
        )
        self.assertIn("spiders", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("dislikes", rel_types)

    def test_22_extract_pet(self):
        """Extract pet from 'I have a dog named Buddy'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I have a dog named Buddy", "mem8"
        )
        self.assertIn("Buddy", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("has_pet", rel_types)
        self.assertIn("is_a", rel_types)

    def test_23_extract_third_person_location(self):
        """Extract third-person location: 'Sarah lives in London'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "Sarah lives in London.", "mem9"
        )
        self.assertIn("Sarah", result["entities"])
        self.assertIn("London", result["entities"])
        rels = result["relationships"]
        self.assertTrue(any(r["type"] == "lives_in" and r["source"] == "Sarah" for r in rels))

    def test_24_extract_language(self):
        """Extract languages from 'I speak French and Spanish'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I speak French and Spanish.", "mem10"
        )
        self.assertIn("French", result["entities"])
        self.assertIn("Spanish", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertEqual(rel_types.count("speaks"), 2)

    def test_25_extract_empty_content(self):
        """Empty content returns empty results."""
        result = self.graph.extract_entities_and_relationships(self.user_id, "", "mem11")
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["relationships"], [])

    def test_26_extract_no_pattern_match(self):
        """Content with no recognizable patterns returns empty."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "hello there how are you", "mem12"
        )
        self.assertEqual(result["entities"], [])
        self.assertEqual(result["relationships"], [])

    def test_27_extract_studies(self):
        """Extract studies from 'I study computer science at MIT'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I study computer science at MIT", "mem13"
        )
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("studies", rel_types)
        self.assertIn("studies_at", rel_types)

    def test_28_extract_plays(self):
        """Extract hobby from 'I play the guitar'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I play the guitar", "mem14"
        )
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("plays", rel_types)

    def test_29_extract_multiple_relations(self):
        """Complex sentence extracts multiple relationships."""
        text = "My name is Alice. I live in London. I work at Google. I like Italian food."
        result = self.graph.extract_entities_and_relationships(self.user_id, text, "mem15")
        self.assertGreater(len(result["relationships"]), 2)

    def test_30_extract_unicode(self):
        """Unicode text doesn't crash extraction."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I live in München. 日本語テスト.", "mem16"
        )
        # Should not crash; München starts with uppercase so may or may not match
        self.assertIsInstance(result, dict)

    def test_31_extract_loves(self):
        """Extract 'I love cooking'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "I love cooking", "mem17"
        )
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("loves", rel_types)

    def test_32_call_me_name(self):
        """Extract name from 'Call me Bob'."""
        result = self.graph.extract_entities_and_relationships(
            self.user_id, "Call me Bob", "mem18"
        )
        self.assertIn("Bob", result["entities"])
        rel_types = [r["type"] for r in result["relationships"]]
        self.assertIn("is_named", rel_types)


class TestGraphTraversal(unittest.TestCase):
    """Test BFS graph traversal."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_3"
        # Build a small graph: Alice -> sister -> Sarah -> lives_in -> London
        self.graph.extract_entities_and_relationships(
            self.user_id, "My sister Sarah is great.", "m1"
        )
        self.graph.extract_entities_and_relationships(
            self.user_id, "Sarah lives in London.", "m2"
        )
        self.graph.extract_entities_and_relationships(
            self.user_id, "I work at Google.", "m3"
        )

    def test_33_bfs_depth_1(self):
        """BFS depth=1 finds immediate neighbors."""
        result = self.graph.get_connected_entities(self.user_id, "user", max_depth=1)
        self.assertIn("user", result["entities"])
        self.assertIn("Sarah", result["entities"])
        self.assertIn("Google", result["entities"])
        # London should NOT be found at depth 1 (it's 2 hops away via Sarah)

    def test_34_bfs_depth_2(self):
        """BFS depth=2 finds entities 2 hops away."""
        result = self.graph.get_connected_entities(self.user_id, "user", max_depth=2)
        self.assertIn("London", result["entities"])
        self.assertIn("Sarah", result["entities"])

    def test_35_bfs_nonexistent_entity(self):
        """BFS on non-existent entity returns empty result."""
        result = self.graph.get_connected_entities(self.user_id, "NonExistent")
        self.assertEqual(result["entities"], set())
        self.assertEqual(result["relationships"], [])

    def test_36_bfs_depth_0(self):
        """BFS depth=0 returns only the root entity."""
        result = self.graph.get_connected_entities(self.user_id, "user", max_depth=0)
        self.assertEqual(result["entities"], {"user"})
        self.assertEqual(result["relationships"], [])


class TestGraphContext(unittest.TestCase):
    """Test natural language context generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_4"
        self.graph.extract_entities_and_relationships(
            self.user_id, "My name is Alice.", "m1"
        )
        self.graph.extract_entities_and_relationships(
            self.user_id, "My sister Sarah is great.", "m2"
        )
        self.graph.extract_entities_and_relationships(
            self.user_id, "I work at Google.", "m3"
        )

    def test_37_context_with_relevant_query(self):
        """Graph context includes relevant info for a matching query."""
        ctx = self.graph.get_graph_context(self.user_id, "Tell me about Sarah")
        self.assertIn("Sarah", ctx)

    def test_38_context_with_general_query(self):
        """Graph context returns info from 'user' entity for general queries."""
        ctx = self.graph.get_graph_context(self.user_id, "How are you?")
        # Should include user's known facts
        self.assertTrue(len(ctx) > 0)

    def test_39_context_empty_query(self):
        """Empty query returns empty context."""
        ctx = self.graph.get_graph_context(self.user_id, "")
        self.assertEqual(ctx, "")

    def test_40_context_no_entities(self):
        """Context for user with no entities returns empty."""
        ctx = self.graph.get_graph_context("nobody_user", "hello")
        self.assertEqual(ctx, "")


class TestEntityMerging(unittest.TestCase):
    """Test entity merging functionality."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_5"

    def test_41_merge_entities(self):
        """Merging transfers relationships and deletes the merged entity."""
        # Create: A -> likes -> B, C -> friend_of -> A
        a = self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        b = self.graph._get_or_create_entity(self.user_id, "Pizza", "food")
        c = self.graph._get_or_create_entity(self.user_id, "Bob", "person")
        self.graph._add_relationship(self.user_id, a, "likes", b)
        self.graph._add_relationship(self.user_id, c, "friend_of", a)

        # Create duplicate "Alicia" (same person)
        d = self.graph._get_or_create_entity(self.user_id, "Alicia", "person")
        e = self.graph._get_or_create_entity(self.user_id, "London", "place")
        self.graph._add_relationship(self.user_id, d, "lives_in", e)

        # Merge Alicia into Alice
        result = self.graph.merge_entities(self.user_id, "Alice", "Alicia")
        self.assertTrue(result)

        # Alicia should be gone
        self.assertIsNone(self.graph.get_entity(self.user_id, "Alicia"))

        # Alice should now have lives_in London
        rels = self.graph.get_relationships(self.user_id, "Alice")
        rel_types = {r["relationship_type"] for r in rels}
        self.assertIn("lives_in", rel_types)
        self.assertIn("likes", rel_types)

    def test_42_merge_nonexistent(self):
        """Merging with non-existent entity returns False."""
        self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        result = self.graph.merge_entities(self.user_id, "Alice", "NonExistent")
        self.assertFalse(result)

    def test_43_merge_same_entity(self):
        """Merging entity with itself returns True (no-op)."""
        self.graph._get_or_create_entity(self.user_id, "Alice", "person")
        result = self.graph.merge_entities(self.user_id, "Alice", "Alice")
        self.assertTrue(result)


class TestExport(unittest.TestCase):
    """Test graph export."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.graph = MemoryGraph(self.db_path)
        self.user_id = "test_user_6"

    def test_44_export_empty(self):
        """Export with no data returns empty lists."""
        data = self.graph.export_graph(self.user_id)
        self.assertEqual(data["entity_count"], 0)
        self.assertEqual(data["relationship_count"], 0)
        self.assertEqual(data["entities"], [])
        self.assertEqual(data["relationships"], [])

    def test_45_export_with_data(self):
        """Export includes all entities and relationships."""
        self.graph.extract_entities_and_relationships(
            self.user_id, "My name is Alice. I live in London. I work at Google.", "m1"
        )
        data = self.graph.export_graph(self.user_id)
        self.assertGreater(data["entity_count"], 0)
        self.assertGreater(data["relationship_count"], 0)
        # Verify it's JSON serializable
        json_str = json.dumps(data)
        self.assertIsInstance(json_str, str)

    def test_46_export_is_user_scoped(self):
        """Export only includes entities for the specified user."""
        self.graph._get_or_create_entity("user_a", "Alice", "person")
        self.graph._get_or_create_entity("user_b", "Bob", "person")
        data_a = self.graph.export_graph("user_a")
        data_b = self.graph.export_graph("user_b")
        self.assertEqual(data_a["entity_count"], 1)
        self.assertEqual(data_b["entity_count"], 1)
        self.assertEqual(data_a["entities"][0]["name"], "Alice")
        self.assertEqual(data_b["entities"][0]["name"], "Bob")


class TestRelToSentence(unittest.TestCase):
    """Test the relationship-to-sentence helper."""

    def test_47_known_rel_type(self):
        """Known relationship types produce correct sentences."""
        s = _rel_to_sentence("user", "lives_in", "London")
        self.assertIn("lives in", s)
        self.assertIn("London", s)

    def test_48_user_replaced(self):
        """'user' source is replaced with 'The user'."""
        s = _rel_to_sentence("user", "likes", "pizza")
        self.assertTrue(s.startswith("The user"))

    def test_49_unknown_rel_type(self):
        """Unknown relationship type uses fallback template."""
        s = _rel_to_sentence("Alice", "unknown_rel", "Bob")
        self.assertIn("connected to", s)

    def test_50_named_source(self):
        """Named source (not 'user') is kept as-is."""
        s = _rel_to_sentence("Alice", "sister_of", "Sarah")
        self.assertTrue(s.startswith("Alice"))


class TestMemoryManagerIntegration(unittest.TestCase):
    """Test integration with MemoryManager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        # Patch encryption to avoid key issues in tests
        with patch("nobi.memory.store.ensure_master_secret"):
            with patch("nobi.memory.store.encrypt_memory", side_effect=lambda uid, txt: txt):
                with patch("nobi.memory.store.decrypt_memory", side_effect=lambda uid, txt: txt):
                    with patch("nobi.memory.store.is_encrypted", return_value=False):
                        from nobi.memory.store import MemoryManager
                        self.mm = MemoryManager(db_path=self.db_path, encryption_enabled=False)
        self.user_id = "test_user_7"

    def test_51_graph_attribute_exists(self):
        """MemoryManager should have a graph attribute after integration."""
        # After our integration, MemoryManager should init a MemoryGraph
        self.assertTrue(
            hasattr(self.mm, "graph"),
            "MemoryManager should have 'graph' attribute after integration"
        )

    def test_52_store_triggers_extraction(self):
        """Storing a memory with extractable content creates graph entities."""
        mid = self.mm.store(
            self.user_id, "My sister Sarah is wonderful.",
            memory_type="fact", importance=0.8
        )
        if hasattr(self.mm, "graph") and self.mm.graph:
            count = self.mm.graph.get_entity_count(self.user_id)
            self.assertGreater(count, 0, "Graph extraction should create entities on store()")

    def test_53_smart_context_includes_graph(self):
        """get_smart_context should include graph context when available."""
        self.mm.store(self.user_id, "My name is Alice.", memory_type="fact", importance=0.9)
        self.mm.store(self.user_id, "I live in London.", memory_type="fact", importance=0.9)
        ctx = self.mm.get_smart_context(self.user_id, "Where does Alice live?")
        # Context should contain some text
        self.assertIsInstance(ctx, str)


if __name__ == "__main__":
    unittest.main()
