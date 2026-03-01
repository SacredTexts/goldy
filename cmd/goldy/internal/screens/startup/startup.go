package startup

import (
	"time"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/platform"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type Model struct {
	spinner spinner.Model
	cfg     *config.Paths
	status  string
	done    bool
	err     error
	width   int
	height  int
}

func New(cfg *config.Paths) Model {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.Gold)
	return Model{spinner: s, cfg: cfg}
}

func (m Model) Init() tea.Cmd {
	return tea.Batch(m.spinner.Tick, m.doUpdate())
}

func (m Model) doUpdate() tea.Cmd {
	return func() tea.Msg {
		result := platform.PullWithResult(m.cfg.GoldySrc)
		return shared.StartupCompleteMsg{
			Updated: result.Updated,
			Summary: result.Summary,
			Error:   result.Error,
		}
	}
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case shared.StartupCompleteMsg:
		m.done = true
		m.err = msg.Error
		if msg.Error != nil {
			m.status = "Could not update: " + msg.Error.Error()
		} else if msg.Updated {
			m.status = "Updated! " + msg.Summary
		} else {
			m.status = "Up to date"
		}
		return m, tea.Tick(800*time.Millisecond, func(time.Time) tea.Msg {
			return shared.StartupDoneMsg{}
		})

	case shared.StartupDoneMsg:
		return m, nil // app.go catches this

	case spinner.TickMsg:
		if !m.done {
			var cmd tea.Cmd
			m.spinner, cmd = m.spinner.Update(msg)
			return m, cmd
		}

	case tea.KeyMsg:
		if m.done {
			return m, func() tea.Msg { return shared.StartupDoneMsg{} }
		}
	}
	return m, nil
}

func (m Model) View() string {
	title := style.Title.Render("GOLDY INSTALLER")

	if !m.done {
		return title + "\n\n  " + m.spinner.View() + " Checking for updates...\n"
	}

	var statusLine string
	if m.err != nil {
		statusLine = lipgloss.NewStyle().Foreground(style.Yellow).Render("  ! " + m.status)
	} else {
		statusLine = style.Success.Render("  Success! ") + style.Muted.Render(m.status)
	}

	return title + "\n\n" + statusLine + "\n"
}
