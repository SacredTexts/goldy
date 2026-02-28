---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Activate GOLDY planning/orchestration with stack-aware resume capsules
argument-hint: [--plan <plan-file>] [options]
---

# GOLDY

Run GOLDY command engine:

```bash
python3 /Users/forest/.agents/skills/goldy/scripts/goldy.py $ARGUMENTS
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
