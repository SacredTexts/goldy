# Synthesis Schema Reference

## Required Fields

Every synthesis output must include these 7 fields:

| Field | Type | Description |
|-------|------|-------------|
| `problem_restatement` | string (1-3 sentences) | The real problem, not the stated one. Must be specific enough to verify. |
| `classification` | `{ type, confidence }` | Type is one of the 6 classification types. Confidence is high/medium/low. |
| `scope` | `{ layers_touched[], surfaces_affected[] }` | Which stack layers and UI surfaces this work touches. |
| `hard_constraints` | string[] | Non-negotiable requirements discovered in the interview. |
| `unknowns` | string[] | Anything still unclear or risky. Empty array if none. |
| `proposed_approach` | string | High-level strategy, not implementation details. |
| `verification_steps` | string[] | How to verify the solution works. Testable criteria. |

## Classification Types

- `bug_issue` — Something is broken or behaving incorrectly
- `feature_build` — New functionality or enhancement
- `ui_surface` — Cross-surface alignment or component work
- `performance` — Speed, latency, or resource optimization
- `schema_db` — Database schema, migration, or query changes
- `refactor_architecture` — Structural improvement without behavior change

## Example 1: Bug/Issue Synthesis

```
## Synthesis

### Problem (precise restatement):
The admin topic-manager page crashes with a blank screen when navigating to a topic
with more than 500 books. The error is a React hydration mismatch caused by the
virtualized table component receiving different data on server vs client render.

### Classification:
- Type: Bug/Issue
- Confidence: high

### Scope:
- Layers touched:
  - [x] TanStack route / loader / server function
  - [ ] Neon schema / query / migration
  - [ ] Cloudflare Worker / R2
  - [ ] AI gateway / model registry
  - [ ] Public app component / page
  - [x] Admin app component / page
- Surfaces affected:
  - [ ] Public app
  - [x] Admin app
  - [ ] Both

### Hard constraints:
- Must not break virtualization performance for large topic lists
- The server function must return the same data shape as the client expects

### Unknowns / risks:
- Unknown whether the issue also affects topics with 200-500 books (threshold unclear)

### Proposed approach:
Ensure the virtualized table receives a stable initial dataset from the server-rendered
pass. Defer client-only sorting/filtering to a useEffect after hydration completes.

### Verification steps:
- Navigate to a topic with 500+ books — no blank screen
- Check React DevTools for hydration warnings — none
- Confirm virtualized scrolling still works at 60fps
```

## Example 2: Feature/Build Synthesis

```
## Synthesis

### Problem (precise restatement):
Admins need to bulk-assign sections to scraped books, but currently must do it
one at a time. With 50+ books per topic page, this takes 30+ minutes per import.

### Classification:
- Type: Feature/Build
- Confidence: high

### Scope:
- Layers touched:
  - [x] TanStack route / loader / server function
  - [x] Neon schema / query / migration
  - [ ] Cloudflare Worker / R2
  - [ ] AI gateway / model registry
  - [ ] Public app component / page
  - [x] Admin app component / page
- Surfaces affected:
  - [ ] Public app
  - [x] Admin app
  - [ ] Both

### Hard constraints:
- Must work with the existing scraped_raw_data staging table
- Must not bypass the user's classification step (auto-assign only applies to section)
- Batch update must be atomic (all or nothing)

### Unknowns / risks:
- Unclear if the current Neon connection pool can handle a 500-row batch update
  without timeout

### Proposed approach:
Add a multi-select checkbox to the scrape table rows. Add a "Assign Section" bulk
action bar that appears when rows are selected. Server function uses a single SQL
UPDATE with WHERE id IN (...) for atomic batch update.

### Verification steps:
- Select 50 rows → bulk assign section → all rows update instantly
- Verify database shows correct section_id for all selected rows
- Test with 200+ rows to confirm no timeout
- Test undo: re-assign to a different section works
```
