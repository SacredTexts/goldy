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
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/picker"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/progress"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/startup"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/screens/verify"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

type Screen int

const (
	ScreenStartup Screen = iota
	ScreenMenu
	ScreenProgress
	ScreenVerify
	ScreenDone
	ScreenInfo
	ScreenPicker
)

type Model struct {
	screen       Screen
	startup      startup.Model
	menu         menu.Model
	progress     progress.Model
	verify       verify.Model
	doneScreen   done.Model
	info         info.Model
	picker       picker.Model
	cfg          *config.Paths
	logger       *errs.Logger
	orchestrator *installer.Orchestrator
	program      *tea.Program
	version      string
	buildDate    string
	builtBy      string
}

func New(cfg *config.Paths, logger *errs.Logger, version, buildDate, builtBy string) *Model {
	comps := components.All(cfg)
	orch := installer.NewOrchestrator(cfg, logger)

	return &Model{
		screen:       ScreenStartup,
		startup:      startup.New(cfg),
		menu:         menu.New(comps, cfg, version, buildDate, builtBy),
		verify:       verify.New(),
		doneScreen:   done.New(),
		info:         info.New(comps),
		cfg:          cfg,
		logger:       logger,
		orchestrator: orch,
		version:      version,
		buildDate:    buildDate,
		builtBy:      builtBy,
	}
}

func (m *Model) SetProgram(p *tea.Program) {
	m.program = p
}

func (m *Model) Init() tea.Cmd {
	return m.startup.Init()
}

func (m *Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.startup, _ = m.startup.Update(msg)
		m.menu, _ = m.menu.Update(msg)
		m.progress, _ = m.progress.Update(msg)
		m.verify, _ = m.verify.Update(msg)
		doneModel, _ := m.doneScreen.Update(msg)
		m.doneScreen = doneModel.(done.Model)
		m.info, _ = m.info.Update(msg)
		m.picker, _ = m.picker.Update(msg)
		return m, nil

	case shared.StartupCompleteMsg:
		var cmd tea.Cmd
		m.startup, cmd = m.startup.Update(msg)
		if msg.Updated {
			comps := components.All(m.cfg)
			m.menu = menu.New(comps, m.cfg, m.version, m.buildDate, m.builtBy)
			m.info = info.New(comps)
		}
		return m, cmd

	case shared.StartupDoneMsg:
		m.screen = ScreenMenu
		return m, nil

	case shared.ShowInfoMsg:
		m.screen = ScreenInfo
		return m, nil

	case shared.ReturnToMenuMsg:
		m.screen = ScreenMenu
		return m, nil

	case shared.OpenPickerMsg:
		m.picker = picker.New(msg.ComponentID, msg.ComponentName, msg.Items)
		m.screen = ScreenPicker
		return m, nil

	case shared.PickerDoneMsg:
		m.menu, _ = m.menu.Update(msg)
		m.screen = ScreenMenu
		return m, nil

	case menu.StartInstallMsg:
		m.progress = progress.New(msg.Components)
		m.screen = ScreenProgress
		if len(msg.SubSelections) > 0 {
			filters := make(map[string][]string)
			for compID, items := range msg.SubSelections {
				var names []string
				for _, item := range items {
					if item.Selected {
						names = append(names, item.Name)
					}
				}
				filters[compID] = names
			}
			m.orchestrator.RunAsyncFiltered(m.program, msg.Components, filters)
		} else {
			m.orchestrator.RunAsync(m.program, msg.Components)
		}
		return m, m.progress.Init()

	case shared.StartUpdateAllMsg:
		allComps := components.All(m.cfg)
		m.progress = progress.NewWithUpdate(allComps)
		m.screen = ScreenProgress
		m.orchestrator.RunUpdateAsync(m.program, allComps)
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
	case ScreenStartup:
		m.startup, cmd = m.startup.Update(msg)
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
	case ScreenPicker:
		m.picker, cmd = m.picker.Update(msg)
	}
	return m, cmd
}

func (m *Model) View() string {
	switch m.screen {
	case ScreenStartup:
		return m.startup.View()
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
	case ScreenPicker:
		return m.picker.View()
	default:
		return ""
	}
}
