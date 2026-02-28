#!/usr/bin/env python3
"""GOLDY command entrypoint.

Creates/loads active plans, resolves stack profile, and emits a deterministic
resume capsule with bounded token budget.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from goldy_memory import (
    DEFAULT_TARGET_TOKENS,
    append_raw_memory,
    build_resume_capsule,
    retrieve_ranked_entries,
    save_capsule,
)
from goldy_session import build_plan_filename, read_json, resolve_session_id, slugify, write_json
from goldy_stack import resolve_stack_profile

INTENT_KEYWORDS = (
    "plan",
    "planning",
    "brainstorm",
    "architecture",
    "roadmap",
    "phase",
    "milestone",
    "to-do",
    "todo",
    "spec",
    "design",
    "refactor",
    "loop",
)

CODING_KEYWORDS = (
    "fix",
    "bug",
    "implement",
    "build",
    "add",
    "create",
    "migrate",
    "update",
    "upgrade",
    "feature",
    "endpoint",
    "component",
    "test",
    "debug",
    "deploy",
    "optimize",
    "integrate",
    "change",
    "modify",
    "remove",
    "delete",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GOLDY planner/orchestrator")
    parser.add_argument("prompt", nargs="*", help="Planning prompt")
    parser.add_argument("--plan", type=str, default=None, help="Use explicit plan path")
    parser.add_argument("--stack", type=str, default=None, help="Optional stack profile name hint")
    parser.add_argument("--temp-plan", action="store_true", help="Force temporary plan creation")
    parser.add_argument("--no-auto", action="store_true", help="Disable intent-triggered auto mode")
    parser.add_argument("--project-root", type=str, default=os.getcwd(), help="Project root")
    parser.add_argument("--target-tokens", type=int, default=DEFAULT_TARGET_TOKENS, help="Capsule token budget")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser.parse_args()


def classify_intent(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in INTENT_KEYWORDS)


def classify_coding_intent(prompt: str) -> bool:
    """Return True if the prompt looks like coding/implementation work."""
    if not prompt:
        return False
    lowered = prompt.lower()
    return any(keyword in lowered for keyword in CODING_KEYWORDS)


def ensure_goldy_runtime(project_root: Path) -> dict[str, Path]:
    goldy_root = project_root / ".goldy"
    sessions_dir = goldy_root / "sessions"
    checkpoints_dir = goldy_root / "checkpoints"
    memory_dir = goldy_root / "memory"
    capsules_dir = goldy_root / "resume-capsules"
    for directory in (goldy_root, sessions_dir, checkpoints_dir, memory_dir, capsules_dir):
        directory.mkdir(parents=True, exist_ok=True)

    config_path = goldy_root / "config.yaml"
    if not config_path.exists():
        config_payload = {
            "name": "goldy",
            "memory_policy": "everything_always_with_compaction",
            "resume_capsule_target_tokens": DEFAULT_TARGET_TOKENS,
            "auto_invoke": "intent_triggered_visible_banner",
        }
        config_path.write_text(json.dumps(config_payload, indent=2, sort_keys=True), encoding="utf-8")

    index_path = goldy_root / "index.json"
    if not index_path.exists():
        write_json(
            index_path,
            {
                "active_plan": None,
                "last_session": None,
                "plans": [],
            },
        )

    profile_path = goldy_root / "profile.yaml"
    if not profile_path.exists():
        profile_path.write_text(
            json.dumps(
                {
                    "name": "platform-override",
                    "frameworks": ["tanstack-start", "react-19", "typescript"],
                    "db": ["drizzle", "neon-postgres"],
                    "auth": ["workos", "rbac"],
                    "ui": ["radix-ui", "shadcn"],
                    "testing": ["vitest", "playwright"],
                    "build": ["pnpm", "vite"],
                    "routing": ["tanstack-router"],
                    "rules": [
                        "Use Gold Standard planning method.",
                        "Create temp plan if no active plan exists.",
                        "Guardrails must not be bypassed.",
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    return {
        "goldy_root": goldy_root,
        "config": config_path,
        "index": index_path,
        "profile": profile_path,
        "sessions": sessions_dir,
        "checkpoints": checkpoints_dir,
    }


def find_latest_plan(temp_plans_dir: Path) -> Path | None:
    candidates = sorted(temp_plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def build_plan_from_template(template: str, session_id: str, plan_title: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    replacements = {
        "[Product Name]": "GOLDY",
        "[Plan Name]": plan_title,
        "[product-name]": "goldy",
        "[Product Display Name]": "GOLDY",
        "[plan-filename].md": f"{session_id}--{slugify(plan_title)}.md",
        "YYYY-MM-DD": today,
    }
    content = template
    for old, new in replacements.items():
        content = content.replace(old, new)
    return content


def resolve_active_plan(
    args: argparse.Namespace,
    project_root: Path,
    runtime: dict[str, Path],
    session_id: str,
    prompt_text: str,
    coding_only: bool = False,
) -> tuple[Path, bool]:
    """Resolve the active plan. Returns (plan_path, is_new_plan).

    When coding_only=True, tries to reuse an existing plan before creating
    a new one. This prevents coding-intent auto-invocations from always
    generating fresh plans when one already exists.
    """
    temp_plans_dir = project_root / "temp-plans"
    temp_plans_dir.mkdir(parents=True, exist_ok=True)

    index = read_json(runtime["index"], {"active_plan": None, "plans": []})

    if args.plan:
        plan_path = Path(args.plan).expanduser().resolve()
        if not plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {plan_path}")
        index["active_plan"] = str(plan_path)
        write_json(runtime["index"], index)
        return plan_path, False

    # Prompt-driven /goldy usage should create a fresh temp plan unless a concrete
    # --plan path is provided. This prevents stale active-plan reuse for new tasks.
    # When coding_only=True, we prefer reusing an existing plan (don't force new).
    force_new_temp_plan = bool(args.temp_plan or (prompt_text.strip() and not coding_only))

    if not force_new_temp_plan:
        active = index.get("active_plan")
        if active and Path(active).exists():
            return Path(active), False

        latest = find_latest_plan(temp_plans_dir)
        if latest is not None:
            index["active_plan"] = str(latest)
            write_json(runtime["index"], index)
            return latest, False

    template_path = Path.home() / ".claude" / "GOLD-STANDARD-SAMPLE-PLAN.md"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else "# GOLDY Plan\n"

    filename = build_plan_filename(
        prompt=prompt_text or "goldy-session",
        session_id=session_id,
        suffix="goldy-completion-plan",
    )
    plan_path = temp_plans_dir / filename
    if plan_path.exists():
        print(
            f"GOLDY WARNING: temp plan filename collision detected: {plan_path.name}",
            file=sys.stderr,
        )
        stem = plan_path.stem
        suffix = plan_path.suffix
        counter = 2
        while True:
            candidate = temp_plans_dir / f"{stem}-v{counter}{suffix}"
            if not candidate.exists():
                plan_path = candidate
                print(
                    f"GOLDY WARNING: using fallback temp plan name: {plan_path.name}",
                    file=sys.stderr,
                )
                break
            counter += 1
    title = prompt_text or "GOLDY Completion Plan"
    plan_path.write_text(build_plan_from_template(template, session_id, title), encoding="utf-8")

    index.setdefault("plans", []).append(str(plan_path))
    index["active_plan"] = str(plan_path)
    write_json(runtime["index"], index)
    return plan_path, True


def main() -> int:
    args = parse_args()
    try:
        project_root = Path(args.project_root).expanduser().resolve()
        prompt_text = " ".join(args.prompt).strip()
        session_id = resolve_session_id(project_root=project_root)
        runtime = ensure_goldy_runtime(project_root)

        intent_match = classify_intent(prompt_text)
        coding_match = classify_coding_intent(prompt_text)
        auto_mode = (intent_match or coding_match) and not args.no_auto
        coding_only = coding_match and not intent_match

        active_plan, is_new_plan = resolve_active_plan(
            args, project_root, runtime, session_id, prompt_text, coding_only=coding_only
        )
        plan_mode_required = coding_only and is_new_plan
        stack_profile = resolve_stack_profile(project_root, runtime["profile"])
        if args.stack:
            stack_profile["name"] = args.stack

        retrieval_query = prompt_text or "resume previous session state"
        ranked_entries = retrieve_ranked_entries(project_root, active_plan, retrieval_query)
        capsule = build_resume_capsule(ranked_entries, target_tokens=args.target_tokens)
        capsule_path = save_capsule(project_root, session_id, capsule)

        session_payload: dict[str, Any] = {
            "session_id": session_id,
            "thread_id": os.environ.get("CODEX_THREAD_ID", session_id),
            "plan_id": active_plan.stem,
            "plan_path": str(active_plan),
            "status": "active",
            "next_action": "continue planning/execution from active plan",
            "auto_mode": auto_mode,
            "intent_match": intent_match,
            "coding_match": coding_match,
            "plan_mode_required": plan_mode_required,
            "stack_profile": stack_profile,
        }
        session_file = runtime["sessions"] / f"{session_id}.json"
        write_json(session_file, session_payload)

        index_payload = read_json(runtime["index"], {"active_plan": str(active_plan), "plans": []})
        index_payload["last_session"] = session_id
        index_payload["last_thread"] = session_payload["thread_id"]
        write_json(runtime["index"], index_payload)

        append_raw_memory(
            project_root,
            session_id,
            {
                "prompt": prompt_text,
                "active_plan": str(active_plan),
                "capsule_path": str(capsule_path),
                "intent_match": intent_match,
            },
        )

        if plan_mode_required:
            banner = "GOLDY ACTIVE (PLAN MODE REQUIRED)"
        elif auto_mode:
            banner = "GOLDY ACTIVE (AUTO-INVOKE)"
        else:
            banner = "GOLDY ACTIVE"
        output = {
            "banner": banner,
            "session_id": session_id,
            "active_plan": str(active_plan),
            "resume_capsule": str(capsule_path),
            "stack_profile": stack_profile,
            "intent_match": intent_match,
            "coding_match": coding_match,
            "plan_mode_required": plan_mode_required,
        }

        if args.json:
            print(json.dumps(output, indent=2, sort_keys=True))
        else:
            print(f"=== {banner} ===")
            print(f"session_id: {session_id}")
            print(f"plan: {active_plan}")
            print(f"resume_capsule: {capsule_path}")
            print(f"stack_profile: {stack_profile.get('name')}")
            print("loaded_stack:", ", ".join(stack_profile.get("frameworks", []) + stack_profile.get("db", [])))
            print(f"intent_match: {intent_match}")
            print(f"coding_match: {coding_match}")
            print(f"plan_mode_required: {plan_mode_required}")
            if plan_mode_required:
                print("")
                print("ACTION REQUIRED: Enter plan mode. Fill in the plan at the path above before writing any code.")

        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"GOLDY ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
