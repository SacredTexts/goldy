package fileops

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
)

func MkdirAll(path string) error {
	return os.MkdirAll(path, 0755)
}

func Symlink(target, link string) error {
	if err := MkdirAll(filepath.Dir(link)); err != nil {
		return fmt.Errorf("mkdir for symlink %s: %w", link, err)
	}
	os.RemoveAll(link)
	if err := os.Symlink(target, link); err != nil {
		return fmt.Errorf("symlink %s -> %s: %w", link, target, err)
	}
	return nil
}

func CopyFile(src, dst string) error {
	if err := MkdirAll(filepath.Dir(dst)); err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("open %s: %w", src, err)
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("create %s: %w", dst, err)
	}
	defer out.Close()

	if _, err := io.Copy(out, in); err != nil {
		return fmt.Errorf("copy %s -> %s: %w", src, dst, err)
	}
	return nil
}

func CopyFileIfNotExists(src, dst string) error {
	if _, err := os.Stat(dst); err == nil {
		return nil // already exists, skip
	}
	return CopyFile(src, dst)
}

func CopyDir(src, dst string) error {
	return filepath.WalkDir(src, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(src, path)
		target := filepath.Join(dst, rel)

		if d.IsDir() {
			return MkdirAll(target)
		}
		if d.Name() == ".DS_Store" {
			return nil
		}
		return CopyFile(path, target)
	})
}

func WriteFile(path, content string) error {
	if err := MkdirAll(filepath.Dir(path)); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(content), 0644)
}

func Remove(path string) error {
	return os.RemoveAll(path)
}

func Exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func DirExists(path string) bool {
	fi, err := os.Stat(path)
	return err == nil && fi.IsDir()
}
