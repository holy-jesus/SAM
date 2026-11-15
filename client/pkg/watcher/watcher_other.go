//go:build !windows

package watcher

import (
	"context"
	"os"
	"time"
)

func startPlatformRegistryWatcher(ctx context.Context, onChange func()) {
	// Для Linux/macOS отслеживаем изменения в каталоге /usr/share/applications
	targetDir := "/usr/share/applications"
	var lastMod time.Time

	if fi, err := os.Stat(targetDir); err == nil {
		lastMod = fi.ModTime()
	}

	ticker := time.NewTicker(4 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if fi, err := os.Stat(targetDir); err == nil {
				if fi.ModTime().After(lastMod) {
					lastMod = fi.ModTime()
					onChange()
				}
			}
		}
	}
}
