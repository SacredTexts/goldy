package components

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/fileops"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func InstallAgents(cfg *config.Paths, log *errs.Logger) shared.StepResult {
	agentsDir := filepath.Join(cfg.GoldySrc, "agents")
	if !fileops.DirExists(agentsDir) {
		log.Log("agents", "agents/ directory not found in repo")
		return shared.StepResult{
			ComponentID: IDAgents,
			Success:     false,
			Message:     "agents/ directory not found",
			Error:       fmt.Errorf("agents/ directory not found in repo"),
		}
	}

	fileops.MkdirAll(cfg.ClaudeAgents)

	entries, err := os.ReadDir(agentsDir)
	if err != nil {
		log.Log("agents", "Failed to read agents/: "+err.Error())
		return shared.StepResult{ComponentID: IDAgents, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".md") {
			continue
		}
		src := filepath.Join(agentsDir, e.Name())
		dst := filepath.Join(cfg.ClaudeAgents, e.Name())
		if err := fileops.CopyFile(src, dst); err != nil {
			log.Log("agents", "Failed to copy "+e.Name()+": "+err.Error())
			continue
		}
		count++
	}

	return shared.StepResult{
		ComponentID: IDAgents,
		Success:     true,
		Message:     fmt.Sprintf("Installed %d agent definitions", count),
		ItemCount:   count,
	}
}
