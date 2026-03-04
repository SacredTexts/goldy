#!/usr/bin/env python3
"""Push coding-research learning data to the goldy repo via GH CLI.

Creates a branch, commits patterns.json, and pushes. Optionally creates a PR.
Designed to run as a background task — skips if no new data since last push.

Usage:
    python3 push_memory.py --project-root /path --goldy-repo /path/to/goldy
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def should_push(project_root: Path) -> bool:
    """Check if there's new data since last push."""
    patterns = project_root / ".goldy" / "coding-research" / "patterns.json"
    push_log = project_root / ".goldy" / "coding-research" / "push.log"

    if not patterns.exists():
        return False

    if not push_log.exists():
        return True

    # Compare modification times
    return patterns.stat().st_mtime > push_log.stat().st_mtime


def find_goldy_repo() -> Path | None:
    """Try to find the goldy repo in common locations."""
    candidates = [
        Path.home() / ".goldy",
        Path("/Volumes/Coding/Code/goldy"),
        Path.home() / "Code" / "goldy",
    ]
    for p in candidates:
        if (p / ".git").exists() or (p / ".git").is_file():
            return p
    return None


def push(project_root: Path, goldy_repo: Path) -> bool:
    """Push patterns.json to the goldy repo shared-knowledge directory."""
    patterns_file = project_root / ".goldy" / "coding-research" / "patterns.json"
    if not patterns_file.exists():
        print("No patterns.json found. Run analyze_patterns.py first.", file=sys.stderr)
        return False

    project_name = project_root.name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch_name = f"memory-push/{project_name}-{timestamp}"

    # Ensure shared-knowledge directory exists
    dest_dir = goldy_repo / "shared-knowledge" / "learning-data"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / f"{project_name}-patterns.json"

    try:
        # Check gh is available
        _run(["gh", "--version"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: gh CLI not found or not authenticated", file=sys.stderr)
        return False

    try:
        # Create branch from current HEAD
        _run(["git", "checkout", "-b", branch_name], cwd=goldy_repo)

        # Copy patterns
        patterns_data = json.loads(patterns_file.read_text())
        patterns_data["source_project"] = project_name
        patterns_data["pushed_at"] = _utc_now_iso()
        dest_file.write_text(json.dumps(patterns_data, indent=2) + "\n")

        # Stage, commit, push
        _run(["git", "add", str(dest_file.relative_to(goldy_repo))], cwd=goldy_repo)
        _run(
            ["git", "commit", "-m", f"chore: push learning data from {project_name}"],
            cwd=goldy_repo,
        )
        _run(["git", "push", "-u", "origin", branch_name], cwd=goldy_repo)

        # Switch back to previous branch
        _run(["git", "checkout", "-"], cwd=goldy_repo)

        return True

    except subprocess.CalledProcessError as e:
        print(f"Error during git operation: {e.stderr}", file=sys.stderr)
        # Try to get back to the original branch
        _run(["git", "checkout", "-"], cwd=goldy_repo, check=False)
        return False


def log_push(project_root: Path, success: bool) -> None:
    """Log push result for skip-if-no-change tracking."""
    push_log = project_root / ".goldy" / "coding-research" / "push.log"
    entry = {
        "timestamp": _utc_now_iso(),
        "success": success,
    }
    with open(push_log, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Push coding-research learning data to goldy repo")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument("--goldy-repo", default=None, help="Path to goldy repo (auto-detected if not specified)")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    if args.goldy_repo:
        goldy_repo = Path(args.goldy_repo).resolve()
    else:
        goldy_repo = find_goldy_repo()
        if not goldy_repo:
            print("Error: Could not find goldy repo. Use --goldy-repo to specify.", file=sys.stderr)
            sys.exit(1)

    if not should_push(project_root):
        print("No new data since last push. Skipping.")
        sys.exit(0)

    print(f"Pushing learning data from {project_root.name} to {goldy_repo}")
    success = push(project_root, goldy_repo)
    log_push(project_root, success)

    if success:
        print("Push successful. Branch created in goldy repo.")
    else:
        print("Push failed. Check errors above.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
