package collector

import (
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type hashCacheEntry struct {
	hash    string
	size    int64
	modTime time.Time
}

var (
	hashCache   = make(map[string]hashCacheEntry)
	hashCacheMu sync.RWMutex
)

// CalculateFileSHA256 вычисляет контрольную сумму SHA-256 файла с кэшированием по времени модификации и размеру
func CalculateFileSHA256(filePath string) (string, error) {
	if filePath == "" {
		return "", os.ErrNotExist
	}

	fi, err := os.Stat(filePath)
	if err != nil {
		return "", err
	}

	if fi.IsDir() {
		return "", os.ErrInvalid
	}

	cleanPath := filepath.Clean(filePath)

	hashCacheMu.RLock()
	cached, ok := hashCache[cleanPath]
	hashCacheMu.RUnlock()

	if ok && cached.size == fi.Size() && cached.modTime.Equal(fi.ModTime()) {
		return cached.hash, nil
	}

	f, err := os.Open(cleanPath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}

	hashStr := hex.EncodeToString(h.Sum(nil))

	hashCacheMu.Lock()
	hashCache[cleanPath] = hashCacheEntry{
		hash:    hashStr,
		size:    fi.Size(),
		modTime: fi.ModTime(),
	}
	hashCacheMu.Unlock()

	return hashStr, nil
}

// FindMainExecutable ищет главный исполняемый файл (.exe) в каталоге установки ПО
func FindMainExecutable(installLoc, displayName string) string {
	if installLoc == "" {
		return ""
	}

	fi, err := os.Stat(installLoc)
	if err != nil {
		return ""
	}

	// Если installLoc уже указывает на файл
	if !fi.IsDir() {
		ext := strings.ToLower(filepath.Ext(installLoc))
		if ext == ".exe" || ext == "" {
			return installLoc
		}
		return ""
	}

	// Ищем исполняемые файлы в корне и подпапках первого уровня
	var candidates []string
	cleanName := strings.ToLower(strings.ReplaceAll(displayName, " ", ""))

	entries, err := os.ReadDir(installLoc)
	if err != nil {
		return ""
	}

	for _, entry := range entries {
		name := entry.Name()
		if entry.IsDir() {
			// Проверяем популярные поддиректории: bin, app, application
			lowDir := strings.ToLower(name)
			if lowDir == "bin" || lowDir == "application" || lowDir == "app" {
				subEntries, err := os.ReadDir(filepath.Join(installLoc, name))
				if err == nil {
					for _, sub := range subEntries {
						if !sub.IsDir() && strings.ToLower(filepath.Ext(sub.Name())) == ".exe" {
							candidates = append(candidates, filepath.Join(installLoc, name, sub.Name()))
						}
					}
				}
			}
			continue
		}

		if strings.ToLower(filepath.Ext(name)) == ".exe" {
			candidates = append(candidates, filepath.Join(installLoc, name))
		}
	}

	if len(candidates) == 0 {
		return ""
	}

	// Сначала ищем точное совпадение по имени или очищенному DisplayName
	for _, cand := range candidates {
		base := strings.ToLower(strings.TrimSuffix(filepath.Base(cand), filepath.Ext(cand)))
		baseClean := strings.ReplaceAll(base, " ", "")
		if strings.Contains(cleanName, baseClean) || strings.Contains(baseClean, cleanName) {
			return cand
		}
	}

	// Отсеиваем uninstall / setup / helper / crash / update утилиты
	for _, cand := range candidates {
		base := strings.ToLower(filepath.Base(cand))
		if strings.Contains(base, "unins") ||
			strings.Contains(base, "setup") ||
			strings.Contains(base, "install") ||
			strings.Contains(base, "update") ||
			strings.Contains(base, "crash") ||
			strings.Contains(base, "helper") {
			continue
		}
		return cand
	}

	return candidates[0]
}
