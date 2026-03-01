package done

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type Model struct {
	results []shared.StepResult
	success bool
	width   int
	height  int
}

func New() Model {
	return Model{}
}

type SetResultsMsg struct {
	Results []shared.StepResult
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case SetResultsMsg:
		m.results = msg.Results
		m.success = true
		for _, r := range msg.Results {
			if !r.Success {
				m.success = false
				break
			}
		}

	case tea.KeyMsg:
		return m, tea.Quit
	}
	return m, nil
}

func (m Model) View() string {
	var b strings.Builder

	if m.success {
		b.WriteString(style.Success.Render("GOLDY installed successfully!"))
	} else {
		failures := 0
		for _, r := range m.results {
			if !r.Success {
				failures++
			}
		}
		b.WriteString(style.Error.Render(fmt.Sprintf("Install completed with %d error(s).", failures)))
	}
	b.WriteString("\n\n")

	for _, r := range m.results {
		icon := style.StatusIcon(r.Success)
		b.WriteString(fmt.Sprintf("  %s %s\n", icon, r.Message))
	}

	b.WriteString("\n")
	b.WriteString(style.Muted.Render("  /goldy          — plan mode"))
	b.WriteString("\n")
	b.WriteString(style.Muted.Render("  /goldy-loop     — phase execution"))
	b.WriteString("\n")
	b.WriteString(style.Muted.Render("  /global-update  — update all components"))
	b.WriteString("\n\n")
	b.WriteString(style.Muted.Render("  Press any key to exit."))

	return b.String()
}
