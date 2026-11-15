package service

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"syscall"
)

const (
	ServiceName        = "SAMAgent"
	ServiceDisplayName = "SAM Asset Management Agent"
	ServiceDescription = "Software Asset Management (SAM) background monitoring and inventory collection agent"
)

// HandleServiceCommand обрабатывает команды управления службой (install, uninstall, start, stop, run)
func HandleServiceCommand(action string, exePath string, runDaemonFunc func(ctx context.Context) error) error {
	switch action {
	case "install":
		return InstallService(exePath)
	case "uninstall":
		return UninstallService()
	case "start":
		return StartService()
	case "stop":
		return StopService()
	case "run":
		return RunService(runDaemonFunc)
	default:
		return fmt.Errorf("unknown service action: %s (available: install, uninstall, start, stop, run)", action)
	}
}

// RunWithGracefulShutdown запускает функцию в текущем процессе с перехватом сигналов остановки
func RunWithGracefulShutdown(runFunc func(ctx context.Context) error) error {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	errChan := make(chan error, 1)
	go func() {
		errChan <- runFunc(ctx)
	}()

	select {
	case <-sigChan:
		cancel()
		return <-errChan
	case err := <-errChan:
		return err
	}
}
