# GOLDY Planning Contract

Full details for `/goldy` planning and orchestration mode.

## Gold Standard Plan Structure

GOLDY prefers the Gold Standard plan template for all plans. Required sections (in order):
1. Document Control
2. Repo Structure Decision
3. Problem Statement
4. Goals (numbered, verifiable)
5. Non-Goals
6. Hard Constraints (checklist-evidence rule + 15% context guardrail)
7. Current Codebase Findings (Audit Baseline)
8. Functional Requirements (FR-XX)
9. Tests (per-phase, monotonically increasing)
10. Error Correction (inline)
11. Phases (mandatory guardrail headers, granular tasks, evidence lines)
12. Acceptance Targets (20-36 testable assertions)
13. Assumptions
14. Execution Notes

Template: `~/.claude/GOLD-STANDARD-SAMPLE-PLAN.md`

## Plan Creation Behavior

- Creates plans in `temp-plans/` with filename: `timestamp + prompt-session-id`.
- Uses active plan if one already exists.
- Loads full memory, then injects compact Resume Capsule (not raw memory).
- Prints a visible activation banner when GOLDY activates.

## Stack-Aware Resolution

Resolves stack profile with precedence:
1. Global baseline
2. Platform defaults
3. Auto-detected dependencies/config
4. Project overrides (`.goldy/profile.yaml`)

## Memory + Compaction Pipeline

- Load all memory sources for retrieval/indexing.
- Rank with hybrid retrieval (lexical + semantic-hash + recency).
- Compact to a bounded Resume Capsule (`~1500 tokens` target by default).
- Inject capsule, not full memory payload.
- `--target-tokens <n>` overrides capsule budget.

## Auto Invoke

When explicit `/goldy` is omitted, GOLDY activates on two intent classes:

1. **Planning intent**: plan, planning, phase, roadmap, spec, architecture, implementation, sequencing
2. **Coding intent** (triggers plan creation if no active plan exists): fix, bug, implement, build, add, create, refactor, migrate, update, upgrade, feature, endpoint, component, test, debug, deploy, optimize, integrate, change, modify, remove, delete

When coding intent is detected and a new plan is created (no existing plan found), goldy emits `plan_mode_required: true`. Claude must enter plan mode and populate the plan before any implementation begins.

When coding intent is detected but an existing active plan is found, goldy reuses the existing plan and does NOT emit `plan_mode_required`.

Auto invoke prints a visible activation banner and applies to `/goldy` planning only.
Auto invoke must never start `/goldy-loop`.

## UI/UX Module Reuse

GOLDY keeps `ui-ux-pro-max` scripts/data. Use when design output is requested:

```bash
python3 /Users/forest/.agents/skills/goldy/scripts/search.py "<query>" --design-system
```

## Key Constraints

- `/goldy` never creates, reuses, or deletes git worktrees.
- `/goldy` never auto-invokes `/goldy-loop`.
- If worktree execution is needed, the user must run `/goldy-loop` explicitly.
