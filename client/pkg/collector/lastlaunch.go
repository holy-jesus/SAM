package collector

import (
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

var (
	launchHistoryMu sync.RWMutex
	launchHistory   = make(map[string]time.Time) // lower(exePath) -> timestamp

	prefetchMu    sync.RWMutex
	prefetchCache map[string]time.Time // lower(baseName) -> modTime
	prefetchInit  bool
)

// RecordProcessExecution фиксирует факт запуска процесса в реальном времени
func RecordProcessExecution(exePath string, launchTime time.Time) {
	if exePath == "" {
		return
	}
	clean := strings.ToLower(filepath.Clean(exePath))
	launchHistoryMu.Lock()
	launchHistory[clean] = launchTime
	launchHistoryMu.Unlock()
}

// GetLastLaunchedTime возвращает предположительное время последнего запуска программы
func GetLastLaunchedTime(exePath string, isRunning bool) *time.Time {
	now := time.Now().UTC()
	if isRunning {
		return &now
	}

	if exePath == "" {
		return nil
	}

	clean := strings.ToLower(filepath.Clean(exePath))

	// 1. Проверяем историю запусков агента в реальном времени
	launchHistoryMu.RLock()
	if t, ok := launchHistory[clean]; ok {
		launchHistoryMu.RUnlock()
		return &t
	}
	launchHistoryMu.RUnlock()

	// 2. Проверяем Windows Prefetch файлы (если система Windows и каталог доступен)
	base := strings.ToLower(filepath.Base(exePath))
	if t := lookupPrefetchTime(base); t != nil {
		return t
	}

	// 3. Фолбэк: время модификации файла
	if fi, err := os.Stat(exePath); err == nil {
		t := fi.ModTime().UTC()
		return &t
	}

	return nil
}

func lookupPrefetchTime(exeBaseName string) *time.Time {
	prefetchMu.Lock()
	if !prefetchInit {
		prefetchCache = make(map[string]time.Time)
		prefetchDir := filepath.Join(os.Getenv("SystemRoot"), "Prefetch")
		if prefetchDir == "Prefetch" {
			prefetchDir = `C:\Windows\Prefetch`
		}

		if entries, err := os.ReadDir(prefetchDir); err == nil {
			for _, entry := range entries {
				if entry.IsDir() || !strings.HasSuffix(strings.ToLower(entry.Name()), ".pf") {
					continue
				}
				name := strings.ToLower(entry.Name())
				// Имя вида: CHROME.EXE-3298AB12.pf
				idx := strings.Index(name, ".exe-")
				if idx != -1 {
					baseName := name[:idx+4] // chrome.exe
					info, err := entry.Info()
					if err == nil {
						mod := info.ModTime().UTC()
						if existing, ok := prefetchCache[baseName]; !ok || mod.After(existing) {
							prefetchCache[baseName] = mod
						}
					}
				}
			}
		}
		prefetchInit = true
	}
	prefetchMu.Unlock()

	prefetchMu.RLock()
	defer prefetchMu.RUnlock()
	if t, ok := prefetchCache[exeBaseName]; ok {
		return &t
	}
	return nil
}

// ResetPrefetchCache сбрасывает кэш Prefetch для повторного чтения
func ResetPrefetchCache() {
	prefetchMu.Lock()
	prefetchInit = false
	prefetchCache = nil
	prefetchMu.Unlock()
}
