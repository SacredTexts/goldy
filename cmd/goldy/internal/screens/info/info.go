package info

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type Model struct {
	categories []components.Component
	cursor     int
	viewing    bool
	viewport   viewport.Model
	width      int
	height     int
}

func New(comps []components.Component) Model {
	vp := viewport.New(80, 20)
	return Model{
		categories: comps,
		viewport:   vp,
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.viewport.Width = msg.Width - 4
		m.viewport.Height = msg.Height - 8

	case tea.KeyMsg:
		if m.viewing {
			switch {
			case key.Matches(msg, shared.Keys.Back) || msg.String() == "q":
				m.viewing = false
				return m, nil
			default:
				var cmd tea.Cmd
				m.viewport, cmd = m.viewport.Update(msg)
				return m, cmd
			}
		}

		switch {
		case key.Matches(msg, shared.Keys.Back) || msg.String() == "q":
			return m, func() tea.Msg { return shared.ReturnToMenuMsg{} }

		case msg.String() == "up" || msg.String() == "k":
			if m.cursor > 0 {
				m.cursor--
			}

		case msg.String() == "down" || msg.String() == "j":
			if m.cursor < len(m.categories)-1 {
				m.cursor++
			}

		case msg.String() == "enter":
			m.viewing = true
			m.viewport.SetContent(m.categories[m.cursor].InfoText)
			m.viewport.GotoTop()
		}
	}
	return m, nil
}

func (m Model) View() string {
	if m.viewing {
		return m.viewDetail()
	}
	return m.viewOverview()
}

func (m Model) viewOverview() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("GOLDY - What's Inside"))
	b.WriteString("\n\n")

	for i, cat := range m.categories {
		cursor := "  "
		if m.cursor == i {
			cursor = style.Cursor.Render("> ")
		}

		name := cat.Name
		if m.cursor == i {
			name = style.Selected.Render(name)
		}

		b.WriteString(fmt.Sprintf("%s%s) %-16s %s\n",
			cursor,
			style.HelpKey.Render(cat.MenuKey),
			name,
			style.Muted.Render(cat.Description),
		))
	}

	b.WriteString("\n")
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" details  "))
	b.WriteString(style.HelpKey.Render("esc"))
	b.WriteString(style.HelpDesc.Render(" back to menu"))

	return b.String()
}

func (m Model) viewDetail() string {
	var b strings.Builder

	cat := m.categories[m.cursor]
	b.WriteString(style.Title.Render(cat.Name))
	b.WriteString("\n")
	b.WriteString(m.viewport.View())
	b.WriteString("\n\n")
	b.WriteString(style.HelpKey.Render("esc"))
	b.WriteString(style.HelpDesc.Render(" back  "))
	b.WriteString(style.HelpKey.Render("up/down"))
	b.WriteString(style.HelpDesc.Render(" scroll"))

	return b.String()
}
