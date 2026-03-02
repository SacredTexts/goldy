package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/mattn/go-isatty"
	"github.com/spf13/cobra"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/app"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/installer"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/platform"
)

var (
	// Set via -ldflags at build time
	Version   = "dev"
	BuildDate = "unknown"
	BuiltBy   = "local"
)

var (
	flagAll     bool
	flagUpdate  bool
	flagCore    bool
	flagInfo    bool
	flagVersion bool
)

var rootCmd = &cobra.Command{
	Use:           "goldy",
	Short:         "GOLDY toolkit for Claude Code",
	Long:          "Interactive TUI installer for the GOLDY planning & orchestration toolkit.",
	RunE:          run,
	SilenceUsage:  true,
	SilenceErrors: true,
}

func init() {
	rootCmd.Flags().BoolVarP(&flagAll, "all", "A", false, "Install everything non-interactively")
	rootCmd.Flags().BoolVarP(&flagUpdate, "update", "U", false, "Update all components from upstream")
	rootCmd.Flags().BoolVarP(&flagCore, "core", "a", false, "Install core only")
	rootCmd.Flags().BoolVarP(&flagInfo, "info", "i", false, "Show detailed component descriptions")
	rootCmd.Flags().BoolVarP(&flagVersion, "version", "v", false, "Show version and build date")
}

func run(cmd *cobra.Command, args []string) error {
	cfg := config.Resolve()
	logger := errs.NewLogger(cfg.ErrorLog)

	if err := ensureRepo(cfg); err != nil {
		return err
	}

	switch {
	case flagVersion:
		fmt.Printf("goldy %s (built %s by %s)\n", Version, BuildDate, BuiltBy)
		return nil
	case flagInfo:
		return runInfo(cfg)
	case flagAll:
		return runNonInteractive(cfg, logger, components.All(cfg))
	case flagCore:
		comps := components.All(cfg)
		return runNonInteractive(cfg, logger, comps[:1])
	case flagUpdate:
		return runUpdate(cfg, logger)
	default:
		if !isatty.IsTerminal(os.Stdin.Fd()) && !isatty.IsCygwinTerminal(os.Stdin.Fd()) {
			return runNonInteractive(cfg, logger, components.All(cfg))
		}
		return runTUI(cfg, logger)
	}
}

func ensureRepo(cfg *config.Paths) error {
	mode := platform.DetectRepoMode()
	if mode == platform.RepoMissing {
		fmt.Println("Cloning goldy to", cfg.GoldyHome, "...")
		if err := platform.Clone(cfg.GoldyHome); err != nil {
			return fmt.Errorf("could not clone goldy repo: %w", err)
		}
		*cfg = *config.Resolve()
	}
	return nil
}

func runInfo(cfg *config.Paths) error {
	comps := components.All(cfg)
	for _, c := range comps {
		fmt.Printf("\n--- %s ---\n%s\n", c.Name, c.InfoText)
	}
	return nil
}

func runNonInteractive(cfg *config.Paths, logger *errs.Logger, comps []components.Component) error {
	fmt.Println()
	fmt.Println("  GOLDY INSTALLER (non-interactive)")
	fmt.Println()

	orch := installer.NewOrchestrator(cfg, logger)
	results := orch.RunSync(comps)

	fmt.Println()
	fmt.Println("  Verification:")
	checks := components.VerifyCore(cfg)
	for _, c := range checks {
		icon := "ok"
		if !c.Exists {
			icon = "XX"
		}
		fmt.Printf("    [%s] %s\n", icon, c.Label)
	}

	errCount := logger.ErrorCount()
	if errCount > 0 {
		fmt.Printf("\n  %d error(s) logged to: %s\n", errCount, logger.Path())
	}

	hasFailure := false
	for _, r := range results {
		if !r.Success {
			hasFailure = true
			break
		}
	}

	fmt.Println()
	if hasFailure {
		fmt.Println("  Install completed with errors.")
		return fmt.Errorf("install completed with errors")
	}
	fmt.Println("  GOLDY installed successfully!")
	return nil
}

func runUpdate(cfg *config.Paths, logger *errs.Logger) error {
	fmt.Println()
	fmt.Println("  GOLDY UPDATE")
	fmt.Println()

	orch := installer.NewOrchestrator(cfg, logger)
	results := orch.RunUpdate(components.All(cfg))

	for _, r := range results {
		if !r.Success {
			return fmt.Errorf("update completed with errors")
		}
	}

	fmt.Println()
	fmt.Println("  Update complete!")
	return nil
}

func runTUI(cfg *config.Paths, logger *errs.Logger) error {
	m := app.New(cfg, logger, Version, BuildDate, BuiltBy)
	p := tea.NewProgram(m, tea.WithAltScreen())
	m.SetProgram(p)
	_, err := p.Run()
	return err
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}
