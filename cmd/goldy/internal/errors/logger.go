package errors

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type Logger struct {
	path string
	mu   sync.Mutex
}

func NewLogger(path string) *Logger {
	return &Logger{path: path}
}

func (l *Logger) Path() string {
	return l.path
}

func (l *Logger) Clear() {
	os.Remove(l.path)
}

func (l *Logger) Log(component, message string) {
	l.mu.Lock()
	defer l.mu.Unlock()

	timestamp := time.Now().Format("2006-01-02 15:04:05")
	entry := fmt.Sprintf("- **[%s]** `%s`: %s\n", timestamp, component, message)

	if err := os.MkdirAll(filepath.Dir(l.path), 0755); err != nil {
		fmt.Fprintf(os.Stderr, "  ERROR [%s]: %s\n", component, message)
		return
	}

	f, err := os.OpenFile(l.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "  ERROR [%s]: %s\n", component, message)
		return
	}
	defer f.Close()

	fi, _ := f.Stat()
	if fi.Size() == 0 {
		f.WriteString("# GOLDY Install Error Log\n\n")
	}
	f.WriteString(entry)

	fmt.Fprintf(os.Stderr, "  ERROR [%s]: %s\n", component, message)
}

func (l *Logger) ErrorCount() int {
	data, err := os.ReadFile(l.path)
	if err != nil {
		return 0
	}
	count := 0
	for _, b := range data {
		if b == '\n' {
			count++
		}
	}
	// Subtract header lines (2: title + blank)
	if count > 2 {
		return count - 2
	}
	return 0
}
