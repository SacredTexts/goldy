package sources

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
	srcs "github.com/SacredTexts/goldy/cmd/goldy/internal/sources"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/style"
)

type mode int

const (
	modeBrowse mode = iota
	modeEdit
)

// LoadMsg triggers async manifest loading.
type LoadMsg struct {
	GoldySrc string
}

// manifestLoadedMsg carries the loaded manifest back to the screen.
type manifestLoadedMsg struct {
	manifest *srcs.Manifest
	err      error
}

type Model struct {
	goldySrc string
	entries  []srcs.Entry
	cursor   int
	scroll   int
	mode     mode
	input    textinput.Model
	editOrig string // original URL before editing
	dirty    bool
	saved    bool // flash "saved" indicator
	saveErr  error
	loaded   bool
	loadErr  error
	width    int
	height   int
}

func New() Model {
	ti := textinput.New()
	ti.Placeholder = "https://github.com/owner/repo"
	ti.CharLimit = 256
	ti.Width = 50
	return Model{input: ti}
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case LoadMsg:
		m.goldySrc = msg.GoldySrc
		goldySrc := msg.GoldySrc
		return m, func() tea.Msg {
			existing, err := srcs.Load(goldySrc)
			if err != nil {
				return manifestLoadedMsg{err: err}
			}
			if len(existing.Entries) > 0 {
				return manifestLoadedMsg{manifest: existing}
			}
			generated, err := srcs.Generate(goldySrc, nil)
			if err != nil {
				return manifestLoadedMsg{err: err}
			}
			_ = srcs.Save(goldySrc, generated)
			return manifestLoadedMsg{manifest: generated}
		}

	case manifestLoadedMsg:
		if msg.err != nil {
			m.loadErr = msg.err
			m.loaded = true
			return m, nil
		}
		m.entries = make([]srcs.Entry, len(msg.manifest.Entries))
		copy(m.entries, msg.manifest.Entries)
		m.loaded = true
		return m, nil

	case tea.KeyMsg:
		if m.mode == modeEdit {
			return m.updateEdit(msg)
		}
		return m.updateBrowse(msg)
	}
	return m, nil
}

func (m Model) updateBrowse(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "up", "k":
		if m.cursor > 0 {
			m.cursor--
			if m.cursor < m.scroll {
				m.scroll = m.cursor
			}
		}

	case "down", "j":
		if m.cursor < len(m.entries)-1 {
			m.cursor++
			maxVisible := m.visibleRows()
			if m.cursor >= m.scroll+maxVisible {
				m.scroll = m.cursor - maxVisible + 1
			}
		}

	case " ":
		if m.cursor < len(m.entries) {
			m.entries[m.cursor].Bundled = !m.entries[m.cursor].Bundled
			if m.entries[m.cursor].Bundled {
				m.entries[m.cursor].URL = ""
			}
			m.dirty = true
			m.saved = false
		}

	case "enter":
		if m.cursor < len(m.entries) && !m.entries[m.cursor].Bundled {
			m.mode = modeEdit
			m.editOrig = m.entries[m.cursor].URL
			m.input.SetValue(m.entries[m.cursor].URL)
			m.input.Focus()
			m.input.CursorEnd()
			return m, textinput.Blink
		}

	case "ctrl+s":
		m.save()

	case "esc", "q":
		if m.dirty {
			m.save()
		}
		return m, func() tea.Msg { return shared.ReturnToMenuMsg{} }
	}
	return m, nil
}

func (m Model) updateEdit(msg tea.KeyMsg) (Model, tea.Cmd) {
	switch msg.String() {
	case "enter":
		val := m.input.Value()
		m.entries[m.cursor].URL = val
		if val != m.editOrig {
			m.dirty = true
			m.saved = false
		}
		m.mode = modeBrowse
		m.input.Blur()
		return m, nil

	case "esc":
		m.mode = modeBrowse
		m.input.Blur()
		return m, nil

	default:
		var cmd tea.Cmd
		m.input, cmd = m.input.Update(msg)
		return m, cmd
	}
}

func (m *Model) save() {
	manifest := &srcs.Manifest{
		Version: srcs.Version,
		Entries: m.entries,
	}
	m.saveErr = srcs.Save(m.goldySrc, manifest)
	if m.saveErr == nil {
		m.dirty = false
		m.saved = true
	}
}

func (m Model) visibleRows() int {
	available := m.height - 10
	if available < 5 {
		available = 5
	}
	return available
}

func (m Model) View() string {
	var b strings.Builder

	b.WriteString(style.Title.Render("GOLDY — Sources & Origins"))
	b.WriteString("\n")
	b.WriteString(style.Muted.Render("Track where each skill and agent comes from"))
	b.WriteString("\n\n")

	if !m.loaded {
		b.WriteString(style.Muted.Render("  Loading..."))
		return b.String()
	}
	if m.loadErr != nil {
		b.WriteString(style.Error.Render(fmt.Sprintf("  Error: %v", m.loadErr)))
		return b.String()
	}

	total := len(m.entries)
	if total == 0 {
		b.WriteString(style.Muted.Render("  No skills or agents found."))
		return b.String()
	}

	// Header
	nameW := 34
	typeW := 8
	showPath := m.width >= 120
	b.WriteString(style.Muted.Render(fmt.Sprintf("      %-*s %-*s %s",
		nameW, "NAME", typeW, "TYPE", "SOURCE")))
	if showPath {
		b.WriteString(style.Muted.Render("                              PATH"))
	}
	b.WriteString("\n")

	maxVisible := m.visibleRows()
	end := m.scroll + maxVisible
	if end > total {
		end = total
	}

	// Scroll-up indicator
	if m.scroll > 0 {
		b.WriteString(style.Muted.Render("      ... more above"))
		b.WriteString("\n")
	}

	for i := m.scroll; i < end; i++ {
		e := m.entries[i]

		// Cursor
		cursor := "  "
		if m.cursor == i {
			cursor = style.Cursor.Render("> ")
		}

		// Bundled checkbox
		checkbox := style.Checkbox(e.Bundled)

		// Name
		name := e.Name
		if len(name) > nameW-1 {
			name = name[:nameW-4] + "..."
		}
		if m.cursor == i {
			name = style.Selected.Render(fmt.Sprintf("%-*s", nameW, name))
		} else {
			name = fmt.Sprintf("%-*s", nameW, name)
		}

		// Type badge
		typeBadge := style.Muted.Render(fmt.Sprintf("%-*s", typeW, string(e.Type)))

		// Source column
		var source string
		if m.cursor == i && m.mode == modeEdit {
			source = m.input.View()
		} else if e.Bundled {
			source = style.Muted.Render("bundled")
		} else if e.URL != "" {
			urlDisplay := e.URL
			maxURLW := m.width - 2 - 4 - nameW - typeW - 4
			if showPath {
				maxURLW -= 34
			}
			if maxURLW < 10 {
				maxURLW = 10
			}
			if len(urlDisplay) > maxURLW {
				urlDisplay = urlDisplay[:maxURLW-3] + "..."
			}
			source = style.Subtitle.Render(urlDisplay)
		} else {
			source = style.Muted.Render("—")
		}

		b.WriteString(fmt.Sprintf("%s%s %s %s %s", cursor, checkbox, name, typeBadge, source))

		// Path column
		if showPath {
			pathStr := e.Path
			padding := ""
			// Rough alignment
			if !e.Bundled && e.URL == "" {
				padding = "  "
			}
			b.WriteString(padding)
			b.WriteString("  ")
			b.WriteString(style.Muted.Render(pathStr))
		}

		b.WriteString("\n")
	}

	// Scroll-down indicator
	if end < total {
		b.WriteString(style.Muted.Render("      ... more below"))
		b.WriteString("\n")
	}

	// Status bar
	b.WriteString("\n")
	skillCount := 0
	agentCount := 0
	urlCount := 0
	for _, e := range m.entries {
		if e.Type == srcs.TypeSkill {
			skillCount++
		} else {
			agentCount++
		}
		if e.URL != "" {
			urlCount++
		}
	}
	status := fmt.Sprintf("  (%d skills · %d agents)  ·  %d with URLs", skillCount, agentCount, urlCount)
	b.WriteString(style.Muted.Render(status))

	if m.dirty {
		b.WriteString("  ")
		b.WriteString(style.Error.Render("[unsaved changes]"))
	} else if m.saved {
		b.WriteString("  ")
		b.WriteString(style.Success.Render("saved"))
	}
	if m.saveErr != nil {
		b.WriteString("  ")
		b.WriteString(style.Error.Render(fmt.Sprintf("save error: %v", m.saveErr)))
	}

	// Help bar
	b.WriteString("\n\n")
	if m.mode == modeEdit {
		b.WriteString(style.HelpKey.Render("enter"))
		b.WriteString(style.HelpDesc.Render(" save URL  "))
		b.WriteString(style.HelpKey.Render("esc"))
		b.WriteString(style.HelpDesc.Render(" cancel"))
	} else {
		b.WriteString(style.HelpKey.Render("space"))
		b.WriteString(style.HelpDesc.Render(" toggle bundled  "))
		b.WriteString(style.HelpKey.Render("enter"))
		b.WriteString(style.HelpDesc.Render(" edit URL  "))
		b.WriteString(style.HelpKey.Render("ctrl+s"))
		b.WriteString(style.HelpDesc.Render(" save  "))
		b.WriteString(style.HelpKey.Render("esc"))
		b.WriteString(style.HelpDesc.Render(" back"))
	}

	return b.String()
}
