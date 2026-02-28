# GOLDY Install Verification

## Skill Links

- Codex: `/Users/forest/.codex/skills/goldy` -> `/Users/forest/.agents/skills/goldy`
- Claude global: `/Users/forest/.claude/skills/goldy` -> `/Users/forest/.agents/skills/goldy`
- Claude project: `/Volumes/Coding/Code/platform/.claude/skills/goldy` -> `/Users/forest/.agents/skills/goldy`

## Command Files + SHA256

- `/Users/forest/.claude/commands/goldy.md`: `b464c02bb266893c68a161969df8cfc80685a906dfc03e6186edc2de8fdef85d`
- `/Users/forest/.claude/commands/goldy-loop.md`: `336ff69c2f8e280020b33967a39e5a9747835b876fcaf5251f2c692f3069b0db`
- `/Users/forest/.claude/commands/goldy-chrome.md`: `cbbf63b4e2c73c6f8c53de53034386d15133d50bd8da6097ec598da29f0c5657`
- `/Volumes/Coding/Code/platform/.claude/commands/goldy.md`: `b464c02bb266893c68a161969df8cfc80685a906dfc03e6186edc2de8fdef85d`
- `/Volumes/Coding/Code/platform/.claude/commands/goldy-loop.md`: `336ff69c2f8e280020b33967a39e5a9747835b876fcaf5251f2c692f3069b0db`
- `/Volumes/Coding/Code/platform/.claude/commands/goldy-chrome.md`: `cbbf63b4e2c73c6f8c53de53034386d15133d50bd8da6097ec598da29f0c5657`

## Runtime State Roots

- Project runtime root: `/Volumes/Coding/Code/platform/.goldy`
- Project plans root: `/Volumes/Coding/Code/platform/temp-plans`

## Verification Commands

```bash
python3 /Users/forest/.agents/skills/goldy/scripts/goldy_install.py verify
python3 -m unittest discover -s /Users/forest/.agents/skills/goldy/tests -v
```
