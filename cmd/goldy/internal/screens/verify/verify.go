package verify

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type Model struct {
	checks   []shared.VerifyCheck
	errCount int
	errLog   string
	width    int
	height   int
}

func New() Model {
	return Model{}
}

type SetChecksMsg struct {
	Checks   []shared.VerifyCheck
	ErrCount int
	ErrLog   string
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case SetChecksMsg:
		m.checks = msg.Checks
		m.errCount = msg.ErrCount
		m.errLog = msg.ErrLog
	}
	return m, nil
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("Verification"))
	b.WriteString("\n\n")

	if len(m.checks) == 0 {
		b.WriteString(style.Muted.Render("  No verification checks available."))
		b.WriteString("\n")
	} else {
		for _, c := range m.checks {
			icon := style.VerifyIcon(c.Exists)
			b.WriteString(fmt.Sprintf("  %s %s\n", icon, c.Label))
		}
	}

	if m.errCount > 0 {
		b.WriteString("\n")
		b.WriteString(style.Error.Render(fmt.Sprintf("  %d error(s) logged to: %s", m.errCount, m.errLog)))
		b.WriteString("\n")
	}

	b.WriteString("\n")
	b.WriteString(style.Muted.Render("  Press any key to continue..."))

	return b.String()
}
