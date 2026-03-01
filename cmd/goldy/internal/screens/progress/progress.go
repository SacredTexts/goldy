package progress

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type StepStatus int

const (
	Pending StepStatus = iota
	Running
	Done
	Failed
)

type stepView struct {
	name    string
	status  StepStatus
	message string
}

type Model struct {
	steps       []stepView
	currentStep int
	spinner     spinner.Model
	done        bool
	results     []shared.StepResult
	width       int
	height      int
}

func New(comps []components.Component) Model {
	steps := make([]stepView, len(comps))
	for i, c := range comps {
		steps[i] = stepView{name: c.Name, status: Pending}
	}

	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.Gold)

	return Model{
		steps:   steps,
		spinner: s,
	}
}

func NewWithUpdate(comps []components.Component) Model {
	steps := make([]stepView, len(comps)+1)
	steps[0] = stepView{name: "Update Repository", status: Pending}
	for i, c := range comps {
		steps[i+1] = stepView{name: c.Name, status: Pending}
	}

	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.Gold)

	return Model{
		steps:   steps,
		spinner: s,
	}
}

func (m Model) Init() tea.Cmd {
	return m.spinner.Tick
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case spinner.TickMsg:
		var cmd tea.Cmd
		m.spinner, cmd = m.spinner.Update(msg)
		return m, cmd

	case shared.StepStartedMsg:
		m.currentStep = msg.Index
		if msg.Index < len(m.steps) {
			m.steps[msg.Index].status = Running
		}
		return m, nil

	case shared.StepCompletedMsg:
		for i := range m.steps {
			if m.steps[i].status == Running {
				if msg.Result.Success {
					m.steps[i].status = Done
				} else {
					m.steps[i].status = Failed
				}
				m.steps[i].message = msg.Result.Message
				break
			}
		}
		m.results = append(m.results, msg.Result)
		return m, nil

	case shared.AllStepsCompleteMsg:
		m.done = true
		m.results = msg.Results
		return m, nil
	}
	return m, nil
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("Installing GOLDY Components"))
	b.WriteString("\n\n")

	completed := 0
	for _, step := range m.steps {
		var icon string
		switch step.status {
		case Pending:
			icon = style.Muted.Render("[ ]")
		case Running:
			icon = m.spinner.View()
		case Done:
			icon = style.Success.Render("[ok]")
			completed++
		case Failed:
			icon = style.Error.Render("[!!]")
			completed++
		}

		name := step.name
		if step.status == Running {
			name = style.Selected.Render(name)
		}

		line := fmt.Sprintf("  %s %-16s", icon, name)
		if step.message != "" {
			line += style.Muted.Render("  " + step.message)
		}
		b.WriteString(line + "\n")
	}

	b.WriteString("\n")
	total := len(m.steps)
	pct := 0
	if total > 0 {
		pct = completed * 100 / total
	}
	bar := renderProgressBar(pct, 30)
	b.WriteString(fmt.Sprintf("  %s %d/%d complete", bar, completed, total))

	if m.done {
		b.WriteString("\n\n")
		b.WriteString(style.Muted.Render("  Press any key to continue..."))
	}

	return b.String()
}

func (m Model) Done() bool {
	return m.done
}

func (m Model) Results() []shared.StepResult {
	return m.results
}

func renderProgressBar(pct, width int) string {
	filled := pct * width / 100
	if filled > width {
		filled = width
	}
	empty := width - filled

	bar := lipgloss.NewStyle().Foreground(style.Gold).Render(strings.Repeat("█", filled))
	bar += lipgloss.NewStyle().Foreground(style.Gray).Render(strings.Repeat("░", empty))
	return bar
}
