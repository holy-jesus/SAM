//go:build windows

package watcher

import (
	"context"
	"syscall"
	"time"
)

const (
	regNotifyChangeName    = 0x00000001
	regNotifyChangeLastSet = 0x00000004
	waitObject0            = 0x00000000
	waitTimeout            = 0x00000102
)

var (
	modadvapi32W = syscall.NewLazyDLL("advapi32.dll")
	modkernel32W = syscall.NewLazyDLL("kernel32.dll")

	procRegNotifyChangeKeyValue = modadvapi32W.NewProc("RegNotifyChangeKeyValue")
	procCreateEventW            = modkernel32W.NewProc("CreateEventW")
	procWaitForSingleObject     = modkernel32W.NewProc("WaitForSingleObject")
	procCloseHandleW            = modkernel32W.NewProc("CloseHandle")
)

func startPlatformRegistryWatcher(ctx context.Context, onChange func()) {
	targets := []struct {
		root syscall.Handle
		path string
		sam  uint32
	}{
		{syscall.HKEY_LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, syscall.KEY_NOTIFY | 0x0100},
		{syscall.HKEY_LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, syscall.KEY_NOTIFY | 0x0200},
		{syscall.HKEY_CURRENT_USER, `Software\Microsoft\Windows\CurrentVersion\Uninstall`, syscall.KEY_NOTIFY},
	}

	for _, target := range targets {
		go watchRegistryKey(ctx, target.root, target.path, target.sam, onChange)
	}

	<-ctx.Done()
}

func watchRegistryKey(ctx context.Context, rootKey syscall.Handle, subKey string, sam uint32, onChange func()) {
	var hKey syscall.Handle
	err := syscall.RegOpenKeyEx(rootKey, syscall.StringToUTF16Ptr(subKey), 0, sam, &hKey)
	if err != nil {
		return
	}
	defer syscall.RegCloseKey(hKey)

	rEvent, _, _ := procCreateEventW.Call(0, 0, 0, 0)
	hEvent := syscall.Handle(rEvent)
	if hEvent == syscall.InvalidHandle || hEvent == 0 {
		return
	}
	defer procCloseHandleW.Call(uintptr(hEvent))

	filter := uintptr(regNotifyChangeName | regNotifyChangeLastSet)

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		// Регистрируем асинхронное уведомление
		r0, _, _ := procRegNotifyChangeKeyValue.Call(
			uintptr(hKey),
			uintptr(1), // bWatchSubtree = TRUE
			filter,
			uintptr(hEvent),
			uintptr(1), // fAsynchronous = TRUE
		)
		if r0 != 0 {
			time.Sleep(5 * time.Second)
			continue
		}

		// Ждём с таймаутом 1 секунда, чтобы можно было проверить ctx.Done()
		rWait, _, _ := procWaitForSingleObject.Call(uintptr(hEvent), uintptr(1000))
		if rWait == uintptr(waitObject0) {
			onChange()
			// Небольшая задержка для дебаунса серийных записей
			time.Sleep(500 * time.Millisecond)
		}
	}
}
