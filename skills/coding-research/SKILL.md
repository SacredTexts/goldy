---
name: coding-research
description: >
  Structured diagnostic interview skill for the ISTA platform. Use before writing
  any code or architecture plan when the user brings a coding problem, bug, system
  design question, feature request, performance issue, schema change, refactoring
  task, or UI/UX work. Trigger on: "help me plan", "I'm trying to build", "I have
  a bug", "how should I approach", "research this for me", "figure out the best way
  to", "I don't know where to start", or any coding/technical problem in the ISTA
  platform — even if the user seems ready to jump straight to code. The goal is to
  ask the right questions first so the solution actually fits the real problem.
---

# Coding Research & Planning Skill

This skill runs a structured diagnostic interview before any code is written or architecture proposed. Its job is to surface the real problem — root cause, hidden constraints, actual requirements — so the solution is targeted and right the first time.

---

## Core Philosophy

**Ask before you build.** Most wasted engineering time comes from solving the wrong problem. Slow down just enough to ask the questions that prevent that.

---

## Platform Context (ISTA)

This skill operates in the context of the **Internet Sacred Text Archive (ISTA)** platform rebuild.

**Tech Stack:**
- Frontend: TanStack Start (SSR, file-based routing, server functions via `createServerFn`)
- Database: Neon PostgreSQL (serverless, connection pooling via pgBouncer, autosuspend-aware)
- Infrastructure: Cloudflare (Workers, R2, CDN), Fly.io for SSR app
- AI Gateway: Shared layer at `apps/web/src/lib/ai/` (model registry, provider abstraction)
- Scale: 5M+ unique visitors, 32M+ monthly views, 50K+ books, 50+ languages

**Key UIs:**
- **Public app** — public-facing reader, SEO pages, landing pages for end users
- **Admin app** — internal admin UI at `/admin/`. Used to manage content, review data, approve changes, and configure platform settings (topic-manager, user management, etc.)

---

## Phase 1: Classify the Request

Classify using signal phrases. Assign a confidence level.

| Signal | Mode | Confidence Cues |
|---|---|---|
| "broken", "not working", "error", "bug", "failing", "weird behavior", "crash" | Bug/Issue | High if error message provided |
| "slow", "timeout", "latency", "performance", "bottleneck", "memory" | Performance/Optimization | High if metrics cited |
| "build", "add", "design", "implement", "plan", "how should I", "new feature" | Feature/Build | High if scope is clear |
| "schema", "migration", "database", "table", "column", "query", "Neon" | Schema/Database | High if specific table named |
| "admin", "public", "both apps", "component", "page", "layout", "responsive" | UI/Surface Alignment | High if surface specified |
| "refactor", "restructure", "clean up", "architecture", "decouple", "extract" | Refactor/Architecture | High if pain point named |
| Unclear or mixed signals | Ask one clarifying question | — |

**Common misclassifications:**
- Performance issues described as bugs → use Performance track
- Schema changes hidden inside feature requests → ask about DB impact early
- Refactoring disguised as "fix" → probe for root cause vs structural issue
- UI work that spans admin + public → use UI/Surface track, not Feature

---

## Phase 2: The Interview

Ask questions **conversationally** — 2–3 at a time, never a form dump. Follow up based on answers.

---

### Track 1: Bug/Issue

**Round 1 — Symptom:**
- What exact behavior are you seeing vs. what you expected?
- When did it start? Any recent changes (deploy, dependency, config, schema migration)?
- Reproducible every time, intermittent, or condition-specific?

**Round 2 — Isolate:**
- Error message or stack trace? (paste it)
- Which environment — local, Fly.io, prod? Does it happen on all of them?
- Which layer — TanStack route/loader, server function, Neon query, Cloudflare Worker?
- Does it affect the admin app, the public app, or both?

*See `references/interview-tracks.md` for Round 3 (Rule out)*

---

### Track 2: Feature/Build

**Round 1 — Real goal:**
- What is the user or system trying to accomplish — in one sentence, ignoring implementation?
- What does success look like? What's the measurable outcome?
- Is there an existing pattern in the codebase that partially does this?

**Round 2 — Stack constraints:**
- Is this a TanStack Start route, server function, Neon schema change, Cloudflare Worker, or a combination?
- Any performance/latency requirements? (Cloudflare edge constraints, Neon cold-start budget)
- Does this touch the admin app, the public app, or both?

*See `references/interview-tracks.md` for Round 3 (Hidden complexity)*

---

### Track 3: UI/Surface Alignment

**Round 1 — Surface ownership:**
- Is this primarily a public app concern, an admin app concern, or does it span both?
- If both: what does the public app render, and what does admin expose for management?

**Round 2 — Data contract:**
- What data shape does the component expect? (component props, route loader shape)
- What does admin need to display and edit? (form fields, review states, approval workflow)
- Shared server function or separate queries?

*See `references/interview-tracks.md` for Round 3 (State and workflow)*

---

### Track 4: Performance/Optimization

**Round 1 — Symptom measurement:**
- What's slow? Page load, API response, database query, or build time?
- Do you have numbers? (response time, Core Web Vitals, query duration)
- Is this user-reported or observed in monitoring/logs?

**Round 2 — Bottleneck isolation:**
- Which layer do you suspect? (TanStack SSR, server function, Neon query, Cloudflare Worker, network)
- Have you profiled it? (browser DevTools, Neon query stats, server timing headers)
- Is it consistent or does it depend on data volume / cold starts / connection pool saturation?

*See `references/interview-tracks.md` for Round 3 (Solution constraints)*

---

### Track 5: Schema/Database

**Round 1 — Scope:**
- Are we adding new tables/columns, modifying existing ones, or changing queries?
- Which tables are affected? Is there existing data that needs migration?
- Is this for a specific feature or a platform-wide schema evolution?

**Round 2 — Neon-specific impact:**
- Does this require a Drizzle migration? What's the migration strategy (additive vs breaking)?
- Connection pool impact — will this add new query patterns that change pool pressure?
- Does it affect server functions that feed the public app, admin app, or both?

*See `references/interview-tracks.md` for Round 3 (Data contract)*

---

### Track 6: Refactor/Architecture

**Round 1 — Current pain:**
- What specific pain is driving this refactor? (duplication, coupling, testability, readability)
- Is there a concrete trigger? (new feature blocked, bug pattern, performance ceiling)
- What's the current architecture of the code being refactored?

**Round 2 — Target state:**
- What does the refactored code look like? (describe the target, not just "cleaner")
- What's the blast radius — how many files/modules/tests are affected?
- Can this be done incrementally or does it require a big-bang change?

*See `references/interview-tracks.md` for Round 3 (Migration strategy)*

---

## Phase 3: Synthesize Before Proposing

After the interview, **before writing any code**, produce this structured synthesis:

```
## Synthesis

### Problem (precise restatement):
[1–3 sentences. Name the real problem, not just the stated one.]

### Classification:
- Type: [Bug/Issue | Feature/Build | UI/Surface | Performance | Schema/DB | Refactor/Architecture]
- Confidence: [high | medium | low]

### Scope:
- Layers touched:
  - [ ] TanStack route / loader / server function
  - [ ] Neon schema / query / migration
  - [ ] Cloudflare Worker / R2
  - [ ] AI gateway / model registry
  - [ ] Public app component / page
  - [ ] Admin app component / page
- Surfaces affected:
  - [ ] Public app
  - [ ] Admin app
  - [ ] Both

### Hard constraints:
- [constraint 1]
- [constraint 2]

### Unknowns / risks:
- [anything still unclear or scope-risky]

### Proposed approach:
[High-level strategy only — not code yet]

### Verification steps:
- [How to verify the solution works]
- [What to test / check]
- [Acceptance criteria]
```

**Do not proceed until the user confirms the synthesis.**

---

## Phase 4: Research (if needed)

1. Check current TanStack Start patterns in the codebase before proposing new ones
2. For Neon queries: review existing query patterns and connection pool usage
3. For AI features: check the AI gateway at `apps/web/src/lib/ai/` for existing provider abstractions
4. For UI work: review existing component patterns in the target app (admin vs public)

---

## Phase 5: Solution

Only after synthesis is confirmed:

- Provide the minimal working solution first
- For schema changes: show the migration before the application code
- For UI work: confirm admin and public app components are aligned before shipping either
- For server functions: use `createServerFn` (never `'use server'`)
- Call out all assumptions
- Name tradeoffs explicitly

**After solution delivery**: Log the outcome for learning (see Learning Integration below).

---

## Hard Rules (Never Violate)

- Never skip the synthesis step — especially for cross-surface or schema-touching work
- Never design public app components without checking if admin app needs a matching surface
- Never propose a Neon schema change without considering connection pool and migration impact
- Never import AI providers directly — use the AI gateway at `apps/web/src/lib/ai/`
- Never use `'use server'` — use `createServerFn` from TanStack Start
- Always confirm which UI surface(s) own the feature before writing component code
- Always ask about both admin and public app implications

---

## Learning Integration

This skill tracks interview outcomes to improve over time.

**Before starting Phase 2**: Check if `.goldy/coding-research/patterns.json` exists in the project root. If it does, read the `recommendations` array and adjust your interview accordingly (e.g., skip rounds that are consistently ineffective, add emphasis to commonly missed areas).

**After Phase 5 (Solution)**: Log the outcome by running:
```bash
python3 {skill_dir}/scripts/track_outcome.py --project-root {project_root}
```

Pass JSON via stdin with: classification_type, track_used, rounds_completed, synthesis_confirmed_first_attempt, solution_delivered.

**After 10+ outcomes**: Run pattern analysis:
```bash
python3 {skill_dir}/scripts/analyze_patterns.py --project-root {project_root}
```

This updates `patterns.json` with recommendations for future interviews.

---

## Per-Phase Protocol

When invoked at a phase boundary during `/goldy-loop` execution, this skill runs a condensed interview focused on the upcoming phase. See `references/phase-hook-protocol.md` for the full protocol.

The per-phase interview covers:
1. **Scope confirmation** — verify the phase's file/layer scope is still accurate
2. **Implementation approach** — present 2-3 approaches and get user preference
3. **Risk/edge case surfacing** — identify what could go wrong in this specific phase
4. **Open brainstorming** — catch anything the plan missed

---

## References (load on demand)

| Reference | When to load |
|-----------|-------------|
| `references/interview-tracks.md` | Need Round 3 questions for any track |
| `references/synthesis-schema.md` | Need synthesis format details or examples |
| `references/phase-hook-protocol.md` | Running per-phase interview during /goldy-loop |
