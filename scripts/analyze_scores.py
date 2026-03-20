#!/usr/bin/env python3
"""
Project Nobi — Miner Score Analyzer CLI
Dragon Lord 🐉

Usage:
    python scripts/analyze_scores.py --rounds 100
    python scripts/analyze_scores.py --leaderboard 20
    python scripts/analyze_scores.py --gaming
    python scripts/analyze_scores.py --miner 42
    python scripts/analyze_scores.py --all
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nobi.validator.tuning import ScoringTuner


def print_section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_distribution(tuner: ScoringTuner, rounds: int):
    print_section(f"Score Distribution (last {rounds} rounds)")
    dist = tuner.get_score_distribution(rounds)

    if dist["count"] == 0:
        print("  No score data available.")
        return

    print(f"  Total scores: {dist['count']}")
    for component in ["quality", "memory", "reliability", "final"]:
        stats = dist[component]
        print(f"\n  {component.upper()}:")
        print(f"    Mean: {stats['mean']:.4f}  Std: {stats['std']:.4f}")
        print(f"    Min: {stats['min']:.4f}  Max: {stats['max']:.4f}")
        print(f"    Median: {stats['median']:.4f}  P25: {stats['p25']:.4f}  P75: {stats['p75']:.4f}")


def print_differentiation(tuner: ScoringTuner):
    print_section("Differentiation Analysis")
    diff = tuner.analyze_differentiation()

    status = "✅ GOOD" if diff["is_differentiated"] else "⚠️ POOR"
    print(f"  Status: {status}")
    print(f"  Miners analyzed: {diff['miner_count']}")
    print(f"  Final score std: {diff['final_std']:.4f}")

    if diff["component_stds"]:
        print(f"\n  Component standard deviations:")
        for comp, std in diff["component_stds"].items():
            print(f"    {comp}: {std:.4f}")

    if diff["dominant_component"]:
        print(f"\n  Dominant component: {diff['dominant_component']}")

    print(f"\n  Recommendation: {diff['recommendation']}")


def print_weights(tuner: ScoringTuner):
    print_section("Weight Suggestions")
    weights = tuner.suggest_weights()

    print(f"  Data points: {weights['data_points']}")
    print(f"\n  Suggested weights:")
    for rt, w in weights["suggested"].items():
        print(f"    {rt}: {w}")
    print(f"\n  Reasoning: {weights['reasoning']}")


def print_leaderboard(tuner: ScoringTuner, limit: int):
    print_section(f"Leaderboard (Top {limit})")
    lb = tuner.get_leaderboard(limit)

    if not lb:
        print("  No data available.")
        return

    print(f"  {'Rank':<6} {'UID':<8} {'Final':<10} {'Quality':<10} {'Memory':<10} {'Reliab.':<10} {'Rounds':<8}")
    print(f"  {'-' * 62}")
    for entry in lb:
        print(
            f"  {entry['rank']:<6} {entry['uid']:<8} {entry['avg_final']:<10.4f} "
            f"{entry['avg_quality']:<10.4f} {entry['avg_memory']:<10.4f} "
            f"{entry['avg_reliability']:<10.4f} {entry['round_count']:<8}"
        )


def print_gaming(tuner: ScoringTuner):
    print_section("Gaming Detection")
    alerts = tuner.detect_gaming()

    if not alerts:
        print("  ✅ No suspicious patterns detected.")
        return

    print(f"  ⚠️ {len(alerts)} alert(s) found:\n")
    for i, alert in enumerate(alerts, 1):
        severity_icon = "🔴" if alert["severity"] == "high" else "🟡"
        uid_str = str(alert.get("uid", alert.get("uids", "?")))
        print(f"  {i}. {severity_icon} [{alert['type']}] UID {uid_str}")
        print(f"     {alert['details']}")


def print_miner_history(tuner: ScoringTuner, uid: int):
    print_section(f"Miner {uid} History")
    history = tuner.get_miner_history(uid)

    if not history:
        print(f"  No data for miner {uid}.")
        return

    print(f"  {'Type':<12} {'Quality':<10} {'Memory':<10} {'Reliab.':<10} {'Final':<10}")
    print(f"  {'-' * 52}")
    for entry in history:
        print(
            f"  {entry['round_type']:<12} {entry['quality']:<10.4f} "
            f"{entry['memory']:<10.4f} {entry['reliability']:<10.4f} "
            f"{entry['final']:<10.4f}"
        )


def main():
    parser = argparse.ArgumentParser(description="Analyze miner scoring patterns")
    parser.add_argument("--rounds", type=int, default=100, help="Number of rounds for distribution")
    parser.add_argument("--leaderboard", type=int, default=0, help="Show top N miners")
    parser.add_argument("--gaming", action="store_true", help="Run gaming detection")
    parser.add_argument("--weights", action="store_true", help="Show weight suggestions")
    parser.add_argument("--miner", type=int, default=None, help="Show history for specific miner UID")
    parser.add_argument("--all", action="store_true", help="Show all analyses")
    parser.add_argument("--db", type=str, default="~/.nobi/scoring_history.db", help="Database path")

    args = parser.parse_args()

    tuner = ScoringTuner(db_path=args.db)

    if args.all or (not args.gaming and not args.weights and args.leaderboard == 0 and args.miner is None):
        print_distribution(tuner, args.rounds)
        print_differentiation(tuner)
        print_weights(tuner)
        print_leaderboard(tuner, 20)
        print_gaming(tuner)
    else:
        if args.leaderboard > 0:
            print_leaderboard(tuner, args.leaderboard)
        if args.gaming:
            print_gaming(tuner)
        if args.weights:
            print_weights(tuner)
        if args.miner is not None:
            print_miner_history(tuner, args.miner)

    print()


if __name__ == "__main__":
    main()
