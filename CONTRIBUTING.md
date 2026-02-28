# Contributing to GOLDY

## Development setup

```bash
# Clone the repo
git clone git@github.com:SacredTexts/goldy.git ~/.goldy
cd ~/.goldy

# Install locally (creates symlinks, so edits take effect immediately)
bash install.sh

# Run tests
make test

# Run linter
make lint
```

Because the installer symlinks `~/.claude/skills/goldy/` and `~/.agents/skills/goldy/` to `~/.goldy/`, any changes you make in the repo are **immediately live** in Claude Code. No re-install needed for code changes.

## Making changes

### 1. Create a branch

```bash
cd ~/.goldy
git checkout -b feature/my-improvement
```

### 2. Make your changes

- **Python scripts** → `scripts/`
- **Data files (CSVs)** → `data/` or `data/stacks/`
- **Reference docs** → `references/`
- **Slash command templates** → `commands/`
- **Skill metadata** → `SKILL.md`
- **Plan template** → `GOLD-STANDARD-SAMPLE-PLAN.md`

### 3. Test

```bash
# Run the test suite
make test

# Lint for syntax issues
make lint

# Smoke test in Claude Code
# Open claude in any project and run /goldy --help
```

### 4. Submit a PR

```bash
git add -A
git commit -m "feat: description of change"
git push -u origin feature/my-improvement
gh pr create
```

### 5. After merge

All team members update with:

```bash
cd ~/.goldy && git pull
```

No re-install needed (symlinks point to the repo).

**Exception:** If you changed `commands/goldy.md` or `commands/goldy-loop.md`, teammates need to re-run `bash install.sh` because command files are copied (not symlinked) to resolve path templates.

## When to re-run install.sh

| Change type | Re-install needed? |
|-------------|-------------------|
| Python script edits | No (symlinked) |
| Data/CSV changes | No (symlinked) |
| Reference doc changes | No (symlinked) |
| SKILL.md changes | No (symlinked) |
| Command template changes (`commands/*.md`) | **Yes** — paths are rendered at install time |
| GOLD-STANDARD-SAMPLE-PLAN.md changes | **Yes** — copied to `~/.claude/` |
| New files added to repo | No (symlinked directory) |

## File structure

```
goldy/
├── scripts/          # Python engine (21 files, pure stdlib)
├── data/             # Design system CSVs
│   └── stacks/       # Per-framework stack profiles
├── references/       # Operational docs loaded on demand
├── commands/         # Claude Code slash command templates
├── tests/            # Python tests
├── install.sh        # Universal installer
├── Makefile          # dev workflow targets
├── SKILL.md          # Claude Code skill registration
└── GOLD-STANDARD-SAMPLE-PLAN.md
```

## Commit conventions

Use conventional commits:

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `refactor:` — code restructuring
- `test:` — test additions/changes
- `chore:` — maintenance tasks

## Release process

1. Merge PRs to `main`
2. Update `CHANGELOG.md` with the changes
3. Tag a release: `git tag v1.x.0 && git push --tags`
4. Team members run `cd ~/.goldy && git pull` to update
