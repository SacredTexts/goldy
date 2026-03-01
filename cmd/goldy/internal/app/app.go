package app

import (
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/installer"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/done"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/info"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/menu"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/progress"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/verify"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

type Screen int

const (
	ScreenMenu Screen = iota
	ScreenProgress
	ScreenVerify
	ScreenDone
	ScreenInfo
)

type Model struct {
	screen       Screen
	menu         menu.Model
	progress     progress.Model
	verify       verify.Model
	doneScreen   done.Model
	info         info.Model
	cfg          *config.Paths
	logger       *errs.Logger
	orchestrator *installer.Orchestrator
	program      *tea.Program
}

func New(cfg *config.Paths, logger *errs.Logger) *Model {
	comps := components.All(cfg)
	orch := installer.NewOrchestrator(cfg, logger)

	return &Model{
		screen:       ScreenMenu,
		menu:         menu.New(comps),
		verify:       verify.New(),
		doneScreen:   done.New(),
		info:         info.New(comps),
		cfg:          cfg,
		logger:       logger,
		orchestrator: orch,
	}
}

func (m *Model) SetProgram(p *tea.Program) {
	m.program = p
}

func (m *Model) Init() tea.Cmd {
	return nil
}

func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.menu, _ = m.menu.Update(msg)
		m.progress, _ = m.progress.Update(msg)
		m.verify, _ = m.verify.Update(msg)
		doneModel, _ := m.doneScreen.Update(msg)
		m.doneScreen = doneModel.(done.Model)
		m.info, _ = m.info.Update(msg)
		return m, nil

	case shared.ShowInfoMsg:
		m.screen = ScreenInfo
		return m, nil

	case shared.ReturnToMenuMsg:
		m.screen = ScreenMenu
		return m, nil

	case menu.StartInstallMsg:
		m.progress = progress.New(msg.Components)
		m.screen = ScreenProgress
		m.orchestrator.RunAsync(m.program, msg.Components)
		return m, m.progress.Init()

	case shared.StepStartedMsg, shared.StepCompletedMsg:
		var cmd tea.Cmd
		m.progress, cmd = m.progress.Update(msg)
		return m, cmd

	case shared.AllStepsCompleteMsg:
		m.progress, _ = m.progress.Update(msg)
		return m, nil

	case tea.KeyMsg:
		if m.screen == ScreenProgress && m.progress.Done() {
			results := m.progress.Results()
			checks := components.VerifyCore(m.cfg)
			m.verify, _ = m.verify.Update(verify.SetChecksMsg{
				Checks:   checks,
				ErrCount: m.logger.ErrorCount(),
				ErrLog:   m.logger.Path(),
			})
			doneModel, _ := m.doneScreen.Update(done.SetResultsMsg{Results: results})
		m.doneScreen = doneModel.(done.Model)
			m.screen = ScreenVerify
			return m, nil
		}
		if m.screen == ScreenVerify {
			m.screen = ScreenDone
			return m, nil
		}
	}

	var cmd tea.Cmd
	switch m.screen {
	case ScreenMenu:
		m.menu, cmd = m.menu.Update(msg)
	case ScreenProgress:
		m.progress, cmd = m.progress.Update(msg)
	case ScreenVerify:
		m.verify, cmd = m.verify.Update(msg)
	case ScreenDone:
		var newDone tea.Model
		newDone, cmd = m.doneScreen.Update(msg)
		m.doneScreen = newDone.(done.Model)
	case ScreenInfo:
		m.info, cmd = m.info.Update(msg)
	}
	return m, cmd
}

func (m *Model) View() string {
	switch m.screen {
	case ScreenMenu:
		return m.menu.View()
	case ScreenProgress:
		return m.progress.View()
	case ScreenVerify:
		return m.verify.View()
	case ScreenDone:
		return m.doneScreen.View()
	case ScreenInfo:
		return m.info.View()
	default:
		return ""
	}
}
