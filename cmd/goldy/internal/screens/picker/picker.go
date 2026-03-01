package picker

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/key"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type Model struct {
	componentID   string
	componentName string
	items         []shared.SubItem
	origItems     []shared.SubItem // snapshot for cancel
	cursor        int
	scroll        int // scroll offset for long lists
	width         int
	height        int
}

func New(componentID, componentName string, items []shared.SubItem) Model {
	orig := make([]shared.SubItem, len(items))
	copy(orig, items)
	return Model{
		componentID:   componentID,
		componentName: componentName,
		items:         items,
		origItems:     orig,
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
			// Cancel — restore original selections
			return m, func() tea.Msg {
				return shared.PickerDoneMsg{
					ComponentID: m.componentID,
					Items:       m.origItems,
				}
			}

		case msg.String() == "q":
			return m, func() tea.Msg {
				return shared.PickerDoneMsg{
					ComponentID: m.componentID,
					Items:       m.origItems,
				}
			}

		case msg.String() == "up" || msg.String() == "k":
			if m.cursor > 0 {
				m.cursor--
				if m.cursor < m.scroll {
					m.scroll = m.cursor
				}
			}

		case msg.String() == "down" || msg.String() == "j":
			if m.cursor < len(m.items)-1 {
				m.cursor++
				maxVisible := m.visibleRows()
				if m.cursor >= m.scroll+maxVisible {
					m.scroll = m.cursor - maxVisible + 1
				}
			}

		case msg.String() == " ":
			if m.cursor < len(m.items) {
				m.items[m.cursor].Selected = !m.items[m.cursor].Selected
			}

		case msg.String() == "a":
			allTrue := true
			for _, item := range m.items {
				if !item.Selected {
					allTrue = false
					break
				}
			}
			for i := range m.items {
				m.items[i].Selected = !allTrue
			}

		case msg.String() == "enter":
			return m, func() tea.Msg {
				return shared.PickerDoneMsg{
					ComponentID: m.componentID,
					Items:       m.items,
				}
			}
		}
	}
	return m, nil
}

func (m Model) visibleRows() int {
	// Reserve lines for: title(1) + blank(1) + subtitle(1) + blank(1) + ... + blank(1) + count(1) + blank(1) + help(1)
	available := m.height - 8
	if available < 5 {
		available = 5
	}
	return available
}

func (m Model) View() string {
	var b strings.Builder

	total := len(m.items)
	selected := 0
	for _, item := range m.items {
		if item.Selected {
			selected++
		}
	}

	b.WriteString(style.Title.Render(fmt.Sprintf("GOLDY — %s (%d items)", m.componentName, total)))
	b.WriteString("\n")
	b.WriteString(style.Muted.Render("Select individual items"))
	b.WriteString("\n\n")

	maxVisible := m.visibleRows()
	end := m.scroll + maxVisible
	if end > total {
		end = total
	}

	for i := m.scroll; i < end; i++ {
		item := m.items[i]
		cursor := "  "
		if m.cursor == i {
			cursor = style.Cursor.Render("> ")
		}

		checkbox := style.Checkbox(item.Selected)
		name := item.Name
		if m.cursor == i {
			name = style.Selected.Render(name)
		}

		b.WriteString(fmt.Sprintf("%s%s %s\n", cursor, checkbox, name))
	}

	// Scroll indicators
	if m.scroll > 0 {
		b.WriteString(style.Muted.Render("  ... more above"))
		b.WriteString("\n")
	}
	if end < total {
		b.WriteString(style.Muted.Render("  ... more below"))
		b.WriteString("\n")
	}

	b.WriteString("\n")
	b.WriteString(style.Muted.Render(fmt.Sprintf("  (%d/%d selected)", selected, total)))
	b.WriteString("\n\n")

	b.WriteString(style.HelpKey.Render("space"))
	b.WriteString(style.HelpDesc.Render(" toggle  "))
	b.WriteString(style.HelpKey.Render("a"))
	b.WriteString(style.HelpDesc.Render(" all  "))
	b.WriteString(style.HelpKey.Render("enter"))
	b.WriteString(style.HelpDesc.Render(" confirm  "))
	b.WriteString(style.HelpKey.Render("esc"))
	b.WriteString(style.HelpDesc.Render(" cancel"))

	return b.String()
}
