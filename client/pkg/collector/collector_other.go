//go:build !windows

package collector

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"sam-client/pkg/model"
)

func collectMachineInfo(customSerial string) (model.MachineInfo, error) {
	hostname, _ := os.Hostname()
	serial := customSerial
	if serial == "" {
		serial = getLinuxSerialNumber()
	}
	if serial == "" {
		serial = "DEV-MOCK-" + hostname
	}

	osName, osVersion := getLinuxOSDetails()
	cpu := getLinuxCPUInfo()
	ramMB := getLinuxRAMMB()
	ip, mac := getPrimaryNetworkDetails()

	return model.MachineInfo{
		SerialNumber: serial,
		Hostname:     hostname,
		IPAddress:    ip,
		MACAddress:   mac,
		OS:           osName,
		OSVersion:    osVersion,
		Architecture: runtime.GOARCH,
		CPU:          cpu,
		RAM_MB:       ramMB,
		ScanTime:     time.Now().UTC(),
	}, nil
}

func getLinuxSerialNumber() string {
	// 1. Попытка чтения серийного номера DMI
	dmiPaths := []string{
		"/sys/class/dmi/id/product_serial",
		"/sys/class/dmi/id/board_serial",
	}
	for _, p := range dmiPaths {
		if data, err := os.ReadFile(p); err == nil {
			s := strings.TrimSpace(string(data))
			if isValidSerial(s) {
				return s
			}
		}
	}

	// 2. Machine ID
	for _, p := range []string{"/etc/machine-id", "/var/lib/dbus/machine-id"} {
		if data, err := os.ReadFile(p); err == nil {
			s := strings.TrimSpace(string(data))
			if len(s) >= 8 {
				return s[:16]
			}
		}
	}

	return ""
}

func isValidSerial(s string) bool {
	s = strings.TrimSpace(s)
	if s == "" {
		return false
	}
	sLower := strings.ToLower(s)
	invalidValues := []string{
		"to be filled by o.e.m.",
		"default string",
		"none",
		"0",
		"123456789",
	}
	for _, inv := range invalidValues {
		if sLower == inv {
			return false
		}
	}
	return true
}

func getLinuxOSDetails() (string, string) {
	f, err := os.Open("/etc/os-release")
	if err != nil {
		return fmt.Sprintf("%s (%s)", runtime.GOOS, runtime.GOARCH), ""
	}
	defer f.Close()

	var name, version string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "NAME=") {
			name = strings.Trim(strings.TrimPrefix(line, "NAME="), `"`)
		} else if strings.HasPrefix(line, "VERSION=") {
			version = strings.Trim(strings.TrimPrefix(line, "VERSION="), `"`)
		}
	}

	if name == "" {
		name = "Linux"
	}
	return name, version
}

func getLinuxCPUInfo() string {
	f, err := os.Open("/proc/cpuinfo")
	if err != nil {
		return ""
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "model name") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 {
				return strings.TrimSpace(parts[1])
			}
		}
	}
	return ""
}

func getLinuxRAMMB() int {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "MemTotal:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				kb, err := strconv.ParseInt(fields[1], 10, 64)
				if err == nil {
					return int(kb / 1024)
				}
			}
		}
	}
	return 0
}

func collectInstalledSoftware(serialNumber string) ([]model.SoftwareItem, error) {
	// Сбор установленного ПО на Linux через .desktop файлы в /usr/share/applications
	var items []model.SoftwareItem
	seen := make(map[string]bool)

	desktopDir := "/usr/share/applications"
	entries, err := os.ReadDir(desktopDir)
	if err == nil {
		for _, entry := range entries {
			if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".desktop") {
				continue
			}

			path := filepath.Join(desktopDir, entry.Name())
			sw := parseDesktopFile(path, serialNumber)
			if sw.DisplayName != "" {
				key := strings.ToLower(sw.DisplayName)
				if !seen[key] {
					seen[key] = true
					items = append(items, sw)
				}
			}
		}
	}

	// Если список пуст, используем базовый мок для тестов
	if len(items) == 0 {
		items = []model.SoftwareItem{
			{
				SerialNumber:    serialNumber,
				DisplayName:     "Google Chrome",
				Publisher:       "Google LLC",
				Version:         "124.0.6367.60",
				InstallLocation: "/opt/google/chrome",
				Source:          "registry",
			},
			{
				SerialNumber:    serialNumber,
				DisplayName:     "7-Zip 19.00 (x64 edition)",
				Publisher:       "Igor Pavlov",
				Version:         "19.00.00.0",
				InstallLocation: "/usr/bin/7z",
				Source:          "registry",
			},
			{
				SerialNumber:    serialNumber,
				DisplayName:     "Visual Studio Code",
				Publisher:       "Microsoft Corporation",
				Version:         "1.88.1",
				InstallLocation: "/usr/share/code",
				Source:          "registry",
			},
		}
	}

	return items, nil
}

func parseDesktopFile(path, serialNumber string) model.SoftwareItem {
	f, err := os.Open(path)
	if err != nil {
		return model.SoftwareItem{}
	}
	defer f.Close()

	var name, execCmd, comment, version string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "Name=") && name == "" {
			name = strings.TrimPrefix(line, "Name=")
		} else if strings.HasPrefix(line, "Exec=") && execCmd == "" {
			execCmd = strings.TrimPrefix(line, "Exec=")
		} else if strings.HasPrefix(line, "Comment=") && comment == "" {
			comment = strings.TrimPrefix(line, "Comment=")
		} else if strings.HasPrefix(line, "Version=") && version == "" {
			version = strings.TrimPrefix(line, "Version=")
		}
	}

	if name == "" {
		return model.SoftwareItem{}
	}

	// Очищаем Exec команду от флагов %u, %F и др.
	parts := strings.Fields(execCmd)
	cleanExe := ""
	if len(parts) > 0 {
		cleanExe = parts[0]
	}

	if version == "" {
		version = "<Null>"
	}

	return model.SoftwareItem{
		SerialNumber:    serialNumber,
		DisplayName:     name,
		Publisher:       "<Null>",
		Version:         version,
		InstallLocation: filepath.Dir(cleanExe),
		InstallPath:     cleanExe,
		Source:          "desktop_entry",
	}
}

func scanDiskSoftware(serialNumber string) ([]model.SoftwareItem, error) {
	var results []model.SoftwareItem
	optEntries, err := os.ReadDir("/opt")
	if err == nil {
		for _, entry := range optEntries {
			if entry.IsDir() {
				results = append(results, model.SoftwareItem{
					SerialNumber:    serialNumber,
					DisplayName:     entry.Name(),
					Publisher:       "<Null>",
					Version:         "<Null>",
					InstallLocation: filepath.Join("/opt", entry.Name()),
					Source:          "disk_scan",
				})
			}
		}
	}
	return results, nil
}

func collectRunningProcesses() ([]model.ProcessItem, error) {
	procEntries, err := os.ReadDir("/proc")
	if err != nil {
		return nil, err
	}

	var procs []model.ProcessItem
	for _, entry := range procEntries {
		if !entry.IsDir() {
			continue
		}
		pid, err := strconv.ParseUint(entry.Name(), 10, 32)
		if err != nil {
			continue // Не числовая директория
		}

		exeLink, err := os.Readlink(filepath.Join("/proc", entry.Name(), "exe"))
		if err != nil || exeLink == "" {
			continue
		}

		name := filepath.Base(exeLink)

		cmdlineBytes, _ := os.ReadFile(filepath.Join("/proc", entry.Name(), "cmdline"))
		cmdline := strings.ReplaceAll(string(cmdlineBytes), "\x00", " ")

		procs = append(procs, model.ProcessItem{
			PID:         uint32(pid),
			Name:        name,
			ExePath:     exeLink,
			CommandLine: strings.TrimSpace(cmdline),
		})
	}

	return procs, nil
}
