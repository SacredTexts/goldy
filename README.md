# GOLDY

Gold Standard planning and orchestration skill for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

GOLDY gives Claude Code two slash commands that turn it into a deterministic, resumable, multi-phase project executor:

- **`/goldy`** — Creates Gold Standard plans with stack-aware architecture decisions, session memory, and resume capsules.
- **`/goldy-loop`** — Executes plans phase-by-phase with worktrees, checkpoints, circuit breakers, and deterministic handoff.

## Requirements

- **Python 3.8+** (pure stdlib — no pip packages needed)
- **Claude Code CLI** (`npm install -g @anthropic-ai/claude-code`)
- **Git** (for worktree support in `/goldy-loop`)

## Install

### One-liner (macOS / Linux / WSL2)

```bash
curl -fsSL https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
```

<details>
<summary>If you get a 404 (private repo), use a GitHub token:</summary>

```bash
# Option 1: Use gh CLI auth (recommended if gh is installed)
gh auth token | GOLDY_TOKEN=$(cat) bash -c \
  'curl -fsSL -H "Authorization: token $GOLDY_TOKEN" https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash'

# Option 2: Pass a personal access token directly
GOLDY_TOKEN=ghp_xxxx curl -fsSL -H "Authorization: token $GOLDY_TOKEN" \
  https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
```

</details>

### Manual install

```bash
git clone git@github.com:SacredTexts/goldy.git ~/.goldy
cd ~/.goldy && bash install.sh
```

### What gets installed

| Location | Contents |
|----------|----------|
| `~/.goldy/` | Cloned repo (source of truth) |
| `~/.agents/skills/goldy/` | Symlink → `~/.goldy/` |
| `~/.claude/skills/goldy/` | Symlink → `~/.goldy/` |
| `~/.claude/commands/goldy.md` | `/goldy` slash command |
| `~/.claude/commands/goldy-loop.md` | `/goldy-loop` slash command |
| `~/.claude/GOLD-STANDARD-SAMPLE-PLAN.md` | Plan template |

Everything is **global** — works in every project without per-repo setup.

## Update

```bash
cd ~/.goldy && git pull && bash install.sh
```

Or use the built-in update command:

```bash
make -C ~/.goldy update
```

## Uninstall

```bash
make -C ~/.goldy uninstall
```

## Usage

### Planning (`/goldy`)

In any Claude Code session:

```
/goldy build a user authentication system
```

GOLDY will:
1. Resolve your project's tech stack
2. Create a Gold Standard plan in `temp-plans/`
3. Enter plan mode for your review before any code is written

### Phase execution (`/goldy-loop`)

After you have a reviewed plan:

```
/goldy-loop --plan plans/auth-plan.md
```

GOLDY will:
1. Create a git worktree for isolation
2. Execute phases with checkpoint/resume
3. Run deep audits (lint, typecheck, tests) before completion
4. Produce a completion report with evidence

### Key flags

| Flag | Description |
|------|-------------|
| `--plan <file>` | Specify plan file |
| `--max-iterations N` | Override loop limit (default: 10) |
| `--commit-phase` | Auto-commit after each phase |
| `--diagnostics` | Enable diagnostic bundles |
| `--commands` | Print full command reference |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

Private — SacredTexts team use only.
