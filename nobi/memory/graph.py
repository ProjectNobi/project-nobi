"""
Project Nobi — Memory Relationship Graph
==========================================
SQLite-based entity-relationship graph for connecting facts about users.

Extracts entities (people, places, organizations, etc.) and relationships
from memory content using regex patterns with optional LLM fallback.
Provides BFS graph traversal, natural language context generation,
entity merging, and full graph export.

Storage: Same SQLite database as MemoryManager (lightweight, no external deps).
Thread-safe via thread-local connections.
"""

import os
import re
import json
import time
import logging
import sqlite3
import threading
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger("nobi-memory-graph")

# ── Constants ─────────────────────────────────────────────────────────────────

ENTITY_TYPES = frozenset({
    "person", "place", "organization", "animal", "object",
    "concept", "event", "food", "activity", "language",
})

RELATIONSHIP_TYPES = frozenset({
    "is_a", "is_named", "has", "likes", "dislikes", "loves",
    "lives_in", "from", "works_at", "works_as",
    "related_to", "sibling_of", "sister_of", "brother_of",
    "parent_of", "child_of", "mother_of", "father_of",
    "friend_of", "partner_of", "married_to",
    "owns", "has_pet", "studies", "studies_at",
    "plays", "speaks", "born_on", "born_in",
    "interested_in", "member_of", "uses",
})

# Family relation words → relationship_type mapping
_FAMILY_RELATIONS = {
    "sister": "sister_of", "brother": "brother_of",
    "mom": "mother_of", "mother": "mother_of",
    "dad": "father_of", "father": "father_of",
    "son": "child_of", "daughter": "child_of",
    "wife": "married_to", "husband": "married_to",
    "partner": "partner_of", "girlfriend": "partner_of",
    "boyfriend": "partner_of", "fiancé": "partner_of",
    "fiancée": "partner_of", "fiance": "partner_of",
    "uncle": "related_to", "aunt": "related_to",
    "cousin": "related_to", "grandma": "related_to",
    "grandpa": "related_to", "grandmother": "related_to",
    "grandfather": "related_to", "niece": "related_to",
    "nephew": "related_to", "friend": "friend_of",
    "best friend": "friend_of", "roommate": "related_to",
    "colleague": "related_to", "boss": "related_to",
    "teacher": "related_to", "mentor": "related_to",
}


class MemoryGraph:
    """
    SQLite-backed entity-relationship graph for user memories.

    Stores entities (people, places, things) and typed relationships
    between them. Supports BFS traversal, natural language context
    generation, and entity merging.

    Optional LLM extraction supplements regex patterns for richer results.
    Optional contradiction detection flags conflicting information.
    """

    def __init__(self, db_path: str, llm_extractor=None, contradiction_detector=None):
        """
        Initialize the MemoryGraph.

        Args:
            db_path: Path to SQLite database file (shared with MemoryManager).
            llm_extractor: Optional LLMEntityExtractor instance.
            contradiction_detector: Optional ContradictionDetector instance.
        """
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._local = threading.local()
        self.llm_extractor = llm_extractor
        self.contradiction_detector = contradiction_detector
        self._init_tables()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, timeout=30)
            self._local.conn.execute("PRAGMA busy_timeout=10000")
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_tables(self):
        """Create graph tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'concept',
                first_seen TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                UNIQUE(user_id, name COLLATE NOCASE)
            );

            CREATE INDEX IF NOT EXISTS idx_entities_user
                ON entities(user_id);
            CREATE INDEX IF NOT EXISTS idx_entities_name
                ON entities(user_id, name COLLATE NOCASE);

            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                source_entity_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,
                target_entity_id INTEGER NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                source_memory_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_rel_user
                ON relationships(user_id);
            CREATE INDEX IF NOT EXISTS idx_rel_source
                ON relationships(source_entity_id);
            CREATE INDEX IF NOT EXISTS idx_rel_target
                ON relationships(target_entity_id);
        """)
        self._conn.commit()

    # ── Entity CRUD ───────────────────────────────────────────────────────────

    def _get_or_create_entity(
        self, user_id: str, name: str, entity_type: str = "concept"
    ) -> int:
        """
        Get existing entity ID or create a new one.

        Args:
            user_id: User who owns this entity.
            name: Entity name (case-insensitive lookup).
            entity_type: One of ENTITY_TYPES.

        Returns:
            Entity row ID.
        """
        name = name.strip()
        if not name:
            raise ValueError("Entity name cannot be empty")

        if entity_type not in ENTITY_TYPES:
            entity_type = "concept"

        conn = self._conn
        row = conn.execute(
            "SELECT id FROM entities WHERE user_id = ? AND name = ? COLLATE NOCASE",
            (user_id, name),
        ).fetchone()

        if row:
            return row["id"]

        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO entities (user_id, name, entity_type, first_seen) VALUES (?, ?, ?, ?)",
            (user_id, name, entity_type, now),
        )
        conn.commit()
        return cursor.lastrowid

    def _add_relationship(
        self,
        user_id: str,
        source_id: int,
        rel_type: str,
        target_id: int,
        confidence: float = 1.0,
        memory_id: Optional[str] = None,
    ) -> int:
        """
        Add a relationship between two entities. Avoids exact duplicates.

        Returns:
            Relationship row ID (existing or new).
        """
        if rel_type not in RELATIONSHIP_TYPES:
            rel_type = "related_to"

        conn = self._conn
        # Check for existing identical relationship
        existing = conn.execute(
            """SELECT id FROM relationships
               WHERE user_id = ? AND source_entity_id = ?
               AND relationship_type = ? AND target_entity_id = ?""",
            (user_id, source_id, rel_type, target_id),
        ).fetchone()

        if existing:
            return existing["id"]

        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            """INSERT INTO relationships
               (user_id, source_entity_id, relationship_type, target_entity_id,
                confidence, source_memory_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, source_id, rel_type, target_id,
             max(0.0, min(1.0, confidence)), memory_id, now),
        )
        conn.commit()
        return cursor.lastrowid

    # ── Entity Extraction (Regex) ─────────────────────────────────────────────

    def extract_entities_and_relationships(
        self, user_id: str, memory_content: str, memory_id: Optional[str] = None
    ) -> dict:
        """
        Parse memory content to extract entities and relationships using regex.

        Args:
            user_id: User who owns this memory.
            memory_content: Raw text of the memory.
            memory_id: Optional memory ID for provenance tracking.

        Returns:
            Dict with 'entities' (list of names) and 'relationships' (list of dicts).
        """
        if not memory_content or not memory_content.strip():
            return {"entities": [], "relationships": []}

        extracted_entities: List[str] = []
        extracted_relationships: List[dict] = []
        text = memory_content.strip()

        try:
            # --- Pattern 1: "My [relation] [Name]" / "My [relation]'s name is [Name]" ---
            for pattern in [
                r"[Mm]y\s+([\w\s]+?)\s+(?:is\s+)?(?:called\s+|named\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                r"[Mm]y\s+([\w\s]+?)'s\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            ]:
                for match in re.finditer(pattern, text):
                    relation_word = match.group(1).strip().lower()
                    name = match.group(2).strip()
                    if relation_word in _FAMILY_RELATIONS and len(name) > 1:
                        rel_type = _FAMILY_RELATIONS[relation_word]
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        tgt_id = self._get_or_create_entity(user_id, name, "person")
                        self._add_relationship(user_id, src_id, rel_type, tgt_id, 0.9, memory_id)
                        extracted_entities.extend(["user", name])
                        extracted_relationships.append({
                            "source": "user", "type": rel_type, "target": name,
                        })

            # --- Pattern 2: "My name is [Name]" / "I'm [Name]" / "Call me [Name]" ---
            for pattern in [
                r"[Mm]y\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                r"[Cc]all\s+me\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            ]:
                match = re.search(pattern, text)
                if match:
                    name = match.group(1).strip()
                    skip_names = {"sorry", "fine", "good", "okay", "well", "sure", "happy"}
                    if name.lower() not in skip_names and 1 < len(name) < 30:
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        tgt_id = self._get_or_create_entity(user_id, name, "person")
                        self._add_relationship(user_id, src_id, "is_named", tgt_id, 1.0, memory_id)
                        extracted_entities.extend(["user", name])
                        extracted_relationships.append({
                            "source": "user", "type": "is_named", "target": name,
                        })

            # --- Pattern 3: Lives in / From ---
            for pattern, rel in [
                (r"(?:I\s+live\s+in|I'm\s+based\s+in|I\s+moved\s+to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "lives_in"),
                (r"(?:I'm\s+from|I\s+am\s+from|I\s+come\s+from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "from"),
            ]:
                match = re.search(pattern, text)
                if match:
                    place = match.group(1).strip()
                    if len(place) > 1:
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        tgt_id = self._get_or_create_entity(user_id, place, "place")
                        self._add_relationship(user_id, src_id, rel, tgt_id, 0.9, memory_id)
                        extracted_entities.extend(["user", place])
                        extracted_relationships.append({
                            "source": "user", "type": rel, "target": place,
                        })

            # --- Pattern 3b: "[Name] lives in [Place]" (third-person) ---
            for match in re.finditer(
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+lives?\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                text,
            ):
                person = match.group(1).strip()
                place = match.group(2).strip()
                if len(person) > 1 and len(place) > 1:
                    src_id = self._get_or_create_entity(user_id, person, "person")
                    tgt_id = self._get_or_create_entity(user_id, place, "place")
                    self._add_relationship(user_id, src_id, "lives_in", tgt_id, 0.8, memory_id)
                    extracted_entities.extend([person, place])
                    extracted_relationships.append({
                        "source": person, "type": "lives_in", "target": place,
                    })

            # --- Pattern 4: Works at / Works as ---
            match = re.search(
                r"I\s+work\s+at\s+([A-Z][\w\s&]+?)(?:\.|,|!|\?|$)", text
            )
            if match:
                org = match.group(1).strip()
                if 1 < len(org) < 60:
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    tgt_id = self._get_or_create_entity(user_id, org, "organization")
                    self._add_relationship(user_id, src_id, "works_at", tgt_id, 0.9, memory_id)
                    extracted_entities.extend(["user", org])
                    extracted_relationships.append({
                        "source": "user", "type": "works_at", "target": org,
                    })

            match = re.search(
                r"I(?:'m| am) (?:a|an)\s+([\w\s]+?)(?:\.|,|!|\?|$| at| in| for)", text, re.IGNORECASE
            )
            if match:
                role = match.group(1).strip()
                skip_roles = {"feeling", "doing", "going", "trying", "looking",
                              "bit", "little", "very", "so", "really", "just",
                              "not", "also", "still", "currently", "vegetarian"}
                if role.split()[0].lower() not in skip_roles and 2 < len(role) < 40:
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    tgt_id = self._get_or_create_entity(user_id, role, "concept")
                    self._add_relationship(user_id, src_id, "works_as", tgt_id, 0.8, memory_id)
                    extracted_entities.extend(["user", role])
                    extracted_relationships.append({
                        "source": "user", "type": "works_as", "target": role,
                    })

            # --- Pattern 5: Pets ---
            for pattern in [
                r"I\s+have\s+(?:a\s+)?(dog|cat|bird|fish|hamster|rabbit|turtle|snake|parrot|guinea pig)\s+(?:named|called)\s+([A-Z][a-z]+)",
                r"[Mm]y\s+(dog|cat|bird|fish|hamster|rabbit|turtle|snake|parrot|guinea pig)(?:'s name is|,?\s+)\s*([A-Z][a-z]+)",
            ]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    animal_type = match.group(1).strip().lower()
                    pet_name = match.group(2).strip()
                    if len(pet_name) > 1:
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        pet_id = self._get_or_create_entity(user_id, pet_name, "animal")
                        type_id = self._get_or_create_entity(user_id, animal_type, "animal")
                        self._add_relationship(user_id, src_id, "has_pet", pet_id, 0.9, memory_id)
                        self._add_relationship(user_id, pet_id, "is_a", type_id, 1.0, memory_id)
                        extracted_entities.extend(["user", pet_name, animal_type])
                        extracted_relationships.append({
                            "source": "user", "type": "has_pet", "target": pet_name,
                        })
                        extracted_relationships.append({
                            "source": pet_name, "type": "is_a", "target": animal_type,
                        })

            # --- Pattern 5b: More general pet pattern ---
            match = re.search(
                r"I\s+have\s+(?:a\s+)?(\w+(?:\s+\w+)?)\s+named\s+([A-Z][a-z]+)", text
            )
            if match:
                thing_type = match.group(1).strip().lower()
                thing_name = match.group(2).strip()
                animal_words = {"dog", "cat", "bird", "fish", "hamster", "rabbit",
                                "turtle", "snake", "parrot", "guinea pig", "puppy",
                                "kitten", "golden retriever", "labrador", "poodle"}
                if thing_type in animal_words and len(thing_name) > 1:
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    pet_id = self._get_or_create_entity(user_id, thing_name, "animal")
                    type_id = self._get_or_create_entity(user_id, thing_type, "animal")
                    self._add_relationship(user_id, src_id, "has_pet", pet_id, 0.9, memory_id)
                    self._add_relationship(user_id, pet_id, "is_a", type_id, 1.0, memory_id)
                    extracted_entities.extend(["user", thing_name, thing_type])
                    extracted_relationships.append({
                        "source": "user", "type": "has_pet", "target": thing_name,
                    })

            # --- Pattern 6: Likes / Loves / Dislikes ---
            for pattern, rel in [
                (r"I\s+(?:really\s+)?(?:like|enjoy)\s+(.+?)(?:\.|,|!|\?|$)", "likes"),
                (r"I\s+(?:really\s+)?love\s+(.+?)(?:\.|,|!|\?|$)", "loves"),
                (r"I\s+(?:hate|dislike|can't stand)\s+(.+?)(?:\.|,|!|\?|$)", "dislikes"),
            ]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    thing = match.group(1).strip()
                    if 1 < len(thing) < 60:
                        # Guess entity type
                        etype = _guess_entity_type(thing)
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        tgt_id = self._get_or_create_entity(user_id, thing, etype)
                        self._add_relationship(user_id, src_id, rel, tgt_id, 0.8, memory_id)
                        extracted_entities.extend(["user", thing])
                        extracted_relationships.append({
                            "source": "user", "type": rel, "target": thing,
                        })

            # --- Pattern 7: Studies / Studies at ---
            match = re.search(
                r"I\s+(?:study|am studying)\s+(.+?)(?:\s+at\s+(.+?))?(?:\.|,|!|\?|$)",
                text, re.IGNORECASE,
            )
            if match:
                subject = match.group(1).strip()
                school = match.group(2)
                if subject and 1 < len(subject) < 60:
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    tgt_id = self._get_or_create_entity(user_id, subject, "concept")
                    self._add_relationship(user_id, src_id, "studies", tgt_id, 0.8, memory_id)
                    extracted_entities.extend(["user", subject])
                    extracted_relationships.append({
                        "source": "user", "type": "studies", "target": subject,
                    })
                if school and 1 < len(school.strip()) < 60:
                    school = school.strip()
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    tgt_id = self._get_or_create_entity(user_id, school, "organization")
                    self._add_relationship(user_id, src_id, "studies_at", tgt_id, 0.8, memory_id)
                    extracted_entities.extend(["user", school])
                    extracted_relationships.append({
                        "source": "user", "type": "studies_at", "target": school,
                    })

            # --- Pattern 8: Speaks [language] ---
            match = re.search(
                r"I\s+speak\s+([\w\s,]+?)(?:\.|!|\?|$)", text, re.IGNORECASE
            )
            if match:
                langs_raw = match.group(1).strip()
                langs = [l.strip() for l in re.split(r"[,\s]+and\s+|,\s*", langs_raw) if l.strip()]
                for lang in langs[:5]:
                    if 1 < len(lang) < 30:
                        src_id = self._get_or_create_entity(user_id, "user", "person")
                        tgt_id = self._get_or_create_entity(user_id, lang, "language")
                        self._add_relationship(user_id, src_id, "speaks", tgt_id, 0.9, memory_id)
                        extracted_entities.extend(["user", lang])
                        extracted_relationships.append({
                            "source": "user", "type": "speaks", "target": lang,
                        })

            # --- Pattern 9: Plays [instrument/sport] ---
            match = re.search(
                r"I\s+play\s+(?:the\s+)?([\w\s]+?)(?:\.|,|!|\?|$)", text, re.IGNORECASE
            )
            if match:
                activity = match.group(1).strip()
                if 1 < len(activity) < 40:
                    src_id = self._get_or_create_entity(user_id, "user", "person")
                    tgt_id = self._get_or_create_entity(user_id, activity, "activity")
                    self._add_relationship(user_id, src_id, "plays", tgt_id, 0.8, memory_id)
                    extracted_entities.extend(["user", activity])
                    extracted_relationships.append({
                        "source": "user", "type": "plays", "target": activity,
                    })

        except Exception as e:
            logger.error(f"[Graph] Extraction error for user {user_id}: {e}")
            return {"entities": [], "relationships": []}

        # Deduplicate
        extracted_entities = list(dict.fromkeys(extracted_entities))
        regex_result = {
            "entities": extracted_entities,
            "relationships": extracted_relationships,
        }

        # ── LLM extraction (optional, supplements regex) ─────────────
        llm_result = {"entities": [], "relationships": []}
        if self.llm_extractor is not None:
            try:
                llm_result = self.llm_extractor.extract_sync(memory_content)
                if llm_result.get("entities") or llm_result.get("relationships"):
                    logger.info(
                        f"[Graph] LLM extracted {len(llm_result.get('entities', []))} entities, "
                        f"{len(llm_result.get('relationships', []))} relationships"
                    )
                    # Persist LLM-extracted entities and relationships into the graph
                    for ent in llm_result.get("entities", []):
                        if isinstance(ent, dict):
                            name = ent.get("name", "").strip()
                            etype = ent.get("type", "concept")
                            if etype not in ENTITY_TYPES:
                                etype = "concept"
                            if name and len(name) > 0:
                                self._get_or_create_entity(user_id, name, etype)
                    for rel in llm_result.get("relationships", []):
                        if isinstance(rel, dict):
                            src = rel.get("source", "").strip()
                            rtype = rel.get("type", "related_to")
                            tgt = rel.get("target", "").strip()
                            if src and tgt:
                                # Determine entity types from LLM entities
                                src_type = "person" if src.lower() == "user" else "concept"
                                tgt_type = "concept"
                                for ent in llm_result.get("entities", []):
                                    if isinstance(ent, dict):
                                        if ent.get("name", "").lower() == tgt.lower():
                                            tgt_type = ent.get("type", "concept")
                                            if tgt_type not in ENTITY_TYPES:
                                                tgt_type = "concept"
                                src_id = self._get_or_create_entity(user_id, src, src_type)
                                tgt_id = self._get_or_create_entity(user_id, tgt, tgt_type)
                                self._add_relationship(
                                    user_id, src_id, rtype, tgt_id, 0.85, memory_id
                                )
            except Exception as e:
                logger.warning(f"[Graph] LLM extraction failed, using regex only: {e}")

        # Merge regex + LLM results for the return value
        try:
            from nobi.memory.llm_extractor import merge_extractions
            merged = merge_extractions(regex_result, llm_result)
        except ImportError:
            merged = regex_result

        # ── Contradiction detection (optional) ───────────────────────
        if self.contradiction_detector is not None and merged.get("relationships"):
            try:
                contradictions = self.contradiction_detector.check_contradiction(
                    user_id, memory_content, merged
                )
                for c in contradictions:
                    logger.info(f"[Graph] Contradiction detected: {c.description}")
                    # Auto-resolve with newest_wins strategy
                    self.contradiction_detector.resolve_contradiction(
                        user_id, c, strategy="newest_wins"
                    )
            except Exception as e:
                logger.warning(f"[Graph] Contradiction detection failed: {e}")

        return merged

    # ── Query Methods ─────────────────────────────────────────────────────────

    def get_entity(self, user_id: str, name: str) -> Optional[dict]:
        """
        Get entity details by name.

        Args:
            user_id: User who owns this entity.
            name: Entity name (case-insensitive).

        Returns:
            Dict with entity info or None.
        """
        row = self._conn.execute(
            "SELECT * FROM entities WHERE user_id = ? AND name = ? COLLATE NOCASE",
            (user_id, name.strip()),
        ).fetchone()

        if not row:
            return None

        return {
            "id": row["id"],
            "name": row["name"],
            "entity_type": row["entity_type"],
            "first_seen": row["first_seen"],
        }

    def get_relationships(self, user_id: str, entity_name: str) -> list:
        """
        Get all relationships involving an entity (as source or target).

        Args:
            user_id: User who owns the entities.
            entity_name: Name of the entity.

        Returns:
            List of relationship dicts with source_name, target_name, type.
        """
        entity = self.get_entity(user_id, entity_name)
        if not entity:
            return []

        eid = entity["id"]
        rows = self._conn.execute(
            """SELECT r.*, s.name as source_name, t.name as target_name
               FROM relationships r
               JOIN entities s ON r.source_entity_id = s.id
               JOIN entities t ON r.target_entity_id = t.id
               WHERE r.user_id = ? AND (r.source_entity_id = ? OR r.target_entity_id = ?)""",
            (user_id, eid, eid),
        ).fetchall()

        return [
            {
                "id": row["id"],
                "source": row["source_name"],
                "relationship_type": row["relationship_type"],
                "target": row["target_name"],
                "confidence": row["confidence"],
                "source_memory_id": row["source_memory_id"],
            }
            for row in rows
        ]

    def get_connected_entities(
        self, user_id: str, entity_name: str, max_depth: int = 2
    ) -> dict:
        """
        BFS graph traversal from an entity, up to max_depth hops.

        Args:
            user_id: User who owns the entities.
            entity_name: Starting entity name.
            max_depth: Maximum BFS depth (default 2).

        Returns:
            Dict with 'root', 'entities' (set of names), 'relationships' (list of edges).
        """
        entity = self.get_entity(user_id, entity_name)
        if not entity:
            return {"root": entity_name, "entities": set(), "relationships": []}

        visited: Set[int] = set()
        queue: deque = deque()
        queue.append((entity["id"], entity["name"], 0))
        visited.add(entity["id"])

        found_entities: Set[str] = {entity["name"]}
        found_rels: List[dict] = []

        while queue:
            current_id, current_name, depth = queue.popleft()
            if depth >= max_depth:
                continue

            rows = self._conn.execute(
                """SELECT r.*, s.name as source_name, s.id as sid,
                          t.name as target_name, t.id as tid
                   FROM relationships r
                   JOIN entities s ON r.source_entity_id = s.id
                   JOIN entities t ON r.target_entity_id = t.id
                   WHERE r.user_id = ?
                   AND (r.source_entity_id = ? OR r.target_entity_id = ?)""",
                (user_id, current_id, current_id),
            ).fetchall()

            for row in rows:
                found_rels.append({
                    "source": row["source_name"],
                    "relationship_type": row["relationship_type"],
                    "target": row["target_name"],
                    "confidence": row["confidence"],
                })

                # Determine neighbor
                neighbor_id = row["tid"] if row["sid"] == current_id else row["sid"]
                neighbor_name = row["target_name"] if row["sid"] == current_id else row["source_name"]

                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    found_entities.add(neighbor_name)
                    queue.append((neighbor_id, neighbor_name, depth + 1))

        # Deduplicate relationships
        seen_rels = set()
        unique_rels = []
        for r in found_rels:
            key = (r["source"], r["relationship_type"], r["target"])
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(r)

        return {
            "root": entity_name,
            "entities": found_entities,
            "relationships": unique_rels,
        }

    def get_graph_context(self, user_id: str, query: str) -> str:
        """
        Generate natural language summary of relevant graph connections.

        Finds entities mentioned in (or related to) the query, traverses
        their 1-2 hop neighborhoods, and returns a human-readable summary.

        Args:
            user_id: User who owns the graph.
            query: Current user message / query text.

        Returns:
            Natural language string, or empty string if nothing relevant.
        """
        if not query or not query.strip():
            return ""

        # Find entities that might be relevant to the query
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Get all entities for this user
        all_entities = self._conn.execute(
            "SELECT id, name, entity_type FROM entities WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        if not all_entities:
            return ""

        # Match entities by name overlap with query
        relevant_entities = []
        for ent in all_entities:
            name_lower = ent["name"].lower()
            # Direct mention
            if name_lower in query_lower or any(w in name_lower for w in query_words if len(w) > 2):
                relevant_entities.append(ent["name"])
            # Also always include "user" entity as it's the main subject
            elif ent["name"] == "user":
                relevant_entities.append("user")

        if not relevant_entities:
            # If no specific entities found, just use "user"
            relevant_entities = ["user"]

        # Traverse connections
        all_rels: List[dict] = []
        seen_rels: Set[tuple] = set()

        for entity_name in relevant_entities[:10]:  # Cap to avoid huge traversals
            graph = self.get_connected_entities(user_id, entity_name, max_depth=2)
            for rel in graph["relationships"]:
                key = (rel["source"], rel["relationship_type"], rel["target"])
                if key not in seen_rels:
                    seen_rels.add(key)
                    all_rels.append(rel)

        if not all_rels:
            return ""

        # Build natural language sentences
        sentences = []
        for rel in all_rels[:20]:  # Cap output
            sentence = _rel_to_sentence(rel["source"], rel["relationship_type"], rel["target"])
            if sentence:
                sentences.append(sentence)

        if not sentences:
            return ""

        return "You know that: " + ". ".join(sentences) + "."

    # ── Entity Merging ────────────────────────────────────────────────────────

    def merge_entities(self, user_id: str, entity1_name: str, entity2_name: str) -> bool:
        """
        Merge entity2 into entity1, transferring all relationships.

        Args:
            user_id: User who owns the entities.
            entity1_name: Primary entity (kept).
            entity2_name: Entity to merge in (deleted after).

        Returns:
            True if merge succeeded, False otherwise.
        """
        e1 = self.get_entity(user_id, entity1_name)
        e2 = self.get_entity(user_id, entity2_name)

        if not e1 or not e2:
            return False

        if e1["id"] == e2["id"]:
            return True  # Same entity, nothing to do

        conn = self._conn

        # Update all relationships pointing to/from entity2 → entity1
        conn.execute(
            "UPDATE relationships SET source_entity_id = ? WHERE source_entity_id = ? AND user_id = ?",
            (e1["id"], e2["id"], user_id),
        )
        conn.execute(
            "UPDATE relationships SET target_entity_id = ? WHERE target_entity_id = ? AND user_id = ?",
            (e1["id"], e2["id"], user_id),
        )

        # Delete self-referential relationships that may have been created
        conn.execute(
            "DELETE FROM relationships WHERE source_entity_id = target_entity_id AND user_id = ?",
            (user_id,),
        )

        # Delete entity2
        conn.execute(
            "DELETE FROM entities WHERE id = ? AND user_id = ?",
            (e2["id"], user_id),
        )
        conn.commit()

        # Clean up duplicate relationships
        self._dedup_relationships(user_id)

        logger.info(f"[Graph] Merged '{entity2_name}' into '{entity1_name}' for user {user_id}")
        return True

    def _dedup_relationships(self, user_id: str):
        """Remove duplicate relationships (same source, type, target)."""
        conn = self._conn
        conn.execute("""
            DELETE FROM relationships WHERE id NOT IN (
                SELECT MIN(id) FROM relationships
                WHERE user_id = ?
                GROUP BY source_entity_id, relationship_type, target_entity_id
            ) AND user_id = ?
        """, (user_id, user_id))
        conn.commit()

    # ── Counts & Export ───────────────────────────────────────────────────────

    def get_entity_count(self, user_id: str) -> int:
        """Get total entity count for a user."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM entities WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_relationship_count(self, user_id: str) -> int:
        """Get total relationship count for a user."""
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM relationships WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def export_graph(self, user_id: str) -> dict:
        """
        Export the full graph for a user as JSON-serializable dict.

        Returns:
            Dict with 'entities' and 'relationships' lists.
        """
        entities = self._conn.execute(
            "SELECT * FROM entities WHERE user_id = ?", (user_id,),
        ).fetchall()

        relationships = self._conn.execute(
            """SELECT r.*, s.name as source_name, t.name as target_name
               FROM relationships r
               JOIN entities s ON r.source_entity_id = s.id
               JOIN entities t ON r.target_entity_id = t.id
               WHERE r.user_id = ?""",
            (user_id,),
        ).fetchall()

        return {
            "user_id": user_id,
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "entities": [
                {
                    "name": e["name"],
                    "entity_type": e["entity_type"],
                    "first_seen": e["first_seen"],
                }
                for e in entities
            ],
            "relationships": [
                {
                    "source": r["source_name"],
                    "relationship_type": r["relationship_type"],
                    "target": r["target_name"],
                    "confidence": r["confidence"],
                    "source_memory_id": r["source_memory_id"],
                    "created_at": r["created_at"],
                }
                for r in relationships
            ],
        }


# ── Helper Functions ──────────────────────────────────────────────────────────

def _guess_entity_type(text: str) -> str:
    """Guess the entity type from text content."""
    text_lower = text.lower().strip()

    food_words = {"food", "pizza", "pasta", "sushi", "cooking", "baking",
                  "chocolate", "coffee", "tea", "beer", "wine", "cake",
                  "italian food", "chinese food", "mexican food", "japanese food"}
    if text_lower in food_words or "food" in text_lower or "cuisine" in text_lower:
        return "food"

    place_words = {"beach", "mountain", "city", "park", "museum", "library"}
    if text_lower in place_words:
        return "place"

    activity_words = {"hiking", "swimming", "reading", "gaming", "running",
                      "yoga", "dancing", "singing", "traveling", "photography"}
    if text_lower in activity_words:
        return "activity"

    return "concept"


def _rel_to_sentence(source: str, rel_type: str, target: str) -> str:
    """Convert a relationship triple to a natural language sentence."""
    # Replace "user" with "the user" for readability
    src = "The user" if source == "user" else source
    tgt = target

    templates = {
        "is_named": f"{src}'s name is {tgt}",
        "is_a": f"{src} is a {tgt}",
        "has": f"{src} has {tgt}",
        "has_pet": f"{src} has a pet named {tgt}",
        "likes": f"{src} likes {tgt}",
        "loves": f"{src} loves {tgt}",
        "dislikes": f"{src} dislikes {tgt}",
        "lives_in": f"{src} lives in {tgt}",
        "from": f"{src} is from {tgt}",
        "works_at": f"{src} works at {tgt}",
        "works_as": f"{src} works as {tgt}",
        "sister_of": f"{src}'s sister is {tgt}",
        "brother_of": f"{src}'s brother is {tgt}",
        "mother_of": f"{src}'s mother is {tgt}",
        "father_of": f"{src}'s father is {tgt}",
        "child_of": f"{src}'s child is {tgt}",
        "parent_of": f"{src}'s parent is {tgt}",
        "sibling_of": f"{src}'s sibling is {tgt}",
        "friend_of": f"{src}'s friend is {tgt}",
        "partner_of": f"{src}'s partner is {tgt}",
        "married_to": f"{src} is married to {tgt}",
        "owns": f"{src} owns {tgt}",
        "studies": f"{src} studies {tgt}",
        "studies_at": f"{src} studies at {tgt}",
        "plays": f"{src} plays {tgt}",
        "speaks": f"{src} speaks {tgt}",
        "born_on": f"{src} was born on {tgt}",
        "born_in": f"{src} was born in {tgt}",
        "interested_in": f"{src} is interested in {tgt}",
        "member_of": f"{src} is a member of {tgt}",
        "uses": f"{src} uses {tgt}",
        "related_to": f"{src} is related to {tgt}",
    }

    return templates.get(rel_type, f"{src} is connected to {tgt} ({rel_type})")
