package components

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func InstallPlannotator(_ *config.Paths, log *errs.Logger) shared.StepResult {
	home, _ := os.UserHomeDir()
	pluginDir := filepath.Join(home, ".claude", "plugins", "cache", "plannotator", "plannotator")

	if fi, err := os.Stat(pluginDir); err == nil && fi.IsDir() {
		versions := latestVersion(pluginDir)
		return shared.StepResult{
			ComponentID: IDPlannotator,
			Success:     true,
			Message:     fmt.Sprintf("plannotator already installed (v%s)", versions),
		}
	}

	log.Log("plannotator", "Not installed. Install via Claude Code plugin manager.")
	return shared.StepResult{
		ComponentID: IDPlannotator,
		Success:     true,
		Message:     "plannotator not found. Install via: claude plugins install plannotator@plannotator",
	}
}
