#!/usr/bin/env bash
# install.sh — Universal GOLDY installer (macOS / Linux / WSL2)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
#   -- or --
#   cd ~/.goldy && bash install.sh
#   cd ~/.goldy && bash install.sh --all        # Non-interactive install everything
#   cd ~/.goldy && bash install.sh --update     # Update all components
#
# This installer is GLOBAL-ONLY. No per-project installation.
set -euo pipefail

REPO_URL="git@github.com:SacredTexts/goldy.git"
REPO_HTTPS="https://github.com/SacredTexts/goldy.git"
GOLDY_HOME="$HOME/.goldy"

# ── Error logging ──
ERROR_LOG="$GOLDY_HOME/install-errors-log.md"

log_error() {
    local component="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    mkdir -p "$(dirname "$ERROR_LOG")"
    if [ ! -f "$ERROR_LOG" ]; then
        echo "# GOLDY Install Error Log" > "$ERROR_LOG"
        echo "" >> "$ERROR_LOG"
    fi
    echo "- **[$timestamp]** \`$component\`: $message" >> "$ERROR_LOG"
    echo "  ERROR [$component]: $message" >&2
}

# ── Detect if running from curl pipe or from cloned repo ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/SKILL.md" ]; then
    echo "╔══════════════════════════════════════════════╗"
    echo "║         GOLDY INSTALLER (Remote)             ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║ Scope: GLOBAL (all projects)                 ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    if [ -d "$GOLDY_HOME/.git" ]; then
        echo "[*] Existing installation found at $GOLDY_HOME"
        echo "    Pulling latest..."
        cd "$GOLDY_HOME" && git pull --ff-only
    else
        echo "[*] Cloning goldy to $GOLDY_HOME..."
        if git clone "$REPO_URL" "$GOLDY_HOME" 2>/dev/null; then
            echo "    Cloned via SSH."
        elif git clone "$REPO_HTTPS" "$GOLDY_HOME" 2>/dev/null; then
            echo "    Cloned via HTTPS."
        else
            echo "ERROR: Could not clone goldy. Check your GitHub access."
            exit 1
        fi
    fi
    exec bash "$GOLDY_HOME/install.sh" "$@"
fi

# ── Running from cloned repo ──
GOLDY_SRC="$SCRIPT_DIR"
CLAUDE_ROOT="$HOME/.claude"
CLAUDE_SKILLS="$CLAUDE_ROOT/skills"
CLAUDE_COMMANDS="$CLAUDE_ROOT/commands"
CLAUDE_AGENTS="$CLAUDE_ROOT/agents"
CLAUDE_HOOKS="$CLAUDE_ROOT/hooks"
AGENTS_SKILLS="$HOME/.agents/skills"
CODEX_SKILLS="$HOME/.codex/skills"

# Track errors
ERRORS=0

check_exists() {
    if [ -e "$1" ] || [ -L "$1" ]; then
        echo "  ✓ $(basename "$1")"
    else
        echo "  ✗ MISSING: $1"
        ERRORS=$((ERRORS + 1))
    fi
}

# =====================================================================
# INSTALL FUNCTIONS — one per component group
# =====================================================================

install_core() {
    echo ""
    echo "━━━ [a] CORE (Goldy) ━━━━━━━━━━━━━━━━━━━━━━━━"

    # Symlink goldy skill
    mkdir -p "$AGENTS_SKILLS" "$CLAUDE_SKILLS" "$CODEX_SKILLS" 2>/dev/null || true
    rm -rf "$AGENTS_SKILLS/goldy" "$CLAUDE_SKILLS/goldy" "$CODEX_SKILLS/goldy" 2>/dev/null || true
    ln -sfn "$GOLDY_SRC" "$AGENTS_SKILLS/goldy"
    ln -sfn "$GOLDY_SRC" "$CLAUDE_SKILLS/goldy"
    ln -sfn "$GOLDY_SRC" "$CODEX_SKILLS/goldy" 2>/dev/null || true
    echo "  Linked goldy skill to ~/.agents/ and ~/.claude/"

    # Generate slash commands with resolved paths
    mkdir -p "$CLAUDE_COMMANDS"
    local SCRIPTS_PATH="$GOLDY_SRC/scripts"

    cat > "$CLAUDE_COMMANDS/goldy.md" << CMDEOF
---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Activate GOLDY planning/orchestration with stack-aware resume capsules
argument-hint: [--plan <plan-file>] [options]
---

# GOLDY

Run GOLDY command engine:

\`\`\`bash
python3 $SCRIPTS_PATH/goldy.py \$ARGUMENTS
\`\`\`

Behavior:
- Uses explicit \`--plan\` when provided.
- Creates a fresh \`temp-plans/\` Gold Standard temp plan for prompt-driven calls.
- For coding-intent auto-invocations, reuses existing plan if one exists; creates new only when none found.
- Loads full memory then injects compact Resume Capsule.
- Prints a visible activation banner.
- Never creates, reuses, or deletes git worktrees.
- Never auto-invokes \`/goldy-loop\`.

## After goldy runs -- Plan Mode Protocol

Read the goldy output carefully. If the output contains \`plan_mode_required: True\`:
1. **STOP** -- do not write any implementation code.
2. **Enter plan mode** -- use the plan file path from goldy's \`plan:\` output line.
3. **Fill in the plan** -- populate the Gold Standard template sections.
4. **Present the plan to the user** for review/approval.
5. Only after approval, exit plan mode and begin implementation.

If \`plan_mode_required\` is False or absent, proceed normally.
CMDEOF

    cat > "$CLAUDE_COMMANDS/goldy-loop.md" << CMDEOF
---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Run GOLDY phase loop with checkpoints and auto-resume chain
argument-hint: --plan <plan-file> [options]
---

# GOLDY LOOP

Run GOLDY loop engine:

\`\`\`bash
python3 $SCRIPTS_PATH/goldy_loop.py \$ARGUMENTS
\`\`\`

Behavior:
- Manual-only command; do not auto-invoke from \`/goldy\`.
- Guardrail-compliant stop on low context.
- Creates/reuses a session git worktree by default.
- Runs up to 10 loop iterations by default (\`--max-iterations\` to override).
- \`--commands\` prints full command list + usage examples.
CMDEOF
    echo "  Installed /goldy and /goldy-loop commands"

    # Gold Standard plan template
    cp "$GOLDY_SRC/GOLD-STANDARD-SAMPLE-PLAN.md" "$CLAUDE_ROOT/"
    echo "  Installed Gold Standard plan template"

    # Prevention hooks
    mkdir -p "$CLAUDE_HOOKS"
    cp "$GOLDY_SRC/hooks/pre_tool_use.py" "$CLAUDE_HOOKS/pre_tool_use.py"
    cp "$GOLDY_SRC/hooks/prevention.md" "$CLAUDE_HOOKS/prevention.md"
    if [ ! -f "$CLAUDE_HOOKS/prevention.config.json" ]; then
        cp "$GOLDY_SRC/hooks/prevention.config.json" "$CLAUDE_HOOKS/prevention.config.json"
    fi
    echo "  Installed prevention hooks"

    # Register hook in settings.json
    _register_pretooluse_hook
    echo "  ✓ Core installed"
}

install_skills() {
    echo ""
    echo "━━━ [b] SKILLS (31 custom skills) ━━━━━━━━━━━"

    if [ ! -d "$GOLDY_SRC/skills" ]; then
        log_error "skills" "skills/ directory not found in repo"
        return
    fi

    mkdir -p "$CLAUDE_SKILLS" "$AGENTS_SKILLS"

    local count=0
    for skill_dir in "$GOLDY_SRC/skills"/*/; do
        local name
        name=$(basename "$skill_dir")
        # Symlink into both locations
        rm -rf "$CLAUDE_SKILLS/$name" 2>/dev/null || true
        ln -sfn "$skill_dir" "$CLAUDE_SKILLS/$name" 2>/dev/null || {
            log_error "skills/$name" "Failed to symlink to ~/.claude/skills/"
            continue
        }
        rm -rf "$AGENTS_SKILLS/$name" 2>/dev/null || true
        ln -sfn "$skill_dir" "$AGENTS_SKILLS/$name" 2>/dev/null || true
        count=$((count + 1))
    done
    echo "  Linked $count skills to ~/.claude/skills/"
    echo "  ✓ Skills installed"
}

install_agents() {
    echo ""
    echo "━━━ [c] AGENTS (19 agent definitions) ━━━━━━━"

    if [ ! -d "$GOLDY_SRC/agents" ]; then
        log_error "agents" "agents/ directory not found in repo"
        return
    fi

    mkdir -p "$CLAUDE_AGENTS"
    local count=0
    for agent_file in "$GOLDY_SRC/agents"/*.md; do
        [ -f "$agent_file" ] || continue
        cp "$agent_file" "$CLAUDE_AGENTS/"
        count=$((count + 1))
    done
    echo "  Installed $count agent definitions"
    echo "  ✓ Agents installed"
}

install_hooks() {
    echo ""
    echo "━━━ [d] EXTRA HOOKS (scripts + utilities) ━━━"

    if [ ! -d "$GOLDY_SRC/extra-hooks" ]; then
        log_error "hooks" "extra-hooks/ directory not found in repo"
        return
    fi

    mkdir -p "$CLAUDE_HOOKS"
    local count=0

    # Copy top-level hook files
    for hook_file in "$GOLDY_SRC/extra-hooks"/*; do
        [ -f "$hook_file" ] || continue
        cp "$hook_file" "$CLAUDE_HOOKS/"
        count=$((count + 1))
    done

    # Copy hook subdirectories (test-kit, utils)
    for hook_dir in "$GOLDY_SRC/extra-hooks"/*/; do
        [ -d "$hook_dir" ] || continue
        local dirname
        dirname=$(basename "$hook_dir")
        mkdir -p "$CLAUDE_HOOKS/$dirname"
        cp -R "$hook_dir"* "$CLAUDE_HOOKS/$dirname/" 2>/dev/null || true
        local sub_count
        sub_count=$(find "$hook_dir" -type f ! -name '.DS_Store' | wc -l | tr -d ' ')
        count=$((count + sub_count))
    done

    echo "  Installed $count extra hooks (scripts, test-kit, LLM/TTS utils, etc.)"
    echo "  ✓ Extra hooks installed"
}

install_extra_commands() {
    echo ""
    echo "━━━ [e] EXTRA COMMANDS ━━━━━━━━━━━━━━━━━━━━━━"

    if [ ! -d "$GOLDY_SRC/extra-commands" ]; then
        log_error "commands" "extra-commands/ directory not found in repo"
        return
    fi

    mkdir -p "$CLAUDE_COMMANDS"
    local count=0
    for cmd_file in "$GOLDY_SRC/extra-commands"/*.md; do
        [ -f "$cmd_file" ] || continue
        cp "$cmd_file" "$CLAUDE_COMMANDS/"
        count=$((count + 1))
    done
    echo "  Installed $count extra commands"
    echo "  ✓ Extra commands installed"
}

install_gsd() {
    echo ""
    echo "━━━ [f] GSD (Get-Shit-Done Workflow) ━━━━━━━━"
    echo "  Source: https://github.com/gsd-framework/gsd"

    # GSD installs via npm — check if already installed
    if [ -d "$HOME/.claude/get-shit-done" ]; then
        echo "  GSD already installed ($(cat "$HOME/.claude/get-shit-done/VERSION" 2>/dev/null || echo 'unknown version'))"
        echo "  To update: use option [U] or run /gsd:update in Claude Code"
    else
        echo "  GSD not found. Attempting install..."
        if command -v npx &>/dev/null; then
            npx -y get-shit-done@latest 2>/dev/null && echo "  ✓ GSD installed" || {
                log_error "gsd" "npx get-shit-done install failed. Install manually: npx -y get-shit-done@latest"
                echo "  ✗ GSD install failed — see install-errors-log.md"
            }
        else
            log_error "gsd" "npx not found. Install Node.js first, then run: npx -y get-shit-done@latest"
            echo "  ✗ npx not available — install Node.js first"
        fi
    fi
}

install_claude_mem() {
    echo ""
    echo "━━━ [g] CLAUDE-MEM (Team Memory Plugin) ━━━━━"
    echo "  Source: https://github.com/thedotmack/claude-mem"

    # claude-mem is a Claude Code plugin
    local PLUGIN_DIR="$HOME/.claude/plugins/cache/thedotmack/claude-mem"
    if [ -d "$PLUGIN_DIR" ]; then
        local versions
        versions=$(ls -1 "$PLUGIN_DIR" 2>/dev/null | sort -V | tail -1)
        echo "  claude-mem already installed (v$versions)"
        echo "  To update: use option [U] or reinstall via Claude Code plugin manager"
    else
        echo "  claude-mem not found."
        echo "  Install via Claude Code: Settings > Plugins > Search 'claude-mem'"
        echo "  Or: claude plugins install claude-mem@thedotmack"
        log_error "claude-mem" "Not installed. Install via Claude Code plugin manager."
    fi
}

install_plannotator() {
    echo ""
    echo "━━━ [h] PLANNOTATOR (Plan Review UI) ━━━━━━━━"
    echo "  Source: https://github.com/backnotprop/plannotator"

    local PLUGIN_DIR="$HOME/.claude/plugins/cache/plannotator/plannotator"
    if [ -d "$PLUGIN_DIR" ]; then
        local versions
        versions=$(ls -1 "$PLUGIN_DIR" 2>/dev/null | sort -V | tail -1)
        echo "  plannotator already installed (v$versions)"
        echo "  To update: use option [U] or reinstall via Claude Code plugin manager"
    else
        echo "  plannotator not found."
        echo "  Install via Claude Code: Settings > Plugins > Search 'plannotator'"
        echo "  Or: claude plugins install plannotator@plannotator"
        log_error "plannotator" "Not installed. Install via Claude Code plugin manager."
    fi
}

# =====================================================================
# UPDATE FUNCTION — pulls latest from all sources
# =====================================================================

update_all() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║         GOLDY UPDATE                         ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    # 1. Update goldy repo
    echo "━━━ Updating goldy repo ━━━"
    if [ -d "$GOLDY_SRC/.git" ]; then
        cd "$GOLDY_SRC" && git pull --ff-only 2>/dev/null && echo "  ✓ goldy repo updated" || {
            log_error "update/goldy" "git pull failed — check for local changes"
            echo "  ✗ goldy pull failed"
        }
    fi

    # 2. Re-run core install (re-generates commands with current paths)
    install_core

    # 3. Re-link skills (picks up any new skills added to repo)
    if [ -d "$GOLDY_SRC/skills" ]; then
        install_skills
    fi

    # 4. Re-copy agents
    if [ -d "$GOLDY_SRC/agents" ]; then
        install_agents
    fi

    # 5. Re-copy hooks (includes subdirs: test-kit, utils/)
    if [ -d "$GOLDY_SRC/extra-hooks" ]; then
        install_hooks
    fi

    # 5b. Re-copy extra commands (picks up /global-update and any new commands)
    if [ -d "$GOLDY_SRC/extra-commands" ]; then
        install_extra_commands
    fi

    # 6. Update GSD
    echo ""
    echo "━━━ Updating GSD ━━━"
    if [ -d "$HOME/.claude/get-shit-done" ]; then
        if command -v npx &>/dev/null; then
            npx -y get-shit-done@latest 2>/dev/null && echo "  ✓ GSD updated" || {
                log_error "update/gsd" "GSD update failed"
                echo "  ✗ GSD update failed"
            }
        fi
    else
        echo "  GSD not installed — skipping"
    fi

    # 7. Update claude-mem
    echo ""
    echo "━━━ Updating claude-mem ━━━"
    local CM_MARKET="$HOME/.claude/plugins/marketplaces/thedotmack"
    if [ -d "$CM_MARKET/.git" ]; then
        cd "$CM_MARKET" && git pull --ff-only 2>/dev/null && echo "  ✓ claude-mem marketplace updated" || {
            log_error "update/claude-mem" "git pull failed on marketplace repo"
            echo "  ✗ claude-mem update failed"
        }
        cd "$GOLDY_SRC"
    else
        echo "  claude-mem marketplace not found — update via Claude Code plugin manager"
    fi

    # 8. Update plannotator
    echo ""
    echo "━━━ Updating plannotator ━━━"
    local PN_MARKET="$HOME/.claude/plugins/marketplaces/plannotator"
    if [ -d "$PN_MARKET/.git" ]; then
        cd "$PN_MARKET" && git pull --ff-only 2>/dev/null && echo "  ✓ plannotator marketplace updated" || {
            log_error "update/plannotator" "git pull failed on marketplace repo"
            echo "  ✗ plannotator update failed"
        }
        cd "$GOLDY_SRC"
    else
        echo "  plannotator marketplace not found — update via Claude Code plugin manager"
    fi

    echo ""
    echo "━━━ Update complete ━━━"
}

# =====================================================================
# HELPER: Register PreToolUse hook in settings.json
# =====================================================================

_register_pretooluse_hook() {
    local SETTINGS_FILE="$CLAUDE_ROOT/settings.json"
    local HOOKS_DIR="$CLAUDE_ROOT/hooks"

    if [ ! -f "$SETTINGS_FILE" ]; then
        python3 -c "
import json
s = {'hooks': {'PreToolUse': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 $HOOKS_DIR/pre_tool_use.py'}]}]}}
with open('$SETTINGS_FILE', 'w') as f: json.dump(s, f, indent=4)
" 2>/dev/null || log_error "hooks" "Could not create settings.json"
        return
    fi

    python3 -c "
import json, sys
with open('$SETTINGS_FILE') as f: s = json.load(f)
hooks = s.get('hooks', {}).get('PreToolUse', [])
for h in hooks:
    for hk in h.get('hooks', []):
        if 'pre_tool_use.py' in hk.get('command', ''): sys.exit(0)
s.setdefault('hooks', {}).setdefault('PreToolUse', []).append({'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 $HOOKS_DIR/pre_tool_use.py'}]})
with open('$SETTINGS_FILE', 'w') as f: json.dump(s, f, indent=4)
" 2>/dev/null || log_error "hooks" "Could not register PreToolUse hook in settings.json"
}

# =====================================================================
# VERIFY FUNCTION
# =====================================================================

verify() {
    echo ""
    echo "━━━ VERIFICATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ERRORS=0
    check_exists "$CLAUDE_SKILLS/goldy"
    check_exists "$CLAUDE_COMMANDS/goldy.md"
    check_exists "$CLAUDE_COMMANDS/goldy-loop.md"
    check_exists "$CLAUDE_ROOT/GOLD-STANDARD-SAMPLE-PLAN.md"
    check_exists "$CLAUDE_HOOKS/pre_tool_use.py"

    if command -v python3 &>/dev/null; then
        echo "  ✓ python3 $(python3 --version 2>&1 | cut -d' ' -f2)"
    else
        echo "  ✗ python3 not found"
        ERRORS=$((ERRORS + 1))
    fi

    # Check error log
    if [ -f "$ERROR_LOG" ]; then
        local err_count
        err_count=$(grep -c '^\-' "$ERROR_LOG" 2>/dev/null || echo 0)
        if [ "$err_count" -gt 0 ]; then
            echo ""
            echo "  ⚠ $err_count error(s) logged to: $ERROR_LOG"
        fi
    fi

    echo ""
    if [ "$ERRORS" -eq 0 ]; then
        echo "╔════════════════════════════════════════════════════╗"
        echo "║  ✓ GOLDY installed successfully!                   ║"
        echo "╠════════════════════════════════════════════════════╣"
        echo "║  /goldy          — plan mode                       ║"
        echo "║  /goldy-loop     — phase execution                 ║"
        echo "║  /global-update  — update all components           ║"
        echo "║                                                    ║"
        echo "║  Protection: PreToolUse hook active                ║"
        echo "║  Update:     /global-update (in Claude Code)       ║"
        echo "║     or:      cd ~/.goldy && bash install.sh -U     ║"
        echo "║  Uninstall:  cd ~/.goldy && make uninstall         ║"
        echo "║                                                    ║"
        echo "║  Errors log: ~/.goldy/install-errors-log.md        ║"
        echo "╚════════════════════════════════════════════════════╝"
    else
        echo "Install completed with $ERRORS error(s)."
        exit 1
    fi
}

# =====================================================================
# INFO FUNCTIONS — detailed component summaries
# =====================================================================

show_info_core() {
    cat << 'EOF'

━━━ CORE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    5-layer protection hook (519 lines) that blocks dangerous file
    deletions, shell commands, credential exfiltration, and .env
    access. Configurable exit codes: block, ask, or allow.

EOF
}

show_info_skills() {
    cat << 'EOF'

━━━ SKILLS (31) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEO (13 skills):

  seo
    Comprehensive SEO analysis across all industries with unified
    reporting and specialized sub-skill delegation.

  seo-audit
    Full website SEO audit with parallel subagent delegation,
    business type detection, and health scoring.

  seo-competitor-pages
    Generate SEO-optimized competitor comparison and alternatives
    pages with schema markup and conversion optimization.

  seo-content
    Analyze content quality and E-E-A-T signals with AI citation
    readiness assessment for GEO visibility.

  seo-geo
    Optimize content for AI Overviews, ChatGPT web search, and
    Perplexity with brand mention and citability analysis.

  seo-hreflang
    Validate existing hreflang implementations and generate correct
    multi-language/multi-region SEO configurations.

  seo-images
    Analyze image optimization for SEO and performance including
    alt text, file sizes, formats, and lazy loading.

  seo-page
    Deep single-page SEO analysis covering on-page elements,
    content quality, technical meta tags, and schema.

  seo-plan
    Strategic SEO planning with industry-specific templates,
    competitive analysis, and implementation roadmaps.

  seo-programmatic
    Plan and analyze SEO pages generated at scale from data sources
    with thin content safeguards and quality gates.

  seo-schema
    Detect, validate, and generate Schema.org structured data in
    JSON-LD format for rich results.

  seo-sitemap
    Analyze existing XML sitemaps or generate new ones with industry
    templates and quality validation.

  seo-technical
    Audit technical SEO across 8 categories: crawlability,
    indexability, security, Core Web Vitals, and JS rendering.

Frontend & TanStack (6 skills):

  react-tanstack-senior
    Senior/lead-level React development expertise with TanStack
    ecosystem libraries and clean code principles.

  tanstack-query
    Manage server state in React with TanStack Query v5 covering
    data fetching, caching, mutations, and SSR patterns.

  tanstack-query-best-practices
    Implement TanStack Query optimization patterns for data
    fetching, caching, mutations, and server state.

  tanstack-integration-best-practices
    Best practices for integrating TanStack Query with Router
    and Start for full-stack data flow.

  tanstack-start-best-practices
    TanStack Start full-stack development patterns including
    server functions, auth, and deployment.

  vercel-react-best-practices
    React and Next.js performance optimization guidelines from
    Vercel Engineering for optimal code patterns.

Development Tools (8 skills):

  antigravity-quota
    Check quota status across all Antigravity accounts configured
    for Claude and Gemini models with ban detection.

  claude-md-improver
    Audit and improve CLAUDE.md files in repositories to ensure
    Claude Code has optimal project context.

  find-skills
    Discover and install agent skills from the open ecosystem
    when looking for specialized capabilities.

  neon-postgres
    Guides and best practices for working with Neon Serverless
    Postgres covering setup, features, and dev tools.

  playground
    Create interactive HTML playgrounds where users configure
    options visually, see live previews, and copy prompts.

  self-improving-agent
    Capture learnings, errors, and corrections to enable
    continuous improvement across sessions.

  skill-creator
    Guidance for creating effective skills that extend Claude's
    capabilities with specialized knowledge and workflows.

  systematic-debugging
    Root cause investigation, pattern analysis, and hypothesis
    testing to fix bugs systematically.

Strategy & Design (4 skills):

  brainstorming
    Explore user intent, requirements, and design through natural
    collaborative dialogue before implementation.

  pricing-strategy
    Design pricing that captures value, drives growth, and aligns
    with customer willingness to pay.

  programmatic-seo
    Create SEO-optimized pages at scale using templates and data
    while avoiding thin content penalties.

  ui-ux-pro-max
    Design intelligence with 50+ styles, 97 color palettes, and
    guidance for web and mobile applications.

EOF
}

show_info_agents() {
    cat << 'EOF'

━━━ AGENTS (19) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GSD Workflow Agents (11):

  gsd-codebase-mapper
    Explores codebase for a specific focus area and writes
    structured analysis documents to .planning/codebase/.

  gsd-debugger
    Investigates bugs using systematic scientific method, manages
    persistent debug sessions, handles checkpoints.

  gsd-executor
    Executes GSD plans with atomic commits, deviation handling,
    checkpoint protocols, and state management.

  gsd-integration-checker
    Verifies cross-phase integration and E2E flows, checks that
    phases connect and user workflows complete.

  gsd-phase-researcher
    Researches how to implement a phase before planning, produces
    RESEARCH.md consumed by gsd-planner.

  gsd-plan-checker
    Verifies plans will achieve phase goal before execution
    through goal-backward analysis of plan quality.

  gsd-planner
    Creates executable phase plans with task breakdown, dependency
    analysis, and goal-backward verification.

  gsd-project-researcher
    Researches domain ecosystem before roadmap creation, produces
    files in .planning/research/.

  gsd-research-synthesizer
    Synthesizes research outputs from parallel researcher agents
    into a consolidated SUMMARY.md.

  gsd-roadmapper
    Creates project roadmaps with phase breakdown, requirement
    mapping, success criteria, and coverage validation.

  gsd-verifier
    Verifies phase goal achievement through goal-backward analysis,
    checks codebase delivers what phase promised.

SEO Agents (6):

  seo-content
    Reviews content quality evaluating E-E-A-T signals,
    readability, content depth, AI citation readiness.

  seo-performance
    Measures and evaluates Core Web Vitals and page load
    performance metrics.

  seo-schema
    Detects, validates, and generates Schema.org structured data
    in JSON-LD format.

  seo-sitemap
    Validates XML sitemaps, generates new ones with industry
    templates, enforces quality gates for location pages.

  seo-technical
    Analyzes crawlability, indexability, security, URL structure,
    mobile optimization, and JavaScript rendering.

  seo-visual
    Captures screenshots, tests mobile rendering, and analyzes
    above-the-fold content using Playwright.

Core Agents (2):

  markdown-rewriter
    Rewrites, restructures, or improves markdown documentation
    for clarity and readability while preserving meaning.

  pair-programmer-reviewer
    Collaborative code review partner for implementation analysis,
    solution architecture, and quality evaluation.

EOF
}

show_info_hooks() {
    cat << 'EOF'

━━━ EXTRA HOOKS (14 scripts + utilities) ━━━━━━━━━━━━━━━━━

Hook Scripts (8 files):

  notification.py
    Sends desktop notifications with text-to-speech support,
    choosing between ElevenLabs, OpenAI, or pyttsx3 based on
    available API keys.

  post_tool_use.py
    Logs completed tool calls and metadata to a JSON file for
    tracking and audit purposes.

  stop.py
    Displays a completion message with text-to-speech support
    when a task or workflow finishes.

  subagent_stop.py
    Notifies when a subagent stops execution, uses text-to-speech
    to vocalize the completion status.

  gsd-check-update.js
    Background update checker that monitors the GSD version from
    local or global sources and caches results.

  gsd-context-monitor.js
    Post-tool-use hook that monitors context window usage and
    injects warnings when context drops below 35% or 25%.

  gsd-statusline.js
    Statusline renderer displaying current model, task status,
    working directory, and scaled context usage.

  CLAUDE.md
    Activity log and session notes for the hooks module.

Test Kit (1 file):

  test-kit/run_tests.py
    Comprehensive test suite (435 lines) for validating
    pre_tool_use.py's protection layers with dangerous
    operation patterns.

LLM Utilities (2 files):

  utils/llm/anth.py
    Anthropic LLM utility providing base prompting functionality
    using Anthropic's fastest available model.

  utils/llm/oai.py
    OpenAI LLM utility providing base prompting functionality
    using OpenAI's fastest available model.

TTS Utilities (3 files):

  utils/tts/elevenlabs_tts.py
    Text-to-speech using ElevenLabs Turbo v2.5 model for fast,
    high-quality voice synthesis.

  utils/tts/openai_tts.py
    Text-to-speech using OpenAI's latest TTS model with async
    support for high-quality voice output.

  utils/tts/pyttsx3_tts.py
    Offline text-to-speech using pyttsx3 for local voice synthesis
    without requiring any API keys.

EOF
}

show_info_extra_commands() {
    cat << 'EOF'

━━━ EXTRA COMMANDS (4) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /agent
    Loads the agent orchestration system for multi-agent
    coordination and micro-task management. Enables dispatching
    parallel subagents for complex workflows.

  /plannotator-review
    Opens interactive code review interface to address feedback
    and annotations from the Plannotator UI. Processes review
    comments and implements suggested changes.

  /revise-claude-md
    Prompts reflection on session learnings and updates CLAUDE.md
    files with relevant context for future sessions. Helps
    maintain accurate project documentation.

  /global-update
    Updates all GOLDY components — pulls repo, re-links skills,
    re-copies agents/hooks, updates GSD and plugins. Same as
    running install.sh --update from the command line.

EOF
}

show_info_gsd() {
    cat << 'EOF'

━━━ GSD (Get-Shit-Done Workflow Engine) ━━━━━━━━━━━━━━━━━━

  Get-Shit-Done (GSD)
    Structured project management framework with phases,
    milestones, and verification. Provides a disciplined workflow
    for breaking down complex projects into executable steps.

    Features:
    - Phase-based project planning and execution
    - Milestone tracking with completion verification
    - Research and planning agents for each phase
    - Codebase mapping and integration checking
    - Debug sessions with scientific method approach
    - Progress tracking and health monitoring

    Install method: npx get-shit-done@latest
    Location: ~/.claude/get-shit-done/
    Source: https://github.com/gsd-framework/gsd

EOF
}

show_info_claude_mem() {
    cat << 'EOF'

━━━ CLAUDE-MEM (Team Memory Plugin) ━━━━━━━━━━━━━━━━━━━━━━

  Claude-Mem
    Team memory plugin providing persistent context sharing
    across Claude Code sessions via MCP search tools. Enables
    agents and developers to build on previous work without
    losing context between conversations.

    Features:
    - Persistent memory storage with semantic search
    - Timeline-based observation retrieval
    - Cross-session context preservation
    - Team-wide knowledge sharing
    - MCP integration for seamless tool access

    Install method: Claude Code plugin manager
    Location: ~/.claude/plugins/cache/thedotmack/claude-mem/
    Source: https://github.com/thedotmack/claude-mem

EOF
}

show_info_plannotator() {
    cat << 'EOF'

━━━ PLANNOTATOR (Plan Review UI Plugin) ━━━━━━━━━━━━━━━━━━

  Plannotator
    Visual plan annotation interface for reviewing and commenting
    on implementation plans. Provides a structured UI for plan
    feedback that integrates with the /plannotator-review command.

    Features:
    - Visual plan review interface
    - Inline annotation and commenting
    - Feedback integration with Claude Code
    - Plan approval workflows
    - Review history tracking

    Install method: Claude Code plugin manager
    Location: ~/.claude/plugins/cache/plannotator/plannotator/
    Source: https://github.com/backnotprop/plannotator

EOF
}

# ── Info Overview ──

show_info_overview() {
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║         GOLDY — WHAT'S INSIDE                            ║"
    echo "╠══════════════════════════════════════════════════════════╣"
    echo "║                                                          ║"
    echo "║  a) Core           5 items — skill, 2 commands,          ║"
    echo "║                    plan template, prevention hooks        ║"
    echo "║  b) Skills         31 skills in 4 domains                ║"
    echo "║                    (SEO, Frontend, Dev Tools, Strategy)   ║"
    echo "║  c) Agents         19 agents in 3 groups                 ║"
    echo "║                    (GSD, SEO, Core)                       ║"
    echo "║  d) Extra Hooks    14 scripts + utilities                ║"
    echo "║                    (notifications, TTS, test-kit)         ║"
    echo "║  e) Extra Cmds     4 slash commands                      ║"
    echo "║                    (/agent, /plannotator-review, ...)     ║"
    echo "║  f) GSD            Get-Shit-Done workflow engine          ║"
    echo "║                    Phases, milestones, verification       ║"
    echo "║  g) Claude-Mem     Team memory plugin                    ║"
    echo "║                    Persistent context across sessions     ║"
    echo "║  h) Plannotator    Plan review UI plugin                 ║"
    echo "║                    Visual plan annotation interface       ║"
    echo "║                                                          ║"
    echo "║  Press a-h for details, Q to return to install menu      ║"
    echo "╚══════════════════════════════════════════════════════════╝"
}

# ── Info Navigation Loop ──

show_info() {
    while true; do
        echo ""
        show_info_overview
        echo ""
        printf "Select category (a-h) or Q to go back: "
        read -r info_choice
        case "${info_choice:-}" in
            a) show_info_core ;;
            b) show_info_skills ;;
            c) show_info_agents ;;
            d) show_info_hooks ;;
            e) show_info_extra_commands ;;
            f) show_info_gsd ;;
            g) show_info_claude_mem ;;
            h) show_info_plannotator ;;
            Q|q) return ;;
            *) echo "  Unknown option: $info_choice" ;;
        esac
        if [ "${info_choice:-}" != "Q" ] && [ "${info_choice:-}" != "q" ]; then
            echo ""
            printf "Press Enter to continue..."
            read -r
        fi
    done
}

# ── Non-interactive info dump (--info flag) ──

show_info_all() {
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║         GOLDY — COMPLETE COMPONENT INDEX                 ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    show_info_core
    show_info_skills
    show_info_agents
    show_info_hooks
    show_info_extra_commands
    show_info_gsd
    show_info_claude_mem
    show_info_plannotator
}

# =====================================================================
# INTERACTIVE MENU
# =====================================================================

show_menu() {
    echo "╔══════════════════════════════════════════════════╗"
    echo "║         GOLDY INSTALLER (Global)                 ║"
    echo "╠══════════════════════════════════════════════════╣"
    echo "║                                                  ║"
    echo "║  a) Core         Goldy skill, commands, hooks,   ║"
    echo "║                  Gold Standard plan template      ║"
    echo "║  b) Skills       31 custom skills (TanStack,     ║"
    echo "║                  SEO, Frontend, Dev Tools, etc.)  ║"
    echo "║  c) Agents       19 agent definitions (GSD,      ║"
    echo "║                  SEO, code review, etc.)          ║"
    echo "║  d) Extra Hooks  Notification, stop, GSD hooks,   ║"
    echo "║                  test-kit, LLM/TTS utilities       ║"
    echo "║  e) Extra Cmds   /agent, /plannotator-review,      ║"
    echo "║                  /revise-claude-md, /global-update  ║"
    echo "║  f) GSD          Get-Shit-Done workflow (npm)     ║"
    echo "║  g) Claude-Mem   Team memory plugin               ║"
    echo "║  h) Plannotator  Plan review UI plugin            ║"
    echo "║                                                   ║"
    echo "║  i) Info         Browse detailed component list   ║"
    echo "║                                                   ║"
    echo "║  A) Install ALL  Everything above                 ║"
    echo "║  U) Update ALL   Pull latest from all sources     ║"
    echo "║  Q) Quit                                          ║"
    echo "║                                                   ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    echo "Select options (e.g. 'a', 'abc', 'A', 'i'): "
}

install_all() {
    install_core
    install_skills
    install_agents
    install_hooks
    install_extra_commands
    install_gsd
    install_claude_mem
    install_plannotator
    verify
}

run_selections() {
    local selections="$1"

    # Handle special single-char options
    case "$selections" in
        A) install_all; return ;;
        U) update_all; verify; return ;;
        Q|q) echo "Bye."; exit 0 ;;
        i) show_info; return ;;
    esac

    # Process each character
    local i=0
    while [ $i -lt ${#selections} ]; do
        local c="${selections:$i:1}"
        case "$c" in
            a) install_core ;;
            b) install_skills ;;
            c) install_agents ;;
            d) install_hooks ;;
            e) install_extra_commands ;;
            f) install_gsd ;;
            g) install_claude_mem ;;
            h) install_plannotator ;;
            i) show_info ;;
            A) install_all; return ;;
            U) update_all; verify; return ;;
            *) echo "Unknown option: $c" ;;
        esac
        i=$((i + 1))
    done

    verify
}

# =====================================================================
# MAIN ENTRY POINT
# =====================================================================

# Clear previous error log on fresh install
[ -f "$ERROR_LOG" ] && rm -f "$ERROR_LOG"

# Handle CLI flags
case "${1:-}" in
    --all|-A)
        install_all
        exit $?
        ;;
    --update|-U)
        update_all
        verify
        exit $?
        ;;
    --core|-a)
        install_core
        verify
        exit $?
        ;;
    --info|-i)
        show_info_all
        exit 0
        ;;
    --help|-h)
        echo "Usage: bash install.sh [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  (none)       Interactive menu"
        echo "  --all, -A    Install everything non-interactively"
        echo "  --update, -U Update all components from upstream"
        echo "  --core, -a   Install core only"
        echo "  --info, -i   Show detailed component descriptions"
        echo "  --help, -h   Show this help"
        exit 0
        ;;
    "")
        # Interactive mode — loop back to menu after info browsing
        while true; do
            show_menu
            read -r choice
            case "${choice:-}" in
                i)
                    show_info
                    # After info browsing, re-show the menu
                    continue
                    ;;
                *)
                    run_selections "$choice"
                    break
                    ;;
            esac
        done
        ;;
    *)
        # Treat argument as selection string (e.g., "abc")
        run_selections "$1"
        ;;
esac
