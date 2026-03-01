package config

import (
	"os"
	"path/filepath"
)

const (
	RepoSSH   = "git@github.com:SacredTexts/goldy.git"
	RepoHTTPS = "https://github.com/SacredTexts/goldy.git"
)

type Paths struct {
	GoldyHome      string
	GoldySrc       string
	ClaudeRoot     string
	ClaudeSkills   string
	ClaudeCommands string
	ClaudeAgents   string
	ClaudeHooks    string
	AgentsSkills   string
	CodexSkills    string
	ErrorLog       string
}

func (p *Paths) ScriptsPath() string {
	return filepath.Join(p.GoldySrc, "scripts")
}

func Resolve() *Paths {
	home, _ := os.UserHomeDir()
	goldyHome := filepath.Join(home, ".goldy")

	// Determine source: prefer CWD if it contains SKILL.md (running from repo)
	src := goldyHome
	if cwd, err := os.Getwd(); err == nil {
		if _, err := os.Stat(filepath.Join(cwd, "SKILL.md")); err == nil {
			src = cwd
		}
	}

	return &Paths{
		GoldyHome:      goldyHome,
		GoldySrc:       src,
		ClaudeRoot:     filepath.Join(home, ".claude"),
		ClaudeSkills:   filepath.Join(home, ".claude", "skills"),
		ClaudeCommands: filepath.Join(home, ".claude", "commands"),
		ClaudeAgents:   filepath.Join(home, ".claude", "agents"),
		ClaudeHooks:    filepath.Join(home, ".claude", "hooks"),
		AgentsSkills:   filepath.Join(home, ".agents", "skills"),
		CodexSkills:    filepath.Join(home, ".codex", "skills"),
		ErrorLog:       filepath.Join(goldyHome, "install-errors-log.md"),
	}
}
