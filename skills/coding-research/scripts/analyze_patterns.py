#!/usr/bin/env python3
"""Analyze coding-research outcomes and generate pattern recommendations.

Reads .goldy/coding-research/outcomes.jsonl, produces patterns.json with:
- Top classification types by frequency
- Track effectiveness (first-attempt confirmation rate)
- Skipped round analysis
- Actionable recommendations

Usage:
    python3 analyze_patterns.py --project-root /path
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MIN_OUTCOMES_FOR_RECOMMENDATIONS = 10


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_outcomes(project_root: Path) -> list[dict]:
    outcomes_file = project_root / ".goldy" / "coding-research" / "outcomes.jsonl"
    if not outcomes_file.exists():
        return []
    entries = []
    for line in outcomes_file.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def analyze_types(outcomes: list[dict]) -> list[dict]:
    """Most common classification types."""
    counter = Counter(o.get("classification_type", "unknown") for o in outcomes)
    total = len(outcomes)
    return [
        {"type": t, "count": c, "pct": round(100 * c / total)}
        for t, c in counter.most_common()
    ]


def analyze_track_effectiveness(outcomes: list[dict]) -> list[dict]:
    """First-attempt synthesis confirmation rate per track."""
    track_outcomes: dict[str, list[bool]] = defaultdict(list)
    for o in outcomes:
        track = o.get("track_used", "unknown")
        confirmed = o.get("synthesis_confirmed_first_attempt", True)
        track_outcomes[track].append(confirmed)

    results = []
    for track, confirmations in sorted(track_outcomes.items()):
        rate = sum(confirmations) / len(confirmations) if confirmations else 0
        results.append({
            "track": track,
            "total": len(confirmations),
            "first_attempt_rate": round(rate, 2),
        })
    return results


def analyze_skipped_rounds(outcomes: list[dict]) -> list[dict]:
    """Which rounds are frequently skipped."""
    track_skips: dict[str, Counter] = defaultdict(Counter)
    track_totals: dict[str, int] = Counter()

    for o in outcomes:
        track = o.get("track_used", "unknown")
        skipped = o.get("rounds_skipped", [])
        track_totals[track] += 1
        for round_num in skipped:
            track_skips[track][round_num] += 1

    results = []
    for track, skip_counter in track_skips.items():
        total = track_totals[track]
        for round_num, skip_count in skip_counter.most_common():
            rate = round(skip_count / total, 2) if total else 0
            if rate >= 0.3:  # Only report if skipped 30%+ of the time
                results.append({
                    "track": track,
                    "round": round_num,
                    "skip_count": skip_count,
                    "skip_rate": rate,
                })
    return results


def analyze_classification_accuracy(outcomes: list[dict]) -> dict:
    """Track reclassification frequency."""
    total = len(outcomes)
    reclassified = sum(1 for o in outcomes if o.get("reclassified_to"))
    reclassifications = Counter(
        f"{o['classification_type']}->{o['reclassified_to']}"
        for o in outcomes if o.get("reclassified_to")
    )
    return {
        "total": total,
        "reclassified_count": reclassified,
        "accuracy_rate": round(1 - reclassified / total, 2) if total else 1.0,
        "common_reclassifications": [
            {"from_to": k, "count": v} for k, v in reclassifications.most_common(5)
        ],
    }


def generate_recommendations(
    types: list[dict],
    effectiveness: list[dict],
    skipped: list[dict],
    accuracy: dict,
    total: int,
) -> list[str]:
    """Generate actionable recommendations from analysis."""
    if total < MIN_OUTCOMES_FOR_RECOMMENDATIONS:
        return [f"Need {MIN_OUTCOMES_FOR_RECOMMENDATIONS - total} more outcomes before generating recommendations."]

    recs = []

    # Low effectiveness tracks
    for t in effectiveness:
        if t["first_attempt_rate"] < 0.7 and t["total"] >= 3:
            recs.append(
                f"{t['track']} track has {t['first_attempt_rate']:.0%} first-attempt rate "
                f"({t['total']} interviews). Review Round 1-2 questions for completeness."
            )

    # Frequently skipped rounds
    for s in skipped:
        recs.append(
            f"{s['track']} Round {s['round']} is skipped {s['skip_rate']:.0%} of the time. "
            f"Consider merging its questions into an earlier round or removing it."
        )

    # Classification accuracy
    if accuracy["accuracy_rate"] < 0.8:
        recs.append(
            f"Classification accuracy is {accuracy['accuracy_rate']:.0%}. "
            f"Review signal phrases in Phase 1 table."
        )
        for r in accuracy["common_reclassifications"][:2]:
            recs.append(f"  Common misclassification: {r['from_to']} ({r['count']} times)")

    # Dominant type
    if types and types[0]["pct"] > 60:
        recs.append(
            f"{types[0]['type']} accounts for {types[0]['pct']}% of all interviews. "
            f"Consider adding sub-tracks for more nuanced questioning."
        )

    if not recs:
        recs.append("All metrics look healthy. No recommendations at this time.")

    return recs


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze coding-research interview patterns")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    outcomes = load_outcomes(project_root)

    if not outcomes:
        print("No outcomes found. Run some interviews first.", file=sys.stderr)
        sys.exit(0)

    types = analyze_types(outcomes)
    effectiveness = analyze_track_effectiveness(outcomes)
    skipped = analyze_skipped_rounds(outcomes)
    accuracy = analyze_classification_accuracy(outcomes)
    recommendations = generate_recommendations(types, effectiveness, skipped, accuracy, len(outcomes))

    result = {
        "last_analyzed": _utc_now_iso(),
        "total_outcomes": len(outcomes),
        "top_types": types,
        "track_effectiveness": effectiveness,
        "skipped_rounds": skipped,
        "classification_accuracy": accuracy,
        "recommendations": recommendations,
    }

    out_dir = project_root / ".goldy" / "coding-research"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "patterns.json"
    out_file.write_text(json.dumps(result, indent=2) + "\n")

    print(f"Pattern analysis written to {out_file}")
    print(f"  {len(outcomes)} outcomes analyzed")
    print(f"  {len(recommendations)} recommendations")
    for rec in recommendations:
        print(f"  - {rec}")


if __name__ == "__main__":
    main()
