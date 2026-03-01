package style

import "github.com/charmbracelet/lipgloss"

var (
	Gold   = lipgloss.Color("#FFD700")
	Green  = lipgloss.Color("#00FF00")
	Red    = lipgloss.Color("#FF4444")
	Gray   = lipgloss.Color("#888888")
	White  = lipgloss.Color("#FFFFFF")
	Cyan   = lipgloss.Color("#00CCCC")
	Yellow = lipgloss.Color("#FFCC00")

	Title = lipgloss.NewStyle().
		Bold(true).
		Foreground(Gold).
		MarginBottom(1)

	Subtitle = lipgloss.NewStyle().
			Foreground(Cyan).
			Bold(true)

	Success = lipgloss.NewStyle().
		Foreground(Green)

	Error = lipgloss.NewStyle().
		Foreground(Red)

	Muted = lipgloss.NewStyle().
		Foreground(Gray)

	Selected = lipgloss.NewStyle().
			Foreground(Gold).
			Bold(true)

	Cursor = lipgloss.NewStyle().
		Foreground(Yellow).
		Bold(true)

	Box = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(Gold).
		Padding(1, 2)

	HelpKey = lipgloss.NewStyle().
		Foreground(Cyan).
		Bold(true)

	HelpDesc = lipgloss.NewStyle().
			Foreground(Gray)
)

func Checkbox(checked bool) string {
	if checked {
		return Success.Render("[x]")
	}
	return Muted.Render("[ ]")
}

func StatusIcon(success bool) string {
	if success {
		return Success.Render("[ok]")
	}
	return Error.Render("[FAIL]")
}

func VerifyIcon(exists bool) string {
	if exists {
		return Success.Render(" ok ")
	}
	return Error.Render(" XX ")
}
