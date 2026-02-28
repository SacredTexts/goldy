# Attribution

GOLDY includes orchestration concepts adapted from MIT-licensed projects:

- `ralph-claude-code` (MIT)
- `ralph-orchestrator` (MIT)

Adaptation mapping (conceptual only, Python-native implementations):

- `scripts/goldy_breaker.py`:
  - three-state breaker (`CLOSED/HALF_OPEN/OPEN`)
  - cooldown + reset semantics
  - configurable threshold controls
- `scripts/goldy_stuck.py`:
  - two-stage error filtering to reduce false positives
  - repeated contextual-error matching before stuck classification
- `scripts/goldy_lock.py`:
  - metadata lock-file model for primary-loop exclusivity
  - stale runtime cleanup behavior
- `scripts/goldy_history.py`:
  - append-only event log and replay summary pattern
- `scripts/goldy_loop.py`:
  - deterministic handoff + resume orchestration flow
  - drift stop + explicit resync gate
  - diagnostics/event telemetry wiring

No source code is copied verbatim from the referenced projects.
