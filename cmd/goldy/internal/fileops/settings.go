package fileops

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func RegisterPreToolUseHook(claudeRoot, hooksDir string) error {
	settingsPath := filepath.Join(claudeRoot, "settings.json")
	hookCommand := fmt.Sprintf("python3 %s/pre_tool_use.py", hooksDir)

	var settings map[string]interface{}
	data, err := os.ReadFile(settingsPath)
	if err != nil {
		settings = make(map[string]interface{})
	} else {
		if err := json.Unmarshal(data, &settings); err != nil {
			settings = make(map[string]interface{})
		}
	}

	// Check if hook already registered
	if hookAlreadyRegistered(settings, "pre_tool_use.py") {
		return nil
	}

	hooks, _ := settings["hooks"].(map[string]interface{})
	if hooks == nil {
		hooks = make(map[string]interface{})
		settings["hooks"] = hooks
	}

	preToolUse, _ := hooks["PreToolUse"].([]interface{})

	newEntry := map[string]interface{}{
		"matcher": "",
		"hooks": []interface{}{
			map[string]interface{}{
				"type":    "command",
				"command": hookCommand,
			},
		},
	}

	preToolUse = append(preToolUse, newEntry)
	hooks["PreToolUse"] = preToolUse

	out, err := json.MarshalIndent(settings, "", "    ")
	if err != nil {
		return fmt.Errorf("marshal settings.json: %w", err)
	}
	return os.WriteFile(settingsPath, out, 0644)
}

func hookAlreadyRegistered(settings map[string]interface{}, marker string) bool {
	hooks, _ := settings["hooks"].(map[string]interface{})
	if hooks == nil {
		return false
	}
	preToolUse, _ := hooks["PreToolUse"].([]interface{})
	for _, entry := range preToolUse {
		entryMap, _ := entry.(map[string]interface{})
		if entryMap == nil {
			continue
		}
		hookList, _ := entryMap["hooks"].([]interface{})
		for _, h := range hookList {
			hMap, _ := h.(map[string]interface{})
			if hMap == nil {
				continue
			}
			cmd, _ := hMap["command"].(string)
			if strings.Contains(cmd, marker) {
				return true
			}
		}
	}
	return false
}
