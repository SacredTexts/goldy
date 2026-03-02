package components

import (
	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"
)

const (
	IDCore        = "core"
	IDSkills      = "skills"
	IDAgents      = "agents"
	IDHooks       = "hooks"
	IDCommands    = "commands"
	IDGSD         = "gsd"
	IDClaudeMem   = "claude-mem"
	IDPlannotator = "plannotator"
)

type InstallFunc func(cfg *config.Paths, log *errs.Logger) shared.StepResult
type SubItemsFunc func(cfg *config.Paths) ([]shared.SubItem, error)
type FilteredInstallFunc func(cfg *config.Paths, log *errs.Logger, filter []string) shared.StepResult

type Component struct {
	ID              string
	MenuKey         string
	Name            string
	Description     string
	InfoText        string
	Install         InstallFunc
	Verify          func(cfg *config.Paths) []shared.VerifyCheck
	SubItems        SubItemsFunc        // nil = monolithic (no sub-item selection)
	InstallFiltered FilteredInstallFunc // nil = no filtering support
}

func All(cfg *config.Paths) []Component {
	return []Component{
		{ID: IDCore, MenuKey: "a", Name: "Core", Description: "Goldy skill, commands, hooks, plan template", InfoText: InfoCore, Install: InstallCore, Verify: VerifyCore},
		{ID: IDSkills, MenuKey: "b", Name: "Skills", Description: "31 custom skills (SEO, Frontend, Dev Tools, etc.)", InfoText: InfoSkills, Install: InstallSkills, Verify: VerifySkills, SubItems: ListSkills, InstallFiltered: InstallSkillsFiltered},
		{ID: IDAgents, MenuKey: "c", Name: "Agents", Description: "19 agent definitions (GSD, SEO, code review)", InfoText: InfoAgents, Install: InstallAgents, Verify: VerifyAgents, SubItems: ListAgents, InstallFiltered: InstallAgentsFiltered},
		{ID: IDHooks, MenuKey: "d", Name: "Extra Hooks", Description: "Notification, stop, GSD hooks, TTS utilities", InfoText: InfoHooks, Install: InstallHooks, Verify: VerifyHooks, SubItems: ListHooks, InstallFiltered: InstallHooksFiltered},
		{ID: IDCommands, MenuKey: "e", Name: "Extra Commands", Description: "/agent, /plannotator-review, /revise-claude-md, /global-update", InfoText: InfoCommands, Install: InstallCommands, Verify: VerifyCommands, SubItems: ListCommands, InstallFiltered: InstallCommandsFiltered},
		{ID: IDGSD, MenuKey: "f", Name: "GSD", Description: "Get-Shit-Done workflow (npm)", InfoText: InfoGSD, Install: InstallGSD},
		{ID: IDClaudeMem, MenuKey: "g", Name: "Claude-Mem", Description: "Team memory plugin", InfoText: InfoClaudeMem, Install: InstallClaudeMem},
		{ID: IDPlannotator, MenuKey: "h", Name: "Plannotator", Description: "Plan review UI plugin", InfoText: InfoPlannotator, Install: InstallPlannotator},
	}
}
