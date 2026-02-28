# [Product Name] - [Plan Name] (Plan-Only)

## Document Control
- Product: `[product-name]` ([Product Display Name])
- File: `[plan-filename].md`
- Date: `YYYY-MM-DD`
- Scope: phased remediation/feature/migration plan (`Phase 0` to `Phase N`) with validation gates and handoff checkpoints.
- Execution rule: implementation-facing checklist; only mark `[x]` with implementation and test/static evidence.

## Repo Structure Decision
- [x] Plan execution root remains `[/path/to/project]`.
- [x] Repository/package identifiers remain `[org/repo]` and `[bundle-id]`.
- [x] Migration sequencing is locked for this plan: `v3` in Phase 4, `v4` in Phase 6.

## Problem Statement
[Product Name] has [N] known gaps in [area 1], [area 2], and [area 3]. Baseline validation is passing but [specific reliability/feature/quality issues remain]. This plan closes those gaps with phased, evidence-backed implementation before [milestone/release/completion].

## Goals
1. Close known functional gaps across [area 1], [area 2], and [area 3].
2. Keep each phase implementation-backed and validation-backed before checklist completion.
3. Preserve deterministic phase handoff/resume behavior across sessions.
4. Finish with explicit acceptance evidence and a clean final audit gate.

## Non-Goals
- Reworking product areas that are not explicitly listed in this phase plan.
- Changing locked repository/package identifiers during this execution plan.
- Marking tasks complete without implementation and validation evidence.
- [Any other specific exclusions relevant to the project].

## Hard Constraints
- [ ] Every phase starts with two mandatory reminders rendered as bold lines: checklist-evidence rule and 15% context guardrail.
- [ ] Soft budget: each phase targets about `~100k context tokens`.
- [ ] Hard budget: if context reaches `15% remaining`, finish the current task, stop, and tell the user to manually start a new session.
- [ ] At phase end: run required validation, report results, hand off.
- [ ] Handoff format: `Phase N complete. Start a new session for Phase N+1 of [plan-filename].md`.
- [ ] If any task fails: leave it `[ ]`, add a short failure note, report, then stop.

## Current Codebase Findings (Audit Baseline)
- [x] Baseline validation is green: `[count]/[count]` tests pass and `[type-check-command]` passes.
- [x] Baseline quality gaps still exist and are now included below: [list specific issues like warnings, mismatch risks, missing gates].
- [x] [Area] audit: [describe what works and what's incomplete].
- [x] [Feature] is not currently active ([describe disabled/incomplete state]).
- [x] [Gap description]: [describe what's missing or broken].
- [x] This plan now adds extra error-correction and testing tasks to close those gaps before final completion.

## Functional Requirements
- FR-01: Execute phases in order with per-phase start guardrails and explicit handoff checkpoints.
- FR-02: Keep validation gates green at required checkpoints (`[test command]`, `[type check command]`).
- FR-03: [Describe first major feature requirement].
- FR-04: [Describe second major feature requirement].
- FR-05: [Describe third major feature requirement].
- FR-06: Satisfy all Acceptance Targets and produce final command-evidence completion handoff.

## Phase 0 - Setup + Baseline Evidence
**Checklist rule: mark `[x]` only when implementation is complete and validated with tests/evidence.**
**Context guardrail: if remaining context window is below 15%, do not start a new task; finish the in-flight task, mark it complete, stop coding, and post a handoff note telling the user exactly where to manually resume.**

- [ ] Verify development environment is ready ([toolchain], [runtime], [package manager]).
- [ ] Run baseline validation: `[test command]`. Evidence: ___/___ tests, ___ suites.
- [ ] Run baseline type check: `[type check command]`. Evidence: ___ errors.
- [ ] Record baseline evidence including test counts and warning count.
- [ ] Mark completed items `[x]`.
- [ ] Emit handoff for Phase 1.

## Phase 1 - [First Feature/Fix Area]
**Checklist rule: mark `[x]` only when implementation is complete and validated with tests/evidence.**
**Context guardrail: if remaining context window is below 15%, do not start a new task; finish the in-flight task, mark it complete, stop coding, and post a handoff note telling the user exactly where to manually resume.**

- [ ] Review `src/[path/to/relevant-file]`.
- [ ] [Specific implementation task 1 with file path].
- [ ] [Specific implementation task 2 with file path].
- [ ] [Specific implementation task 3].
- [ ] Ensure [edge case or guard condition].
- [ ] Add tests for [specific behavior 1].
- [ ] Add tests for [specific behavior 2].
- [ ] Add tests for [edge case or error path].
- [ ] Run full test suite. Evidence: ___/___ tests, ___ suites.
- [ ] Run type check. Evidence: ___ errors.
- [ ] Mark completed items `[x]`.
- [ ] Emit handoff for Phase 2.

## Phase 2 - [Second Feature/Fix Area]
**Checklist rule: mark `[x]` only when implementation is complete and validated with tests/evidence.**
**Context guardrail: if remaining context window is below 15%, do not start a new task; finish the in-flight task, mark it complete, stop coding, and post a handoff note telling the user exactly where to manually resume.**

- [ ] Review `src/[path/to/relevant-file]`.
- [ ] Add/export `[functionName]([params])` in `[file]`.
- [ ] [Implementation detail 1].
- [ ] [Implementation detail 2].
- [ ] [Implementation detail 3].
- [ ] [Implementation detail 4].
- [ ] Update [dependent file 1] to use new [function/component].
- [ ] Update [dependent file 2] to use new [function/component].
- [ ] Ensure no [specific anti-pattern like duplicate logging, stale state, etc.].
- [ ] Add tests: [specific test scenario 1].
- [ ] Add tests: [specific test scenario 2].
- [ ] Add tests: [specific test scenario 3].
- [ ] Add tests: [specific test scenario 4].
- [ ] Run full test suite. Evidence: ___/___ tests, ___ suites.
- [ ] Run type check. Evidence: ___ errors.
- [ ] Mark completed items `[x]`.
- [ ] Emit handoff for Phase 3.

## Phase 3 - [Third Feature/Fix Area]
**Checklist rule: mark `[x]` only when implementation is complete and validated with tests/evidence.**
**Context guardrail: if remaining context window is below 15%, do not start a new task; finish the in-flight task, mark it complete, stop coding, and post a handoff note telling the user exactly where to manually resume.**

- [ ] [Task 1 — be specific: "Add `column_name TYPE` to `table` in migration `vN`"].
- [ ] [Task 2 — include file paths: "Create `src/services/newService.ts`"].
- [ ] [Task 3 — single verifiable action, not "implement feature"].
- [ ] [Task 4].
- [ ] [Task 5].
- [ ] [Task 6].
- [ ] Add tests for [behavior 1].
- [ ] Add tests for [behavior 2].
- [ ] Add tests for [behavior 3].
- [ ] Run full test suite. Evidence: ___/___ tests, ___ suites.
- [ ] Run type check. Evidence: ___ errors.
- [ ] Mark completed items `[x]`.
- [ ] Emit handoff for Phase 4.

## Phase N - Final Audit Gate and Release Evidence
**Checklist rule: mark `[x]` only when implementation is complete and validated with tests/evidence.**
**Context guardrail: if remaining context window is below 15%, do not start a new task; finish the in-flight task, mark it complete, stop coding, and post a handoff note telling the user exactly where to manually resume.**

- [ ] Run final full suite: `[test command]`.
- [ ] Run final type check: `[type check command]`.
- [ ] Confirm no [framework-specific warnings] remain in test output.
- [ ] Confirm no unexpected `console.error`/`console.warn` noise remains in test output.
- [ ] Run targeted regression tests for changed flows ([list key flows]).
- [ ] Verify migration path from older versions through latest.
- [ ] Verify all acceptance targets below are explicitly checked and evidenced.
- [ ] Produce final completion handoff with command evidence summary and known limitations (if any).
- [ ] Mark completed items `[x]`.
- [ ] Emit final completion handoff.

## Acceptance Targets
1. [Specific testable assertion about feature 1].
2. [Specific testable assertion about feature 2].
3. [Specific testable assertion about edge case].
4. [Specific testable assertion about error handling].
5. [Specific testable assertion about data integrity].
6. [Specific testable assertion about UI state].
7. [Specific testable assertion about migration safety].
8. [Specific testable assertion about test/type check cleanliness].
9. [Continue numbering — aim for 20-36 targets covering all phases].
10. Final evidence report includes command outputs, pass counts, and residual risks.

## Assumptions
1. "100k content" means `~100k context tokens` per phase.
2. All tasks start as `[ ]` for a fresh rerun.
3. Exactly one phase per session with hard stop at phase end or at 15% remaining context (after current task).
4. Repo/package identifiers remain `[org/repo]` and `[bundle-id]`.
5. [Migration sequencing assumption].
6. [Default value or behavior assumption].
7. [Scope boundary assumption].

## Execution Notes
- [ ] Do not mark `[x]` without implementation + test/static evidence.
- [ ] Continue completing tasks in phase order until the remaining context window drops below 15%.
- [ ] At `<15%` remaining context, do not begin a new task; complete the in-flight task, mark it complete, then stop coding.
- [ ] When stopping at the threshold, post a concise handoff note with exact resume point (current state, changed files, next exact step, open risks) and instruct the user to manually continue from that point.
