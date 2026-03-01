package components

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/platform"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func InstallGSD(_ *config.Paths, log *errs.Logger) shared.StepResult {
	home, _ := os.UserHomeDir()
	gsdDir := filepath.Join(home, ".claude", "get-shit-done")

	if _, err := os.Stat(gsdDir); err == nil {
		version := "unknown"
		if data, err := os.ReadFile(filepath.Join(gsdDir, "VERSION")); err == nil {
			version = string(data)
		}
		return shared.StepResult{
			ComponentID: IDGSD,
			Success:     true,
			Message:     fmt.Sprintf("GSD already installed (v%s)", version),
		}
	}

	if !platform.CommandExists("npx") {
		log.Log("gsd", "npx not found. Install Node.js first, then run: npx -y get-shit-done@latest")
		return shared.StepResult{
			ComponentID: IDGSD,
			Success:     false,
			Message:     "npx not available — install Node.js first",
			Error:       fmt.Errorf("npx not found"),
		}
	}

	if err := platform.RunCommand("npx", "-y", "get-shit-done@latest"); err != nil {
		log.Log("gsd", "npx get-shit-done install failed: "+err.Error())
		return shared.StepResult{
			ComponentID: IDGSD,
			Success:     false,
			Message:     "GSD install failed — see install-errors-log.md",
			Error:       err,
		}
	}

	return shared.StepResult{
		ComponentID: IDGSD,
		Success:     true,
		Message:     "GSD installed",
	}
}
