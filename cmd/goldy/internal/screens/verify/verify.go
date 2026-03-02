package verify

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type group struct {
	name    string
	checks  []shared.VerifyCheck
	okCount int
}

type Model struct {
	checks   []shared.VerifyCheck
	groups   []group
	errCount int
	errLog   string
	scroll   int
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
		m.scroll = 0
		m.groups = buildGroups(msg.Checks)

	case tea.KeyMsg:
		switch msg.String() {
		case "up", "k":
			if m.scroll > 0 {
				m.scroll--
			}
		case "down", "j":
			total := m.totalLines()
			maxVisible := m.visibleRows()
			if m.scroll < total-maxVisible {
				m.scroll++
			}
		}
	}
	return m, nil
}

func buildGroups(checks []shared.VerifyCheck) []group {
	seen := map[string]int{}
	var groups []group
	for _, c := range checks {
		name := c.Group
		if name == "" {
			name = "Other"
		}
		idx, ok := seen[name]
		if !ok {
			idx = len(groups)
			seen[name] = idx
			groups = append(groups, group{name: name})
		}
		groups[idx].checks = append(groups[idx].checks, c)
		if c.Exists {
			groups[idx].okCount++
		}
	}
	return groups
}

func (m Model) totalLines() int {
	// Each group: header(1) + checks + blank(1)
	lines := 0
	for _, g := range m.groups {
		lines += 1 + len(g.checks) + 1
	}
	return lines
}

func (m Model) visibleRows() int {
	// Reserve: title(1) + margin(1) + ... + error(2) + help(2)
	available := m.height - 6
	if available < 5 {
		available = 5
	}
	return available
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("Verification"))
	b.WriteString("\n\n")

	if len(m.groups) == 0 {
		b.WriteString(style.Muted.Render("  No verification checks available."))
		b.WriteString("\n")
	} else {
		// Build all lines then apply scroll window
		var lines []string
		for _, g := range m.groups {
			header := fmt.Sprintf("  %s (%d/%d)",
				style.Subtitle.Render(g.name),
				g.okCount, len(g.checks))
			lines = append(lines, header)

			for _, c := range g.checks {
				icon := style.VerifyIcon(c.Exists)
				lines = append(lines, fmt.Sprintf("    %s %s", icon, c.Label))
			}
			lines = append(lines, "")
		}

		maxVisible := m.visibleRows()
		end := m.scroll + maxVisible
		if end > len(lines) {
			end = len(lines)
		}
		start := m.scroll
		if start < 0 {
			start = 0
		}

		if start > 0 {
			b.WriteString(style.Muted.Render("  ... more above"))
			b.WriteString("\n")
		}

		for i := start; i < end; i++ {
			b.WriteString(lines[i])
			b.WriteString("\n")
		}

		if end < len(lines) {
			b.WriteString(style.Muted.Render("  ... more below"))
			b.WriteString("\n")
		}
	}

	if m.errCount > 0 {
		b.WriteString("\n")
		b.WriteString(style.Error.Render(fmt.Sprintf("  %d error(s) logged to: %s", m.errCount, m.errLog)))
		b.WriteString("\n")
	}

	b.WriteString("\n")
	b.WriteString("  ")
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" continue  "))
	if m.totalLines() > m.visibleRows() {
		b.WriteString(style.HelpKey.Render("j/k"))
		b.WriteString(style.HelpDesc.Render(" scroll"))
	}

	return b.String()
}
