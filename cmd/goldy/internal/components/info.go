package components

const InfoCore = `
  goldy skill
    Planning and orchestration engine with stack-aware resume
    capsules. Detects your project's tech stack and creates
    Gold Standard plans with bounded token budgets.

  /goldy command
    Plan mode entry point. Creates or loads active plans,
    resolves stack profile, and emits deterministic resume
    capsules. Never auto-invokes /goldy-loop.

  /goldy-loop command
    Long-loop phase executor with guardrail-compliant checkpoints,
    git worktree management, deep audits (lint, typecheck, tests,
    integration, robustness), and session resume capabilities.

  Gold Standard plan template
    Structured plan template with 14 mandatory sections including
    document control, problem statement, goals, hard constraints,
    phases with guardrail headers, and acceptance targets.

  Prevention hooks (pre_tool_use.py)
    5-layer protection hook that blocks dangerous file deletions,
    shell commands, credential exfiltration, and .env access.
    Configurable exit codes: block, ask, or allow.
`

const InfoSkills = `
SEO (13 skills):
  seo, seo-audit, seo-competitor-pages, seo-content, seo-geo,
  seo-hreflang, seo-images, seo-page, seo-plan, seo-programmatic,
  seo-schema, seo-sitemap, seo-technical

Frontend & TanStack (6 skills):
  react-tanstack-senior, tanstack-query, tanstack-query-best-practices,
  tanstack-integration-best-practices, tanstack-start-best-practices,
  vercel-react-best-practices

Development Tools (8 skills):
  antigravity-quota, claude-md-improver, find-skills, neon-postgres,
  playground, self-improving-agent, skill-creator, systematic-debugging

Strategy & Design (4 skills):
  brainstorming, pricing-strategy, programmatic-seo, ui-ux-pro-max
`

const InfoAgents = `
GSD Workflow Agents (11):
  gsd-codebase-mapper, gsd-debugger, gsd-executor,
  gsd-integration-checker, gsd-phase-researcher, gsd-plan-checker,
  gsd-planner, gsd-project-researcher, gsd-research-synthesizer,
  gsd-roadmapper, gsd-verifier

SEO Agents (6):
  seo-content, seo-performance, seo-schema, seo-sitemap,
  seo-technical, seo-visual

Core Agents (2):
  markdown-rewriter, pair-programmer-reviewer
`

const InfoHooks = `
Hook Scripts (8 files):
  notification.py, post_tool_use.py, stop.py, subagent_stop.py,
  gsd-check-update.js, gsd-context-monitor.js, gsd-statusline.js,
  CLAUDE.md

Test Kit (1 file):
  test-kit/run_tests.py — Comprehensive test suite for validating
  pre_tool_use.py's protection layers.

LLM Utilities (2 files):
  utils/llm/anth.py, utils/llm/oai.py

TTS Utilities (3 files):
  utils/tts/elevenlabs_tts.py, utils/tts/openai_tts.py,
  utils/tts/pyttsx3_tts.py
`

const InfoCommands = `
  /agent          — Multi-agent orchestration and micro-task management
  /plannotator-review — Interactive code review from Plannotator UI
  /revise-claude-md   — Update CLAUDE.md with session learnings
  /global-update      — Update all GOLDY components
`

const InfoGSD = `
  Get-Shit-Done (GSD)
    Structured project management framework with phases,
    milestones, and verification. Provides a disciplined workflow
    for breaking down complex projects into executable steps.

    Features: phase-based planning, milestone tracking, research
    agents, codebase mapping, debug sessions, progress monitoring.

    Install: npx get-shit-done@latest
    Source:  https://github.com/gsd-framework/gsd
`

const InfoClaudeMem = `
  Claude-Mem
    Team memory plugin providing persistent context sharing
    across Claude Code sessions via MCP search tools.

    Features: persistent memory storage, semantic search,
    timeline-based retrieval, cross-session context preservation.

    Install: claude plugins install claude-mem@thedotmack
    Source:  https://github.com/thedotmack/claude-mem
`

const InfoPlannotator = `
  Plannotator
    Visual plan annotation interface for reviewing and commenting
    on implementation plans.

    Features: visual plan review, inline annotation, feedback
    integration with Claude Code, plan approval workflows.

    Install: claude plugins install plannotator@plannotator
    Source:  https://github.com/backnotprop/plannotator
`
