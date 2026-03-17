"""
Project Nobi — Memory Module
=============================
Persistent memory system for personal AI companions.
Stores conversation history and user facts in JSON files.
"""

import os
import json
import time
import threading
from typing import Optional, List, Dict, Tuple
from pathlib import Path

from .fact_extractor import extract_facts


# ═══════════════════════════════════════════════════════════════════
# UserMemory Class
# ═══════════════════════════════════════════════════════════════════


class UserMemory:
    """
    Memory storage for a single user.
    Stores conversation history and persistent facts.
    """

    def __init__(self, user_id: str, data_dir: str):
        self.user_id = user_id
        self.data_dir = data_dir
        self.file_path = os.path.join(data_dir, f"{user_id}.json")
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        """Load memory from disk, or create empty structure."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load memory for {self.user_id}: {e}")
        
        # Default structure
        return {
            "user_id": self.user_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "facts": {},  # key -> {"value": str, "updated_at": timestamp}
            "conversations": {},  # conv_id -> [{"role": str, "content": str, "timestamp": float}]
        }

    def _save(self):
        """Save memory to disk."""
        self._data["updated_at"] = time.time()
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error: Failed to save memory for {self.user_id}: {e}")

    def add_message(self, conversation_id: str, role: str, content: str):
        """Add a message to conversation history."""
        with self._lock:
            if conversation_id not in self._data["conversations"]:
                self._data["conversations"][conversation_id] = []
            
            self._data["conversations"][conversation_id].append({
                "role": role,
                "content": content,
                "timestamp": time.time()
            })
            self._save()

    def get_history(self, conversation_id: str, max_turns: int = 10) -> List[Dict]:
        """
        Get recent conversation history.
        Returns list of {"role": str, "content": str} dicts suitable for LLM context.
        """
        with self._lock:
            messages = self._data["conversations"].get(conversation_id, [])
            # Return the last max_turns messages
            recent = messages[-max_turns:] if len(messages) > max_turns else messages
            # Return in LLM format (without timestamp)
            return [{"role": m["role"], "content": m["content"]} for m in recent]

    def set_user_fact(self, key: str, value: str):
        """Store or update a user fact."""
        with self._lock:
            self._data["facts"][key] = {
                "value": value,
                "updated_at": time.time()
            }
            self._save()

    def get_user_facts(self) -> Dict[str, str]:
        """Get all user facts as a simple dict (key -> value)."""
        with self._lock:
            return {k: v["value"] for k, v in self._data["facts"].items()}

    def summarize_user(self) -> str:
        """Generate a short text summary of what we know about this user."""
        facts = self.get_user_facts()
        
        if not facts:
            return "New user — no information yet."
        
        summary_parts = []
        
        # Name
        if "name" in facts:
            summary_parts.append(f"Name: {facts['name']}")
        
        # Location
        if "location" in facts:
            summary_parts.append(f"Location: {facts['location']}")
        
        # Occupation
        if "occupation" in facts:
            summary_parts.append(f"Occupation: {facts['occupation']}")
        
        # Likes
        if "likes" in facts:
            summary_parts.append(f"Likes: {facts['likes']}")
        
        # Dislikes
        if "dislikes" in facts:
            summary_parts.append(f"Dislikes: {facts['dislikes']}")
        
        # Life events
        if "life_event" in facts:
            summary_parts.append(f"Recent: {facts['life_event']}")
        
        return " | ".join(summary_parts)

    def extract_facts_from_message(self, user_message: str, assistant_response: str):
        """
        Extract facts from a conversation turn and store them.
        Uses simple pattern matching to auto-learn from conversation.
        """
        facts = extract_facts(self.user_id, user_message, assistant_response)
        
        for key, value in facts:
            # Multi-value fields: append instead of replace
            if key in ["likes", "dislikes", "life_event"]:
                existing = self._data["facts"].get(key, {}).get("value", "")
                if existing and value not in existing:
                    value = f"{existing}; {value}"
            
            self.set_user_fact(key, value)


# ═══════════════════════════════════════════════════════════════════
# MemoryManager Singleton
# ═══════════════════════════════════════════════════════════════════


class MemoryManager:
    """
    Singleton manager for all user memories.
    Handles concurrent access and lazy loading.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, data_dir: Optional[str] = None):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, data_dir: Optional[str] = None):
        if self._initialized:
            return
        
        # Default data dir: memory/data/ relative to project root
        if data_dir is None:
            project_root = Path(__file__).parent.parent
            data_dir = os.path.join(project_root, "memory", "data")
        
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        self._memories: Dict[str, UserMemory] = {}
        self._lock = threading.Lock()
        self._initialized = True

    def get_user_memory(self, user_id: str) -> UserMemory:
        """Get or create a UserMemory instance for a user."""
        with self._lock:
            if user_id not in self._memories:
                self._memories[user_id] = UserMemory(user_id, self.data_dir)
            return self._memories[user_id]

    def add_message(self, conversation_id: str, role: str, content: str, user_id: Optional[str] = None):
        """
        Add a message to conversation history.
        If user_id is provided, also store in user-specific memory.
        """
        # Use conversation_id as user_id fallback for backward compatibility
        if user_id is None:
            user_id = conversation_id
        
        memory = self.get_user_memory(user_id)
        memory.add_message(conversation_id, role, content)

    def get_history(self, conversation_id: str, max_turns: int = 10, user_id: Optional[str] = None) -> List[Dict]:
        """Get conversation history."""
        if user_id is None:
            user_id = conversation_id
        
        memory = self.get_user_memory(user_id)
        return memory.get_history(conversation_id, max_turns)

    def set_user_fact(self, user_id: str, key: str, value: str):
        """Store a user fact."""
        memory = self.get_user_memory(user_id)
        memory.set_user_fact(key, value)

    def get_user_facts(self, user_id: str) -> Dict[str, str]:
        """Get all facts about a user."""
        memory = self.get_user_memory(user_id)
        return memory.get_user_facts()

    def summarize_user(self, user_id: str) -> str:
        """Get a text summary of what we know about a user."""
        memory = self.get_user_memory(user_id)
        return memory.summarize_user()

    def extract_facts_from_message(self, user_id: str, user_message: str, assistant_response: str):
        """Extract and store facts from a conversation turn."""
        memory = self.get_user_memory(user_id)
        memory.extract_facts_from_message(user_message, assistant_response)


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

# Export the main classes
__all__ = ["MemoryManager", "UserMemory"]
