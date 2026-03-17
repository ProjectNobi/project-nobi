"""
Project Nobi — Fact Extractor
==============================
Simple pattern-based fact extraction from conversation.
No LLM needed — just regex patterns for common personal information.
"""

import re
from typing import List, Tuple


def extract_facts(user_id: str, user_message: str, assistant_response: str) -> List[Tuple[str, str]]:
    """
    Extract facts from a conversation turn using simple pattern matching.
    
    Returns:
        List of (key, value) tuples representing extracted facts.
    """
    facts = []
    
    # Combine both messages for extraction (user might state, assistant might confirm)
    combined_text = f"{user_message}\n{assistant_response}"
    
    # ── Extract name ────────────────────────────────────────────────
    name_patterns = [
        r"(?:I'm|I am|my name is|call me|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        r"(?:I'm|I am)\s+([A-Z][a-z]+)\b(?:\s+and|,|\.|!|\?|$)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up common trailing words
            name = re.sub(r"\s+(from|in|at|and)$", "", name, flags=re.IGNORECASE)
            # Skip common false positives
            if name.lower() not in ["sorry", "fine", "good", "okay", "well", "sure"] and len(name) > 1:
                facts.append(("name", name))
                break  # Only extract one name per turn
    
    # ── Extract preferences (positive) ──────────────────────────────
    like_patterns = [
        r"I (?:love|like|enjoy|prefer|adore)\s+(.+?)(?:\.|,|!|\?|$)",
        r"(?:my favorite|I'm into|I'm a fan of)\s+(.+?)(?:\.|,|!|\?|$)",
    ]
    for pattern in like_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            preference = match.group(1).strip()
            # Clean up common trailing words
            preference = re.sub(r"\s+(too|so much|a lot|very much)$", "", preference, flags=re.IGNORECASE)
            if len(preference) > 2 and len(preference) < 100:
                facts.append(("likes", preference))
    
    # ── Extract preferences (negative) ──────────────────────────────
    dislike_patterns = [
        r"I (?:hate|dislike|don't like|can't stand)\s+(.+?)(?:\.|,|!|\?|$)",
    ]
    for pattern in dislike_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            preference = match.group(1).strip()
            preference = re.sub(r"\s+(at all|much|very much)$", "", preference, flags=re.IGNORECASE)
            if len(preference) > 2 and len(preference) < 100:
                facts.append(("dislikes", preference))
    
    # ── Extract life events ─────────────────────────────────────────
    life_event_patterns = [
        r"I (?:got|have|recently|just)\s+(?:a\s+)?(.+?)(?:\.|,|!|\?|$)",
        r"I (?:was|got)\s+(promoted|hired|fired|married|divorced|engaged)",
        r"I have a (?:new\s+)?(.+?)(?:\.|,|!|\?|$)",
    ]
    event_keywords = [
        "promotion", "job", "married", "divorced", "engaged", "baby", "child", "kid",
        "pet", "dog", "cat", "bird", "house", "apartment", "car", "degree", "graduated"
    ]
    for pattern in life_event_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            event = match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
            # Only extract if it contains a keyword
            if any(kw in event.lower() for kw in event_keywords) and len(event) < 100:
                facts.append(("life_event", event))
    
    # ── Extract location ────────────────────────────────────────────
    location_patterns = [
        r"I (?:live in|am from|was born in|grew up in)\s+([A-Z][a-zA-Z\s,]+?)(?:\s+and\b|\.|,|!|\?|$)",
        r"from\s+([A-Z][a-zA-Z\s]+?)(?:\s+and\b|\.|,|!|\?|$)",  # "I am James from London"
        r"I'm (?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:\s+now|\s+right now|\s+and\b|,|\.|$)",
    ]
    for pattern in location_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up trailing words
            location = re.sub(r"\s+(now|right now|currently)$", "", location, flags=re.IGNORECASE)
            if len(location) > 2 and len(location) < 50:
                facts.append(("location", location))
                break
    
    # ── Extract occupation ──────────────────────────────────────────
    occupation_patterns = [
        r"I (?:work as|am a)\s+(?:a\s+)?(.+?)(?:\.|,|!|\?|$)",
        r"I'm (?:a|an)\s+(.+?)(?:\.|,|!|\?|$)",
        r"work at\s+(.+?)(?:\.|,|!|\?|$)",
    ]
    for pattern in occupation_patterns:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            occupation = match.group(1).strip()
            # Clean up
            occupation = re.sub(r"\s+(too|also)$", "", occupation, flags=re.IGNORECASE)
            # Filter out common non-occupation phrases (whole word matches)
            skip_patterns = [r"\bbit\b", r"\blittle\b", r"\bvery\b", r"\breally\b", r"\bperson\b", r"\bguy\b", r"\bgirl\b"]
            if not any(re.search(sp, occupation, re.IGNORECASE) for sp in skip_patterns) and len(occupation) > 3 and len(occupation) < 50:
                facts.append(("occupation", occupation))
                break
    
    return facts


def test_extraction():
    """Test the fact extractor with sample conversations."""
    test_cases = [
        ("Hi, I'm James", ""),
        ("I love pizza and coding", ""),
        ("I hate waking up early", ""),
        ("I just got a promotion at work!", ""),
        ("I have a new puppy named Max", ""),
        ("I live in London", ""),
        ("I work as a software engineer", ""),
        ("My name is Sarah and I'm from New York", ""),
    ]
    
    print("Testing fact extractor:")
    for user_msg, assistant_msg in test_cases:
        facts = extract_facts("test_user", user_msg, assistant_msg)
        print(f"  Input: {user_msg}")
        print(f"  Facts: {facts}")
        print()


if __name__ == "__main__":
    test_extraction()
