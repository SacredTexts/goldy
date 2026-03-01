package platform

import (
	"os"
	"runtime"
	"strings"
)

type OS int

const (
	MacOS OS = iota
	Linux
	WSL2
	Unknown
)

func (o OS) String() string {
	switch o {
	case MacOS:
		return "macOS"
	case Linux:
		return "Linux"
	case WSL2:
		return "WSL2"
	default:
		return "Unknown"
	}
}

func Detect() OS {
	switch runtime.GOOS {
	case "darwin":
		return MacOS
	case "linux":
		data, err := os.ReadFile("/proc/version")
		if err == nil && strings.Contains(strings.ToLower(string(data)), "microsoft") {
			return WSL2
		}
		return Linux
	default:
		return Unknown
	}
}
