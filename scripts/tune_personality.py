#!/usr/bin/env python3
"""
Nori Personality Tuning CLI
============================
Analyze responses, detect issues, and suggest improvements.

Usage:
    python scripts/tune_personality.py --analyze      # Analyze recent responses
    python scripts/tune_personality.py --issues       # Show detected issues
    python scripts/tune_personality.py --suggest      # Suggest improvements
    python scripts/tune_personality.py --test "msg"   # Test response quality
    python scripts/tune_personality.py --mood "msg"   # Detect mood in a message
"""

import argparse
import os
import sys

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.personality.tuner import PersonalityTuner
from nobi.personality.mood import detect_mood, get_mood_emoji


DEFAULT_DB = os.path.expanduser("~/.nobi/personality.db")


def cmd_analyze(tuner: PersonalityTuner):
    """Show aggregate analysis of stored conversations."""
    stats = tuner.get_personality_stats()
    if stats["total_conversations"] == 0:
        print("No conversations analyzed yet.")
        print("Use --test to analyze individual responses.")
        return

    print("=== Nori Personality Stats ===")
    print(f"  Total conversations: {stats['total_conversations']}")
    print(f"  Avg warmth:          {stats['avg_warmth']:.2f}")
    print(f"  Avg engagement:      {stats['avg_engagement']:.2f}")
    print(f"  Avg quality:         {stats['avg_quality']:.2f}")
    print(f"  Avg verbosity:       {stats['avg_verbosity']:.1f}x")
    print()
    if stats["common_issues"]:
        print("  Common issues:")
        for item in stats["common_issues"]:
            print(f"    - {item['issue']}: {item['count']}x")


def cmd_issues(tuner: PersonalityTuner):
    """Show detected issues from stored data."""
    stats = tuner.get_personality_stats()
    if not stats["common_issues"]:
        print("No issues detected yet. Analyze some conversations first.")
        return

    print("=== Detected Issues ===")
    for item in stats["common_issues"]:
        print(f"  [{item['count']}x] {item['issue']}")


def cmd_suggest(tuner: PersonalityTuner):
    """Show improvement suggestions."""
    suggestions = tuner.suggest_improvements()
    print("=== Suggestions ===")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s}")


def cmd_test(tuner: PersonalityTuner, message: str):
    """Test a response for quality."""
    score = tuner.get_response_quality_score(message)
    issues = tuner.detect_issues(message)

    print(f"=== Response Quality Test ===")
    print(f"  Response: {message[:100]}{'...' if len(message) > 100 else ''}")
    print(f"  Quality score: {score:.2f}")
    print(f"  Issues: {', '.join(issues) if issues else 'None'}")


def cmd_mood(message: str):
    """Detect mood in a message."""
    mood = detect_mood(message)
    emoji = get_mood_emoji(mood)
    print(f"  Message: {message}")
    print(f"  Detected mood: {mood} {emoji}")


def main():
    parser = argparse.ArgumentParser(description="Nori Personality Tuning CLI")
    parser.add_argument("--analyze", action="store_true", help="Analyze recent responses")
    parser.add_argument("--issues", action="store_true", help="Show detected issues")
    parser.add_argument("--suggest", action="store_true", help="Suggest improvements")
    parser.add_argument("--test", type=str, help="Test response quality")
    parser.add_argument("--mood", type=str, help="Detect mood in a message")
    parser.add_argument("--db", type=str, default=DEFAULT_DB, help="Database path")

    args = parser.parse_args()

    if args.mood:
        cmd_mood(args.mood)
        return

    tuner = PersonalityTuner(args.db)
    try:
        if args.analyze:
            cmd_analyze(tuner)
        elif args.issues:
            cmd_issues(tuner)
        elif args.suggest:
            cmd_suggest(tuner)
        elif args.test:
            cmd_test(tuner, args.test)
        else:
            parser.print_help()
    finally:
        tuner.close()


if __name__ == "__main__":
    main()
