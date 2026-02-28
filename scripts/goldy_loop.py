#!/usr/bin/env python3
"""
GOLDY long-loop executor with guardrail-compliant checkpoints/resume.

Attribution: orchestration safety patterns are adapted from MIT-licensed
ralph-claude-code and ralph-orchestrator, implemented here as Python-native
runtime behavior for GOLDY.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

from goldy_audit_policy import evaluate_audit_policy, load_audit_policy, should_fail_fast
from goldy_breaker import CircuitBreaker
from goldy_browser import build_smoke_check, format_protocol
from goldy_history import append_history_event, replay_history
from goldy_lock import LoopLock, cleanup_stale_runtime_artifacts, register_active_session, unregister_active_session
from goldy_memory import build_resume_capsule, retrieve_ranked_entries, save_capsule
from goldy_permission import classify_permission_denial
from goldy_recovery import compute_resume_phase, recover_stale_running_state
from goldy_session import read_json, resolve_session_id, write_json
from goldy_stuck import default_stuck_state, update_stuck_detection
from goldy_task_lifecycle import (
    apply_evidence_backpressure,
    evaluate_phase_task_lifecycle,
    persist_phase_task_lifecycle,
)

PHASE_HEADER_RE = re.compile(r"^(#{2,4})\s+Phase\s+(\d+)\s*-\s*(.+)$", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"\[(?:[^\]]*(?:todo|tbd|first feature|second feature|third feature|placeholder)[^\]]*)\]",
    re.IGNORECASE,
)
# Waiver syntax: - [~] Task description (waived: reason)
WAIVER_RE = re.compile(r"^\s*-\s*\[~\]\s*(.+)$", re.MULTILINE)
# Checklist item: - [ ] or - [x] or - [X]
CHECKLIST_RE = re.compile(r"^\s*-\s*\[([ xX~])\]\s*(.+)$", re.MULTILINE)
# Validation gate line
VALIDATION_GATE_RE = re.compile(r"^\s*-?\s*\[?[xX~]?\]?\s*Validation gate\s*:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

DEFAULT_MAX_ITERATIONS = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GOLDY loop executor")
    parser.add_argument("--plan", required=False, help="Path to plan markdown")
    parser.add_argument("--phase", default="all", help="all or phase number")
    parser.add_argument("--resume", default="auto", help="auto or specific session id")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--project-root", default=os.getcwd())
    parser.add_argument("--context-remaining", type=float, default=None, help="Override context remaining percent")
    parser.add_argument("--commit-phase", action="store_true", help="Commit when each phase validates")
    parser.add_argument("--no-worktree", action="store_true", help="Run in current tree without creating worktree")
    parser.add_argument(
        "--allow-temp-plan",
        action="store_true",
        help="Allow temp-plans/* as loop input (disabled by default)",
    )
    parser.add_argument(
        "--preflight-answer",
        action="append",
        default=[],
        help="Answer to a clarifying preflight question (repeat per question)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=("start", "chat"),
        help="Post-preflight mode: start loop execution or chat about the plan first",
    )
    parser.add_argument(
        "--commands",
        action="store_true",
        help="Show /goldy-loop command reference and exit",
    )
    parser.add_argument(
        "--breaker-status",
        action="store_true",
        help="Show circuit breaker state and exit",
    )
    parser.add_argument(
        "--breaker-reset",
        action="store_true",
        help="Reset circuit breaker to CLOSED and exit",
    )
    parser.add_argument(
        "--breaker-auto-reset",
        action="store_true",
        help="Auto-reset circuit breaker on startup if OPEN",
    )
    parser.add_argument(
        "--browser-check",
        default=None,
        metavar="URL",
        help="Enable post-phase browser smoke checks (navigate + screenshot + console) at the given URL",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Write diagnostics bundle to .goldy/diagnostics/<timestamp>/",
    )
    parser.add_argument(
        "--require-resync",
        action="store_true",
        help="Resync plan copy in worktree and continue after plan-source drift is detected",
    )
    return parser.parse_args()


def print_command_reference() -> None:
    print("=== /goldy-loop Command Reference ===")
    print("Purpose: run phased GOLD plans with worktrees, preflight, audits, and resumable checkpoints.")
    print("")
    print(
        "Workflow: GOLDY Loop runs up to 10 execution loops by default (configurable with --max-iterations). "
        "In each loop, it re-checks the current phase/task checklist, rebuilds compact context, and validates "
        "implementation signals before marking progress. After plan completion, it runs 5 deep audits "
        "(lint, typecheck, tests, integration, robustness/security) and prints a completion report with total "
        "compactions and total minutes."
    )
    print("")
    print("Core options:")
    print("- --plan <path>: user-authored plan markdown file (required for execution)")
    print("- --phase all|N: run all phases or only one phase number")
    print("- --resume auto|<id>: resume session id, or use env/metadata auto resolution")
    print("- --max-iterations N: cap number of loop iterations in this invocation")
    print("")
    print("Execution behavior:")
    print("- --mode start|chat: choose Start to execute phases, Chat to pause after preflight")
    print("- --dry-run: simulate phase completion without mutating implementation steps")
    print("- --commit-phase: create phase commit after validation")
    print("- --context-remaining <percent>: guardrail override for low-context stop testing")
    print("- --diagnostics: write .goldy/diagnostics bundle artifacts")
    print("- --require-resync: sync source plan into worktree after hash drift detection")
    print("")
    print("Preflight options:")
    print("- --preflight-answer \"...\": answer ambiguity questions (repeat per question)")
    print("- --commands: print this reference and exit")
    print("")
    print("Browser smoke checks:")
    print("- --browser-check <url>: run navigate+screenshot+console after each phase")
    print("  Emits a browser investigation protocol block for the detected backend")
    print("")
    print("Worktree/plan controls:")
    print("- --no-worktree: run in current tree (default is plan-based worktree)")
    print("- --allow-temp-plan: allow temp-plans/* input (default is rejected)")
    print("- --project-root <path>: project root for runtime + repository discovery")
    print("")
    print("Circuit breaker controls:")
    print("- --breaker-status: show current breaker state (CLOSED/HALF_OPEN/OPEN)")
    print("- --breaker-reset: manually reset breaker to CLOSED")
    print("- --breaker-auto-reset: auto-reset OPEN breaker on startup (skip cooldown)")
    print("  Env overrides: GOLDY_BREAKER_NO_PROGRESS_THRESHOLD (default 3),")
    print("  GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD (default 2),")
    print("  GOLDY_BREAKER_COOLDOWN_MINUTES (default 5)")
    print("")
    print("Typical usage:")
    print("1) Start full loop:")
    print("   /goldy-loop --plan plans/my-plan.md --mode start")
    print("2) Run one phase:")
    print("   /goldy-loop --plan plans/my-plan.md --phase 2 --mode start")
    print("3) Handle preflight questions:")
    print("   /goldy-loop --plan plans/my-plan.md --preflight-answer \"...\" --preflight-answer \"...\" --mode start")
    print("4) Chat-first planning pass:")
    print("   /goldy-loop --plan plans/my-plan.md --mode chat")
    print("5) Resume previous loop:")
    print("   /goldy-loop --plan plans/my-plan.md --resume <session-id> --mode start")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _print_breaker_remediation(reason: str | None) -> None:
    normalized = (reason or "").lower()
    if "permission_denied" in normalized:
        print("Remediation: update tool permissions, then reset breaker and resume.")
    elif "completion_signal" in normalized:
        print("Remediation: verify completion signals are valid, then reset breaker and resume.")
    else:
        print("Remediation: resolve the breaker condition, then reset breaker and resume.")
    print("Reset with: /goldy-loop --breaker-reset --project-root <path>")


def _append_history(
    runtime_root: Path,
    session_id: str,
    event_type: str,
    *,
    phase: int | None = None,
    data: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> None:
    if dry_run:
        return
    try:
        append_history_event(
            runtime_root,
            session_id,
            event_type,
            phase=phase,
            data=data,
        )
    except Exception as exc:  # pragma: no cover - non-fatal telemetry guard.
        print(f"HISTORY WARNING: failed to append {event_type}: {exc}")


def _resolve_context_remaining(override: float | None) -> float:
    if override is not None:
        return override
    env_val = os.environ.get("GOLDY_CONTEXT_REMAINING_PERCENT", "100").strip()
    try:
        return float(env_val)
    except ValueError:
        return 100.0


def _run_git(repo_root: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
    )


def _git_repo_root(project_root: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"/goldy-loop requires a git repository: {project_root}")
    return Path(result.stdout.strip()).resolve()


def _sanitize_branch_token(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._/-]+", "-", value).strip("-./")
    return sanitized or "session"


def _plan_token(source_plan_path: Path) -> str:
    """
    Worktree identity is plan-based (not session-based).
    Uses plan filename stem primarily and adds a short path hash to avoid collisions.
    """
    base = _sanitize_branch_token(source_plan_path.stem)
    digest = hashlib.sha1(str(source_plan_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{base}-{digest}"


def _list_worktrees(repo_root: Path) -> list[dict[str, str]]:
    result = _run_git(repo_root, ["worktree", "list", "--porcelain"], check=False)
    if result.returncode != 0:
        return []

    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            if current:
                items.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["worktree"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            current["branch"] = line.split(" ", 1)[1]
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
    if current:
        items.append(current)
    return items


def _find_worktree_for_branch(repo_root: Path, branch_name: str) -> Path | None:
    wanted = f"refs/heads/{branch_name}"
    for item in _list_worktrees(repo_root):
        if item.get("branch") == wanted and item.get("worktree"):
            return Path(item["worktree"]).resolve()
    return None


def _is_worktree_path(path: Path) -> bool:
    return (path / ".git").exists()


def _next_available_path(base: Path) -> Path:
    index = 1
    while True:
        candidate = base.parent / f"{base.name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def ensure_loop_worktree(project_root: Path, source_plan_path: Path) -> dict[str, str]:
    repo_root = _git_repo_root(project_root)
    token = _plan_token(source_plan_path)
    branch_name = f"goldy-loop/{token}"

    existing_branch_path = _find_worktree_for_branch(repo_root, branch_name)
    if existing_branch_path is not None:
        return {
            "mode": "reused-branch",
            "repo_root": str(repo_root),
            "path": str(existing_branch_path),
            "branch": branch_name,
            "plan_token": token,
        }

    env_root = os.environ.get("GOLDY_WORKTREE_ROOT", "").strip()
    worktrees_root = (
        Path(env_root).expanduser().resolve()
        if env_root
        else (repo_root.parent / f"{repo_root.name}-goldy-worktrees").resolve()
    )
    worktrees_root.mkdir(parents=True, exist_ok=True)

    desired_path = worktrees_root / token
    if desired_path.exists() and not _is_worktree_path(desired_path):
        desired_path = _next_available_path(desired_path)

    if _is_worktree_path(desired_path):
        return {
            "mode": "reused-path",
            "repo_root": str(repo_root),
            "path": str(desired_path),
            "branch": branch_name,
            "plan_token": token,
        }

    branch_exists = _run_git(repo_root, ["show-ref", "--verify", f"refs/heads/{branch_name}"], check=False).returncode == 0
    if branch_exists:
        command = ["worktree", "add", str(desired_path), branch_name]
    else:
        command = ["worktree", "add", "-b", branch_name, str(desired_path)]
    result = _run_git(repo_root, command, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Failed creating worktree for {branch_name}")

    return {
        "mode": "created",
        "repo_root": str(repo_root),
        "path": str(desired_path),
        "branch": branch_name,
        "plan_token": token,
    }


def _map_plan_to_worktree(source_plan_path: Path, repo_root: Path, worktree_path: Path) -> Path:
    try:
        relative = source_plan_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return source_plan_path

    mapped_path = worktree_path / relative
    if not mapped_path.exists():
        mapped_path.parent.mkdir(parents=True, exist_ok=True)
        mapped_path.write_text(source_plan_path.read_text(encoding="utf-8"), encoding="utf-8")
    return mapped_path


def _is_temp_plan(project_root: Path, plan_path: Path) -> bool:
    temp_root = (project_root / "temp-plans").resolve()
    try:
        plan_path.resolve().relative_to(temp_root)
        return True
    except ValueError:
        return False


def _phase_block(lines: list[str], phase: dict[str, object]) -> str:
    start = max(0, int(phase["start_line"]) - 1)
    end = min(len(lines), int(phase["end_line"]))
    return "\n".join(lines[start:end])


def _phase_task_summary(plan_path: Path, phase: dict[str, object]) -> dict[str, Any]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    block = _phase_block(lines, phase)
    matches = re.findall(r"^\s*-\s*\[([ xX])\]\s*(.+)$", block, flags=re.MULTILINE)
    total = len(matches)
    checked = sum(1 for mark, _ in matches if mark.lower() == "x")
    unchecked = total - checked
    sample = [task.strip() for _, task in matches[:5]]
    return {
        "total": total,
        "checked": checked,
        "unchecked": unchecked,
        "sample": sample,
    }


def _parse_validation_evidence(block: str) -> dict[str, Any]:
    """Parse validation gate text from a phase block.

    Returns evidence dict with 'present' flag, 'text', and whether it appears checked.
    """
    match = VALIDATION_GATE_RE.search(block)
    if not match:
        return {"present": False, "text": "", "checked": False}

    gate_text = match.group(1).strip()
    # Check if the validation gate line itself is inside a checked item
    full_line = match.group(0).strip()
    is_checked = bool(re.match(r"^\s*-\s*\[[xX]\]", full_line))
    return {"present": True, "text": gate_text, "checked": is_checked}


def strict_phase_validator(plan_path: Path, phase: dict[str, object]) -> dict[str, Any]:
    """Strict phase completion validator (FR-01, FR-02).

    Requires ALL mandatory checklist items to be checked [x] or waived [~].
    Waived items must include a reason in parentheses: - [~] Task (waived: reason)
    Also verifies validation gate evidence is present.

    Returns:
        {
            "validated": bool,
            "reason": str,
            "total": int,
            "checked": int,
            "unchecked": int,
            "waived": int,
            "waived_without_reason": list[str],
            "unchecked_tasks": list[str],
            "evidence": dict,
            "sample": list[str],
        }
    """
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    block = _phase_block(lines, phase)

    matches = CHECKLIST_RE.findall(block)
    total = len(matches)
    checked = 0
    unchecked = 0
    waived = 0
    waived_without_reason: list[str] = []
    unchecked_tasks: list[str] = []

    for mark, task_text in matches:
        task_text = task_text.strip()
        if mark.lower() == "x":
            checked += 1
        elif mark == "~":
            waived += 1
            # Check for waiver reason: (waived: ...) or (waiver: ...)
            if not re.search(r"\(waive[dr]\s*:", task_text, re.IGNORECASE):
                waived_without_reason.append(task_text)
        else:
            unchecked += 1
            unchecked_tasks.append(task_text)

    evidence = _parse_validation_evidence(block)
    sample = [task.strip() for _, task in matches[:5]]

    # Validation logic
    if total == 0:
        return {
            "validated": False,
            "reason": "phase_validation_failed:no_checklist",
            "total": 0, "checked": 0, "unchecked": 0, "waived": 0,
            "waived_without_reason": [], "unchecked_tasks": [],
            "evidence": evidence, "sample": [],
        }

    if unchecked > 0:
        tasks_preview = "; ".join(unchecked_tasks[:3])
        return {
            "validated": False,
            "reason": f"phase_validation_failed:unchecked_tasks({unchecked})[{tasks_preview}]",
            "total": total, "checked": checked, "unchecked": unchecked, "waived": waived,
            "waived_without_reason": waived_without_reason,
            "unchecked_tasks": unchecked_tasks,
            "evidence": evidence, "sample": sample,
        }

    if waived_without_reason:
        preview = "; ".join(waived_without_reason[:3])
        return {
            "validated": False,
            "reason": f"phase_validation_failed:waived_without_reason({len(waived_without_reason)})[{preview}]",
            "total": total, "checked": checked, "unchecked": unchecked, "waived": waived,
            "waived_without_reason": waived_without_reason,
            "unchecked_tasks": unchecked_tasks,
            "evidence": evidence, "sample": sample,
        }

    if not evidence["present"]:
        return {
            "validated": False,
            "reason": "phase_validation_failed:missing_validation_gate",
            "total": total, "checked": checked, "unchecked": unchecked, "waived": waived,
            "waived_without_reason": [], "unchecked_tasks": [],
            "evidence": evidence, "sample": sample,
        }

    return {
        "validated": True,
        "reason": "phase_validated",
        "total": total, "checked": checked, "unchecked": unchecked, "waived": waived,
        "waived_without_reason": [], "unchecked_tasks": [],
        "evidence": evidence, "sample": sample,
    }


def build_preflight_questions(plan_path: Path, phases: list[dict[str, object]]) -> list[str]:
    text = plan_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    questions: list[str] = []
    if not phases:
        questions.append(
            "No 'Phase N - Title' headers were detected. Should GOLDY continue, or should we fix the plan structure first?"
        )

    placeholder_hits = sorted(set(match.group(0) for match in PLACEHOLDER_RE.finditer(text)))
    if placeholder_hits:
        snippet = ", ".join(placeholder_hits[:4])
        questions.append(
            f"Template placeholders are still present ({snippet}). What concrete values should replace these placeholders?"
        )

    missing_validation: list[str] = []
    for phase in phases:
        block = _phase_block(lines, phase).lower()
        if "validation gate" not in block:
            missing_validation.append(str(phase["phase"]))
    if missing_validation:
        questions.append(
            f"Validation gate text is missing for phase(s) {', '.join(missing_validation)}. "
            "What validation command/evidence should be required before completion?"
        )

    missing_checklist: list[str] = []
    for phase in phases:
        block = _phase_block(lines, phase)
        if "- [ ]" not in block and "- [x]" not in block:
            missing_checklist.append(str(phase["phase"]))
    if missing_checklist:
        questions.append(
            f"No checklist items found in phase(s) {', '.join(missing_checklist)}. "
            "Should GOLDY proceed, or wait until actionable checklist items are added?"
        )

    return questions[:3]


def resolve_preflight_answers(questions: list[str], provided_answers: list[str]) -> list[str] | None:
    if not questions:
        return []

    answers = list(provided_answers)
    if len(answers) >= len(questions):
        return answers[: len(questions)]

    if sys.stdin.isatty():
        for idx in range(len(answers), len(questions)):
            print(f"PREFLIGHT Q{idx + 1}: {questions[idx]}")
            answer = input(f"PREFLIGHT A{idx + 1}: ").strip()
            if not answer:
                return None
            answers.append(answer)
        return answers

    return None


def resolve_post_preflight_mode(provided_mode: str | None) -> str:
    print("POST-PREFLIGHT OPTIONS:")
    print("* Start")
    print("* Chat")

    if provided_mode:
        selected = provided_mode.strip().lower()
        print(f"POST-PREFLIGHT SELECTED: {selected.title()}")
        return selected

    if sys.stdin.isatty():
        while True:
            answer = input("Choose mode [Start/Chat]: ").strip().lower()
            if answer in ("start", "chat"):
                print(f"POST-PREFLIGHT SELECTED: {answer.title()}")
                return answer
            print("Invalid selection. Choose 'Start' or 'Chat'.")

    print("POST-PREFLIGHT SELECTED: Start (default non-interactive)")
    return "start"


def _minutes(seconds: float) -> float:
    return round(seconds / 60.0, 3)


def _safe_tail(text: str, max_chars: int = 800) -> str:
    snippet = (text or "").strip()
    if len(snippet) <= max_chars:
        return snippet
    return snippet[-max_chars:]


def _slugify(value: str, *, max_len: int = 64) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    if not safe:
        return "session"
    return safe[:max_len]


def _resolve_diagnostics_enabled(args: argparse.Namespace) -> bool:
    env_enabled = os.environ.get("GOLDY_DIAGNOSTICS", "").strip().lower()
    return bool(args.diagnostics) or env_enabled in {"1", "true", "yes", "on"}


def _diagnostics_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _init_diagnostics_bundle(runtime_root: Path, session_id: str, enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        return None

    bundle_root = runtime_root / "diagnostics" / f"{_diagnostics_stamp()}-{_slugify(session_id)}"
    bundle_root.mkdir(parents=True, exist_ok=True)

    categories = {
        "agent_output": str(bundle_root / "agent-output.jsonl"),
        "orchestration": str(bundle_root / "orchestration.jsonl"),
        "errors": str(bundle_root / "errors.jsonl"),
        "performance": str(bundle_root / "performance.jsonl"),
    }
    for raw_path in categories.values():
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    manifest = {
        "session_id": session_id,
        "created_at": _utc_now_iso(),
        "enabled": True,
        "categories": categories,
    }
    (bundle_root / "bundle.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _append_diagnostics_event(bundle: dict[str, Any] | None, category: str, event_type: str, payload: dict[str, Any]) -> None:
    if not bundle:
        return

    category_key = {
        "agent-output": "agent_output",
        "agent_output": "agent_output",
        "orchestration": "orchestration",
        "errors": "errors",
        "error": "errors",
        "performance": "performance",
    }.get(category, category)

    path_raw = (bundle.get("categories") or {}).get(category_key)
    if not path_raw:
        return

    path = Path(path_raw)
    line = (
        json.dumps(
            {
                "event_type": event_type,
                "timestamp": _utc_now_iso(),
                **payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _plan_file_sha256(plan_path: Path) -> str:
    digest = hashlib.sha256()
    with plan_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compute_plan_drift(source_plan_path: Path, worktree_plan_path: Path) -> dict[str, Any]:
    source_hash = _plan_file_sha256(source_plan_path)
    worktree_hash = _plan_file_sha256(worktree_plan_path)
    drifted = source_hash != worktree_hash
    return {
        "source_hash": source_hash,
        "worktree_hash": worktree_hash,
        "checked_at": _utc_now_iso(),
        "drifted": drifted,
        "action": "require_resync" if drifted else "none",
    }


def _sync_plan_to_worktree(source_plan_path: Path, worktree_plan_path: Path, *, dry_run: bool) -> None:
    # `--require-resync` is an explicit operator action, so keep plan copies aligned
    # even during dry-run sessions.
    _ = dry_run
    worktree_plan_path.parent.mkdir(parents=True, exist_ok=True)
    content = source_plan_path.read_text(encoding="utf-8")
    worktree_plan_path.write_text(content, encoding="utf-8")


def _ensure_metrics(session_state: dict[str, Any]) -> dict[str, Any]:
    metrics = session_state.setdefault("metrics", {})
    metrics.setdefault("loop_started_at", _utc_now_iso())
    metrics.setdefault("loop_seconds_total", 0.0)
    metrics.setdefault("compaction_runs_total", 0)
    metrics.setdefault("compaction_seconds_total", 0.0)
    metrics.setdefault("compaction_history", [])
    metrics.setdefault("deep_audit_runs_total", 0)
    metrics.setdefault("deep_audit_seconds_total", 0.0)
    metrics.setdefault("breaker_events_total", 0)
    metrics.setdefault("stuck_events_total", 0)
    metrics.setdefault("policy_failures_total", 0)
    metrics.setdefault("permission_events_total", 0)
    metrics.setdefault("lock_events_total", 0)
    metrics.setdefault(
        "signal_counts",
        {
            "progress": 0,
            "no_progress": 0,
            "completion": 0,
            "test_only": 0,
            "error": 0,
        },
    )
    metrics.setdefault(
        "malformed_events",
        {
            "total_malformed": 0,
            "total_valid": 0,
            "malformed_ratio": 0.0,
            "last_malformed_at": None,
            "samples": [],
        },
    )
    metrics.setdefault("stuck_detection", default_stuck_state())
    return metrics


def _collect_malformed_backpressure(runtime_root: Path, session_id: str) -> dict[str, Any]:
    replay = replay_history(runtime_root, session_id)
    parsed_malformed = int(replay.get("total_malformed", 0))
    events = [event for event in replay.get("events", []) if isinstance(event, dict)]
    malformed_events = [
        event
        for event in events
        if event.get("event_type") == "malformed_event"
    ]
    parser_valid_events = [
        event
        for event in events
        if event.get("event_type") in {"history_event_valid", "parsed_event", "event_parsed"}
    ]
    semantic_malformed = len(malformed_events)
    total_malformed = parsed_malformed + semantic_malformed
    total_valid = len(parser_valid_events)
    samples: list[str] = []
    for event in malformed_events[-5:]:
        if not isinstance(event, dict):
            continue
        data = event.get("data")
        if isinstance(data, dict):
            reason = data.get("reason", "")
            event_id = data.get("event_id", "")
            fragment = str(reason or event_id).strip()
            samples.append(fragment or str(data))
        else:
            samples.append(str(event))
    total_events = total_malformed + total_valid
    ratio = float(total_malformed / total_events) if total_events > 0 else 0.0
    return {
        "session_id": session_id,
        "total_malformed": total_malformed,
        "total_valid": total_valid,
        "malformed_ratio": ratio,
        "last_malformed_at": malformed_events[-1].get("timestamp") if malformed_events else replay.get("last_malformed_at"),
        "samples": samples,
    }


def _is_git_repository(path: Path) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _parse_plan_tasks(plan_path: Path) -> dict[int, dict[str, list[dict[str, str | None]]]]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    phases = parse_phases(plan_path)
    parsed: dict[int, dict[str, list[dict[str, str | None]]]] = {}
    for phase in phases:
        phase_number = int(phase["phase"])
        block = _phase_block(lines, phase)
        completed: list[dict[str, str | None]] = []
        pending: list[dict[str, str | None]] = []
        for match in re.finditer(r"^\s*-\s*\[([ xX~])\]\s*(.+)$", block, flags=re.MULTILINE):
            marker, text = match.groups()
            if marker.lower() == "x" or marker == "~":
                evidence = "waived" if marker == "~" else "validated"
                completed.append(
                    {
                        "phase": phase_number,
                        "description": text.strip(),
                        "evidence": None if marker == "~" else evidence,
                    }
                )
            else:
                blocked_by = None
                pending.append({"phase": phase_number, "description": text.strip(), "blocked_by": blocked_by})
        parsed[phase_number] = {"completed": completed, "pending": pending}
    return parsed


def _write_handoff_artifact(
    runtime_root: Path,
    session_id: str,
    plan_path: Path,
    session_state: dict[str, Any],
    stop_reason: str | None,
    resume_command: str,
    selected_phases: list[dict[str, object]],
) -> Path:
    completed_phases = {int(phase) for phase in session_state.get("completed_phases", []) if str(phase).isdigit()}
    task_map = _parse_plan_tasks(plan_path)

    completed_tasks: list[dict[str, str | None]] = []
    pending_tasks: list[dict[str, str | None]] = []
    for phase in selected_phases:
        phase_no = int(phase["phase"])
        payload = task_map.get(phase_no, {"completed": [], "pending": []})
        if phase_no in completed_phases:
            completed_tasks.extend(payload.get("completed", []))
        else:
            pending_tasks.extend(payload.get("pending", []))

    content = [
        f"# GOLDY Handoff ({session_id})",
        "",
        f"plan_path: {plan_path}",
        f"created_at: {_utc_now_iso()}",
        f"stop_reason: {stop_reason or 'loop_complete'}",
        f"current_phase: {session_state.get('current_phase')}",
        f"completed_phases: {sorted(completed_phases)}",
        "",
        "## Completed tasks",
    ]

    if completed_tasks:
        for task in completed_tasks:
            content.append(f"- [x] P{task['phase']}: {task['description']}")
    else:
        content.append("- (none)")

    content.extend(["", "## Pending tasks", ""]) 
    if pending_tasks:
        for task in pending_tasks:
            blocked = task.get("blocked_by")
            blocked_text = f" (blocked_by: {blocked})" if blocked else ""
            content.append(f"- [ ] P{task['phase']}: {task['description']}{blocked_text}")
    else:
        content.append("- (none)")

    content.append("")
    content.append("## Handoff command")
    content.append(resume_command)
    handoffs_root = runtime_root / "handoffs"
    handoffs_root.mkdir(parents=True, exist_ok=True)
    path = handoffs_root / f"{session_id}.md"
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    return path


def _run_compaction(execution_root: Path, plan_path: Path, session_id: str, query: str) -> dict[str, Any]:
    start = monotonic()
    entries = retrieve_ranked_entries(execution_root, plan_path, query, limit=160)
    capsule = build_resume_capsule(entries, target_tokens=1500)
    capsule_path = save_capsule(execution_root, session_id, capsule)
    seconds = monotonic() - start
    return {
        "query": query,
        "seconds": seconds,
        "minutes": _minutes(seconds),
        "entries": len(entries),
        "capsule_path": str(capsule_path),
        "timestamp": _utc_now_iso(),
    }


def _load_package_scripts(execution_root: Path) -> list[dict[str, Any]]:
    candidates = [execution_root / "package.json", execution_root / "apps" / "web" / "package.json"]
    packages: list[dict[str, Any]] = []
    for pkg_path in candidates:
        if not pkg_path.exists():
            continue
        payload = read_json(pkg_path, {})
        scripts = payload.get("scripts", {}) if isinstance(payload, dict) else {}
        if isinstance(scripts, dict):
            packages.append({"cwd": pkg_path.parent, "scripts": scripts})
    return packages


def _select_script_command(execution_root: Path, script_names: list[str]) -> tuple[list[str], Path, str] | None:
    for pkg in _load_package_scripts(execution_root):
        scripts = pkg["scripts"]
        for name in script_names:
            if name in scripts:
                cwd = Path(pkg["cwd"])
                return (["pnpm", "run", name], cwd, f"pnpm run {name} ({cwd})")
    return None


def _run_cmd(command: list[str], cwd: Path, timeout_sec: int = 1800) -> tuple[bool, str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if result.returncode == 0:
        return True, _safe_tail(result.stdout)
    combined = f"{result.stdout}\n{result.stderr}".strip()
    return False, _safe_tail(combined)


def _run_robustness_scan(execution_root: Path) -> tuple[bool, str]:
    checks = [
        (
            "merge-conflict-markers",
            ["rg", "-n", "--hidden", "--glob", "!.git", "--glob", "!node_modules", "^(<<<<<<<|=======|>>>>>>>)", "."],
        ),
        (
            "secret-like-patterns",
            [
                "rg",
                "-n",
                "--hidden",
                "--glob",
                "!.git",
                "--glob",
                "!node_modules",
                "(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA)? ?PRIVATE KEY-----|xox[baprs]-)",
                ".",
            ],
        ),
    ]

    findings: list[str] = []
    for label, cmd in checks:
        result = subprocess.run(cmd, cwd=execution_root, check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            findings.append(f"{label}: { _safe_tail(result.stdout, 400)}")
        elif result.returncode > 1:
            findings.append(f"{label}: scan_error: {_safe_tail(result.stderr, 300)}")

    if findings:
        return False, " ; ".join(findings)
    return True, "robustness scan clean"


def _run_unittest_fallback(execution_root: Path) -> tuple[bool, str]:
    """
    Run unittest discovery with a no-tests-safe exit code:
    - pass when tests pass
    - pass when no tests are discovered
    - fail when discovered tests fail
    """
    script = (
        "import sys, unittest;"
        "suite = unittest.defaultTestLoader.discover('.');"
        "count = suite.countTestCases();"
        "print(f'discovered_tests={count}');"
        "runner = unittest.TextTestRunner(verbosity=0);"
        "res = runner.run(suite) if count else None;"
        "sys.exit(0 if (count == 0 or (res and res.wasSuccessful())) else 1)"
    )
    result = subprocess.run(
        ["python3", "-c", script],
        cwd=execution_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, _safe_tail(result.stdout)
    return False, _safe_tail(f"{result.stdout}\n{result.stderr}")


def run_deep_code_audits(
    execution_root: Path,
    dry_run: bool,
    policy: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Execute exactly five audits for robustness.
    Includes linting, type checks, tests, integration/build checks, and security/hygiene.
    """
    plans: list[dict[str, Any]] = [
        {
            "id": "A1",
            "name": "Lint Audit",
            "scripts": ["lint", "lint:check", "check:lint"],
            "fallback_cmd": ["git", "diff", "--check"],
            "fallback_label": "git diff --check",
        },
        {
            "id": "A2",
            "name": "Typecheck Audit",
            "scripts": ["typecheck", "check-types", "types", "tsc"],
            "fallback_cmd": ["python3", "-m", "compileall", "-q", "."],
            "fallback_label": "python3 -m compileall -q .",
        },
        {
            "id": "A3",
            "name": "Test Audit",
            "scripts": ["test", "test:unit", "unit:test"],
            "fallback_cmd": None,
            "fallback_label": "python unittest discovery (no-tests-safe)",
        },
        {
            "id": "A4",
            "name": "Integration Audit",
            "scripts": ["test:integration", "test:e2e", "e2e", "build"],
            "fallback_cmd": ["git", "fsck", "--no-dangling"],
            "fallback_label": "git fsck --no-dangling",
        },
        {
            "id": "A5",
            "name": "Robustness Audit",
            "scripts": [],
            "fallback_cmd": None,
            "fallback_label": "rg-based merge/secrets scan",
        },
    ]

    active_policy = dict(policy or load_audit_policy())
    git_available = _is_git_repository(execution_root)
    results: list[dict[str, Any]] = []
    for audit in plans:
        started = monotonic()
        method = "fallback"
        status = "passed"
        details = ""
        command_label = audit["fallback_label"]

        if dry_run:
            method = "dry-run"
            details = "simulated pass in dry-run mode"
        else:
            selected = _select_script_command(execution_root, audit["scripts"])
            if selected is not None:
                cmd, cwd, label = selected
                command_label = label
                method = "script"
                ok, output = _run_cmd(cmd, cwd)
                status = "passed" if ok else "failed"
                details = output or ("script passed" if ok else "script failed")
            elif audit["id"] == "A5":
                ok, output = _run_robustness_scan(execution_root)
                status = "passed" if ok else "failed"
                details = output
            elif audit["id"] == "A3":
                ok, output = _run_unittest_fallback(execution_root)
                status = "passed" if ok else "failed"
                details = output
            else:
                fallback_cmd = deepcopy(audit["fallback_cmd"])
                is_git_fallback = bool(fallback_cmd) and len(fallback_cmd) > 0 and fallback_cmd[0] == "git"
                if is_git_fallback and not git_available:
                    status = "passed"
                    details = "fallback skipped: not a git repository"
                else:
                    ok, output = _run_cmd(fallback_cmd, execution_root)
                    status = "passed" if ok else "failed"
                    details = output or ("fallback passed" if ok else "fallback failed")

        seconds = monotonic() - started
        results.append(
            {
                "id": audit["id"],
                "category": {
                    "A1": "lint",
                    "A2": "typecheck",
                    "A3": "test",
                    "A4": "integration",
                    "A5": "robustness",
                }.get(audit["id"], "unknown"),
                "name": audit["name"],
                "status": status,
                "method": method,
                "command": command_label,
                "seconds": round(seconds, 3),
                "minutes": _minutes(seconds),
                "details": details,
            }
        )
        if not dry_run and should_fail_fast(active_policy, str(audit["id"]), str(status)):
            break

    return results


def print_completion_report(
    plan_path: Path,
    session_id: str,
    session_state: dict[str, Any],
    audits: list[dict[str, Any]],
) -> None:
    metrics = session_state.get("metrics", {})
    compaction_runs = int(metrics.get("compaction_runs_total", 0))
    compaction_minutes = _minutes(float(metrics.get("compaction_seconds_total", 0.0)))
    loop_minutes = _minutes(float(metrics.get("loop_seconds_total", 0.0)))
    audit_minutes = _minutes(float(metrics.get("deep_audit_seconds_total", 0.0)))
    signal_counts = metrics.get("signal_counts", {})
    stuck_detection = metrics.get("stuck_detection", {})
    malformed_events = metrics.get("malformed_events", {})
    signal_window = stuck_detection.get("signal_window", [])
    signal_window_signals = [str(item.get("signal", "")) for item in signal_window if isinstance(item, dict)]
    breaker_events_total = int(metrics.get("breaker_events_total", 0))
    stuck_events_total = int(metrics.get("stuck_events_total", 0))
    permission_events_total = int(metrics.get("permission_events_total", 0))
    policy_failures_total = int(metrics.get("policy_failures_total", 0))
    lock_events_total = int(metrics.get("lock_events_total", 0))
    task_lifecycle = session_state.get("task_lifecycle", {})
    lifecycle_phase_count = 0
    lifecycle_task_total = 0
    lifecycle_retry_total = 0
    lifecycle_timeout_total = 0
    if isinstance(task_lifecycle, dict):
        lifecycle_phase_count = len(task_lifecycle)
        for phase_payload in task_lifecycle.values():
            if not isinstance(phase_payload, dict):
                continue
            summary = phase_payload.get("summary", {})
            if not isinstance(summary, dict):
                continue
            lifecycle_task_total += int(summary.get("total_tasks", 0))
            lifecycle_retry_total += int(summary.get("retry_attempts_total", 0))
            lifecycle_timeout_total += int(summary.get("timeout_configured_count", 0))

    print("=== GOLDY LOOP COMPLETION REPORT ===")
    print(f"plan: {plan_path}")
    print(f"session_id: {session_id}")
    print(f"compaction_runs_total: {compaction_runs}")
    print(f"compaction_minutes_total: {compaction_minutes}")
    print(f"loop_minutes_total: {loop_minutes}")
    print(f"deep_code_audits_run: {len(audits)}")
    print(f"deep_code_audit_minutes_total: {audit_minutes}")
    print(f"breaker_events_total: {breaker_events_total}")
    print(f"stuck_events_total: {stuck_events_total}")
    print(f"permission_events_total: {permission_events_total}")
    print(f"policy_failures_total: {policy_failures_total}")
    print(f"lock_events_total: {lock_events_total}")
    print(f"malformed_events_total: {int(malformed_events.get('total_malformed', 0))}")
    print(f"malformed_events_ratio: {float(malformed_events.get('malformed_ratio', 0.0))}")
    print(f"malformed_events_samples: {malformed_events.get('samples', [])}")
    print(f"stuck_detected: {bool(stuck_detection.get('is_stuck', False))}")
    print(f"stuck_consecutive_matches: {int(stuck_detection.get('consecutive_matches', 0))}")
    print(f"stuck_false_positive_suppressed: {int(stuck_detection.get('false_positive_suppressed', 0))}")
    print(f"signal_window_entries: {len(signal_window)}")
    print(f"signal_window_signals: {signal_window_signals}")
    print(f"signal_counts: {json.dumps(signal_counts, sort_keys=True)}")
    print(f"task_lifecycle_phases: {lifecycle_phase_count}")
    print(f"task_lifecycle_tasks_total: {lifecycle_task_total}")
    print(f"task_lifecycle_retries_total: {lifecycle_retry_total}")
    print(f"task_lifecycle_timeouts_configured: {lifecycle_timeout_total}")
    for idx, audit in enumerate(audits, start=1):
        print(
            f"{idx}. {audit['name']}: {audit['status']} "
            f"({audit['minutes']} min, method={audit['method']}, command={audit['command']})"
        )


def ensure_runtime(project_root: Path) -> dict[str, Path]:
    root = project_root / ".goldy"
    sessions = root / "sessions"
    checkpoints = root / "checkpoints"
    history = root / "history"
    index = root / "index.json"
    for folder in (root, sessions, checkpoints, history):
        folder.mkdir(parents=True, exist_ok=True)
    if not index.exists():
        write_json(index, {"active_plan": None, "plans": [], "last_session": None})
    return {"root": root, "sessions": sessions, "checkpoints": checkpoints, "history": history, "index": index}


def parse_phases(plan_path: Path) -> list[dict[str, object]]:
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    phases: list[dict[str, object]] = []

    current: dict[str, object] | None = None
    for idx, line in enumerate(lines, start=1):
        match = PHASE_HEADER_RE.match(line.strip())
        if match:
            if current:
                current["end_line"] = idx - 1
                phases.append(current)
            current = {
                "phase": int(match.group(2)),
                "title": match.group(3).strip(),
                "start_line": idx,
                "end_line": len(lines),
            }

    if current:
        phases.append(current)

    return phases


def _phase_selection(phases: list[dict[str, object]], phase_arg: str) -> list[dict[str, object]]:
    if phase_arg.lower() == "all":
        return phases
    try:
        phase_num = int(phase_arg)
    except ValueError as exc:
        raise ValueError("--phase must be 'all' or an integer") from exc

    selected = [p for p in phases if int(p["phase"]) == phase_num]
    if not selected:
        raise ValueError(f"Phase {phase_num} not found in plan")
    return selected


def _session_file(runtime: dict[str, Path], session_id: str) -> Path:
    return runtime["sessions"] / f"{session_id}.json"


def _checkpoint_file(runtime: dict[str, Path], session_id: str, phase: int) -> Path:
    phase_dir = runtime["checkpoints"] / session_id
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir / f"phase-{phase}.json"


def _write_checkpoint(
    runtime: dict[str, Path],
    session_id: str,
    phase: dict[str, object],
    status: str,
    reason: str,
    details: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> Path:
    checkpoint_path = _checkpoint_file(runtime, session_id, int(phase["phase"]))
    payload: dict[str, Any] = {
        "session_id": session_id,
        "phase": phase["phase"],
        "title": phase["title"],
        "status": status,
        "reason": reason,
        "timestamp": _utc_now_iso(),
    }
    if isinstance(details, dict) and details:
        payload["details"] = details
    write_json(
        checkpoint_path,
        payload,
    )
    _append_history(
        runtime["root"],
        session_id,
        "checkpoint_written",
        phase=int(phase["phase"]),
        data={"status": status, "reason": reason},
        dry_run=dry_run,
    )
    return checkpoint_path


def _has_pending_git_changes(project_root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _commit_phase(project_root: Path, phase: dict[str, object], session_id: str) -> tuple[bool, str]:
    if not _has_pending_git_changes(project_root):
        return False, "no_changes"

    subprocess.run(["git", "add", "-A"], cwd=project_root, check=True)
    message = f"goldy-loop: complete phase {phase['phase']} ({phase['title']}) [{session_id}]"
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "commit_failed"
    return True, message


def run_loop(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    source_plan_path = Path(args.plan).expanduser().resolve()

    if not source_plan_path.exists():
        raise FileNotFoundError(f"Plan not found: {source_plan_path}")
    if _is_temp_plan(project_root, source_plan_path) and not args.allow_temp_plan:
        raise ValueError(
            f"/goldy-loop requires a user-authored plan outside temp-plans: {source_plan_path}. "
            "Create/use a persistent plan file (for example, plans/my-plan.md), or pass --allow-temp-plan."
        )

    session_id = resolve_session_id(project_root=project_root) if args.resume == "auto" else args.resume

    execution_root = project_root
    worktree_info: dict[str, str] | None = None
    plan_path = source_plan_path
    if not args.no_worktree:
        worktree_info = ensure_loop_worktree(project_root, source_plan_path)
        execution_root = Path(worktree_info["path"]).resolve()
        plan_path = _map_plan_to_worktree(source_plan_path, Path(worktree_info["repo_root"]), execution_root)
        print(
            f"WORKTREE: {worktree_info['mode']} path={worktree_info['path']} "
            f"branch={worktree_info['branch']} plan_token={worktree_info.get('plan_token', 'n/a')}"
        )

    runtime = ensure_runtime(execution_root)
    diagnostics_bundle = _init_diagnostics_bundle(runtime["root"], session_id, _resolve_diagnostics_enabled(args))
    _append_diagnostics_event(
        diagnostics_bundle,
        "agent_output",
        "loop_runtime_initialized",
        {
            "session_id": session_id,
            "plan_path": str(source_plan_path),
            "execution_root": str(execution_root),
            "phase_arg": str(args.phase),
        },
    )

    phases = parse_phases(plan_path)
    selected_phases = _phase_selection(phases, args.phase)
    drifted_plan = _compute_plan_drift(source_plan_path, plan_path)
    if drifted_plan.get("drifted"):
        _append_diagnostics_event(
            diagnostics_bundle,
            "errors",
            "plan_drift_detected",
            {"source_hash": drifted_plan.get("source_hash"), "worktree_hash": drifted_plan.get("worktree_hash")},
        )

    preflight_questions = build_preflight_questions(plan_path, selected_phases)
    preflight_answers = resolve_preflight_answers(preflight_questions, args.preflight_answer)
    if preflight_questions and preflight_answers is None:
        print("PREFLIGHT: Clarifications required before loop execution.")
        for idx, question in enumerate(preflight_questions, start=1):
            print(f"- Q{idx}: {question}")
        print("Provide answers and rerun:")
        print("  /goldy-loop --plan <path> --preflight-answer \"<answer 1>\" ...")
        return 3

    print("PREFLIGHT: PASS" if not preflight_questions else "PREFLIGHT: PASS (clarifications captured)")
    post_mode = resolve_post_preflight_mode(args.mode)
    loop_started = monotonic()

    session_path = _session_file(runtime, session_id)
    session_state = read_json(
        session_path,
        {
            "session_id": session_id,
            "plan_path": str(plan_path),
            "source_plan_path": str(source_plan_path),
            "source_project_root": str(project_root),
            "execution_root": str(execution_root),
            "status": "running",
            "owner_pid": os.getpid(),
            "current_phase": None,
            "completed_phases": [],
            "phase_task_checks": {},
            "task_lifecycle": {},
            "max_iterations": args.max_iterations,
            "last_checkpoint_at": None,
            "next_action": "run next phase",
            "post_preflight_mode": post_mode,
            "deep_audits": [],
            "preflight": {
                "questions": preflight_questions,
                "answers": preflight_answers,
                "status": "pass" if preflight_answers is not None else "blocked",
                "checked_at": _utc_now_iso(),
            },
        },
    )
    session_state["preflight"] = {
        "questions": preflight_questions,
        "answers": preflight_answers,
        "status": "pass" if preflight_answers is not None else "blocked",
        "checked_at": _utc_now_iso(),
    }
    session_state["post_preflight_mode"] = post_mode
    session_state["owner_pid"] = os.getpid()
    session_state.setdefault("deep_audits", [])
    session_state.setdefault("phase_task_checks", {})
    session_state.setdefault("task_lifecycle", {})
    metrics = _ensure_metrics(session_state)
    audit_policy = load_audit_policy()
    if worktree_info:
        session_state["worktree"] = {
            "path": worktree_info["path"],
            "branch": worktree_info["branch"],
            "repo_root": worktree_info["repo_root"],
            "mode": worktree_info["mode"],
        }
    session_state["plan_drift"] = drifted_plan

    def _resume_command(resume_phase: int | None = None) -> str:
        resume_target = f"/goldy-loop --plan {source_plan_path} --resume {session_id}"
        if resume_phase is not None:
            resume_target += f" --phase {resume_phase}"
        return resume_target

    def _emit_handoff(stop_reason: str | None, resume_phase: int | None = None) -> Path:
        command = _resume_command(resume_phase)
        return _write_handoff_artifact(
            runtime["root"],
            session_id,
            source_plan_path,
            session_state,
            stop_reason,
            command,
            selected_phases,
        )

    if drifted_plan.get("drifted"):
        if args.require_resync:
            _sync_plan_to_worktree(source_plan_path, plan_path, dry_run=args.dry_run)
            drifted_plan = _compute_plan_drift(source_plan_path, plan_path)
            drifted_plan["action"] = "auto_synced"
            session_state["plan_drift"] = drifted_plan
            _append_diagnostics_event(
                diagnostics_bundle,
                "orchestration",
                "plan_drift_auto_synced",
                drifted_plan,
            )
        else:
            resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
            session_state.update(
                {
                    "status": "paused",
                    "stop_reason": "plan_drift_detected",
                    "next_action": "rerun with --require-resync",
                    "last_checkpoint_at": _utc_now_iso(),
                }
            )
            session_state["metrics"] = metrics
            write_json(session_path, session_state)
            handoff_path = _emit_handoff("plan_drift_detected", resume_phase)
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                phase=resume_phase,
                data={"path": str(handoff_path), "reason": "plan_drift_detected"},
                dry_run=args.dry_run,
            )
            print("PLAN DRIFT DETECTED: source plan and worktree plan hashes differ.")
            print(
                "Resume safely with --require-resync to sync the worktree plan copy from source before continuing:"
            )
            print(f"  {_resume_command(resume_phase)} --require-resync")
            print(f"HANDOFF: {handoff_path}")
            _append_history(
                runtime["root"],
                session_id,
                "loop_paused",
                phase=resume_phase,
                data={"reason": "plan_drift_detected", "source_hash": drifted_plan.get("source_hash"), "worktree_hash": drifted_plan.get("worktree_hash")},
                dry_run=args.dry_run,
            )
            _append_diagnostics_event(
                diagnostics_bundle,
                "errors",
                "loop_paused",
                {
                    "reason": "plan_drift_detected",
                    "resume_phase": resume_phase,
                    "source_hash": drifted_plan.get("source_hash"),
                    "worktree_hash": drifted_plan.get("worktree_hash"),
                },
            )
            return 8

    if post_mode == "chat":
        session_state.update(
            {
                "status": "chat_pause",
                "next_action": "discuss plan and rerun in start mode",
                "last_checkpoint_at": _utc_now_iso(),
            }
        )
        session_state["metrics"] = metrics
        write_json(session_path, session_state)
        handoff_path = _emit_handoff("chat_mode")
        _append_history(
            runtime["root"],
            session_id,
            "handoff_generated",
            data={"reason": "chat_mode", "path": str(handoff_path)},
            dry_run=args.dry_run,
        )
        print("CHAT MODE: loop execution not started.")
        print("Rerun with Start mode when ready:")
        print(
            f"  {_resume_command(compute_resume_phase(selected_phases, session_state.get('completed_phases', [])))} --mode start"
        )
        return 0

    index_payload = read_json(runtime["index"], {"active_plan": str(plan_path), "plans": []})
    index_payload["last_session"] = session_id
    write_json(runtime["index"], index_payload)

    cleanup_summary = cleanup_stale_runtime_artifacts(runtime)
    if any(bool(cleanup_summary.get(key)) for key in ("stale_registry_removed", "stale_sessions_marked", "stale_lock_cleaned")):
        print(
            "STALE CLEANUP: "
            f"registry={cleanup_summary.get('stale_registry_removed', 0)} "
            f"sessions={cleanup_summary.get('stale_sessions_marked', 0)} "
            f"lock_cleaned={cleanup_summary.get('stale_lock_cleaned', False)}"
        )

    loop_lock: LoopLock | None = None
    lock_registered = False

    def _finalize_lock(reason: str) -> None:
        nonlocal loop_lock, lock_registered
        if args.dry_run:
            return
        if lock_registered:
            unregister_active_session(runtime["root"], session_id)
            lock_registered = False
        if loop_lock is not None and loop_lock.is_held:
            _append_history(
                runtime["root"],
                session_id,
                "lock_released",
                data={"reason": reason},
                dry_run=args.dry_run,
            )
            metrics["lock_events_total"] = int(metrics.get("lock_events_total", 0)) + 1
            session_state["metrics"] = metrics
            write_json(session_path, session_state)
            loop_lock.release()
            loop_lock = None

    if not args.dry_run:
        loop_lock = LoopLock(
            runtime["root"],
            session_id,
            plan_path=str(plan_path),
            prompt_summary=f"phase={args.phase}",
        )
        lock_result = loop_lock.acquire()
        if str(lock_result.get("status")) == "conflict":
            holder = lock_result.get("holder", {}) if isinstance(lock_result.get("holder"), dict) else {}
            holder_pid = holder.get("pid", "unknown")
            holder_session = holder.get("session_id", "unknown")
            holder_when = holder.get("acquired_at", "unknown")
            holder_plan = holder.get("plan_path", "unknown")
            print("GOLDY LOOP STOP: loop lock conflict (another primary loop is running).")
            print(
                f"Lock holder: pid={holder_pid} session={holder_session} acquired_at={holder_when} plan={holder_plan}"
            )
            print("Remediation: wait for the current run to finish, or clean stale metadata and retry.")
            _emit_handoff("loop_lock_conflict")
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                data={"reason": "loop_lock_conflict"},
                dry_run=args.dry_run,
            )
            _append_diagnostics_event(
                diagnostics_bundle,
                "errors",
                "loop_lock_conflict",
                {
                    "holder_session": holder_session,
                    "holder_pid": holder_pid,
                    "holder_plan": holder_plan,
                    "holder_when": holder_when,
                },
            )
            _finalize_lock("lock_conflict")
            return 7

        register_active_session(runtime["root"], session_id, plan_path=str(plan_path))
        lock_registered = True
        metrics["lock_events_total"] = int(metrics.get("lock_events_total", 0)) + 1
        session_state["metrics"] = metrics
        _append_history(
            runtime["root"],
            session_id,
            "lock_acquired",
            data={"plan_path": str(plan_path)},
            dry_run=args.dry_run,
        )
        _append_diagnostics_event(
            diagnostics_bundle,
            "orchestration",
            "lock_acquired",
            {"plan_path": str(plan_path), "session_id": session_id},
        )

    recovery_result = recover_stale_running_state(
        runtime,
        session_id,
        session_state,
        selected_phases,
        mutate_files=not args.dry_run,
    )
    if bool(recovery_result.get("recovered")):
        session_state = recovery_result["session_state"]
        metrics = _ensure_metrics(session_state)
        session_state["metrics"] = metrics
        write_json(session_path, session_state)
        resume_phase = recovery_result.get("resume_phase")
        print(
            "RECOVERY: stale running session/checkpoint state detected and marked interrupted. "
            f"resume_phase={resume_phase if resume_phase is not None else 'none'}"
        )
        if isinstance(resume_phase, int):
            print(
                "RECOVERY RESUME POINTER: "
                f"/goldy-loop --plan {plan_path} --resume {session_id} --phase {resume_phase} --mode start"
            )
        _append_history(
            runtime["root"],
            session_id,
            "recovery_started",
            phase=resume_phase if isinstance(resume_phase, int) else None,
            data={
                "stale_checkpoints": recovery_result.get("stale_checkpoints", []),
                "resume_phase": resume_phase,
                },
            dry_run=args.dry_run,
        )

    malformed_payload = _collect_malformed_backpressure(runtime["root"], session_id)
    malformed_threshold_count = int(os.environ.get("GOLDY_MALFORMED_EVENT_THRESHOLD_COUNT", "3"))
    malformed_threshold_ratio = float(os.environ.get("GOLDY_MALFORMED_EVENT_THRESHOLD_RATIO", "0.25"))
    malformed_metrics = metrics.setdefault("malformed_events", {})
    malformed_metrics.update(
        {
            "session_id": session_id,
            "total_malformed": int(malformed_payload.get("total_malformed", 0)),
            "total_valid": int(malformed_payload.get("total_valid", 0)),
            "malformed_ratio": float(malformed_payload.get("malformed_ratio", 0.0)),
            "last_malformed_at": malformed_payload.get("last_malformed_at"),
            "samples": list(malformed_payload.get("samples", [])),
        }
    )
    _append_diagnostics_event(
        diagnostics_bundle,
        "errors",
        "malformed_backpressure_snapshot",
        malformed_metrics,
    )

    if (
        malformed_metrics["total_malformed"] >= malformed_threshold_count
        and malformed_metrics["malformed_ratio"] >= malformed_threshold_ratio
        and not args.dry_run
    ):
        resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
        session_state.update(
            {
                "status": "paused",
                "stop_reason": "malformed_backpressure",
                "next_action": "repair history file and rerun",
                "last_checkpoint_at": _utc_now_iso(),
            }
        )
        session_state["metrics"] = metrics
        write_json(session_path, session_state)
        handoff_path = _emit_handoff(
            "malformed_backpressure",
            resume_phase,
        )
        _append_history(
            runtime["root"],
            session_id,
            "loop_failed",
            phase=resume_phase,
            data={
                "reason": "malformed_backpressure",
                "total_malformed": malformed_metrics["total_malformed"],
                "malformed_ratio": malformed_metrics["malformed_ratio"],
                "resume_phase": resume_phase,
            },
            dry_run=args.dry_run,
        )
        print(
            "MALFORMED EVENT BACKPRESSURE: history parsing quality is below threshold. "
            f"threshold_count={malformed_threshold_count} threshold_ratio={malformed_threshold_ratio}"
        )
        print(f"HANDOFF: {handoff_path}")
        _append_history(
            runtime["root"],
            session_id,
            "handoff_generated",
            phase=resume_phase,
            data={"path": str(handoff_path), "reason": "malformed_backpressure"},
            dry_run=args.dry_run,
        )
        _append_diagnostics_event(
            diagnostics_bundle,
            "errors",
            "loop_failed",
            {
                "reason": "malformed_backpressure",
                "resume_phase": resume_phase,
            },
        )
        _finalize_lock("malformed_backpressure")
        return 9

    session_state["metrics"] = metrics
    write_json(session_path, session_state)

    _append_history(
        runtime["root"],
        session_id,
        "loop_started",
        data={"plan_path": str(plan_path), "phase_arg": str(args.phase)},
        dry_run=args.dry_run,
    )
    _append_diagnostics_event(
        diagnostics_bundle,
        "orchestration",
        "loop_started",
        {"plan_path": str(plan_path), "phase_arg": str(args.phase)},
    )

    context_remaining = _resolve_context_remaining(args.context_remaining)
    if context_remaining < 15:
        resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
        session_state.update(
            {
                "status": "paused",
                "next_action": "resume in a fresh session",
                "stop_reason": "context_below_15_percent",
                "last_checkpoint_at": _utc_now_iso(),
            }
        )
        write_json(session_path, session_state)
        handoff_path = _emit_handoff("context_below_15_percent", resume_phase)
        _append_history(
            runtime["root"],
            session_id,
            "loop_paused",
            phase=resume_phase,
            data={"reason": "context_below_15_percent", "resume_phase": resume_phase},
            dry_run=args.dry_run,
        )
        _append_history(
            runtime["root"],
            session_id,
            "handoff_generated",
            phase=resume_phase,
            data={"path": str(handoff_path), "reason": "context_below_15_percent"},
            dry_run=args.dry_run,
        )
        print("GOLDY LOOP STOP: remaining context below 15%.")
        current_phase = session_state.get("current_phase")
        if current_phase is not None:
            next_phase = int(current_phase) + 1
            print(
                f"Phase {current_phase} complete. Start a new session for Phase {next_phase} of {plan_path.name}."
            )
        print(f"Resume command: {_resume_command(resume_phase)}")
        print(f"HANDOFF: {handoff_path}")
        _append_diagnostics_event(
            diagnostics_bundle,
            "orchestration",
            "loop_paused",
            {"reason": "context_below_15_percent", "resume_command": _resume_command(resume_phase), "resume_phase": resume_phase},
        )
        _finalize_lock("context_below_15_percent")
        return 2

    # Initialize circuit breaker
    breaker = CircuitBreaker(runtime["root"], session_id)
    startup_result = breaker.startup_check(auto_reset=getattr(args, "breaker_auto_reset", False))
    if startup_result["action"] == "blocked":
        resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
        session_state["status"] = "paused"
        session_state["stop_reason"] = "breaker_open"
        session_state["next_action"] = "reset breaker and resume"
        write_json(session_path, session_state)
        handoff_path = _emit_handoff("breaker_open", resume_phase)
        _append_history(
            runtime["root"],
            session_id,
            "loop_failed",
            phase=resume_phase,
            data={
                "reason": "breaker_open",
                "breaker_reason": startup_result.get("reason"),
                "resume_phase": resume_phase,
            },
            dry_run=args.dry_run,
        )
        _append_history(
            runtime["root"],
            session_id,
            "handoff_generated",
            phase=resume_phase,
            data={"path": str(handoff_path), "reason": "breaker_open"},
            dry_run=args.dry_run,
        )
        print(f"GOLDY LOOP STOP: circuit breaker OPEN (reason: {startup_result.get('reason', 'unknown')})")
        print(f"HANDOFF: {handoff_path}")
        _print_breaker_remediation(startup_result.get("reason"))
        _finalize_lock("breaker_open_startup")
        return 6
    elif startup_result["action"] != "none":
        print(f"BREAKER STARTUP: {startup_result['action']} → state={startup_result['state']}")

    iterations = 0
    completed = set(int(p) for p in session_state.get("completed_phases", []))
    pending_phases = [phase for phase in selected_phases if int(phase["phase"]) not in completed]

    for phase in pending_phases:
        if iterations >= args.max_iterations:
            break

        # Check breaker before each phase
        if not breaker.can_execute():
            breaker_reason = str(breaker.status().get("open_reason") or "unknown")
            resume_phase = int(phase["phase"])
            session_state["status"] = "paused"
            session_state["stop_reason"] = "breaker_open"
            session_state["next_action"] = "reset breaker and resume"
            write_json(session_path, session_state)
            handoff_path = _emit_handoff("breaker_open_pre_phase", resume_phase)
            _append_history(
                runtime["root"],
                session_id,
                "loop_failed",
                phase=resume_phase,
                data={"reason": "breaker_open", "breaker_reason": breaker_reason, "resume_phase": resume_phase},
                dry_run=args.dry_run,
            )
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                phase=resume_phase,
                data={"path": str(handoff_path), "reason": "breaker_open_pre_phase"},
                dry_run=args.dry_run,
            )
            print(
                f"GOLDY LOOP STOP: circuit breaker OPEN before phase {int(phase['phase'])} "
                f"(reason: {breaker_reason})"
            )
            print(f"HANDOFF: {handoff_path}")
            _print_breaker_remediation(breaker_reason)
            _finalize_lock("breaker_open_pre_phase")
            return 6

        iterations += 1

        phase_number = int(phase["phase"])
        _append_history(
            runtime["root"],
            session_id,
            "phase_started",
            phase=phase_number,
            data={"title": str(phase.get("title", ""))},
            dry_run=args.dry_run,
        )
        _append_diagnostics_event(
            diagnostics_bundle,
            "orchestration",
            "phase_started",
            {"phase": phase_number, "title": str(phase.get("title", ""))},
        )
        session_state["current_phase"] = phase_number
        session_state["status"] = "running"
        session_state["last_checkpoint_at"] = _utc_now_iso()
        write_json(session_path, session_state)

        compaction_event = _run_compaction(
            execution_root,
            plan_path,
            session_id,
            f"phase {phase_number} {phase['title']} execution context",
        )
        metrics["compaction_runs_total"] = int(metrics.get("compaction_runs_total", 0)) + 1
        metrics["compaction_seconds_total"] = float(metrics.get("compaction_seconds_total", 0.0)) + float(
            compaction_event["seconds"]
        )
        history = metrics.setdefault("compaction_history", [])
        if isinstance(history, list):
            history.append(compaction_event)
            if len(history) > 50:
                del history[:-50]
        session_state["metrics"] = metrics
        write_json(session_path, session_state)

        phase_lines = plan_path.read_text(encoding="utf-8").splitlines()
        phase_block = _phase_block(phase_lines, phase)
        validation_result = strict_phase_validator(plan_path, phase)
        validation_result = apply_evidence_backpressure(validation_result, phase_block)
        task_summary = _phase_task_summary(plan_path, phase)

        phase_key = str(phase_number)
        lifecycle_store = session_state.setdefault("task_lifecycle", {})
        previous_lifecycle: dict[str, Any] | None = None
        if isinstance(lifecycle_store, dict):
            existing_payload = lifecycle_store.get(phase_key)
            if isinstance(existing_payload, dict):
                previous_lifecycle = existing_payload
        lifecycle_result = evaluate_phase_task_lifecycle(
            plan_path=plan_path,
            phase=phase,
            previous_payload=previous_lifecycle,
        )
        lifecycle_payload = lifecycle_result["payload"]
        lifecycle_checkpoint = persist_phase_task_lifecycle(runtime, session_id, phase_number, lifecycle_payload)
        if isinstance(lifecycle_store, dict):
            lifecycle_store[phase_key] = lifecycle_payload
        lifecycle_summary = dict(lifecycle_result["summary"])
        lifecycle_summary["checkpoint_path"] = str(lifecycle_checkpoint)
        lifecycle_summary["new_events_total"] = len(lifecycle_result.get("new_events", []))
        evidence_backpressure = validation_result.get("evidence_backpressure", {})
        if isinstance(evidence_backpressure, dict):
            lifecycle_summary["evidence_backpressure"] = evidence_backpressure

        _write_checkpoint(
            runtime,
            session_id,
            phase,
            "started",
            "phase_started",
            details={"task_lifecycle": lifecycle_summary},
            dry_run=args.dry_run,
        )

        checks = session_state.setdefault("phase_task_checks", {})
        if isinstance(checks, dict):
            checks[phase_key] = {
                **task_summary,
                "waived": validation_result["waived"],
                "task_lifecycle": lifecycle_summary,
            }
        print(
            f"TASK CHECK: phase {phase_number} checked={task_summary['checked']}/{task_summary['total']} "
            f"unchecked={task_summary['unchecked']} waived={validation_result['waived']}"
        )
        print(
            f"TASK LIFECYCLE: phase {phase_number} "
            f"states={json.dumps(lifecycle_summary.get('states', {}), sort_keys=True)} "
            f"retries={int(lifecycle_summary.get('retry_attempts_total', 0))}"
        )

        validated = bool(validation_result["validated"])
        reason = validation_result["reason"]
        if args.dry_run and validated:
            reason = "dry_run_phase_validated"
        elif args.dry_run and not validated and validation_result["unchecked"] > 0:
            # In dry-run mode, unchecked tasks are expected — skip strict enforcement
            validated = True
            reason = "dry_run_phase_validated"

        phase_title = str(phase.get("title", ""))
        evidence_payload = validation_result.get("evidence", {})
        evidence_text = ""
        if isinstance(evidence_payload, dict):
            evidence_text = str(evidence_payload.get("text", ""))
        iteration_text = "\n".join(item for item in (reason, phase_title, evidence_text) if item)
        base_signal = "test_only" if args.dry_run else ("progress" if validated else "no_progress")
        permission_bundle = classify_permission_denial(iteration_text)

        previous_stuck_state = metrics.get("stuck_detection", default_stuck_state())
        was_stuck = bool(previous_stuck_state.get("is_stuck", False))
        stuck_update = update_stuck_detection(
            previous_stuck_state,
            iteration=iterations,
            signal=base_signal,
            text=iteration_text,
            signal_window_size=int(breaker.thresholds.get("signal_window_size", 5)),
        )
        metrics["stuck_detection"] = stuck_update["state"]

        effective_signal = base_signal
        if not args.dry_run and stuck_update["completion_signal"]:
            effective_signal = "completion"
            signal_window = metrics["stuck_detection"].get("signal_window", [])
            if isinstance(signal_window, list) and signal_window and isinstance(signal_window[-1], dict):
                signal_window[-1]["signal"] = "completion"

        signal_counts = metrics.setdefault(
            "signal_counts",
            {"progress": 0, "no_progress": 0, "completion": 0, "test_only": 0, "error": 0},
        )
        signal_counts[effective_signal] = int(signal_counts.get(effective_signal, 0)) + 1
        if not validated and stuck_update["error_lines"]:
            signal_counts["error"] = int(signal_counts.get("error", 0)) + 1

        now_stuck = bool(metrics["stuck_detection"].get("is_stuck", False))
        if now_stuck and not was_stuck:
            metrics["stuck_events_total"] = int(metrics.get("stuck_events_total", 0)) + 1

        permission_denied = bool(stuck_update["permission_denied"]) or bool(permission_bundle["permission_denied"])
        if permission_denied:
            metrics["permission_events_total"] = int(metrics.get("permission_events_total", 0)) + 1
            _append_history(
                runtime["root"],
                session_id,
                "permission_denied",
                phase=phase_number,
                data={
                    "signals": permission_bundle.get("signals", []),
                    "summary": permission_bundle.get("summary", ""),
                },
                dry_run=args.dry_run,
            )
            print("PERMISSION SIGNAL: permission/tool denial detected.")
            print("Remediation: verify tool permissions, then reset breaker and resume if needed.")

        breaker_result = {"tripped": False, "reason": "ok", "trigger": "none"}
        if not args.dry_run:
            breaker_result = breaker.record_iteration(
                had_progress=validated,
                had_error=not validated,
                same_error=bool(stuck_update["repeated_error_match"]),
                permission_denied=permission_denied,
                completion_signal=bool(stuck_update["completion_signal"]),
            )
            if str(breaker_result.get("trigger", "none")) != "none":
                metrics["breaker_events_total"] = int(metrics.get("breaker_events_total", 0)) + 1

        session_state["metrics"] = metrics
        write_json(session_path, session_state)

        if not args.dry_run and bool(breaker_result.get("tripped")):
            breaker_reason = str(breaker_result.get("reason", "breaker_open"))
            _write_checkpoint(
                runtime,
                session_id,
                phase,
                "failed",
                f"breaker_open:{breaker_reason}",
                details={
                    "task_lifecycle": lifecycle_summary,
                    "evidence_backpressure": validation_result.get("evidence_backpressure", {}),
                },
                dry_run=args.dry_run,
            )
            _append_history(
                runtime["root"],
                session_id,
                "phase_failed",
                phase=phase_number,
                data={"reason": breaker_reason},
                dry_run=args.dry_run,
            )
            _append_diagnostics_event(
                diagnostics_bundle,
                "orchestration",
                "phase_failed",
                {"phase": phase_number, "reason": breaker_reason},
            )
            session_state["status"] = "paused"
            session_state["next_action"] = "reset breaker and resume"
            session_state["stop_reason"] = breaker_reason
            session_state["last_checkpoint_at"] = _utc_now_iso()
            write_json(session_path, session_state)
            handoff_path = _emit_handoff(breaker_reason, phase_number)
            _append_history(
                runtime["root"],
                session_id,
                "loop_failed",
                phase=phase_number,
                data={"reason": breaker_reason, "resume_phase": phase_number},
                dry_run=args.dry_run,
            )
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                phase=phase_number,
                data={"path": str(handoff_path), "reason": breaker_reason},
                dry_run=args.dry_run,
            )
            print(f"GOLDY LOOP STOP: circuit breaker OPEN (reason: {breaker_reason})")
            print(f"HANDOFF: {handoff_path}")
            _print_breaker_remediation(breaker_reason)
            _finalize_lock("breaker_open_iteration")
            return 6

        commit_info = "commit_skipped"
        if args.commit_phase and not args.dry_run and validated:
            committed, commit_message = _commit_phase(execution_root, phase, session_id)
            commit_info = commit_message if committed else f"commit_skipped:{commit_message}"

        if not validated:
            _write_checkpoint(
                runtime,
                session_id,
                phase,
                "failed",
                reason,
                details={
                    "task_lifecycle": lifecycle_summary,
                    "validation": {
                        "reason": validation_result.get("reason"),
                        "unchecked": validation_result.get("unchecked", 0),
                        "waived": validation_result.get("waived", 0),
                    },
                    "evidence_backpressure": validation_result.get("evidence_backpressure", {}),
                },
                dry_run=args.dry_run,
            )
            _append_diagnostics_event(
                diagnostics_bundle,
                "orchestration",
                "phase_failed",
                {"phase": phase_number, "reason": reason},
            )
            _append_history(
                runtime["root"],
                session_id,
                "phase_failed",
                phase=phase_number,
                data={"reason": reason},
                dry_run=args.dry_run,
            )
            session_state["status"] = "paused"
            session_state["next_action"] = "fix checklist coverage and resume loop"
            session_state["stop_reason"] = reason
            session_state["last_checkpoint_at"] = _utc_now_iso()
            write_json(session_path, session_state)
            handoff_path = _emit_handoff(reason, phase_number)
            _append_history(
                runtime["root"],
                session_id,
                "loop_paused",
                phase=phase_number,
                data={"reason": reason, "resume_phase": phase_number},
                dry_run=args.dry_run,
            )
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                phase=phase_number,
                data={"path": str(handoff_path), "reason": reason},
                dry_run=args.dry_run,
            )
            print(f"GOLDY LOOP STOP: {reason}")
            print(f"HANDOFF: {handoff_path}")
            _finalize_lock("phase_validation_failed")
            return 5

        _write_checkpoint(
            runtime,
            session_id,
            phase,
            "completed",
            reason,
            details={
                "task_lifecycle": lifecycle_summary,
                "evidence_backpressure": validation_result.get("evidence_backpressure", {}),
            },
            dry_run=args.dry_run,
        )
        _append_history(
            runtime["root"],
            session_id,
            "phase_completed",
            phase=phase_number,
            data={"reason": reason},
            dry_run=args.dry_run,
        )
        _append_diagnostics_event(
            diagnostics_bundle,
            "orchestration",
            "phase_completed",
            {"phase": phase_number, "reason": reason},
        )
        session_state.setdefault("completed_phases", [])
        if phase_number not in session_state["completed_phases"]:
            session_state["completed_phases"].append(phase_number)

        session_state["last_checkpoint_at"] = _utc_now_iso()
        session_state["next_action"] = "run next phase"
        write_json(session_path, session_state)

        print(f"Phase {phase_number} complete: {phase['title']} ({reason}; {commit_info})")
        print(
            f"Phase {phase_number} complete. Start a new session for Phase {phase_number + 1} of {plan_path.name}."
        )

        # Post-phase browser smoke check (if --browser-check is set)
        if args.browser_check and not args.dry_run:
            smoke_protocol = build_smoke_check(args.browser_check)
            print(f"BROWSER SMOKE CHECK: {args.browser_check}")
            print(format_protocol(smoke_protocol))

    all_complete = set(int(p["phase"]) for p in selected_phases).issubset(set(session_state.get("completed_phases", [])))
    if all_complete:
        audits = run_deep_code_audits(execution_root, args.dry_run, policy=audit_policy)
        audit_seconds = sum(float(item.get("seconds", 0.0)) for item in audits)
        metrics["deep_audit_runs_total"] = int(metrics.get("deep_audit_runs_total", 0)) + len(audits)
        metrics["deep_audit_seconds_total"] = float(metrics.get("deep_audit_seconds_total", 0.0)) + audit_seconds
        metrics["loop_seconds_total"] = float(metrics.get("loop_seconds_total", 0.0)) + (monotonic() - loop_started)
        for audit in audits:
            _append_history(
                runtime["root"],
                session_id,
                "audit_result",
                data={
                    "id": audit.get("id"),
                    "category": audit.get("category"),
                    "status": audit.get("status"),
                    "method": audit.get("method"),
                },
                dry_run=args.dry_run,
            )

        session_state["deep_audits"] = audits
        session_state["audit_policy"] = audit_policy
        session_state["metrics"] = metrics
        policy_eval = evaluate_audit_policy(audits, audit_policy)
        session_state["audit_policy_evaluation"] = policy_eval
        if bool(policy_eval.get("blocked")) and not args.dry_run:
            metrics["policy_failures_total"] = int(metrics.get("policy_failures_total", 0)) + 1
            session_state["metrics"] = metrics
            resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
            session_state["status"] = "paused"
            session_state["next_action"] = "resolve deep audit failures and rerun /goldy-loop"
            session_state["stop_reason"] = str(policy_eval.get("reason", "deep_audit_failed"))
            session_state["last_checkpoint_at"] = _utc_now_iso()
            write_json(session_path, session_state)
            _append_history(
                runtime["root"],
                session_id,
                "loop_failed",
                phase=resume_phase,
                data={
                    "reason": str(policy_eval.get("reason", "deep_audit_failed")),
                    "issues": policy_eval.get("issues", []),
                    "resume_phase": resume_phase,
                },
                dry_run=args.dry_run,
            )
            handoff_path = _emit_handoff("deep_audit_failed", resume_phase)
            _append_history(
                runtime["root"],
                session_id,
                "handoff_generated",
                phase=resume_phase,
                data={"path": str(handoff_path), "reason": "deep_audit_failed"},
                dry_run=args.dry_run,
            )
            _append_diagnostics_event(
                diagnostics_bundle,
                "errors",
                "loop_failed",
                {
                    "reason": "deep_audit_failed",
                    "issues": policy_eval.get("issues", []),
                },
            )
            print_completion_report(plan_path, session_id, session_state, audits)
            print(f"GOLDY LOOP STOP: {policy_eval.get('reason', 'deep_audit_failed')}")
            print(f"HANDOFF: {handoff_path}")
            _finalize_lock("deep_audit_failed")
            return 4

        session_state["status"] = "loop_complete"
        session_state["next_action"] = "LOOP_COMPLETE"
        write_json(session_path, session_state)
        handoff_path = _emit_handoff("loop_complete")
        _append_history(
            runtime["root"],
            session_id,
            "loop_completed",
            data={"reason": "loop_complete", "resume_phase": None},
            dry_run=args.dry_run,
        )
        _append_diagnostics_event(
            diagnostics_bundle,
            "orchestration",
            "loop_completed",
            {"reason": "loop_complete"},
        )
        print_completion_report(plan_path, session_id, session_state, audits)
        print("LOOP_COMPLETE")
        print(f"Resume chain pointer: {_resume_command(None)}")
        print(f"HANDOFF: {handoff_path}")
        _finalize_lock("loop_complete")
        return 0

    resume_phase = compute_resume_phase(selected_phases, session_state.get("completed_phases", []))
    history_summary = replay_history(runtime["root"], session_id)
    if resume_phase is None and isinstance(history_summary.get("resume_phase"), int):
        resume_phase = int(history_summary["resume_phase"])

    metrics["loop_seconds_total"] = float(metrics.get("loop_seconds_total", 0.0)) + (monotonic() - loop_started)
    session_state["metrics"] = metrics
    session_state["status"] = "paused"
    session_state["next_action"] = "resume from next pending phase"
    write_json(session_path, session_state)
    handoff_path = _emit_handoff("max_iterations_reached", resume_phase)
    _append_history(
        runtime["root"],
        session_id,
        "loop_paused",
        phase=resume_phase,
        data={"reason": "max_iterations_reached", "resume_phase": resume_phase},
        dry_run=args.dry_run,
    )
    _append_history(
        runtime["root"],
        session_id,
        "handoff_generated",
        phase=resume_phase,
        data={"path": str(handoff_path), "reason": "max_iterations_reached"},
        dry_run=args.dry_run,
    )
    print("Loop paused before completion.")
    print(f"Resume: {_resume_command(resume_phase)}")
    print(f"HANDOFF: {handoff_path}")
    _finalize_lock("max_iterations_reached")
    return 1


def main() -> int:
    args = parse_args()
    if args.commands:
        print_command_reference()
        return 0

    # Breaker operator commands (work without --plan)
    if args.breaker_status or args.breaker_reset:
        project_root = Path(args.project_root).expanduser().resolve()
        runtime = ensure_runtime(project_root)
        session_id = resolve_session_id(project_root=project_root) if args.resume == "auto" else args.resume
        breaker = CircuitBreaker(runtime["root"], session_id)
        if args.breaker_reset:
            breaker.reset("operator_manual_reset")
            print("BREAKER RESET: state=CLOSED")
        breaker.print_status()
        return 0

    if not args.plan:
        print_command_reference()
        print("")
        print("No --plan provided. Provide a user plan file to execute the loop.")
        return 0
    try:
        return run_loop(args)
    except Exception as exc:  # pragma: no cover - defensive CLI guard.
        print(f"GOLDY LOOP ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
