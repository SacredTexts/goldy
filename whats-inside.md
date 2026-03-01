# What's Inside GOLDY

A portable toolkit for Claude Code — skills, agents, hooks, commands, and workflow integrations.

## Quick Stats

| Category | Count |
|----------|-------|
| Skills | 31 |
| Agents | 19 |
| Core Hooks | 3 |
| Extra Hooks | 14 (scripts + utilities) |
| Slash Commands | 6 (/goldy, /goldy-loop, /agent, /plannotator-review, /revise-claude-md, /global-update) |
| Python Scripts | 20 |
| Third-Party Integrations | 3 (GSD, Claude-Mem, Plannotator) |

---

## Skills (31)

Installed to `~/.claude/skills/` as symlinks.

### SEO (13 skills)

| Skill | What It Does |
|-------|-------------|
| `seo` | Comprehensive SEO analysis across all industries with unified reporting and specialized sub-skill delegation |
| `seo-audit` | Full website SEO audit with parallel subagent delegation, business type detection, and health scoring |
| `seo-competitor-pages` | Generate SEO-optimized competitor comparison and alternatives pages with schema markup and conversion optimization |
| `seo-content` | Analyze content quality and E-E-A-T signals with AI citation readiness assessment for GEO visibility |
| `seo-geo` | Optimize content for AI Overviews, ChatGPT web search, and Perplexity with brand mention and citability analysis |
| `seo-hreflang` | Validate existing hreflang implementations and generate correct multi-language/multi-region SEO configurations |
| `seo-images` | Analyze image optimization for SEO and performance including alt text, file sizes, formats, and lazy loading |
| `seo-page` | Deep single-page SEO analysis covering on-page elements, content quality, technical meta tags, and schema |
| `seo-plan` | Strategic SEO planning with industry-specific templates, competitive analysis, and implementation roadmaps |
| `seo-programmatic` | Plan and analyze SEO pages generated at scale from data sources with thin content safeguards and quality gates |
| `seo-schema` | Detect, validate, and generate Schema.org structured data in JSON-LD format for rich results |
| `seo-sitemap` | Analyze existing XML sitemaps or generate new ones with industry templates and quality validation |
| `seo-technical` | Audit technical SEO across 8 categories: crawlability, indexability, security, Core Web Vitals, and JS rendering |

### Frontend & TanStack (6 skills)

| Skill | What It Does |
|-------|-------------|
| `react-tanstack-senior` | Senior/lead-level React development expertise with TanStack ecosystem libraries and clean code principles |
| `tanstack-query` | Manage server state in React with TanStack Query v5 covering data fetching, caching, mutations, and SSR patterns |
| `tanstack-query-best-practices` | Implement TanStack Query optimization patterns for data fetching, caching, mutations, and server state |
| `tanstack-integration-best-practices` | Best practices for integrating TanStack Query with Router and Start for full-stack data flow |
| `tanstack-start-best-practices` | TanStack Start full-stack development patterns including server functions, auth, and deployment |
| `vercel-react-best-practices` | React and Next.js performance optimization guidelines from Vercel Engineering for optimal code patterns |

### Development Tools (8 skills)

| Skill | What It Does |
|-------|-------------|
| `antigravity-quota` | Check quota status across all Antigravity accounts configured for Claude and Gemini models with ban detection |
| `claude-md-improver` | Audit and improve CLAUDE.md files in repositories to ensure Claude Code has optimal project context |
| `find-skills` | Discover and install agent skills from the open ecosystem when looking for specialized capabilities |
| `neon-postgres` | Guides and best practices for working with Neon Serverless Postgres covering setup, features, and dev tools |
| `playground` | Create interactive HTML playgrounds where users configure options visually, see live previews, and copy prompts |
| `self-improving-agent` | Capture learnings, errors, and corrections to enable continuous improvement across sessions |
| `skill-creator` | Guidance for creating effective skills that extend Claude's capabilities with specialized knowledge and workflows |
| `systematic-debugging` | Root cause investigation, pattern analysis, and hypothesis testing to fix bugs systematically |

### Strategy & Design (4 skills)

| Skill | What It Does |
|-------|-------------|
| `brainstorming` | Explore user intent, requirements, and design through natural collaborative dialogue before implementation |
| `pricing-strategy` | Design pricing that captures value, drives growth, and aligns with customer willingness to pay |
| `programmatic-seo` | Create SEO-optimized pages at scale using templates and data while avoiding thin content penalties |
| `ui-ux-pro-max` | Design intelligence with 50+ styles, 97 color palettes, and guidance for web and mobile applications |

---

## Agents (19)

Installed to `~/.claude/agents/` as markdown files. Agents are specialized subprocesses launched by the Task tool for parallel, autonomous work.

### GSD Workflow Agents (11)

| Agent | What It Does |
|-------|-------------|
| `gsd-codebase-mapper` | Explores codebase for a specific focus area and writes structured analysis documents to `.planning/codebase/` |
| `gsd-debugger` | Investigates bugs using systematic scientific method, manages persistent debug sessions, handles checkpoints |
| `gsd-executor` | Executes GSD plans with atomic commits, deviation handling, checkpoint protocols, and state management |
| `gsd-integration-checker` | Verifies cross-phase integration and E2E flows, checks that phases connect and user workflows complete |
| `gsd-phase-researcher` | Researches how to implement a phase before planning, produces RESEARCH.md consumed by gsd-planner |
| `gsd-plan-checker` | Verifies plans will achieve phase goal before execution through goal-backward analysis of plan quality |
| `gsd-planner` | Creates executable phase plans with task breakdown, dependency analysis, and goal-backward verification |
| `gsd-project-researcher` | Researches domain ecosystem before roadmap creation, produces files in `.planning/research/` |
| `gsd-research-synthesizer` | Synthesizes research outputs from parallel researcher agents into a consolidated SUMMARY.md |
| `gsd-roadmapper` | Creates project roadmaps with phase breakdown, requirement mapping, success criteria, and coverage validation |
| `gsd-verifier` | Verifies phase goal achievement through goal-backward analysis, checks codebase delivers what phase promised |

### SEO Agents (6)

| Agent | What It Does |
|-------|-------------|
| `seo-content` | Reviews content quality evaluating E-E-A-T signals, readability, content depth, AI citation readiness, thin content |
| `seo-performance` | Measures and evaluates Core Web Vitals and page load performance metrics |
| `seo-schema` | Detects, validates, and generates Schema.org structured data in JSON-LD format |
| `seo-sitemap` | Validates XML sitemaps, generates new ones with industry templates, enforces quality gates for location pages |
| `seo-technical` | Analyzes crawlability, indexability, security, URL structure, mobile optimization, and JavaScript rendering |
| `seo-visual` | Captures screenshots, tests mobile rendering, and analyzes above-the-fold content using Playwright |

### Core Agents (2)

| Agent | What It Does |
|-------|-------------|
| `markdown-rewriter` | Rewrites, restructures, or improves markdown documentation for clarity and readability while preserving meaning |
| `pair-programmer-reviewer` | Collaborative code review partner for implementation analysis, solution architecture, and quality evaluation |

---

## Hooks

Installed to `~/.claude/hooks/`. Hooks are lifecycle scripts that fire before/after tool calls, on stop, etc.

### Core Prevention Hooks (3 files)

| File | What It Does |
|------|-------------|
| `pre_tool_use.py` | 5-layer protection hook (519 lines) that blocks dangerous file deletions, shell commands, credential exfiltration, and .env access with configurable exit codes (block, ask, or allow) |
| `prevention.config.json` | Configuration file specifying allowed paths and rules for the pre_tool_use prevention hook |
| `prevention.md` | Documentation for the hook's exit codes, architecture, and three protection layers against destructive operations |

### Extra Hook Scripts (8 files)

| File | What It Does |
|------|-------------|
| `notification.py` | Sends desktop notifications with text-to-speech support, choosing between ElevenLabs, OpenAI, or pyttsx3 based on available API keys |
| `post_tool_use.py` | Logs completed tool calls and metadata to a JSON file for tracking and audit purposes |
| `stop.py` | Displays a completion message with text-to-speech support when a task or workflow finishes |
| `subagent_stop.py` | Notifies when a subagent stops execution, uses text-to-speech to vocalize the completion status |
| `gsd-check-update.js` | Background update checker that monitors the GSD version from local or global sources and caches results |
| `gsd-context-monitor.js` | Post-tool-use hook that monitors context window usage and injects warnings when context drops below 35% or 25% |
| `gsd-statusline.js` | Statusline renderer displaying current model, task status, working directory, and scaled context usage |
| `CLAUDE.md` | Activity log and session notes for the hooks module |

### Hook Utilities (6 files)

**Test Kit:**

| File | What It Does |
|------|-------------|
| `test-kit/run_tests.py` | Comprehensive test suite (435 lines) for validating pre_tool_use.py's protection layers with dangerous operation patterns |

**LLM Utilities:**

| File | What It Does |
|------|-------------|
| `utils/llm/anth.py` | Anthropic LLM utility providing base prompting functionality using Anthropic's fastest available model |
| `utils/llm/oai.py` | OpenAI LLM utility providing base prompting functionality using OpenAI's fastest available model |

**TTS Utilities:**

| File | What It Does |
|------|-------------|
| `utils/tts/elevenlabs_tts.py` | Text-to-speech using ElevenLabs Turbo v2.5 model for fast, high-quality voice synthesis |
| `utils/tts/openai_tts.py` | Text-to-speech using OpenAI's latest TTS model with async support for high-quality voice output |
| `utils/tts/pyttsx3_tts.py` | Offline text-to-speech using pyttsx3 for local voice synthesis without requiring any API keys |

---

## Slash Commands (6)

Installed to `~/.claude/commands/`. Invoked with `/command-name` inside Claude Code.

| Command | Source | What It Does |
|---------|--------|-------------|
| `/goldy` | Core | Activates GOLDY planning and orchestration with stack-aware resume capsules, creates or reuses temp plans |
| `/goldy-loop` | Core | Runs phase-based loop iterations with checkpoints, git worktree management, deep audits, and session resume |
| `/global-update` | Extra | Updates all GOLDY components — pulls repo, re-links skills, re-copies agents/hooks, updates GSD and plugins |
| `/agent` | Extra | Loads the agent orchestration system for multi-agent coordination and micro-task management |
| `/plannotator-review` | Extra | Opens interactive code review interface to address feedback and annotations from the Plannotator UI |
| `/revise-claude-md` | Extra | Prompts reflection on session learnings and updates CLAUDE.md files with relevant context for future sessions |

---

## Python Engine (20 scripts)

Located in `scripts/`. Powers the `/goldy` and `/goldy-loop` commands.

### Core Engine

| Script | What It Does |
|--------|-------------|
| `goldy.py` | Main command engine — creates/loads active plans, resolves stack profile, emits deterministic resume capsule with bounded token budget |
| `goldy_loop.py` | Long-loop executor with guardrail-compliant checkpoints and resume capabilities across sessions |
| `core.py` | BM25 search engine for UI/UX style guides with configurable CSV data sources |

### Session & State Management

| Script | What It Does |
|--------|-------------|
| `goldy_session.py` | Session naming and management helpers for GOLDY |
| `goldy_stack.py` | Stack profile resolution — detects project tech stack for context-aware planning |
| `goldy_history.py` | Append-only loop history helpers for event replay and state management |
| `goldy_lock.py` | Loop lock and stale runtime cleanup with process-local Python safeguards |
| `goldy_memory.py` | Memory storage, indexing, retrieval, and compaction system |
| `goldy_recovery.py` | Startup recovery helpers for interrupted GOLDY loop sessions |

### Safety & Permissions

| Script | What It Does |
|--------|-------------|
| `goldy_breaker.py` | Three-state circuit breaker (CLOSED → HALF_OPEN → OPEN) with JSON persistence for loop protection |
| `goldy_permission.py` | Permission/tool-denial classifier for breaker and operator remediation |
| `goldy_stuck.py` | Stuck-loop detection using two-stage error filtering and repeated-line matching |
| `goldy_audit_policy.py` | Audit policy loading and evaluation for GOLDY deep audits |
| `goldy_task_lifecycle.py` | Task lifecycle state machine and evidence backpressure helpers |

### Browser & Integration

| Script | What It Does |
|--------|-------------|
| `goldy_browser.py` | Browser abstraction supporting both Chrome Extension (Claude Code) and Playwright execution backends |
| `goldy_chrome.py` | Chrome profile resolver matching email addresses to Chrome profiles for Playwright authentication |

### Design & Search

| Script | What It Does |
|--------|-------------|
| `design_system.py` | Design system generator aggregating search results and applying reasoning for comprehensive recommendations |
| `search.py` | BM25 search engine for UI/UX style guides with support for domains, stacks, and persistence patterns |

### Installation

| Script | What It Does |
|--------|-------------|
| `goldy_install.py` | Deploys GOLDY links and slash commands to global user directories (~/.agents/ and ~/.claude/) |
| `goldy_schemas.py` | JSON schema definitions for all state artifacts — source of truth for file formats |

---

## Third-Party Integrations (3)

Installed via their own mechanisms, not copied from goldy.

| Integration | Install Method | What It Does |
|-------------|---------------|-------------|
| **GSD** | `npx get-shit-done@latest` | Get-Shit-Done workflow engine — structured project management with phases, milestones, and verification |
| **Claude-Mem** | Claude Code plugin manager | Team memory plugin — persistent context sharing across sessions via MCP search tools |
| **Plannotator** | Claude Code plugin manager | Plan review UI — visual interface for reviewing and annotating implementation plans |

---

## Infrastructure Files

| File | What It Does |
|------|-------------|
| `install.sh` | Interactive/CLI installer with 8 component groups, info browser, update mechanism, error logging, and hook registration |
| `Makefile` | Dev workflow targets: install, uninstall, count, dev re-install, and component listing |
| `SKILL.md` | Goldy skill definition — the frontmatter and instructions that make `/goldy` work |
| `README.md` | Repository documentation with install instructions and feature overview |
| `CONTRIBUTING.md` | Development workflow guide with re-install rules and testing procedures |
| `CHANGELOG.md` | Version history tracking all releases and changes |
| `GOLD-STANDARD-SAMPLE-PLAN.md` | Plan template with all required sections for structured project execution |
| `.github/workflows/ci.yml` | CI pipeline with matrix testing across macOS/Linux and install verification |

---

## Installer

### How to Install

```bash
# Remote one-liner (clones repo, then runs installer)
curl -fsSL https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash

# From cloned repo — interactive menu
cd ~/.goldy && bash install.sh

# From cloned repo — non-interactive
cd ~/.goldy && bash install.sh --all
```

### Install Modes

| Mode | Command | Description |
|------|---------|-------------|
| **Interactive Menu** | `bash install.sh` | Shows lettered menu, pick components |
| **Install All** | `bash install.sh --all` or `-A` | Everything, no prompts |
| **Update All** | `bash install.sh --update` or `-U` | Pull latest + re-install all |
| **Core Only** | `bash install.sh --core` or `-a` | Just goldy skill, commands, hooks |
| **Info** | `bash install.sh --info` or `-i` | Show detailed descriptions of all components |
| **Help** | `bash install.sh --help` or `-h` | Show usage |
| **Multi-select** | `bash install.sh abc` | Install components a, b, c |

### Interactive Menu Options

```
  a) Core         Goldy skill, /goldy & /goldy-loop commands,
                   Gold Standard plan template, prevention hooks
  b) Skills       31 custom skills (symlinked to ~/.claude/skills/)
  c) Agents       19 agent definitions (copied to ~/.claude/agents/)
  d) Extra Hooks  Notification, stop, GSD hooks, test-kit, LLM/TTS utilities
  e) Extra Cmds   /agent, /plannotator-review, /revise-claude-md, /global-update
  f) GSD          Get-Shit-Done workflow engine (via npm)
  g) Claude-Mem   Team memory plugin (via Claude Code plugin manager)
  h) Plannotator  Plan review UI plugin (via Claude Code plugin manager)

  i) Info         Browse detailed descriptions of all components

  A) Install ALL  Everything above
  U) Update ALL   Pull latest from all sources
  Q) Quit
```

You can combine letters: typing `abcde` installs core, skills, agents, hooks, and commands in one shot.

The `i` option opens a two-level info browser: an overview of all 8 categories with counts, then drill into any category (a-h) to see every item with a detailed 2-3 line description. Press Q to return to the install menu. The `--info` CLI flag prints all descriptions non-interactively.

### How Each Component Installs

| Component | Method | Install Location |
|-----------|--------|-----------------|
| Goldy skill | Symlink | `~/.claude/skills/goldy` + `~/.agents/skills/goldy` |
| 31 Custom skills | Symlink per skill | `~/.claude/skills/<name>` |
| 19 Agents | File copy | `~/.claude/agents/<name>.md` |
| /goldy, /goldy-loop | Generated with resolved paths | `~/.claude/commands/` |
| Prevention hooks | File copy | `~/.claude/hooks/pre_tool_use.py` etc. |
| Extra hooks | File copy + recursive copy | `~/.claude/hooks/` (includes subdirs) |
| Extra commands | File copy | `~/.claude/commands/` |
| GSD | `npx get-shit-done@latest` | `~/.claude/get-shit-done/` |
| Claude-Mem | Plugin manager | `~/.claude/plugins/cache/thedotmack/claude-mem/` |
| Plannotator | Plugin manager | `~/.claude/plugins/cache/plannotator/plannotator/` |

### Update (`--update` / `-U` / `/global-update`)

The update pulls latest from all upstream sources and re-installs:

1. **Git pull** the goldy repo at `~/.goldy/`
2. **Re-install core** — regenerates `/goldy` and `/goldy-loop` commands with current paths, re-copies prevention hooks
3. **Re-link all skills** — picks up any new skills added to the repo
4. **Re-copy agents** — overwrites agent definitions with latest versions
5. **Re-copy extra hooks** — includes subdirectories (test-kit, utils/)
6. **Re-copy extra commands** — picks up new commands like `/global-update`
7. **Update GSD** — runs `npx get-shit-done@latest`
8. **Update Claude-Mem** — git pull on marketplace repo
9. **Update Plannotator** — git pull on marketplace repo
10. **Verify** — checks all core files exist, reports error count

### Error Handling

- All install errors are logged to `~/.goldy/install-errors-log.md` with timestamps
- Individual component failures don't stop the rest of the installer
- The error log is cleared on each fresh install run
- After install/update, the verification step reports any errors found

### Uninstall

```bash
cd ~/.goldy && make uninstall
```

### Remote vs Local Detection

When run via `curl | bash`, the installer:
1. Detects it's running remotely (no `SKILL.md` found in script directory)
2. Clones the repo via SSH (falls back to HTTPS if SSH fails)
3. Re-executes itself from the cloned location
4. Proceeds as a normal local install

### Hook Registration

The installer automatically registers `pre_tool_use.py` in `~/.claude/settings.json`:
- Creates the `PreToolUse` hook entry if not present
- Checks for duplicates before adding
- Creates `settings.json` from scratch if the file doesn't exist
