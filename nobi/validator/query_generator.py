# Project Nobi — Dynamic Query Generator
# Generates unique, unpredictable test queries so miners can't pre-cache answers.

import os
import random
import hashlib
import time
from typing import List, Dict, Optional
import bittensor as bt

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# Seed topics for dynamic generation (combined randomly)
TOPICS = [
    "cooking", "fitness", "travel", "career", "relationships", "health",
    "technology", "hobbies", "finance", "education", "parenting", "pets",
    "mental health", "creativity", "productivity", "nature", "music",
    "movies", "books", "sports", "gardening", "photography", "gaming",
    "volunteering", "meditation", "fashion", "home improvement", "science",
]

MOODS = [
    "happy", "stressed", "curious", "bored", "anxious", "excited",
    "confused", "motivated", "lonely", "grateful", "overwhelmed", "nostalgic",
]

SITUATIONS = [
    "just started a new job", "moving to a new city", "planning a vacation",
    "learning a new language", "going through a breakup", "preparing for an exam",
    "starting a diet", "adopting a pet", "dealing with a difficult coworker",
    "trying to save money", "recovering from an illness", "changing careers",
    "becoming a parent", "planning a wedding", "starting a business",
    "dealing with insomnia", "training for a race", "learning to cook",
    "decorating a new apartment", "managing a long-distance relationship",
]

NAMES = [
    "Alex", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Avery", "Quinn",
    "Taylor", "Reese", "Harper", "Emery", "Sage", "Rowan", "Phoenix",
    "Kai", "Nova", "Aria", "Mika", "Zara", "Leo", "Noor", "Yuki", "Ren",
]

PETS = [
    ("dog", "Luna"), ("cat", "Mochi"), ("dog", "Bear"), ("cat", "Whiskers"),
    ("rabbit", "Bun"), ("dog", "Max"), ("cat", "Shadow"), ("dog", "Daisy"),
    ("bird", "Kiwi"), ("hamster", "Peanut"), ("dog", "Rocky"), ("cat", "Nala"),
]

CAREERS = [
    "software engineer", "teacher", "nurse", "designer", "chef",
    "marketing manager", "student", "freelance writer", "data analyst",
    "mechanic", "pharmacist", "artist", "accountant", "social worker",
    "architect", "physical therapist", "entrepreneur", "journalist",
]

HOBBIES = [
    "hiking", "painting", "reading", "yoga", "cooking", "photography",
    "gardening", "cycling", "swimming", "playing guitar", "writing poetry",
    "pottery", "knitting", "rock climbing", "dancing", "birdwatching",
    "board games", "martial arts", "baking", "woodworking",
]


def generate_single_turn_query() -> str:
    """Generate a unique, unpredictable single-turn test query."""
    template = random.choice([
        _mood_query,
        _topic_query,
        _situation_query,
        _advice_query,
        _creative_query,
    ])
    return template()


def _mood_query() -> str:
    mood = random.choice(MOODS)
    topic = random.choice(TOPICS)
    templates = [
        f"I'm feeling {mood} today. Any advice related to {topic}?",
        f"I've been quite {mood} lately. Can you help me with something about {topic}?",
        f"Feeling {mood} — what's something interesting about {topic} you could share?",
    ]
    return random.choice(templates)


def _topic_query() -> str:
    topic = random.choice(TOPICS)
    templates = [
        f"I want to get better at {topic}. Where should I start?",
        f"Can you explain the basics of {topic} in a simple way?",
        f"What are some common mistakes people make with {topic}?",
        f"What's one surprising thing about {topic} most people don't know?",
        f"I need some practical tips for {topic}. What would you suggest?",
    ]
    return random.choice(templates)


def _situation_query() -> str:
    situation = random.choice(SITUATIONS)
    templates = [
        f"I'm {situation}. Any advice?",
        f"So I'm {situation} and feeling a bit lost. Can you help?",
        f"I've been {situation} recently. What should I keep in mind?",
    ]
    return random.choice(templates)


def _advice_query() -> str:
    templates = [
        f"I have about {random.randint(1,4)} hours free this {random.choice(['morning', 'afternoon', 'evening'])}. What should I do?",
        f"I need to make a decision about {random.choice(['my career', 'a relationship', 'moving', 'a purchase', 'my health'])}. How should I think about it?",
        f"I want to surprise my {random.choice(['friend', 'partner', 'parent', 'sibling', 'colleague'])} with something nice. Ideas?",
        f"How can I be more {random.choice(['productive', 'creative', 'confident', 'patient', 'organized', 'positive'])}?",
    ]
    return random.choice(templates)


def _creative_query() -> str:
    templates = [
        f"Tell me a short story about a {random.choice(['curious', 'brave', 'kind', 'clever'])} {random.choice(['robot', 'cat', 'child', 'explorer'])}.",
        f"Write me a {random.choice(['motivational', 'calming', 'funny', 'thoughtful'])} message for my {random.choice(['morning', 'evening', 'monday', 'stressful day'])}.",
        f"If you could recommend one {random.choice(['book', 'movie', 'song', 'place', 'habit'])} that changed your life, what would it be?",
    ]
    return random.choice(templates)


def generate_multi_turn_scenario() -> Dict:
    """
    Generate a unique multi-turn scenario with randomized details.
    Returns a scenario dict with setup messages, test query, and expected keywords.
    """
    name = random.choice(NAMES)
    career = random.choice(CAREERS)
    hobby = random.choice(HOBBIES)
    pet_type, pet_name = random.choice(PETS)
    mood = random.choice(MOODS)
    situation = random.choice(SITUATIONS)

    # Pick a random scenario template
    template = random.choice([
        _scenario_name_career_hobby,
        _scenario_pet_hobby,
        _scenario_situation_preference,
        _scenario_family_event,
        _scenario_goal_context,
    ])

    return template(name=name, career=career, hobby=hobby,
                   pet_type=pet_type, pet_name=pet_name,
                   mood=mood, situation=situation)


def _scenario_name_career_hobby(name, career, hobby, **kw) -> Dict:
    return {
        "setup": [
            {"role": "user", "content": f"Hi! My name is {name} and I work as a {career}."},
            {"role": "user", "content": f"I really enjoy {hobby} in my free time."},
        ],
        "test_query": f"What's a good way for me to combine my work and hobbies?",
        "memory_keywords": [name.lower(), career.split()[-1], hobby.split()[-1]],
        "description": f"Name ({name}) + career ({career}) + hobby ({hobby})",
    }


def _scenario_pet_hobby(name, pet_type, pet_name, hobby, **kw) -> Dict:
    return {
        "setup": [
            {"role": "user", "content": f"I'm {name} and I have a {pet_type} named {pet_name}."},
            {"role": "user", "content": f"We both love being outdoors. I'm also into {hobby}."},
        ],
        "test_query": f"What fun activity could I do with {pet_name} this weekend?",
        "memory_keywords": [name.lower(), pet_name.lower(), pet_type, hobby.split()[-1]],
        "description": f"Pet ({pet_name} the {pet_type}) + hobby ({hobby})",
    }


def _scenario_situation_preference(name, situation, mood, career, **kw) -> Dict:
    time_pref = random.choice(["morning", "evening", "night"])
    drink = random.choice(["coffee", "tea", "matcha", "smoothies"])
    return {
        "setup": [
            {"role": "user", "content": f"I'm {name}, a {career}. I'm currently {situation}."},
            {"role": "user", "content": f"I prefer {time_pref}s and I love {drink}."},
        ],
        "test_query": "Any suggestions to help me through this phase?",
        "memory_keywords": [name.lower(), career.split()[-1], time_pref, drink],
        "description": f"Situation ({situation}) + preferences ({time_pref}, {drink})",
    }


def _scenario_family_event(**kw) -> Dict:
    family_member = random.choice(["daughter", "son", "niece", "nephew"])
    child_name = random.choice(["Emma", "Liam", "Sophia", "Noah", "Mia", "Oliver", "Ava", "Elijah"])
    age = random.randint(3, 12)
    interest1 = random.choice(["dinosaurs", "space", "animals", "cars", "robots", "princesses"])
    interest2 = random.choice(["painting", "building things", "dancing", "reading", "playing outside"])
    return {
        "setup": [
            {"role": "user", "content": f"My {family_member} {child_name} just turned {age}!"},
            {"role": "user", "content": f"{child_name} loves {interest1} and {interest2}."},
        ],
        "test_query": f"What would be a great birthday gift for {child_name}?",
        "memory_keywords": [child_name.lower(), str(age), interest1, interest2.split()[-1]],
        "description": f"Family ({family_member} {child_name}, age {age}) + interests",
    }


def _scenario_goal_context(name, career, **kw) -> Dict:
    goal = random.choice([
        ("run a marathon", "4 hours", "running"),
        ("write a novel", "50000 words", "writing"),
        ("learn piano", "6 months", "piano"),
        ("lose weight", "10 kg", "fitness"),
        ("learn Spanish", "conversational level", "spanish"),
        ("save money", "emergency fund", "saving"),
    ])
    frequency = random.choice(["3 times a week", "every day", "on weekends", "twice a week"])
    return {
        "setup": [
            {"role": "user", "content": f"I'm {name} and I want to {goal[0]}. My target is {goal[1]}."},
            {"role": "user", "content": f"I practice {frequency} but I want to improve."},
        ],
        "test_query": "How should I adjust my routine this week?",
        "memory_keywords": [name.lower(), goal[2], frequency.split()[0]],
        "description": f"Goal ({goal[0]}) + routine ({frequency})",
    }
