//go:build windows

package service

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"
	"unsafe"
)

var (
	modadvapi32Service = syscall.NewLazyDLL("advapi32.dll")

	procStartServiceCtrlDispatcherW = modadvapi32Service.NewProc("StartServiceCtrlDispatcherW")
	procRegisterServiceCtrlHandlerW = modadvapi32Service.NewProc("RegisterServiceCtrlHandlerExW")
	procSetServiceStatus            = modadvapi32Service.NewProc("SetServiceStatus")
)

type serviceTableEntry struct {
	ServiceName *uint16
	ServiceProc uintptr
}

type serviceStatus struct {
	ServiceType             uint32
	CurrentState            uint32
	ControlsAccepted        uint32
	Win32ExitCode           uint32
	ServiceSpecificExitCode uint32
	CheckPoint              uint32
	WaitHint                uint32
}

const (
	serviceWin32OwnProcess = 0x00000010
	serviceStartPending    = 0x00000002
	serviceRunning         = 0x00000004
	serviceStopPending     = 0x00000003
	serviceStopped         = 0x00000001

	serviceAcceptStop     = 0x00000001
	serviceAcceptShutdown = 0x00000004

	serviceControlStop     = 0x00000001
	serviceControlShutdown = 0x00000005
)

var (
	globalStatusHandle uintptr
	globalCancelFunc   context.CancelFunc
)

// InstallService регистрирует агент как системную службу Windows
func InstallService(exePath string) error {
	if exePath == "" {
		p, err := os.Executable()
		if err != nil {
			return err
		}
		exePath = p
	}
	absPath, _ := filepath.Abs(exePath)
	binPath := fmt.Sprintf("\"%s\" -daemon", absPath)

	cmd := exec.Command("sc.exe", "create", ServiceName,
		"binPath=", binPath,
		"start=", "auto",
		"DisplayName=", ServiceDisplayName,
	)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to create service: %v (%s)", err, string(out))
	}

	// Установка описания службы
	_ = exec.Command("sc.exe", "description", ServiceName, ServiceDescription).Run()

	// Настройка политики автоперезапуска при сбое
	_ = exec.Command("sc.exe", "failure", ServiceName, "reset=", "86400", "actions=", "restart/5000/restart/10000/restart/60000").Run()

	return nil
}

// UninstallService удаляет системную службу Windows
func UninstallService() error {
	// Сначала останавливаем, если запущена
	_ = StopService()
	time.Sleep(1 * time.Second)

	cmd := exec.Command("sc.exe", "delete", ServiceName)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to delete service: %v (%s)", err, string(out))
	}
	return nil
}

// StartService запускает системную службу Windows
func StartService() error {
	cmd := exec.Command("sc.exe", "start", ServiceName)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to start service: %v (%s)", err, string(out))
	}
	return nil
}

// StopService останавливает системную службу Windows
func StopService() error {
	cmd := exec.Command("sc.exe", "stop", ServiceName)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to stop service: %v (%s)", err, string(out))
	}
	return nil
}

// RunService запускает цикл обслуживания диспетчера служб Windows
func RunService(runDaemonFunc func(ctx context.Context) error) error {
	// Попытка запуска через диспетчер служб Windows (StartServiceCtrlDispatcher)
	serviceNamePtr, _ := syscall.UTF16PtrFromString(ServiceName)
	entry := serviceTableEntry{
		ServiceName: serviceNamePtr,
		ServiceProc: syscall.NewCallback(func(argc uint32, argv **uint16) uintptr {
			handlerCallback := syscall.NewCallback(func(control uint32, eventType uint32, eventData uintptr, context uintptr) uintptr {
				switch control {
				case serviceControlStop, serviceControlShutdown:
					setWindowsServiceStatus(serviceStopPending, 0)
					if globalCancelFunc != nil {
						globalCancelFunc()
					}
					return 0
				}
				return 0
			})

			rHandle, _, _ := procRegisterServiceCtrlHandlerW.Call(
				uintptr(unsafe.Pointer(serviceNamePtr)),
				handlerCallback,
				0,
			)
			globalStatusHandle = rHandle

			setWindowsServiceStatus(serviceStartPending, 3000)

			ctx, cancel := context.WithCancel(context.Background())
			globalCancelFunc = cancel

			setWindowsServiceStatus(serviceRunning, 0)

			err := runDaemonFunc(ctx)

			setWindowsServiceStatus(serviceStopped, 0)
			if err != nil {
				return 1
			}
			return 0
		}),
	}

	table := []serviceTableEntry{
		entry,
		{ServiceName: nil, ServiceProc: 0},
	}

	r0, _, err := procStartServiceCtrlDispatcherW.Call(uintptr(unsafe.Pointer(&table[0])))
	if r0 == 0 {
		// Ошибка 1063: ERROR_FAILED_SERVICE_CONTROLLER_CONNECT
		// Это означает, что процесс запущен интерактивно из консоли, а не через Service Manager
		return RunWithGracefulShutdown(runDaemonFunc)
	}

	return err
}

func setWindowsServiceStatus(state uint32, waitHint uint32) {
	if globalStatusHandle == 0 {
		return
	}
	st := serviceStatus{
		ServiceType:      serviceWin32OwnProcess,
		CurrentState:     state,
		ControlsAccepted: serviceAcceptStop | serviceAcceptShutdown,
		WaitHint:         waitHint,
	}
	_, _, _ = procSetServiceStatus.Call(globalStatusHandle, uintptr(unsafe.Pointer(&st)))
}
