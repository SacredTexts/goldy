package components

import (
	"path/filepath"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/fileops"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func InstallCore(cfg *config.Paths, log *errs.Logger) shared.StepResult {
	fileops.MkdirAll(cfg.AgentsSkills)
	fileops.MkdirAll(cfg.ClaudeSkills)
	fileops.MkdirAll(cfg.CodexSkills)

	fileops.Remove(filepath.Join(cfg.AgentsSkills, "goldy"))
	fileops.Remove(filepath.Join(cfg.ClaudeSkills, "goldy"))
	fileops.Remove(filepath.Join(cfg.CodexSkills, "goldy"))

	if err := fileops.Symlink(cfg.GoldySrc, filepath.Join(cfg.AgentsSkills, "goldy")); err != nil {
		log.Log("core", "Failed to symlink to ~/.agents/skills/: "+err.Error())
	}
	if err := fileops.Symlink(cfg.GoldySrc, filepath.Join(cfg.ClaudeSkills, "goldy")); err != nil {
		log.Log("core", "Failed to symlink to ~/.claude/skills/: "+err.Error())
	}
	fileops.Symlink(cfg.GoldySrc, filepath.Join(cfg.CodexSkills, "goldy"))

	fileops.MkdirAll(cfg.ClaudeCommands)
	scriptsPath := cfg.ScriptsPath()

	goldyCmd := fileops.RenderTemplate(fileops.GoldyCmdTemplate(), scriptsPath)
	if err := fileops.WriteFile(filepath.Join(cfg.ClaudeCommands, "goldy.md"), goldyCmd); err != nil {
		log.Log("core", "Failed to write goldy.md command: "+err.Error())
	}

	loopCmd := fileops.RenderTemplate(fileops.GoldyLoopCmdTemplate(), scriptsPath)
	if err := fileops.WriteFile(filepath.Join(cfg.ClaudeCommands, "goldy-loop.md"), loopCmd); err != nil {
		log.Log("core", "Failed to write goldy-loop.md command: "+err.Error())
	}

	src := filepath.Join(cfg.GoldySrc, "GOLD-STANDARD-SAMPLE-PLAN.md")
	dst := filepath.Join(cfg.ClaudeRoot, "GOLD-STANDARD-SAMPLE-PLAN.md")
	if err := fileops.CopyFile(src, dst); err != nil {
		log.Log("core", "Failed to copy Gold Standard template: "+err.Error())
	}

	fileops.MkdirAll(cfg.ClaudeHooks)
	hooksSrc := filepath.Join(cfg.GoldySrc, "hooks")
	if err := fileops.CopyFile(filepath.Join(hooksSrc, "pre_tool_use.py"), filepath.Join(cfg.ClaudeHooks, "pre_tool_use.py")); err != nil {
		log.Log("core", "Failed to copy pre_tool_use.py: "+err.Error())
	}
	if err := fileops.CopyFile(filepath.Join(hooksSrc, "prevention.md"), filepath.Join(cfg.ClaudeHooks, "prevention.md")); err != nil {
		log.Log("core", "Failed to copy prevention.md: "+err.Error())
	}
	fileops.CopyFileIfNotExists(filepath.Join(hooksSrc, "prevention.config.json"), filepath.Join(cfg.ClaudeHooks, "prevention.config.json"))

	if err := fileops.RegisterPreToolUseHook(cfg.ClaudeRoot, cfg.ClaudeHooks); err != nil {
		log.Log("core/hooks", "Could not register PreToolUse hook: "+err.Error())
	}

	return shared.StepResult{
		ComponentID: IDCore,
		Success:     true,
		Message:     "Linked goldy skill, installed commands, hooks, and template",
	}
}

func VerifyCore(cfg *config.Paths) []shared.VerifyCheck {
	return []shared.VerifyCheck{
		{Label: "goldy skill", Path: filepath.Join(cfg.ClaudeSkills, "goldy"), Exists: fileops.Exists(filepath.Join(cfg.ClaudeSkills, "goldy"))},
		{Label: "goldy command", Path: filepath.Join(cfg.ClaudeCommands, "goldy.md"), Exists: fileops.Exists(filepath.Join(cfg.ClaudeCommands, "goldy.md"))},
		{Label: "goldy-loop command", Path: filepath.Join(cfg.ClaudeCommands, "goldy-loop.md"), Exists: fileops.Exists(filepath.Join(cfg.ClaudeCommands, "goldy-loop.md"))},
		{Label: "Gold Standard template", Path: filepath.Join(cfg.ClaudeRoot, "GOLD-STANDARD-SAMPLE-PLAN.md"), Exists: fileops.Exists(filepath.Join(cfg.ClaudeRoot, "GOLD-STANDARD-SAMPLE-PLAN.md"))},
		{Label: "pre_tool_use.py", Path: filepath.Join(cfg.ClaudeHooks, "pre_tool_use.py"), Exists: fileops.Exists(filepath.Join(cfg.ClaudeHooks, "pre_tool_use.py"))},
	}
}
