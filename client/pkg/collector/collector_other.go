//go:build !windows

package collector

import (
	"fmt"
	"os"
	"runtime"
	"time"

	"sam-client/pkg/model"
)

func collectMachineInfo(customSerial string) (model.MachineInfo, error) {
	hostname, _ := os.Hostname()
	serial := customSerial
	if serial == "" {
		serial = "DEV-MOCK-" + hostname
	}

	return model.MachineInfo{
		SerialNumber: serial,
		Hostname:     hostname,
		OS:           fmt.Sprintf("%s (%s)", runtime.GOOS, runtime.GOARCH),
		Architecture: runtime.GOARCH,
		ScanTime:     time.Now().UTC(),
	}, nil
}

func collectInstalledSoftware(serialNumber string) ([]model.SoftwareItem, error) {
	// Заглушка для сборки и локального тестирования на Linux/macOS
	return []model.SoftwareItem{
		{
			SerialNumber:    serialNumber,
			DisplayName:     "Google Chrome",
			Publisher:       "Google LLC",
			Version:         "124.0.6367.60",
			InstallLocation: "/opt/google/chrome",
		},
		{
			SerialNumber:    serialNumber,
			DisplayName:     "7-Zip 19.00 (x64 edition)",
			Publisher:       "Igor Pavlov",
			Version:         "19.00.00.0",
			InstallLocation: "/usr/bin/7z",
		},
		{
			SerialNumber:    serialNumber,
			DisplayName:     "Visual Studio Code",
			Publisher:       "Microsoft Corporation",
			Version:         "1.88.1",
			InstallLocation: "/usr/share/code",
		},
	}, nil
}

func collectRunningProcesses() ([]model.ProcessItem, error) {
	// Заглушка для сборки и локального тестирования на Linux/macOS
	return []model.ProcessItem{
		{
			PID:             1001,
			Name:            "chrome",
			ExePath:         "/opt/google/chrome/chrome",
			ProductName:     "Google Chrome",
			CompanyName:     "Google LLC",
			FileDescription: "Google Chrome",
			FileVersion:     "124.0.6367.60",
		},
		{
			PID:             1002,
			Name:            "code",
			ExePath:         "/usr/share/code/code",
			ProductName:     "Visual Studio Code",
			CompanyName:     "Microsoft Corporation",
			FileDescription: "Visual Studio Code",
			FileVersion:     "1.88.1",
		},
	}, nil
}
