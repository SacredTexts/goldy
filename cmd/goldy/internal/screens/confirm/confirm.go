package confirm

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type ConfirmInstallMsg struct {
	Components    []components.Component
	SubSelections map[string][]shared.SubItem
}

type Model struct {
	components    []components.Component
	subSelections map[string][]shared.SubItem
	width         int
	height        int
}

func New(comps []components.Component, subs map[string][]shared.SubItem) Model {
	return Model{
		components:    comps,
		subSelections: subs,
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
		case key.Matches(msg, shared.Keys.Back):
			return m, func() tea.Msg { return shared.ReturnToMenuMsg{} }
		case msg.String() == "q":
			return m, func() tea.Msg { return shared.ReturnToMenuMsg{} }
		case msg.String() == "enter":
			return m, func() tea.Msg {
				return ConfirmInstallMsg{
					Components:    m.components,
					SubSelections: m.subSelections,
				}
			}
		}
	}
	return m, nil
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("GOLDY INSTALLER — Confirm Installation"))
	b.WriteString("\n\n")
	b.WriteString("  The following will be installed:\n\n")

	for _, comp := range m.components {
		name := comp.Name
		desc := comp.Description

		// Show sub-selection counts if applicable
		if items, ok := m.subSelections[comp.ID]; ok {
			selected := 0
			for _, item := range items {
				if item.Selected {
					selected++
				}
			}
			name = fmt.Sprintf("%s (%d/%d)", comp.Name, selected, len(items))
		}

		b.WriteString(fmt.Sprintf("    %s  %s\n",
			style.Subtitle.Render(fmt.Sprintf("%-24s", name)),
			style.Muted.Render(desc),
		))
	}

	b.WriteString("\n\n")
	b.WriteString("  ")
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" install  "))
	b.WriteString(style.HelpKey.Render("esc"))
	b.WriteString(style.HelpDesc.Render(" go back"))

	return b.String()
}
