package installer

import (
	"fmt"

	"github.com/SacredTexts/goldy/cmd/goldy/internal/components"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/config"
	errs "github.com/SacredTexts/goldy/cmd/goldy/internal/errors"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/platform"
	"github.com/SacredTexts/goldy/cmd/goldy/internal/shared"

	tea "github.com/charmbracelet/bubbletea"
)

type Orchestrator struct {
	cfg    *config.Paths
	logger *errs.Logger
}

func NewOrchestrator(cfg *config.Paths, logger *errs.Logger) *Orchestrator {
	return &Orchestrator{cfg: cfg, logger: logger}
}

func (o *Orchestrator) RunAsync(p *tea.Program, comps []components.Component) {
	o.logger.Clear()

	go func() {
		var results []shared.StepResult
		for i, comp := range comps {
			p.Send(shared.StepStartedMsg{ComponentID: comp.ID, Index: i})
			result := o.runStep(comp)
			results = append(results, result)
			p.Send(shared.StepCompletedMsg{Result: result})
		}
		p.Send(shared.AllStepsCompleteMsg{Results: results})
	}()
}

func (o *Orchestrator) RunSync(comps []components.Component) []shared.StepResult {
	o.logger.Clear()

	var results []shared.StepResult
	for _, comp := range comps {
		fmt.Printf("  Installing %s...\n", comp.Name)
		result := o.runStep(comp)
		results = append(results, result)
		if result.Success {
			fmt.Printf("    [ok] %s\n", result.Message)
		} else {
			fmt.Printf("    [FAIL] %s\n", result.Message)
		}
	}
	return results
}

func (o *Orchestrator) RunUpdate(comps []components.Component) []shared.StepResult {
	fmt.Println("  Updating goldy repo...")
	if err := platform.Pull(o.cfg.GoldySrc); err != nil {
		o.logger.Log("update/goldy", "git pull failed: "+err.Error())
		fmt.Printf("    [FAIL] goldy pull failed: %v\n", err)
	} else {
		fmt.Println("    [ok] goldy repo updated")
	}
	fmt.Println()
	return o.RunSync(comps)
}

func (o *Orchestrator) RunAsyncFiltered(p *tea.Program, comps []components.Component, filters map[string][]string) {
	o.logger.Clear()

	go func() {
		var results []shared.StepResult
		for i, comp := range comps {
			p.Send(shared.StepStartedMsg{ComponentID: comp.ID, Index: i})
			var result shared.StepResult
			if filter, ok := filters[comp.ID]; ok && comp.InstallFiltered != nil {
				result = o.runFilteredStep(comp, filter)
			} else {
				result = o.runStep(comp)
			}
			results = append(results, result)
			p.Send(shared.StepCompletedMsg{Result: result})
		}
		p.Send(shared.AllStepsCompleteMsg{Results: results})
	}()
}

func (o *Orchestrator) RunUpdateAsync(p *tea.Program, comps []components.Component) {
	o.logger.Clear()

	go func() {
		var results []shared.StepResult

		// Step 0: git pull
		p.Send(shared.StepStartedMsg{ComponentID: "update", Index: 0})
		pullResult := platform.PullWithResult(o.cfg.GoldySrc)
		var updateStepResult shared.StepResult
		if pullResult.Error != nil {
			o.logger.Log("update", "git pull failed: "+pullResult.Error.Error())
			updateStepResult = shared.StepResult{
				ComponentID: "update",
				Success:     false,
				Message:     "Pull failed: " + pullResult.Error.Error(),
				Error:       pullResult.Error,
			}
		} else {
			msg := "Already up to date"
			if pullResult.Updated {
				msg = "Updated: " + pullResult.Summary
			}
			updateStepResult = shared.StepResult{
				ComponentID: "update",
				Success:     true,
				Message:     msg,
			}
		}
		results = append(results, updateStepResult)
		p.Send(shared.StepCompletedMsg{Result: updateStepResult})

		// Steps 1-N: install each component
		for i, comp := range comps {
			p.Send(shared.StepStartedMsg{ComponentID: comp.ID, Index: i + 1})
			result := o.runStep(comp)
			results = append(results, result)
			p.Send(shared.StepCompletedMsg{Result: result})
		}
		p.Send(shared.AllStepsCompleteMsg{Results: results})
	}()
}

func (o *Orchestrator) runFilteredStep(comp components.Component, filter []string) (result shared.StepResult) {
	defer func() {
		if r := recover(); r != nil {
			o.logger.Log(comp.ID, fmt.Sprintf("panic: %v", r))
			result = shared.StepResult{
				ComponentID: comp.ID,
				Success:     false,
				Message:     fmt.Sprintf("panic: %v", r),
				Error:       fmt.Errorf("panic: %v", r),
			}
		}
	}()
	return comp.InstallFiltered(o.cfg, o.logger, filter)
}

func (o *Orchestrator) runStep(comp components.Component) (result shared.StepResult) {
	defer func() {
		if r := recover(); r != nil {
			o.logger.Log(comp.ID, fmt.Sprintf("panic: %v", r))
			result = shared.StepResult{
				ComponentID: comp.ID,
				Success:     false,
				Message:     fmt.Sprintf("panic: %v", r),
				Error:       fmt.Errorf("panic: %v", r),
			}
		}
	}()
	return comp.Install(o.cfg, o.logger)
}
