"""
Project Nobi — Contradiction Detection & Resolution
=====================================================
Detects when new memories contradict existing knowledge in the graph.
Supports automatic resolution strategies: newest_wins, keep_both, ask_user.

Examples:
  - "I live in London" → later "I moved to Paris" → location contradiction
  - "My dog is named Buddy" → "I renamed my dog to Max" → name contradiction
  - "I work at Google" → "I just quit my job" → status contradiction
  - "My girlfriend Sarah" → "We broke up" → relationship contradiction
  - "I love coffee" → "I stopped drinking coffee" → preference contradiction

Thread-safe. Never crashes — all errors are caught and logged.
"""

import logging
import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger("nobi-contradictions")

# ── Contradiction types ──────────────────────────────────────────────────────

CONTRADICTION_TYPES = frozenset({
    "location_change",
    "name_change",
    "status_change",
    "relationship_change",
    "preference_change",
    "general",
})

# Relationship types that are "exclusive" — only one target expected at a time
_EXCLUSIVE_RELATIONS = {
    "lives_in": "location_change",
    "works_at": "status_change",
    "works_as": "status_change",
    "is_named": "name_change",
    "married_to": "relationship_change",
    "partner_of": "relationship_change",
    "studies_at": "status_change",
}

# Relationship types that represent preferences (can change)
_PREFERENCE_RELATIONS = {"likes", "loves", "dislikes", "interested_in"}

# Opposite relationship pairs
_OPPOSITE_RELATIONS = {
    "likes": "dislikes",
    "dislikes": "likes",
    "loves": "dislikes",
}

# Keywords indicating negation/change
_NEGATION_KEYWORDS = [
    "stopped", "quit", "left", "moved", "no longer", "not anymore",
    "broke up", "divorced", "separated", "ended", "gave up",
    "switched", "changed", "renamed", "relocated", "transferred",
    "fired", "laid off", "resigned", "retired",
]

_CHANGE_KEYWORDS = [
    "moved to", "relocated to", "transferred to", "switched to",
    "renamed", "now called", "changed to", "now live in",
    "just started", "now work", "new job",
]


@dataclass
class Contradiction:
    """Represents a detected contradiction between old and new information."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    contradiction_type: str = "general"
    description: str = ""
    old_relationship: Optional[Dict[str, Any]] = None
    new_relationship: Optional[Dict[str, Any]] = None
    old_value: str = ""
    new_value: str = ""
    source_entity: str = ""
    relationship_type: str = ""
    confidence: float = 0.8
    resolved: bool = False
    resolution_strategy: str = ""
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            "id": self.id,
            "contradiction_type": self.contradiction_type,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "source_entity": self.source_entity,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "resolved": self.resolved,
            "resolution_strategy": self.resolution_strategy,
            "detected_at": self.detected_at,
        }


class ContradictionDetector:
    """
    Detects contradictions between new memories and existing graph state.

    Thread-safe. Stores detected contradictions per user for later review.
    """

    def __init__(self, memory_manager=None, memory_graph=None):
        """
        Initialize the detector.

        Args:
            memory_manager: MemoryManager instance (optional, for querying memories).
            memory_graph: MemoryGraph instance (required, for querying relationships).
        """
        self.memory_manager = memory_manager
        self.memory_graph = memory_graph
        self._contradictions: Dict[str, List[Contradiction]] = {}
        self._lock = threading.Lock()

    def check_contradiction(
        self,
        user_id: str,
        new_content: str,
        new_entities: Optional[Dict] = None,
    ) -> List[Contradiction]:
        """
        Check if new content contradicts existing graph relationships.

        Args:
            user_id: User ID to check against.
            new_content: The new memory text.
            new_entities: Pre-extracted entities/relationships dict (optional).

        Returns:
            List of detected Contradiction objects.
        """
        if not self.memory_graph or not new_content:
            return []

        contradictions = []

        try:
            # Get new relationships from extraction
            new_rels = []
            if new_entities and isinstance(new_entities, dict):
                new_rels = new_entities.get("relationships", [])

            # Check each new relationship against existing ones
            for new_rel in new_rels:
                if not isinstance(new_rel, dict):
                    continue
                source = new_rel.get("source", "").strip()
                rtype = new_rel.get("type", "").strip()
                target = new_rel.get("target", "").strip()

                if not source or not rtype or not target:
                    continue

                c = self._check_exclusive_conflict(user_id, source, rtype, target)
                if c:
                    contradictions.append(c)

                c = self._check_preference_conflict(user_id, source, rtype, target, new_content)
                if c:
                    contradictions.append(c)

            # Check for negation keywords even without explicit new relationships
            contradictions.extend(self._check_negation_patterns(user_id, new_content))

            # Store contradictions
            if contradictions:
                with self._lock:
                    if user_id not in self._contradictions:
                        self._contradictions[user_id] = []
                    self._contradictions[user_id].extend(contradictions)

                logger.info(
                    f"[Contradiction] Detected {len(contradictions)} contradiction(s) for user {user_id}"
                )

        except Exception as e:
            logger.error(f"[Contradiction] Detection error for user {user_id}: {e}")

        return contradictions

    def _check_exclusive_conflict(
        self, user_id: str, source: str, rtype: str, target: str
    ) -> Optional[Contradiction]:
        """Check if an exclusive relationship already exists with a different target."""
        if rtype not in _EXCLUSIVE_RELATIONS:
            return None

        try:
            existing_rels = self.memory_graph.get_relationships(user_id, source)
            for existing in existing_rels:
                if (
                    existing.get("relationship_type") == rtype
                    and existing.get("source", "").lower() == source.lower()
                    and existing.get("target", "").lower() != target.lower()
                ):
                    ctype = _EXCLUSIVE_RELATIONS[rtype]
                    old_target = existing.get("target", "")
                    return Contradiction(
                        contradiction_type=ctype,
                        description=f"{source} {rtype} changed from '{old_target}' to '{target}'",
                        old_relationship=existing,
                        new_relationship={"source": source, "type": rtype, "target": target},
                        old_value=old_target,
                        new_value=target,
                        source_entity=source,
                        relationship_type=rtype,
                        confidence=0.9,
                    )
        except Exception as e:
            logger.debug(f"[Contradiction] Exclusive check error: {e}")

        return None

    def _check_preference_conflict(
        self, user_id: str, source: str, rtype: str, target: str, new_content: str
    ) -> Optional[Contradiction]:
        """Check if a preference contradicts an existing one (likes vs dislikes)."""
        if rtype not in _OPPOSITE_RELATIONS:
            return None

        opposite = _OPPOSITE_RELATIONS[rtype]

        try:
            existing_rels = self.memory_graph.get_relationships(user_id, source)
            for existing in existing_rels:
                ext_type = existing.get("relationship_type", "")
                ext_target = existing.get("target", "").lower()
                ext_source = existing.get("source", "").lower()

                # Check if opposite relation exists for same target
                if (
                    ext_type == opposite
                    and ext_source == source.lower()
                    and ext_target == target.lower()
                ):
                    return Contradiction(
                        contradiction_type="preference_change",
                        description=f"{source} previously {opposite} '{target}', now {rtype} '{target}'",
                        old_relationship=existing,
                        new_relationship={"source": source, "type": rtype, "target": target},
                        old_value=f"{opposite} {target}",
                        new_value=f"{rtype} {target}",
                        source_entity=source,
                        relationship_type=rtype,
                        confidence=0.85,
                    )

                # Check if same relation type but user says "stopped"
                if (
                    ext_type == rtype
                    and ext_source == source.lower()
                    and ext_target == target.lower()
                ):
                    content_lower = new_content.lower()
                    if any(kw in content_lower for kw in ["stopped", "no longer", "quit", "gave up", "don't"]):
                        return Contradiction(
                            contradiction_type="preference_change",
                            description=f"{source} stopped {rtype} '{target}'",
                            old_relationship=existing,
                            new_relationship={"source": source, "type": rtype, "target": target},
                            old_value=f"{rtype} {target}",
                            new_value=f"stopped {rtype} {target}",
                            source_entity=source,
                            relationship_type=rtype,
                            confidence=0.8,
                        )
        except Exception as e:
            logger.debug(f"[Contradiction] Preference check error: {e}")

        return None

    def _check_negation_patterns(
        self, user_id: str, new_content: str
    ) -> List[Contradiction]:
        """Check for negation/change keywords that imply contradictions."""
        contradictions = []
        content_lower = new_content.lower()

        try:
            # Check for "moved to [place]" — might conflict with existing lives_in
            for keyword in _CHANGE_KEYWORDS:
                if keyword in content_lower:
                    existing_rels = self.memory_graph.get_relationships(user_id, "user")
                    for existing in existing_rels:
                        ext_type = existing.get("relationship_type", "")

                        # "moved to" → conflict with existing lives_in
                        if "moved" in keyword and ext_type == "lives_in":
                            # Already handled by exclusive check if new_entities were provided
                            pass

                        # "quit" / "left" → conflict with existing works_at
                        if ("quit" in keyword or "left" in keyword or "resigned" in keyword) and ext_type == "works_at":
                            old_target = existing.get("target", "")
                            contradictions.append(Contradiction(
                                contradiction_type="status_change",
                                description=f"User may have left their job at '{old_target}'",
                                old_relationship=existing,
                                old_value=old_target,
                                new_value="(left/quit)",
                                source_entity="user",
                                relationship_type="works_at",
                                confidence=0.7,
                            ))
                            break

            # Check for "broke up" → conflict with partner_of
            if any(kw in content_lower for kw in ["broke up", "broken up", "separated", "divorced"]):
                existing_rels = self.memory_graph.get_relationships(user_id, "user")
                for existing in existing_rels:
                    if existing.get("relationship_type") in ("partner_of", "married_to"):
                        old_target = existing.get("target", "")
                        contradictions.append(Contradiction(
                            contradiction_type="relationship_change",
                            description=f"User may have broken up with / separated from '{old_target}'",
                            old_relationship=existing,
                            old_value=old_target,
                            new_value="(ended)",
                            source_entity="user",
                            relationship_type=existing.get("relationship_type", ""),
                            confidence=0.75,
                        ))

        except Exception as e:
            logger.debug(f"[Contradiction] Negation check error: {e}")

        return contradictions

    def resolve_contradiction(
        self,
        user_id: str,
        contradiction: Contradiction,
        strategy: str = "newest_wins",
    ) -> bool:
        """
        Resolve a contradiction using the specified strategy.

        Args:
            user_id: User ID.
            contradiction: The Contradiction to resolve.
            strategy: Resolution strategy — "newest_wins", "keep_both", "ask_user".

        Returns:
            True if resolved, False otherwise.
        """
        if not self.memory_graph:
            return False

        try:
            if strategy == "newest_wins":
                return self._resolve_newest_wins(user_id, contradiction)
            elif strategy == "keep_both":
                contradiction.resolved = True
                contradiction.resolution_strategy = "keep_both"
                return True
            elif strategy == "ask_user":
                # Mark as pending — don't auto-resolve
                contradiction.resolution_strategy = "ask_user"
                return False
            else:
                logger.warning(f"[Contradiction] Unknown strategy: {strategy}")
                return False

        except Exception as e:
            logger.error(f"[Contradiction] Resolution error: {e}")
            return False

    def _resolve_newest_wins(
        self, user_id: str, contradiction: Contradiction
    ) -> bool:
        """Resolve by removing old relationship and keeping the new one."""
        old_rel = contradiction.old_relationship
        if not old_rel:
            contradiction.resolved = True
            contradiction.resolution_strategy = "newest_wins"
            return True

        try:
            conn = self.memory_graph._conn

            # Remove the old relationship
            old_id = old_rel.get("id")
            if old_id:
                conn.execute(
                    "DELETE FROM relationships WHERE id = ? AND user_id = ?",
                    (old_id, user_id),
                )
                conn.commit()
                logger.info(
                    f"[Contradiction] Resolved (newest_wins): removed old "
                    f"'{contradiction.relationship_type}' → '{contradiction.old_value}'"
                )

            contradiction.resolved = True
            contradiction.resolution_strategy = "newest_wins"
            return True

        except Exception as e:
            logger.error(f"[Contradiction] newest_wins resolution error: {e}")
            return False

    def resolve_by_id(
        self, user_id: str, contradiction_id: str, strategy: str = "newest_wins"
    ) -> bool:
        """
        Resolve a contradiction by its ID.

        Args:
            user_id: User ID.
            contradiction_id: The contradiction's unique ID.
            strategy: Resolution strategy.

        Returns:
            True if found and resolved, False otherwise.
        """
        with self._lock:
            user_contradictions = self._contradictions.get(user_id, [])
            for c in user_contradictions:
                if c.id == contradiction_id and not c.resolved:
                    return self.resolve_contradiction(user_id, c, strategy)
        return False

    def get_contradictions(
        self, user_id: str, include_resolved: bool = False
    ) -> List[Contradiction]:
        """
        Get all contradictions for a user.

        Args:
            user_id: User ID.
            include_resolved: Whether to include already-resolved contradictions.

        Returns:
            List of Contradiction objects.
        """
        with self._lock:
            contradictions = self._contradictions.get(user_id, [])
            if include_resolved:
                return list(contradictions)
            return [c for c in contradictions if not c.resolved]

    def clear_contradictions(self, user_id: str):
        """Clear all contradictions for a user."""
        with self._lock:
            self._contradictions.pop(user_id, None)
