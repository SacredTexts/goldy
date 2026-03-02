# GOLDY

**The Claude Code power-up you didn't know you needed (but absolutely do).**

Goldy is a globally-installed toolkit that straps a jetpack onto [Claude Code](https://docs.anthropic.com/en/docs/claude-code). It ships 31 skills, 19 agents, safety hooks, slash commands, and third-party integrations — all wired up through a slick terminal UI. No per-project config. No YAML nightmares. Just install and go.

---

## What It Is

- A **planning engine** (`/goldy`) that writes Gold Standard project plans with stack-aware architecture, session memory, and resume capsules — so Claude stops winging it and starts engineering
- A **phase executor** (`/goldy-loop`) that runs those plans step-by-step with git worktrees, checkpoints, circuit breakers, and deep audits — like CI/CD but for your AI pair programmer
- An **interactive TUI installer** built in Go + Bubbletea, because clicking through install wizards is so 2004
- A **global toolkit** — install once, works everywhere, follows you across every project like a loyal golden retriever

## What's Inside

- **31 Skills** — SEO (13 flavors), TanStack/React frontend, dev tools, brainstorming, pricing strategy, UI/UX design intelligence, and more
- **19 Agents** — GSD workflow agents (plan, research, execute, verify, debug), SEO specialists, a markdown rewriter, and a pair programmer reviewer who actually reads your code
- **8 Hooks** — Notifications, TTS (your terminal can talk now), safety guards against dangerous file deletions, credential leak prevention, and context monitoring
- **4 Extra Commands** — `/agent` for orchestration, `/plannotator-review` for interactive code review, `/revise-claude-md` for session reflection, `/global-update` to refresh everything
- **3rd Party Integrations** — GSD (structured project management), Claude-Mem (persistent team memory), Plannotator (plan review UI)
- **Gold Standard Plan Template** — A battle-tested plan skeleton with 14 mandatory sections, because "just figure it out" isn't a spec

## How It Works

- You type `/goldy build me an auth system` in any Claude Code session
- Goldy detects your stack (React? Next.js? Svelte? It knows 13 profiles), then generates a comprehensive plan with phases, requirements, test criteria, and acceptance targets
- You review the plan. You're still the boss here.
- You run `/goldy-loop --plan plans/auth-plan.md` and Goldy executes each phase in an isolated git worktree, runs lint + typecheck + tests before marking anything done, and hands you a completion report with actual evidence
- If something breaks mid-flight, the circuit breaker kicks in (3-state: CLOSED → HALF_OPEN → OPEN) and Goldy stops before it makes things worse — unlike that one coworker
- Sessions are resumable. Close your laptop, go touch grass, come back, and Goldy picks up exactly where it left off

## How to Install

### The one-liner (macOS / Linux / WSL2)

```bash
curl -fsSL https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
```

### The npm way

```bash
npm install -g goldy-cli
```

### The "I read install scripts before running them" way

```bash
git clone git@github.com:SacredTexts/goldy.git ~/.goldy
cd ~/.goldy && bash install.sh
```

<details>
<summary>Private repo? Use a GitHub token:</summary>

```bash
# With gh CLI (recommended)
gh auth token | GOLDY_TOKEN=$(cat) bash -c \
  'curl -fsSL -H "Authorization: token $GOLDY_TOKEN" https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash'

# With a personal access token
GOLDY_TOKEN=ghp_xxxx curl -fsSL -H "Authorization: token $GOLDY_TOKEN" \
  https://raw.githubusercontent.com/SacredTexts/goldy/main/install.sh | bash
```

</details>

### Install modes

- **Interactive menu** — `bash install.sh` — browse and pick what you want
- **Install everything** — `bash install.sh --all` — the "yes to all" approach
- **Core only** — `bash install.sh --core` — just the skill, commands, and hooks
- **Cherry pick** — `bash install.sh abc` — install components a, b, and c by letter
- **Info mode** — `bash install.sh --info` — read descriptions before committing

### Where things land

| Location | What lives there |
|----------|-----------------|
| `~/.goldy/` | Cloned repo (source of truth) |
| `~/.claude/skills/goldy/` | Symlink to the repo |
| `~/.claude/commands/` | `/goldy` and `/goldy-loop` slash commands |
| `~/.claude/agents/` | 19 agent definitions |
| `~/.claude/hooks/` | Safety hooks and notifications |
| `~/.claude/GOLD-STANDARD-SAMPLE-PLAN.md` | The plan template |

## Key Flags

| Flag | What it does |
|------|-------------|
| `--plan <file>` | Point to a specific plan file |
| `--max-iterations N` | Override the loop limit (default: 10, for the cautious) |
| `--commit-phase` | Auto-commit after each phase completes |
| `--diagnostics` | Enable diagnostic bundles for debugging |
| `--commands` | Print the full command reference |

## Update

```bash
cd ~/.goldy && git pull && bash install.sh
```

Or just run `/global-update` from inside Claude Code. It updates itself. The future is now.

## Uninstall

```bash
make -C ~/.goldy uninstall
```

No hard feelings.

## Requirements

- **Python 3.8+** (pure stdlib — zero pip dependencies, because dependency hell is real)
- **Claude Code CLI** (`npm install -g @anthropic-ai/claude-code`)
- **Git** (for worktree isolation in `/goldy-loop`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

Private — SacredTexts team use only.
