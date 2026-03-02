package sources

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const ManifestFile = "sources.json"
const Version = 1

type EntryType string

const (
	TypeSkill EntryType = "skill"
	TypeAgent EntryType = "agent"
)

type Entry struct {
	Name    string    `json:"name"`
	Type    EntryType `json:"type"`
	Path    string    `json:"path"`
	Bundled bool      `json:"bundled"`
	URL     string    `json:"url"`
}

type Manifest struct {
	Version int     `json:"version"`
	Entries []Entry `json:"entries"`
}

// ManifestPath returns the absolute path to sources.json given the repo root.
func ManifestPath(goldySrc string) string {
	return filepath.Join(goldySrc, ManifestFile)
}

// Load reads the manifest from disk. Returns an empty manifest if the file
// doesn't exist yet — the caller should then call Generate.
func Load(goldySrc string) (*Manifest, error) {
	path := ManifestPath(goldySrc)
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return &Manifest{Version: Version}, nil
	}
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

// Save writes the manifest to disk with indented JSON.
func Save(goldySrc string, m *Manifest) error {
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(ManifestPath(goldySrc), data, 0644)
}

// Generate scans the skills/ and agents/ directories under goldySrc and
// creates a Manifest with sensible defaults. Entries from existing are
// preserved (by name+type key) rather than overwritten.
func Generate(goldySrc string, existing []Entry) (*Manifest, error) {
	lookup := make(map[string]Entry)
	for _, e := range existing {
		lookup[string(e.Type)+":"+e.Name] = e
	}

	var entries []Entry

	// Scan skills/
	skillsDir := filepath.Join(goldySrc, "skills")
	if infos, err := os.ReadDir(skillsDir); err == nil {
		for _, info := range infos {
			if !info.IsDir() {
				continue
			}
			name := info.Name()
			key := string(TypeSkill) + ":" + name
			if ex, ok := lookup[key]; ok {
				entries = append(entries, ex)
				continue
			}
			entries = append(entries, defaultSkillEntry(name))
		}
	}

	// Scan agents/
	agentsDir := filepath.Join(goldySrc, "agents")
	if infos, err := os.ReadDir(agentsDir); err == nil {
		for _, info := range infos {
			if info.IsDir() || !strings.HasSuffix(info.Name(), ".md") {
				continue
			}
			name := strings.TrimSuffix(info.Name(), ".md")
			key := string(TypeAgent) + ":" + name
			if ex, ok := lookup[key]; ok {
				entries = append(entries, ex)
				continue
			}
			entries = append(entries, defaultAgentEntry(name))
		}
	}

	sort.Slice(entries, func(i, j int) bool {
		if entries[i].Type != entries[j].Type {
			return entries[i].Type < entries[j].Type // agents before skills
		}
		return entries[i].Name < entries[j].Name
	})

	return &Manifest{Version: Version, Entries: entries}, nil
}

// knownExternalSkills holds pre-seeded origins for known external items.
var knownExternalSkills = map[string]string{
	"antigravity-quota":  "",
	"self-improving-agent": "",
	"vercel-react-best-practices": "",
}

// seoSkillPrefixes marks SEO skills as external (from AgriciDaniel/claude-seo).
func isSEOSkill(name string) bool {
	return strings.HasPrefix(name, "seo") || name == "programmatic-seo"
}

func defaultSkillEntry(name string) Entry {
	_, isKnownExternal := knownExternalSkills[name]
	bundled := !isKnownExternal && !isSEOSkill(name)
	return Entry{
		Name:    name,
		Type:    TypeSkill,
		Path:    "skills/" + name,
		Bundled: bundled,
		URL:     "",
	}
}

func defaultAgentEntry(name string) Entry {
	return Entry{
		Name:    name,
		Type:    TypeAgent,
		Path:    "agents/" + name + ".md",
		Bundled: true,
		URL:     "",
	}
}
