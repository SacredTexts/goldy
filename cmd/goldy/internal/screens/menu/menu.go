package menu

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type StartInstallMsg struct {
	Components []components.Component
}

type Model struct {
	items    []components.Component
	cursor   int
	selected map[int]bool
	width    int
	height   int
}

func New(items []components.Component) Model {
	return Model{
		items:    items,
		selected: make(map[int]bool),
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

	case tea.KeyMsg:
		switch {
		case key.Matches(msg, shared.Keys.Quit):
			return m, tea.Quit

		case msg.String() == "up" || msg.String() == "k":
			if m.cursor > 0 {
				m.cursor--
			}

		case msg.String() == "down" || msg.String() == "j":
			if m.cursor < len(m.items)-1 {
				m.cursor++
			}

		case msg.String() == " ":
			m.selected[m.cursor] = !m.selected[m.cursor]

		case msg.String() == "a":
			allTrue := true
			for i := range m.items {
				if !m.selected[i] {
					allTrue = false
					break
				}
			}
			if allTrue {
				m.selected = make(map[int]bool)
			} else {
				for i := range m.items {
					m.selected[i] = true
				}
			}

		case msg.String() == "i":
			return m, func() tea.Msg { return shared.ShowInfoMsg{} }

		case msg.String() == "enter":
			selected := m.SelectedComponents()
			if len(selected) == 0 {
				return m, nil
			}
			return m, func() tea.Msg {
				return StartInstallMsg{Components: selected}
			}
		}
	}
	return m, nil
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("GOLDY INSTALLER"))
	b.WriteString("\n")
	b.WriteString(style.Muted.Render("Select components to install"))
	b.WriteString("\n\n")

	for i, item := range m.items {
		cursor := "  "
		if m.cursor == i {
			cursor = style.Cursor.Render("> ")
		}

		checkbox := style.Checkbox(m.selected[i])
		name := item.Name
		if m.cursor == i {
			name = style.Selected.Render(name)
		}

		b.WriteString(fmt.Sprintf("%s%s %s) %-16s %s\n",
			cursor,
			checkbox,
			style.HelpKey.Render(item.MenuKey),
			name,
			style.Muted.Render(item.Description),
		))
	}

	b.WriteString("\n")
	b.WriteString(style.HelpKey.Render("space"))
	b.WriteString(style.HelpDesc.Render(" toggle  "))
	b.WriteString(style.HelpKey.Render("a"))
	b.WriteString(style.HelpDesc.Render(" all  "))
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" install  "))
	b.WriteString(style.HelpKey.Render("i"))
	b.WriteString(style.HelpDesc.Render(" info  "))
	b.WriteString(style.HelpKey.Render("q"))
	b.WriteString(style.HelpDesc.Render(" quit"))

	return b.String()
}

func (m Model) SelectedComponents() []components.Component {
	var selected []components.Component
	for i, item := range m.items {
		if m.selected[i] {
			selected = append(selected, item)
		}
	}
	return selected
}
