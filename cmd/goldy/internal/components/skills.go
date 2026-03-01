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

func ListSkills(cfg *config.Paths) ([]shared.SubItem, error) {
	skillsDir := filepath.Join(cfg.GoldySrc, "skills")
	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		return nil, err
	}
	var items []shared.SubItem
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		items = append(items, shared.SubItem{Name: e.Name(), Selected: true})
	}
	return items, nil
}

func InstallSkillsFiltered(cfg *config.Paths, log *errs.Logger, filter []string) shared.StepResult {
	filterSet := make(map[string]bool, len(filter))
	for _, f := range filter {
		filterSet[f] = true
	}

	skillsDir := filepath.Join(cfg.GoldySrc, "skills")
	if !fileops.DirExists(skillsDir) {
		log.Log("skills", "skills/ directory not found in repo")
		return shared.StepResult{ComponentID: IDSkills, Success: false, Message: "skills/ directory not found"}
	}

	fileops.MkdirAll(cfg.ClaudeSkills)
	fileops.MkdirAll(cfg.AgentsSkills)

	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		log.Log("skills", "Failed to read skills/: "+err.Error())
		return shared.StepResult{ComponentID: IDSkills, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		if !e.IsDir() || !filterSet[e.Name()] {
			continue
		}
		name := e.Name()
		src := filepath.Join(skillsDir, name)

		fileops.Remove(filepath.Join(cfg.ClaudeSkills, name))
		if err := fileops.Symlink(src, filepath.Join(cfg.ClaudeSkills, name)); err != nil {
			log.Log("skills/"+name, "Failed to symlink: "+err.Error())
			continue
		}
		fileops.Remove(filepath.Join(cfg.AgentsSkills, name))
		fileops.Symlink(src, filepath.Join(cfg.AgentsSkills, name))
		count++
	}

	return shared.StepResult{
		ComponentID: IDSkills,
		Success:     true,
		Message:     fmt.Sprintf("Linked %d/%d skills to ~/.claude/skills/", count, len(filter)),
		ItemCount:   count,
	}
}

func InstallSkills(cfg *config.Paths, log *errs.Logger) shared.StepResult {
	skillsDir := filepath.Join(cfg.GoldySrc, "skills")
	if !fileops.DirExists(skillsDir) {
		log.Log("skills", "skills/ directory not found in repo")
		return shared.StepResult{
			ComponentID: IDSkills,
			Success:     false,
			Message:     "skills/ directory not found",
			Error:       fmt.Errorf("skills/ directory not found in repo"),
		}
	}

	fileops.MkdirAll(cfg.ClaudeSkills)
	fileops.MkdirAll(cfg.AgentsSkills)

	entries, err := os.ReadDir(skillsDir)
	if err != nil {
		log.Log("skills", "Failed to read skills/: "+err.Error())
		return shared.StepResult{ComponentID: IDSkills, Success: false, Error: err}
	}

	count := 0
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		name := e.Name()
		src := filepath.Join(skillsDir, name)

		fileops.Remove(filepath.Join(cfg.ClaudeSkills, name))
		if err := fileops.Symlink(src, filepath.Join(cfg.ClaudeSkills, name)); err != nil {
			log.Log("skills/"+name, "Failed to symlink: "+err.Error())
			continue
		}

		fileops.Remove(filepath.Join(cfg.AgentsSkills, name))
		fileops.Symlink(src, filepath.Join(cfg.AgentsSkills, name))

		count++
	}

	return shared.StepResult{
		ComponentID: IDSkills,
		Success:     true,
		Message:     fmt.Sprintf("Linked %d skills to ~/.claude/skills/", count),
		ItemCount:   count,
	}
}
