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

func InstallCommands(cfg *config.Paths, log *errs.Logger) shared.StepResult {
	cmdsDir := filepath.Join(cfg.GoldySrc, "extra-commands")
	if !fileops.DirExists(cmdsDir) {
		log.Log("commands", "extra-commands/ directory not found in repo")
		return shared.StepResult{
			ComponentID: IDCommands,
			Success:     false,
			Message:     "extra-commands/ directory not found",
			Error:       fmt.Errorf("extra-commands/ directory not found in repo"),
		}
	}

	fileops.MkdirAll(cfg.ClaudeCommands)

	entries, err := os.ReadDir(cmdsDir)
	if err != nil {
		log.Log("commands", "Failed to read extra-commands/: "+err.Error())
		return shared.StepResult{ComponentID: IDCommands, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".md") {
			continue
		}
		src := filepath.Join(cmdsDir, e.Name())
		dst := filepath.Join(cfg.ClaudeCommands, e.Name())
		if err := fileops.CopyFile(src, dst); err != nil {
			log.Log("commands", "Failed to copy "+e.Name()+": "+err.Error())
			continue
		}
		count++
	}

	return shared.StepResult{
		ComponentID: IDCommands,
		Success:     true,
		Message:     fmt.Sprintf("Installed %d extra commands", count),
		ItemCount:   count,
	}
}
