package shared

import "github.com/charmbracelet/bubbles/key"

// StepResult is the outcome of a component install
type StepResult struct {
	ComponentID string
	Success     bool
	Message     string
	Error       error
	ItemCount   int
}

// VerifyCheck is a single file-existence check
type VerifyCheck struct {
	Label  string
	Path   string
	Exists bool
}

// Messages for screen transitions
type ShowInfoMsg struct{}
type ReturnToMenuMsg struct{}
type QuitMsg struct{}

// Messages for install flow
type StepStartedMsg struct {
	ComponentID string
	Index       int
}

type StepCompletedMsg struct {
	Result StepResult
}

type AllStepsCompleteMsg struct {
	Results []StepResult
}

// Key bindings
type KeyMap struct {
	Quit key.Binding
	Back key.Binding
}

var Keys = KeyMap{
	Quit: key.NewBinding(
		key.WithKeys("q", "ctrl+c"),
		key.WithHelp("q", "quit"),
	),
	Back: key.NewBinding(
		key.WithKeys("esc"),
		key.WithHelp("esc", "back"),
	),
}
