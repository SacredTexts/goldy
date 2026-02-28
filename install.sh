#!/usr/bin/env bash
# install.sh — Universal GOLDY installer (macOS / Linux / WSL2)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
#   -- or --
#   cd ~/.goldy && bash install.sh
#
# This installer is GLOBAL-ONLY. No per-project installation.
set -euo pipefail

REPO_URL="git@github.com:SacredTexts/goldy.git"
REPO_HTTPS="https://github.com/SacredTexts/goldy.git"
GOLDY_HOME="$HOME/.goldy"

# ── Detect if running from curl pipe or from cloned repo ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

if [ -z "$SCRIPT_DIR" ] || [ ! -f "$SCRIPT_DIR/SKILL.md" ]; then
    # Running from curl pipe — need to clone first
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
        # Try SSH first, fall back to HTTPS
        if git clone "$REPO_URL" "$GOLDY_HOME" 2>/dev/null; then
            echo "    Cloned via SSH."
        elif git clone "$REPO_HTTPS" "$GOLDY_HOME" 2>/dev/null; then
            echo "    Cloned via HTTPS."
        else
            echo "ERROR: Could not clone goldy. Check your GitHub access."
            echo "  SSH:   $REPO_URL"
            echo "  HTTPS: $REPO_HTTPS"
            exit 1
        fi
    fi

    # Re-exec the install from the cloned repo
    exec bash "$GOLDY_HOME/install.sh"
fi

# ── Running from cloned repo ──
GOLDY_SRC="$SCRIPT_DIR"

AGENTS_SKILL="$HOME/.agents/skills/goldy"
CLAUDE_SKILL="$HOME/.claude/skills/goldy"
CLAUDE_COMMANDS="$HOME/.claude/commands"
CLAUDE_ROOT="$HOME/.claude"
CODEX_SKILLS="$HOME/.codex/skills"

echo "╔══════════════════════════════════════════════╗"
echo "║         GOLDY INSTALLER (Global)              ║"
echo "╠══════════════════════════════════════════════╣"
echo "║ Scope:   GLOBAL (all projects)                ║"
echo "║ Source:  $GOLDY_SRC"
echo "║ Skill:   $CLAUDE_SKILL"
echo "║ Cmds:    $CLAUDE_COMMANDS"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Symlink into ~/.agents/skills/goldy ──
echo "[1/5] Linking skill to ~/.agents/skills/goldy..."
mkdir -p "$(dirname "$AGENTS_SKILL")"
rm -rf "$AGENTS_SKILL"
ln -sfn "$GOLDY_SRC" "$AGENTS_SKILL"
echo "      -> $AGENTS_SKILL -> $GOLDY_SRC"

# ── Step 2: Symlink into ~/.claude/skills/goldy ──
echo "[2/5] Linking skill to ~/.claude/skills/goldy..."
mkdir -p "$(dirname "$CLAUDE_SKILL")"
rm -rf "$CLAUDE_SKILL"
ln -sfn "$GOLDY_SRC" "$CLAUDE_SKILL"
echo "      -> $CLAUDE_SKILL -> $GOLDY_SRC"

# Optional: codex skills
mkdir -p "$CODEX_SKILLS" 2>/dev/null || true
rm -rf "$CODEX_SKILLS/goldy" 2>/dev/null || true
ln -sfn "$GOLDY_SRC" "$CODEX_SKILLS/goldy" 2>/dev/null || true

# ── Step 3: Install command files with resolved paths ──
echo "[3/5] Installing slash commands..."
mkdir -p "$CLAUDE_COMMANDS"

SCRIPTS_PATH="$GOLDY_SRC/scripts"

# Generate goldy.md with resolved script path
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
- Reuses active/latest temp plan only when prompt is empty (or by explicit workflow choice).
- Loads full memory then injects compact Resume Capsule.
- Prints a visible activation banner.
- Never creates, reuses, or deletes git worktrees.
- Never auto-invokes \`/goldy-loop\`.
- If worktree execution is needed, run \`/goldy-loop\` manually in the prompt.

## After goldy runs -- Plan Mode Protocol

Read the goldy output carefully. If the output contains \`plan_mode_required: True\`:
1. **STOP** -- do not write any implementation code.
2. **Enter plan mode** -- use the plan file path from goldy's \`plan:\` output line.
3. **Fill in the plan** -- populate the Gold Standard template sections (Problem Statement, Goals, Phases, etc.) based on the user's original prompt.
4. **Present the plan to the user** for review/approval before any coding begins.
5. Only after the user approves the plan, exit plan mode and begin implementation.

If \`plan_mode_required\` is False or absent, proceed normally with the active plan.
CMDEOF

# Generate goldy-loop.md with resolved script path
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
- Requires a user-authored plan outside \`temp-plans/\` (unless \`--allow-temp-plan\` is set).
- Worktree identity is derived from the plan file, so different plan files use different worktrees.
- Enforces plan drift detection; use \`--require-resync\` to sync source plan into mapped worktree plan copy.
- Runs preflight ambiguity checks and asks clarifying questions before executing the loop.
- After preflight, offers \`Start\` and \`Chat\` options before execution.
- Runs up to 10 loop iterations by default (\`--max-iterations\` to override).
- Runs 5 deep audits (lint, typecheck, tests, integration, robustness) before final completion.
- Prints a completion report including total compactions and total minutes.
- Writes checkpoints, append-only history, lock metadata, diagnostics (optional), and deterministic handoff artifacts.
- Supports resume via session id.
- Supports breaker operator controls (\`--breaker-status\`, \`--breaker-reset\`, \`--breaker-auto-reset\`).
- Supports \`--diagnostics\` for per-session diagnostic bundles in \`.goldy/diagnostics\`.
- Optional phase-level commits with \`--commit-phase\`.
- \`--commands\` prints full command list + usage examples.
- Running without \`--plan\` prints the same command reference.
CMDEOF

echo "      -> $CLAUDE_COMMANDS/goldy.md"
echo "      -> $CLAUDE_COMMANDS/goldy-loop.md"

# ── Step 4: Install Gold Standard plan template ──
echo "[4/5] Installing Gold Standard plan template..."
cp "$GOLDY_SRC/GOLD-STANDARD-SAMPLE-PLAN.md" "$CLAUDE_ROOT/"
echo "      -> $CLAUDE_ROOT/GOLD-STANDARD-SAMPLE-PLAN.md"

# ── Step 5: Verify ──
echo "[5/5] Verifying installation..."
echo ""

ERRORS=0

check_exists() {
    if [ -e "$1" ] || [ -L "$1" ]; then
        echo "  ✓ $1"
    else
        echo "  ✗ MISSING: $1"
        ERRORS=$((ERRORS + 1))
    fi
}

check_exists "$AGENTS_SKILL/scripts/goldy.py"
check_exists "$AGENTS_SKILL/scripts/goldy_loop.py"
check_exists "$CLAUDE_SKILL/SKILL.md"
check_exists "$CLAUDE_SKILL/data/colors.csv"
check_exists "$CLAUDE_SKILL/references/planning-contract.md"
check_exists "$CLAUDE_COMMANDS/goldy.md"
check_exists "$CLAUDE_COMMANDS/goldy-loop.md"
check_exists "$CLAUDE_ROOT/GOLD-STANDARD-SAMPLE-PLAN.md"

# Verify python3 is available
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo "  ✓ python3 found: $PY_VER"
else
    echo "  ✗ python3 not found in PATH"
    ERRORS=$((ERRORS + 1))
fi

echo ""
if [ "$ERRORS" -eq 0 ]; then
    echo "╔══════════════════════════════════════════════╗"
    echo "║  ✓ GOLDY installed successfully!              ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║  Commands:                                    ║"
    echo "║    /goldy          — plan mode                ║"
    echo "║    /goldy-loop     — phase execution          ║"
    echo "║                                               ║"
    echo "║  Update:  cd ~/.goldy && make update          ║"
    echo "║  Remove:  cd ~/.goldy && make uninstall       ║"
    echo "║                                               ║"
    echo "║  Python: pure stdlib, no pip needed            ║"
    echo "╚══════════════════════════════════════════════╝"
else
    echo "Install completed with $ERRORS error(s). Check above."
    exit 1
fi
