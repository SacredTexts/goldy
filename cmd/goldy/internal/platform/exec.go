package platform

import (
	"bytes"
	"fmt"
	"os/exec"
)

func RunCommand(name string, args ...string) error {
	cmd := exec.Command(name, args...)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s: %w (%s)", name, err, stderr.String())
	}
	return nil
}

func RunCommandInDir(dir, name string, args ...string) error {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s in %s: %w (%s)", name, dir, err, stderr.String())
	}
	return nil
}

func RunCommandOutput(dir, name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	if dir != "" {
		cmd.Dir = dir
	}
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return stdout.String(), fmt.Errorf("%s: %w (%s)", name, err, stderr.String())
	}
	return stdout.String(), nil
}

func CommandExists(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}
