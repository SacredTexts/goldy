---
name: goldy
description: "Global planning/orchestration skill. Use for: (1) Gold Standard plan creation and phased execution, (2) stack-aware decisions across TanStack/React/Neon/Drizzle/WorkOS/Radix/shadcn and other stacks, (3) session memory and deterministic resume capsules, (4) long-running /goldy-loop phase automation with checkpoints and resume chaining, (5) UI/UX module reuse from ui-ux-pro-max when design output is needed, (6) browser-based bug investigation and smoke testing via auto-detected backend (Chrome Extension for Claude Code, Playwright for Codex). Trigger for planning, roadmap, phase, architecture, implementation sequencing, or when user asks for /goldy or /goldy-loop behavior. Also auto-invokes on any coding work that lacks a pre-existing plan: fix, bug, implement, build, add, create, refactor, migrate, update, upgrade, feature, endpoint, component, test, debug, deploy, optimize, integrate, change, modify, remove, delete."
---

# GOLDY

Umbrella skill: planning + loop execution + UI/UX + stack resolution.

## Core Guarantees

- Gold Standard planning structure preferred for all plans.
- Memory: "everything always" at storage, compact capsule (~1500 tokens) at injection.
- Runtime state lives in `.goldy/` under project root.
- `/goldy` is planning-only: never creates worktrees, never auto-invokes `/goldy-loop`.
- `/goldy-loop` is manual-only: explicit invocation required.
- `/goldy-loop` uses checkpoint + resume chain, not unsafe guardrail bypass.
- Worktrees are never auto-deleted.
- Legacy UI/UX engine remains callable.

## Commands

| Command | Script | Purpose |
|---------|--------|---------|
| `/goldy` | `scripts/goldy.py $ARGUMENTS` | Planning, stack resolution, resume capsules |
| `/goldy-loop` | `scripts/goldy_loop.py $ARGUMENTS` | Phase loop with worktrees, checkpoints, audits |

Scripts root: resolved at install time (symlinked from `~/.agents/skills/goldy/scripts/`)

## Auto Invoke

Activates on two classes of intent:
1. **Planning intent** — plan, phase, roadmap, architecture, spec, implementation, sequencing
2. **Coding intent without active plan** — fix, bug, implement, build, add, create, refactor, migrate, update, upgrade, feature, endpoint, component, test, debug, deploy, optimize, integrate, change, modify, remove, delete

When coding intent is detected and no active plan exists, goldy creates a temp plan and emits `plan_mode_required: true`. Claude MUST enter plan mode (call EnterPlanMode) before proceeding with any implementation.

Auto-invoke applies to `/goldy` only — never starts `/goldy-loop`.
Prints visible activation banner.

## Browser Investigation Protocol

GOLDY supports browser-based bug investigation and smoke testing via two auto-detected backends.

**Backend detection:**
- `CODEX_THREAD_ID` env var present → **Playwright** (direct execution with Chrome profile auth)
- Otherwise → **Chrome Extension** (JSON protocol for Claude Code MCP tools)

**When goldy output includes a `browser_investigation` block:**

1. Read the `backend` field
2. If `chrome-extension`, execute each step using the corresponding MCP tool:
   - `navigate` → `mcp__claude-in-chrome__puppeteer_navigate`
   - `screenshot` → `mcp__claude-in-chrome__puppeteer_screenshot`
   - `console` → `mcp__claude-in-chrome__read_console_messages`
   - `evaluate` → `mcp__claude-in-chrome__javascript_tool`
   - `click` → `mcp__claude-in-chrome__puppeteer_click`
   - `fill` → `mcp__claude-in-chrome__puppeteer_fill`
3. If `playwright`, goldy already executed the steps — just read the results
4. Report findings after all steps complete

**Smoke checks (`--browser-check <url>` on `/goldy-loop`):**
After each phase completes, goldy-loop emits a 3-step smoke check (navigate, screenshot, console). These are observe-only. Interaction (click, fill, evaluate) requires explicit user request.

## Coding Research (Auto-Invoke)

When goldy output includes `coding_research.required: true`, Claude MUST:
1. Load the coding-research skill at the path in `coding_research.skill_path`
2. Run the structured diagnostic interview (classify → interview → synthesize)
3. Get user confirmation on the synthesis
4. Use the confirmed synthesis as input to the Gold Standard plan

This ensures the real problem is understood before any plan is written.

## References (load on demand)

| Reference | When to load |
|-----------|-------------|
| `references/planning-contract.md` | `/goldy` invoked or planning-mode questions |
| `references/loop-contract.md` | `/goldy-loop` invoked or loop execution questions |
| `references/operations-runbook.md` | Install, invoke, resume, recovery operations |
| `references/attribution.md` | Attribution or licensing questions |
| `references/book-flow-domain-pack.md` | Book/TOC/reader domain work |
| `skills/coding-research/SKILL.md` | Auto-loaded before planning when coding_research.required is true |

## Install / Verify

```bash
# From the repo root (e.g., ~/.goldy/):
make install     # Install globally
make verify      # Verify installation
make update      # Pull latest + re-install
make uninstall   # Remove from system
```
