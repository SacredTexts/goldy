package components

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/fileops"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

func ListHooks(cfg *config.Paths) ([]shared.SubItem, error) {
	hooksDir := filepath.Join(cfg.GoldySrc, "extra-hooks")
	entries, err := os.ReadDir(hooksDir)
	if err != nil {
		return nil, err
	}
	var items []shared.SubItem
	for _, e := range entries {
		items = append(items, shared.SubItem{Name: e.Name(), Selected: true})
	}
	return items, nil
}

func InstallHooksFiltered(cfg *config.Paths, log *errs.Logger, filter []string) shared.StepResult {
	filterSet := make(map[string]bool, len(filter))
	for _, f := range filter {
		filterSet[f] = true
	}

	hooksDir := filepath.Join(cfg.GoldySrc, "extra-hooks")
	if !fileops.DirExists(hooksDir) {
		log.Log("hooks", "extra-hooks/ directory not found in repo")
		return shared.StepResult{ComponentID: IDHooks, Success: false, Message: "extra-hooks/ directory not found"}
	}

	fileops.MkdirAll(cfg.ClaudeHooks)

	entries, err := os.ReadDir(hooksDir)
	if err != nil {
		log.Log("hooks", "Failed to read extra-hooks/: "+err.Error())
		return shared.StepResult{ComponentID: IDHooks, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		if !filterSet[e.Name()] {
			continue
		}
		src := filepath.Join(hooksDir, e.Name())
		if e.IsDir() {
			dstDir := filepath.Join(cfg.ClaudeHooks, e.Name())
			fileops.MkdirAll(dstDir)
			if err := fileops.CopyDir(src, dstDir); err != nil {
				log.Log("hooks/"+e.Name(), "Failed to copy directory: "+err.Error())
				continue
			}
			sub, _ := countFiles(src)
			count += sub
		} else {
			dst := filepath.Join(cfg.ClaudeHooks, e.Name())
			if err := fileops.CopyFile(src, dst); err != nil {
				log.Log("hooks", "Failed to copy "+e.Name()+": "+err.Error())
				continue
			}
			count++
		}
	}

	return shared.StepResult{
		ComponentID: IDHooks,
		Success:     true,
		Message:     fmt.Sprintf("Installed %d extra hooks", count),
		ItemCount:   count,
	}
}

func InstallHooks(cfg *config.Paths, log *errs.Logger) shared.StepResult {
	hooksDir := filepath.Join(cfg.GoldySrc, "extra-hooks")
	if !fileops.DirExists(hooksDir) {
		log.Log("hooks", "extra-hooks/ directory not found in repo")
		return shared.StepResult{
			ComponentID: IDHooks,
			Success:     false,
			Message:     "extra-hooks/ directory not found",
			Error:       fmt.Errorf("extra-hooks/ directory not found in repo"),
		}
	}

	fileops.MkdirAll(cfg.ClaudeHooks)

	entries, err := os.ReadDir(hooksDir)
	if err != nil {
		log.Log("hooks", "Failed to read extra-hooks/: "+err.Error())
		return shared.StepResult{ComponentID: IDHooks, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		src := filepath.Join(hooksDir, e.Name())
		if e.IsDir() {
			dstDir := filepath.Join(cfg.ClaudeHooks, e.Name())
			fileops.MkdirAll(dstDir)
			if err := fileops.CopyDir(src, dstDir); err != nil {
				log.Log("hooks/"+e.Name(), "Failed to copy directory: "+err.Error())
				continue
			}
			sub, _ := countFiles(src)
			count += sub
		} else {
			dst := filepath.Join(cfg.ClaudeHooks, e.Name())
			if err := fileops.CopyFile(src, dst); err != nil {
				log.Log("hooks", "Failed to copy "+e.Name()+": "+err.Error())
				continue
			}
			count++
		}
	}

	return shared.StepResult{
		ComponentID: IDHooks,
		Success:     true,
		Message:     fmt.Sprintf("Installed %d extra hooks", count),
		ItemCount:   count,
	}
}

func countFiles(dir string) (int, error) {
	count := 0
	err := filepath.WalkDir(dir, func(_ string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() && d.Name() != ".DS_Store" {
			count++
		}
		return nil
	})
	return count, err
}
