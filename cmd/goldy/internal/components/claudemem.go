package components

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func InstallClaudeMem(_ *config.Paths, log *errs.Logger) shared.StepResult {
	home, _ := os.UserHomeDir()
	pluginDir := filepath.Join(home, ".claude", "plugins", "cache", "thedotmack", "claude-mem")

	if fi, err := os.Stat(pluginDir); err == nil && fi.IsDir() {
		versions := latestVersion(pluginDir)
		return shared.StepResult{
			ComponentID: IDClaudeMem,
			Success:     true,
			Message:     fmt.Sprintf("claude-mem already installed (v%s)", versions),
		}
	}

	log.Log("claude-mem", "Not installed. Install via Claude Code plugin manager.")
	return shared.StepResult{
		ComponentID: IDClaudeMem,
		Success:     true,
		Message:     "claude-mem not found. Install via: claude plugins install claude-mem@thedotmack",
	}
}

func latestVersion(dir string) string {
	entries, err := os.ReadDir(dir)
	if err != nil || len(entries) == 0 {
		return "unknown"
	}
	names := make([]string, 0, len(entries))
	for _, e := range entries {
		names = append(names, e.Name())
	}
	sort.Strings(names)
	return names[len(names)-1]
}
