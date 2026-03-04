# Interview Tracks — Full Question Banks

This file contains Round 3 questions for all 6 interview tracks. Rounds 1-2 are in the main SKILL.md.

---

## Track 1: Bug/Issue — Round 3 (Rule out)

- What have you already tried?
- Any Neon connection pool exhaustion, cold-start/autosuspend, or pgBouncer timeouts in play?
- Affecting all users/requests or a subset (specific route, specific data, specific browser)?
- Have you checked the Fly.io logs for the deploy window? Any recent config changes?
- Could this be a caching issue? (Cloudflare CDN cache, TanStack query cache, browser cache)
- Is the behavior the same in development and production?

---

## Track 2: Feature/Build — Round 3 (Hidden complexity)

- What are the edge cases? (missing data, concurrent access, multi-language content, empty states)
- Does this need to work offline or with degraded connectivity?
- What's the simplest version that actually solves it? (MVP vs full feature)
- What are you most uncertain about?
- Are there existing components or utilities in the codebase that do something similar?
- Does this affect SEO? (server-rendered content, meta tags, structured data)

---

## Track 3: UI/Surface Alignment — Round 3 (State and workflow)

- Does this content go through an approval state before appearing in the public app? (draft → reviewed → published)
- Who can approve — any admin, or a specific role?
- If data is wrong, can admin correct it without re-running any pipeline?
- Are there optimistic updates needed in the UI? (instant feedback while saving)
- Does the admin UI need real-time sync with the public app, or is eventual consistency OK?
- What happens when the same data is edited by two admins simultaneously?

---

## Track 4: Performance/Optimization — Round 3 (Solution constraints)

- What's the acceptable target? (e.g., <200ms response, LCP <2.5s, query <50ms)
- Are there caching opportunities? (CDN, in-memory, query result cache)
- Can you accept stale data for some period? (cache TTL tradeoffs)
- Is the bottleneck in a hot path (every request) or a cold path (occasional operation)?
- Would denormalization help, or would it create data integrity risks?
- Can the work be deferred to a background job or Cloudflare Worker?

---

## Track 5: Schema/Database — Round 3 (Data contract)

- What data shape do the consuming server functions expect after this change?
- Do any existing queries need to be updated? (JOINs, WHERE clauses, ORDER BY)
- Is there a backfill needed for existing rows? How many rows are affected?
- Does this change affect the Drizzle schema types used by TypeScript? (type safety chain)
- Are there any indexes that need to be added or modified?
- What's the rollback strategy if the migration fails?

---

## Track 6: Refactor/Architecture — Round 3 (Migration strategy)

- Can you put the old and new code side-by-side temporarily? (strangler fig pattern)
- What's the testing strategy — existing tests cover this, or new tests needed first?
- Are there other teams or features depending on the code being refactored?
- What's the definition of "done" for this refactor? How do you know it's complete?
- Can this be done behind a feature flag to reduce risk?
- What's the order of operations — which files/modules first, which last?
