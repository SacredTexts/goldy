#!/usr/bin/env python3
"""Log coding-research interview outcomes to .goldy/coding-research/outcomes.jsonl.

Usage:
    echo '{"classification_type": "bug_issue", ...}' | python3 track_outcome.py --project-root /path
    python3 track_outcome.py --project-root /path --help
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_FIELDS = {"classification_type", "track_used"}
OPTIONAL_FIELDS = {
    "classification_confidence": "medium",
    "rounds_completed": 0,
    "rounds_skipped": [],
    "synthesis_confirmed_first_attempt": True,
    "solution_delivered": False,
    "notes": "",
    "reclassified_to": None,
}
VALID_TYPES = {
    "bug_issue", "feature_build", "ui_surface",
    "performance", "schema_db", "refactor_architecture",
}
VALID_TRACKS = VALID_TYPES | {"phase_interview"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dir(project_root: Path) -> Path:
    out_dir = project_root / ".goldy" / "coding-research"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def validate(data: dict) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    if data.get("classification_type") and data["classification_type"] not in VALID_TYPES:
        errors.append(f"Invalid classification_type: {data['classification_type']}. Valid: {VALID_TYPES}")
    if data.get("track_used") and data["track_used"] not in VALID_TRACKS:
        errors.append(f"Invalid track_used: {data['track_used']}. Valid: {VALID_TRACKS}")
    return errors


def track(project_root: Path, data: dict) -> Path:
    # Fill defaults
    for key, default in OPTIONAL_FIELDS.items():
        if key not in data:
            data[key] = default

    # Add metadata
    data["timestamp"] = _utc_now_iso()
    data["project"] = project_root.name

    # Validate
    errors = validate(data)
    if errors:
        raise ValueError(f"Validation errors: {'; '.join(errors)}")

    # Write
    out_dir = ensure_dir(project_root)
    out_file = out_dir / "outcomes.jsonl"
    with open(out_file, "a") as f:
        f.write(json.dumps(data, separators=(",", ":")) + "\n")

    return out_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Log coding-research interview outcome")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"Error: {project_root} is not a directory", file=sys.stderr)
        sys.exit(1)

    # Read JSON from stdin
    raw = sys.stdin.read().strip()
    if not raw:
        print("Error: No JSON provided on stdin", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        out_file = track(project_root, data)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Outcome logged to {out_file}")
    print(f"  type={data['classification_type']} track={data['track_used']} confirmed={data['synthesis_confirmed_first_attempt']}")


if __name__ == "__main__":
    main()
