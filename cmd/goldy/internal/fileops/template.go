package fileops

import "strings"

const goldyCmdTemplate = `---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Activate GOLDY planning/orchestration with stack-aware resume capsules
argument-hint: [--plan <plan-file>] [options]
---

# GOLDY

Run GOLDY command engine:

` + "```bash" + `
python3 {{SCRIPTS_PATH}}/goldy.py $ARGUMENTS
` + "```" + `

Behavior:
- Uses explicit ` + "`--plan`" + ` when provided.
- Creates a fresh ` + "`temp-plans/`" + ` Gold Standard temp plan for prompt-driven calls.
- For coding-intent auto-invocations, reuses existing plan if one exists; creates new only when none found.
- Loads full memory then injects compact Resume Capsule.
- Prints a visible activation banner.
- Never creates, reuses, or deletes git worktrees.
- Never auto-invokes ` + "`/goldy-loop`" + `.

## After goldy runs -- Plan Mode Protocol

Read the goldy output carefully. If the output contains ` + "`plan_mode_required: True`" + `:
1. **STOP** -- do not write any implementation code.
2. **Enter plan mode** -- use the plan file path from goldy's ` + "`plan:`" + ` output line.
3. **Fill in the plan** -- populate the Gold Standard template sections.
4. **Present the plan to the user** for review/approval.
5. Only after approval, exit plan mode and begin implementation.

If ` + "`plan_mode_required`" + ` is False or absent, proceed normally.
`

const goldyLoopCmdTemplate = `---
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Glob
description: Run GOLDY phase loop with checkpoints and auto-resume chain
argument-hint: --plan <plan-file> [options]
---

# GOLDY LOOP

Run GOLDY loop engine:

` + "```bash" + `
python3 {{SCRIPTS_PATH}}/goldy_loop.py $ARGUMENTS
` + "```" + `

Behavior:
- Manual-only command; do not auto-invoke from ` + "`/goldy`" + `.
- Guardrail-compliant stop on low context.
- Creates/reuses a session git worktree by default.
- Runs up to 10 loop iterations by default (` + "`--max-iterations`" + ` to override).
- ` + "`--commands`" + ` prints full command list + usage examples.
`

func GoldyCmdTemplate() string     { return goldyCmdTemplate }
func GoldyLoopCmdTemplate() string { return goldyLoopCmdTemplate }

func RenderTemplate(tmpl, scriptsPath string) string {
	return strings.ReplaceAll(tmpl, "{{SCRIPTS_PATH}}", scriptsPath)
}
