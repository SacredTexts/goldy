#!/usr/bin/env python3
"""Install GOLDY links and slash commands — GLOBAL scope only.

This installer deploys goldy to ~/.agents/ and ~/.claude/ (user-global).
No per-project installation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

HOME = Path.home()
SOURCE_SKILL = HOME / ".agents/skills/goldy"
GLOBAL_CLAUDE_COMMANDS = HOME / ".claude/commands"
GLOBAL_CLAUDE_SKILLS = HOME / ".claude/skills"
CODEX_SKILLS = HOME / ".codex/skills"

GOLDY_COMMAND = """---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Activate GOLDY planning/orchestration with stack-aware resume capsules
argument-hint: [--plan <plan-file>] [options]
---

# GOLDY

Run GOLDY command engine:

```bash
python3 {scripts_dir}/goldy.py $ARGUMENTS
```

Behavior:
- Uses explicit `--plan` when provided.
- Creates a fresh `temp-plans/` Gold Standard temp plan for prompt-driven calls.
- For coding-intent auto-invocations, reuses existing plan if one exists; creates new only when none found.
- Reuses active/latest temp plan only when prompt is empty (or by explicit workflow choice).
- Loads full memory then injects compact Resume Capsule.
- Prints a visible activation banner.
- Never creates, reuses, or deletes git worktrees.
- Never auto-invokes `/goldy-loop`.
- If worktree execution is needed, run `/goldy-loop` manually in the prompt.

## After goldy runs -- Plan Mode Protocol

Read the goldy output carefully. If the output contains `plan_mode_required: True`:
1. **STOP** -- do not write any implementation code.
2. **Enter plan mode** -- use the plan file path from goldy's `plan:` output line.
3. **Fill in the plan** -- populate the Gold Standard template sections (Problem Statement, Goals, Phases, etc.) based on the user's original prompt.
4. **Present the plan to the user** for review/approval before any coding begins.
5. Only after the user approves the plan, exit plan mode and begin implementation.

If `plan_mode_required` is False or absent, proceed normally with the active plan.
"""

GOLDY_LOOP_COMMAND = """---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Run GOLDY phase loop with checkpoints and auto-resume chain
argument-hint: --plan <plan-file> [options]
---

# GOLDY LOOP

Run GOLDY loop engine:

```bash
python3 {scripts_dir}/goldy_loop.py $ARGUMENTS
```

Behavior:
- Manual-only command; do not auto-invoke from `/goldy`.
- Guardrail-compliant stop on low context.
- Creates/reuses a session git worktree by default.
- Requires a user-authored plan outside `temp-plans/` (unless `--allow-temp-plan` is set).
- Worktree identity is derived from the plan file, so different plan files use different worktrees.
- Enforces plan drift detection; use `--require-resync` to sync source plan into mapped worktree plan copy.
- Runs preflight ambiguity checks and asks clarifying questions before executing the loop.
- After preflight, offers `Start` and `Chat` options before execution.
- Runs up to 10 loop iterations by default (`--max-iterations` to override).
- Runs 5 deep audits (lint, typecheck, tests, integration, robustness) before final completion.
- Prints a completion report including total compactions and total minutes.
- Writes checkpoints, append-only history, lock metadata, diagnostics (optional), and deterministic handoff artifacts.
- Supports resume via session id.
- Supports breaker operator controls (`--breaker-status`, `--breaker-reset`, `--breaker-auto-reset`).
- Supports `--diagnostics` for per-session diagnostic bundles in `.goldy/diagnostics`.
- Optional phase-level commits with `--commit-phase`.
- `--commands` prints full command list + usage examples.
- Running without `--plan` prints the same command reference.
"""


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _symlink(target: Path, link_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()
    link_path.symlink_to(target)


def install() -> None:
    scripts_dir = str(SOURCE_SKILL / "scripts")

    # Global symlinks only
    _symlink(SOURCE_SKILL, GLOBAL_CLAUDE_SKILLS / "goldy")
    CODEX_SKILLS.mkdir(parents=True, exist_ok=True)
    _symlink(SOURCE_SKILL, CODEX_SKILLS / "goldy")

    # Render command templates with resolved paths
    goldy_cmd = GOLDY_COMMAND.format(scripts_dir=scripts_dir)
    loop_cmd = GOLDY_LOOP_COMMAND.format(scripts_dir=scripts_dir)

    checksums = {}
    checksums[str(GLOBAL_CLAUDE_COMMANDS / "goldy.md")] = _write(
        GLOBAL_CLAUDE_COMMANDS / "goldy.md", goldy_cmd
    )
    checksums[str(GLOBAL_CLAUDE_COMMANDS / "goldy-loop.md")] = _write(
        GLOBAL_CLAUDE_COMMANDS / "goldy-loop.md", loop_cmd
    )

    # Clean up legacy command files if they exist
    legacy = GLOBAL_CLAUDE_COMMANDS / "goldy-chrome.md"
    if legacy.exists():
        legacy.unlink()

    print("GOLDY install complete (global scope).")
    print("Checksums:")
    for path, digest in sorted(checksums.items()):
        print(f"- {path}: {digest}")


def verify() -> int:
    required = [
        GLOBAL_CLAUDE_SKILLS / "goldy",
        GLOBAL_CLAUDE_COMMANDS / "goldy.md",
        GLOBAL_CLAUDE_COMMANDS / "goldy-loop.md",
        SOURCE_SKILL / "scripts" / "goldy.py",
        SOURCE_SKILL / "scripts" / "goldy_loop.py",
    ]

    # Optional — don't fail if codex isn't used
    optional = [CODEX_SKILLS / "goldy"]

    missing = [p for p in required if not p.exists() and not p.is_symlink()]
    if missing:
        print("Missing required artifacts:")
        for path in missing:
            print(f"- {path}")
        return 1

    missing_opt = [p for p in optional if not p.exists() and not p.is_symlink()]
    if missing_opt:
        print("Optional (non-blocking):")
        for path in missing_opt:
            print(f"- {path}")

    print("GOLDY install verification passed (global scope).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install/verify GOLDY artifacts (global only)")
    parser.add_argument("action", choices=["install", "verify"], default="install")
    args = parser.parse_args()

    if args.action == "install":
        install()
        return 0
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
