package platform

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

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

type PullResult struct {
	Updated bool
	Summary string
	Error   error
}

func PullWithResult(dir string) PullResult {
	out, err := RunCommandOutput(dir, "git", "pull", "--ff-only")
	if err != nil {
		return PullResult{Error: err, Summary: "Pull failed"}
	}
	if strings.Contains(out, "Already up to date") {
		return PullResult{Updated: false, Summary: "Already up to date"}
	}
	// Extract summary from git output (last non-empty line usually)
	lines := strings.Split(strings.TrimSpace(out), "\n")
	summary := lines[len(lines)-1]
	return PullResult{Updated: true, Summary: summary}
}
