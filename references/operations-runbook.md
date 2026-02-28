# GOLDY Operations Runbook

## Install / Verify

```bash
python3 /Users/forest/.agents/skills/goldy/scripts/goldy_install.py install
python3 /Users/forest/.agents/skills/goldy/scripts/goldy_install.py verify
```

## Core Commands

| Command | Quick usage |
|---------|------------|
| `/goldy` | `/goldy <prompt>` (planning/orchestration only) |
| `/goldy-loop` | `/goldy-loop --plan <path> --mode start` (phase execution) |

For full flags and examples: `/goldy-loop --commands`.

## Common Loop Operations

Start:

```bash
/goldy-loop --plan plans/my-plan.md --mode start
```

Chat pause:

```bash
/goldy-loop --plan plans/my-plan.md --mode chat
```

Resume explicit session:

```bash
/goldy-loop --plan plans/my-plan.md --resume <session-id> --mode start
```

Resume after drift (safe resync):

```bash
/goldy-loop --plan plans/my-plan.md --resume <session-id> --require-resync --mode start
```

## Breaker Operations

Inspect breaker:

```bash
/goldy-loop --breaker-status --project-root <path>
```

Manual reset:

```bash
/goldy-loop --breaker-reset --project-root <path>
```

Startup auto-reset for OPEN state:

```bash
/goldy-loop --plan plans/my-plan.md --breaker-auto-reset --mode start
```

## Diagnostics + Handoff

Enable diagnostics bundle:

```bash
/goldy-loop --plan plans/my-plan.md --diagnostics --mode start
```

Artifacts:
- `.goldy/diagnostics/<timestamp>-<session-id>/bundle.json`
- `.goldy/diagnostics/<timestamp>-<session-id>/*.jsonl`
- `.goldy/handoffs/<session-id>.md`

## Recovery Checklist

1. Inspect `.goldy/sessions/<session-id>.json` (`status`, `stop_reason`, `next_action`).
2. Inspect `.goldy/checkpoints/<session-id>/` for latest phase checkpoint.
3. Inspect `.goldy/history/<session-id>.jsonl` for event continuity.
4. If drift stop occurred, rerun with `--require-resync`.
5. Resume from emitted command in the handoff artifact.

## Chrome Profile Helper (Codex / Playwright)

`goldy_chrome.py` is a module helper (not a standalone CLI command). Use via Python:

```bash
python3 - <<'PY'
from goldy_chrome import DEFAULT_EMAIL, DEFAULT_LOCAL_STATE, load_local_state, resolve_profile_directory, build_launch_command

state = load_local_state(DEFAULT_LOCAL_STATE)
profile = resolve_profile_directory(DEFAULT_EMAIL, state)
print(profile)
print(" ".join(build_launch_command(profile, "http://localhost:3000")))
PY
```

## Safety Rules

- Guardrails are never bypassed.
- Context under 15% must stop with handoff.
- Worktrees are never auto-deleted.
- Use `--dry-run` for rehearsal/non-destructive validation.
