package menu

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type StartInstallMsg struct {
	Components    []components.Component
	SubSelections map[string][]shared.SubItem
}

type Model struct {
	items            []components.Component
	cursor           int
	selected         map[int]bool
	pickerSelections map[string][]shared.SubItem
	cfg              *config.Paths
	version          string
	buildDate        string
	builtBy          string
	width            int
	height           int
}

func New(items []components.Component, cfg *config.Paths, version, buildDate, builtBy string) Model {
	return Model{
		items:            items,
		selected:         make(map[int]bool),
		pickerSelections: make(map[string][]shared.SubItem),
		cfg:              cfg,
		version:          version,
		buildDate:        buildDate,
		builtBy:          builtBy,
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

// totalItems returns the number of selectable rows including the Update/Install All item
func (m Model) totalItems() int {
	return len(m.items) + 1 // +1 for "Update / Install All"
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case shared.PickerDoneMsg:
		m.pickerSelections[msg.ComponentID] = msg.Items

	case tea.KeyMsg:
		switch {
		case key.Matches(msg, shared.Keys.Quit):
			return m, tea.Quit

		case msg.String() == "up" || msg.String() == "k":
			if m.cursor > 0 {
				m.cursor--
			}

		case msg.String() == "down" || msg.String() == "j":
			if m.cursor < m.totalItems()-1 {
				m.cursor++
			}

		case msg.String() == " ":
			// Only toggle component items, not the Update/Install All row
			if m.cursor < len(m.items) {
				m.selected[m.cursor] = !m.selected[m.cursor]
			}

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
			return m, func() tea.Msg { return shared.StartUpdateAllMsg{} }

		case msg.String() == "?":
			return m, func() tea.Msg { return shared.ShowInfoMsg{} }

		case msg.String() == "p":
			// Picky chooser: only if cursor is on a component that is selected and has sub-items
			if m.cursor < len(m.items) && m.selected[m.cursor] {
				comp := m.items[m.cursor]
				if comp.SubItems != nil {
					items, err := comp.SubItems(m.cfg)
					if err == nil {
						// Apply existing picker selections if present
						if existing, ok := m.pickerSelections[comp.ID]; ok && len(existing) > 0 {
							existingMap := make(map[string]bool)
							for _, e := range existing {
								existingMap[e.Name] = e.Selected
							}
							for i, item := range items {
								if sel, ok := existingMap[item.Name]; ok {
									items[i].Selected = sel
								}
							}
						}
						return m, func() tea.Msg {
							return shared.OpenPickerMsg{
								ComponentID:   comp.ID,
								ComponentName: comp.Name,
								Items:         items,
							}
						}
					}
				}
			}

		case msg.String() == "enter":
			// If cursor is on Update/Install All row
			if m.cursor == len(m.items) {
				return m, func() tea.Msg { return shared.StartUpdateAllMsg{} }
			}
			selected := m.SelectedComponents()
			if len(selected) == 0 {
				return m, nil
			}
			// Build sub-selections map
			var subSel map[string][]shared.SubItem
			if len(m.pickerSelections) > 0 {
				subSel = make(map[string][]shared.SubItem)
				for _, comp := range selected {
					if items, ok := m.pickerSelections[comp.ID]; ok {
						subSel[comp.ID] = items
					}
				}
			}
			return m, func() tea.Msg {
				return StartInstallMsg{
					Components:    selected,
					SubSelections: subSel,
				}
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

		desc := item.Description
		// Show sub-selection count if custom picks exist
		if picks, ok := m.pickerSelections[item.ID]; ok && m.selected[i] {
			total := len(picks)
			selected := 0
			for _, p := range picks {
				if p.Selected {
					selected++
				}
			}
			if selected < total {
				desc = fmt.Sprintf("(%d/%d) %s", selected, total, item.Description)
			}
		}

		b.WriteString(fmt.Sprintf("%s%s %s) %-16s %s\n",
			cursor,
			checkbox,
			style.HelpKey.Render(item.MenuKey),
			name,
			style.Muted.Render(desc),
		))
	}

	// Separator + Update / Install All item
	b.WriteString("\n")
	updateCursor := "  "
	if m.cursor == len(m.items) {
		updateCursor = style.Cursor.Render("> ")
	}
	updateName := "Update / Install All"
	if m.cursor == len(m.items) {
		updateName = style.Selected.Render(updateName)
	}
	b.WriteString(fmt.Sprintf("%s    %s) %-16s %s\n",
		updateCursor,
		style.HelpKey.Render("i"),
		updateName,
		style.Muted.Render("Updates and installs all"),
	))

	b.WriteString("\n")
	b.WriteString(style.Success.Render("        Auto updates the CLI and adds new stuff"))

	b.WriteString("\n\n")
	b.WriteString(style.HelpKey.Render("space"))
	b.WriteString(style.HelpDesc.Render(" toggle  "))
	b.WriteString(style.HelpKey.Render("a"))
	b.WriteString(style.HelpDesc.Render(" all  "))
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" install  "))
	b.WriteString(style.HelpKey.Render("i"))
	b.WriteString(style.HelpDesc.Render(" update/install all  "))
	b.WriteString(style.HelpKey.Render("?"))
	b.WriteString(style.HelpDesc.Render(" info  "))
	b.WriteString(style.HelpKey.Render("p"))
	b.WriteString(style.HelpDesc.Render(" picky chooser  "))
	b.WriteString(style.HelpKey.Render("q"))
	b.WriteString(style.HelpDesc.Render(" quit"))

	b.WriteString("\n\n")
	b.WriteString(style.Muted.Render(fmt.Sprintf("v%s · built %s by %s", m.version, m.buildDate, m.builtBy)))

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
