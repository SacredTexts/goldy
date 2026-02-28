# GOLDY Loop Execution Contract

Full details for `/goldy-loop` phase automation.

## Invocation

```bash
python3 /Users/forest/.agents/skills/goldy/scripts/goldy_loop.py $ARGUMENTS
```

Manual-only: run only when the user explicitly invokes `/goldy-loop` or calls the script directly.

## Command Contract (C-01)

- `--commands` and no-plan invocation must print the same deterministic command reference.
- Reference output must include:
  - workflow paragraph (default `10` loops, per-loop checklist validation, post-completion `5` deep audits)
  - supported options and behavior notes
  - usage examples

## Worktree + Plan Mapping

- Default mode creates/reuses a plan-based git worktree (`--no-worktree` to skip).
- Worktree identity is derived from `_plan_token(plan_path)`.
- Branch format (C-02): `goldy-loop/<plan-stem>-<hash>`.
- Different plan files map to different worktree identities.
- Worktrees are never auto-deleted by GOLDY.

## Plan Drift Contract

- GOLDY computes source-plan and mapped-plan hashes before execution.
- If hashes drift, execution halts with stop reason `plan_drift_detected` and emits a handoff.
- `--require-resync` explicitly copies source plan into worktree plan path and then continues.
- Resync is an explicit operator action and is allowed even in dry-run mode.

## Preflight + Mode Selection

- Preflight checks for ambiguous structure (placeholders, missing validation gates, missing checklist structure).
- Without required answers, execution blocks with clarifying questions.
- Mode options after preflight are exactly:
  - `Start`
  - `Chat`
- `--mode start|chat` forces non-interactive selection.

## Runtime Artifacts (`.goldy/`)

- `sessions/<session-id>.json`: session state + metrics.
- `checkpoints/<session-id>/phase-*.json`: per-phase checkpoint trail.
- `history/<session-id>.jsonl`: append-only event history with replay metadata.
- `loop.lock`: primary-loop lock metadata (PID/session/timestamp/plan).
- `diagnostics/<timestamp>-<session-id>/` (when enabled):
  - `agent-output.jsonl`
  - `orchestration.jsonl`
  - `errors.jsonl`
  - `performance.jsonl`
  - `bundle.json` manifest
- `handoffs/<session-id>.md`: deterministic handoff artifact with completed/pending tasks and exact resume command.

## Execution Loop

- Default loop budget: up to `10` iterations (`--max-iterations` to override).
- Each iteration performs:
  - context compaction
  - strict checklist validation
  - lifecycle + evidence-backpressure checks
  - breaker/stuck/permission signal accounting
- On full completion, GOLDY runs exactly five audits:
  1. lint
  2. typecheck
  3. tests
  4. integration/build
  5. robustness/security

## Circuit Breaker Controls

- State model: `CLOSED -> HALF_OPEN -> OPEN`.
- Tracks:
  - no-progress streak
  - repeated-error streak
  - permission-denial streak
  - completion-signal streak
- Operator commands:
  - `--breaker-status`
  - `--breaker-reset`
  - `--breaker-auto-reset`
- Supported env overrides:
  - `GOLDY_BREAKER_NO_PROGRESS_THRESHOLD`
  - `GOLDY_BREAKER_REPEATED_ERROR_THRESHOLD`
  - `GOLDY_BREAKER_PERMISSION_DENIAL_THRESHOLD`
  - `GOLDY_BREAKER_COMPLETION_SIGNAL_THRESHOLD`
  - `GOLDY_BREAKER_COOLDOWN_MINUTES`
  - `GOLDY_BREAKER_SIGNAL_WINDOW_SIZE`

## Malformed Event Backpressure

- Malformed-history pressure is measured before phase execution.
- Threshold controls:
  - `GOLDY_MALFORMED_EVENT_THRESHOLD_COUNT` (default `3`)
  - `GOLDY_MALFORMED_EVENT_THRESHOLD_RATIO` (default `0.25`)
- When threshold is exceeded, GOLDY halts with stop reason `malformed_backpressure` and emits handoff + diagnostics error entry.

## Resume + Handoff

- Resume command form:
  - `/goldy-loop --plan <path> --resume <session-id>`
  - optional `--phase <N>` pointer is emitted when deterministic.
- Handoff artifact includes:
  - stop reason
  - completed tasks
  - pending tasks
  - exact resume command

## Plan Input Rules

- Plans inside `temp-plans/` are blocked by default.
- `--allow-temp-plan` is the explicit override.
- `--dry-run` simulates loop behavior without normal mutating loop actions (except explicit `--require-resync` plan copy).
