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
	Group  string // component name for grouped display
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

// SubItem is one selectable item within a component (e.g., one skill)
type SubItem struct {
	Name     string
	Selected bool
}

// Startup screen messages
type StartupCompleteMsg struct {
	Updated bool
	Summary string
	Error   error
}

type StartupDoneMsg struct{}

// Picker screen messages
type OpenPickerMsg struct {
	ComponentID   string
	ComponentName string
	Items         []SubItem
}

type PickerDoneMsg struct {
	ComponentID string
	Items       []SubItem
}

// Update / Install All
type StartUpdateAllMsg struct{}

// Sources screen
type OpenSourcesMsg struct{}

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
