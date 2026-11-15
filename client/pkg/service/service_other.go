//go:build !windows

package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)

// InstallService создает systemd unit для Linux
func InstallService(exePath string) error {
	if exePath == "" {
		p, err := os.Executable()
		if err != nil {
			return err
		}
		exePath = p
	}
	absPath, _ := filepath.Abs(exePath)

	unitContent := fmt.Sprintf(`[Unit]
Description=%s
After=network.target

[Service]
Type=simple
ExecStart=%s -daemon
Restart=always
RestartSec=5
WorkingDirectory=%s

[Install]
WantedBy=multi-user.target
`, ServiceDescription, absPath, filepath.Dir(absPath))

	unitPath := "/etc/systemd/system/sam-agent.service"
	if err := os.WriteFile(unitPath, []byte(unitContent), 0644); err != nil {
		return fmt.Errorf("failed to write %s (run as root / sudo): %w", unitPath, err)
	}

	_ = exec.Command("systemctl", "daemon-reload").Run()
	_ = exec.Command("systemctl", "enable", "sam-agent").Run()
	return nil
}

// UninstallService удаляет systemd unit
func UninstallService() error {
	_ = exec.Command("systemctl", "stop", "sam-agent").Run()
	_ = exec.Command("systemctl", "disable", "sam-agent").Run()
	_ = os.Remove("/etc/systemd/system/sam-agent.service")
	_ = exec.Command("systemctl", "daemon-reload").Run()
	return nil
}

// StartService запускает службу через systemctl
func StartService() error {
	cmd := exec.Command("systemctl", "start", "sam-agent")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("systemctl start failed: %v (%s)", err, string(out))
	}
	return nil
}

// StopService останавливает службу через systemctl
func StopService() error {
	cmd := exec.Command("systemctl", "stop", "sam-agent")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("systemctl stop failed: %v (%s)", err, string(out))
	}
	return nil
}

// RunService запускает агент с обработкой сигналов POSIX
func RunService(runDaemonFunc func(ctx context.Context) error) error {
	return RunWithGracefulShutdown(runDaemonFunc)
}
