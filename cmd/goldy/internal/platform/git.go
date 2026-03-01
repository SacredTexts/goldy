package platform

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
)

type RepoMode int

const (
	RepoLocal     RepoMode = iota // Running from cloned repo (CWD has SKILL.md)
	RepoInstalled                 // ~/.goldy exists from previous install
	RepoMissing                   // Need to clone
)

func DetectRepoMode() RepoMode {
	if _, err := os.Stat("SKILL.md"); err == nil {
		return RepoLocal
	}
	home, _ := os.UserHomeDir()
	goldyHome := filepath.Join(home, ".goldy")
	if _, err := os.Stat(filepath.Join(goldyHome, "SKILL.md")); err == nil {
		return RepoInstalled
	}
	return RepoMissing
}

func Clone(dest string) error {
	if err := RunCommand("git", "clone", config.RepoSSH, dest); err == nil {
		return nil
	}
	if err := RunCommand("git", "clone", config.RepoHTTPS, dest); err == nil {
		return nil
	}
	return fmt.Errorf("could not clone goldy repo (tried SSH and HTTPS)")
}

func Pull(dir string) error {
	return RunCommandInDir(dir, "git", "pull", "--ff-only")
}
