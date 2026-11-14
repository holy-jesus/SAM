//go:build windows

package collector

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"

	"sam-client/pkg/model"
)

const (
	th32csSnapProcess           = 0x00000002
	processQueryLimitedInfo     = 0x1000
	keyWow6464Key               = 0x0100
	keyWow6432Key               = 0x0200
)

type processEntry32W struct {
	Size            uint32
	Usage           uint32
	ProcessID       uint32
	DefaultHeapID   uintptr
	ModuleID        uint32
	Threads         uint32
	ParentProcessID uint32
	PriClassBase    int32
	Flags           uint32
	ExeFile         [260]uint16
}

type translation struct {
	Language uint16
	CodePage uint16
}

var (
	modkernel32 = syscall.NewLazyDLL("kernel32.dll")
	modadvapi32 = syscall.NewLazyDLL("advapi32.dll")
	modversion  = syscall.NewLazyDLL("version.dll")

	procCreateToolhelp32Snapshot = modkernel32.NewProc("CreateToolhelp32Snapshot")
	procProcess32FirstW          = modkernel32.NewProc("Process32FirstW")
	procProcess32NextW           = modkernel32.NewProc("Process32NextW")
	procOpenProcess              = modkernel32.NewProc("OpenProcess")
	procCloseHandle              = modkernel32.NewProc("CloseHandle")
	procQueryFullProcessImage    = modkernel32.NewProc("QueryFullProcessImageNameW")

	procGetFileVersionInfoSizeW = modversion.NewProc("GetFileVersionInfoSizeW")
	procGetFileVersionInfoW     = modversion.NewProc("GetFileVersionInfoW")
	procVerQueryValueW          = modversion.NewProc("VerQueryValueW")
)

func collectMachineInfo(customSerial string) (model.MachineInfo, error) {
	hostname, _ := os.Hostname()

	serial := customSerial
	if serial == "" {
		serial = getHardwareSerialNumber()
	}
	if serial == "" {
		serial = hostname
	}

	osVersion := getWindowsOSName()
	if osVersion == "" {
		osVersion = fmt.Sprintf("Windows (%s)", runtime.GOARCH)
	}

	return model.MachineInfo{
		SerialNumber: serial,
		Hostname:     hostname,
		OS:           osVersion,
		Architecture: runtime.GOARCH,
		ScanTime:     time.Now().UTC(),
	}, nil
}

func getHardwareSerialNumber() string {
	// 1. Попытка чтения из реестра BIOS
	var hKey syscall.Handle
	err := syscall.RegOpenKeyEx(syscall.HKEY_LOCAL_MACHINE, syscall.StringToUTF16Ptr(`HARDWARE\DESCRIPTION\System\BIOS`), 0, syscall.KEY_READ, &hKey)
	if err == nil {
		defer syscall.RegCloseKey(hKey)
		s := regReadString(hKey, "SystemSerialNumber")
		if isValidSerial(s) {
			return strings.TrimSpace(s)
		}
		s = regReadString(hKey, "BaseBoardSerialNumber")
		if isValidSerial(s) {
			return strings.TrimSpace(s)
		}
	}

	// 2. Попытка через PowerShell CIM / WMI
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_BIOS).SerialNumber")
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err == nil {
		s := strings.TrimSpace(out.String())
		if isValidSerial(s) {
			return s
		}
	}

	// 3. Попытка через wmic
	ctx2, cancel2 := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel2()
	cmdWmic := exec.CommandContext(ctx2, "wmic", "bios", "get", "serialnumber")
	var outWmic bytes.Buffer
	cmdWmic.Stdout = &outWmic
	if err := cmdWmic.Run(); err == nil {
		lines := strings.Split(outWmic.String(), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line != "" && !strings.EqualFold(line, "SerialNumber") && isValidSerial(line) {
				return line
			}
		}
	}

	// 4. Попытка MachineGuid из реестра Cryptography
	err = syscall.RegOpenKeyEx(syscall.HKEY_LOCAL_MACHINE, syscall.StringToUTF16Ptr(`SOFTWARE\Microsoft\Cryptography`), 0, syscall.KEY_READ, &hKey)
	if err == nil {
		defer syscall.RegCloseKey(hKey)
		s := regReadString(hKey, "MachineGuid")
		if s != "" {
			return strings.TrimSpace(s)
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
		"to be filled by oem",
		"default string",
		"none",
		"system serial number",
		"chassis serial number",
		"0",
		"123456789",
		"0123456789",
	}
	for _, inv := range invalidValues {
		if sLower == inv {
			return false
		}
	}
	return true
}

func getWindowsOSName() string {
	var hKey syscall.Handle
	err := syscall.RegOpenKeyEx(syscall.HKEY_LOCAL_MACHINE, syscall.StringToUTF16Ptr(`SOFTWARE\Microsoft\Windows NT\CurrentVersion`), 0, syscall.KEY_READ, &hKey)
	if err != nil {
		return ""
	}
	defer syscall.RegCloseKey(hKey)

	prodName := regReadString(hKey, "ProductName")
	dispVer := regReadString(hKey, "DisplayVersion")
	if dispVer == "" {
		dispVer = regReadString(hKey, "ReleaseId")
	}
	if prodName != "" && dispVer != "" {
		return fmt.Sprintf("%s (%s)", prodName, dispVer)
	}
	return prodName
}

type regScanTarget struct {
	rootKey syscall.Handle
	path    string
	sam     uint32
}

func collectInstalledSoftware(serialNumber string) ([]model.SoftwareItem, error) {
	targets := []regScanTarget{
		{rootKey: syscall.HKEY_LOCAL_MACHINE, path: `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, sam: syscall.KEY_READ | keyWow6464Key},
		{rootKey: syscall.HKEY_LOCAL_MACHINE, path: `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, sam: syscall.KEY_READ | keyWow6432Key},
		{rootKey: syscall.HKEY_CURRENT_USER, path: `Software\Microsoft\Windows\CurrentVersion\Uninstall`, sam: syscall.KEY_READ},
	}

	seen := make(map[string]bool)
	var items []model.SoftwareItem

	for _, target := range targets {
		var hKey syscall.Handle
		err := syscall.RegOpenKeyEx(target.rootKey, syscall.StringToUTF16Ptr(target.path), 0, target.sam, &hKey)
		if err != nil {
			continue
		}

		for idx := uint32(0); ; idx++ {
			var subKeyBuf [256]uint16
			subKeyLen := uint32(len(subKeyBuf))
			errEnum := syscall.RegEnumKeyEx(hKey, idx, &subKeyBuf[0], &subKeyLen, nil, nil, nil, nil)
			if errEnum != nil {
				break
			}
			subKeyName := syscall.UTF16ToString(subKeyBuf[:subKeyLen])

			var hAppKey syscall.Handle
			errOpen := syscall.RegOpenKeyEx(hKey, syscall.StringToUTF16Ptr(subKeyName), 0, target.sam, &hAppKey)
			if errOpen != nil {
				continue
			}

			dispName := regReadString(hAppKey, "DisplayName")
			if dispName == "" {
				dispName = regReadString(hAppKey, "QuietDisplayName")
			}
			dispName = strings.TrimSpace(dispName)
			if dispName == "" {
				syscall.RegCloseKey(hAppKey)
				continue
			}

			publisher := strings.TrimSpace(regReadString(hAppKey, "Publisher"))
			if publisher == "" {
				publisher = "<Null>"
			}

			version := strings.TrimSpace(regReadString(hAppKey, "DisplayVersion"))
			if version == "" {
				version = "<Null>"
			}

			installLoc := strings.TrimSpace(regReadString(hAppKey, "InstallLocation"))
			if installLoc == "" {
				installLoc = strings.TrimSpace(regReadString(hAppKey, "InstallSource"))
			}

			installDate := strings.TrimSpace(regReadString(hAppKey, "InstallDate"))

			syscall.RegCloseKey(hAppKey)

			// Дедупликация идентичных записей ПО
			dedupKey := strings.ToLower(dispName) + "|" + strings.ToLower(publisher) + "|" + strings.ToLower(version)
			if seen[dedupKey] {
				continue
			}
			seen[dedupKey] = true

			items = append(items, model.SoftwareItem{
				SerialNumber:    serialNumber,
				DisplayName:     dispName,
				Publisher:       publisher,
				Version:         version,
				InstallLocation: installLoc,
				InstallDate:     installDate,
				SourceKey:       subKeyName,
			})
		}
		syscall.RegCloseKey(hKey)
	}

	return items, nil
}

func collectRunningProcesses() ([]model.ProcessItem, error) {
	hSnap, _, _ := procCreateToolhelp32Snapshot.Call(uintptr(th32csSnapProcess), 0)
	if syscall.Handle(hSnap) == syscall.InvalidHandle {
		return nil, fmt.Errorf("failed to create toolhelp32 snapshot")
	}
	defer procCloseHandle.Call(hSnap)

	var entry processEntry32W
	entry.Size = uint32(unsafe.Sizeof(entry))

	r0, _, _ := procProcess32FirstW.Call(hSnap, uintptr(unsafe.Pointer(&entry)))
	if r0 == 0 {
		return nil, fmt.Errorf("process32first failed")
	}

	var processes []model.ProcessItem
	for {
		pid := entry.ProcessID
		name := syscall.UTF16ToString(entry.ExeFile[:])

		item := model.ProcessItem{
			PID:  pid,
			Name: name,
		}

		// Попытка открыть процесс и получить полный путь к исполняемому файлу
		hProc, _, _ := procOpenProcess.Call(uintptr(processQueryLimitedInfo), 0, uintptr(pid))
		if hProc != 0 {
			var pathBuf [1024]uint16
			pathLen := uint32(len(pathBuf))
			rQuery, _, _ := procQueryFullProcessImage.Call(hProc, 0, uintptr(unsafe.Pointer(&pathBuf[0])), uintptr(unsafe.Pointer(&pathLen)))
			procCloseHandle.Call(hProc)

			if rQuery != 0 && pathLen > 0 {
				exePath := syscall.UTF16ToString(pathBuf[:pathLen])
				item.ExePath = exePath

				// Чтение метаданных версии PE файла
				prod, comp, desc, ver, prodVer := getExecutableVersionInfo(exePath)
				item.ProductName = prod
				item.CompanyName = comp
				item.FileDescription = desc
				item.FileVersion = ver
				item.ProductVersion = prodVer
			}
		}

		processes = append(processes, item)

		entry.Size = uint32(unsafe.Sizeof(entry))
		rNext, _, _ := procProcess32NextW.Call(hSnap, uintptr(unsafe.Pointer(&entry)))
		if rNext == 0 {
			break
		}
	}

	return processes, nil
}

func getExecutableVersionInfo(path string) (prod, comp, desc, ver, prodVer string) {
	pPath, err := syscall.UTF16PtrFromString(path)
	if err != nil {
		return
	}

	var handle uintptr
	rSize, _, _ := procGetFileVersionInfoSizeW.Call(uintptr(unsafe.Pointer(pPath)), uintptr(unsafe.Pointer(&handle)))
	size := uint32(rSize)
	if size == 0 {
		return
	}

	buf := make([]byte, size)
	rGet, _, _ := procGetFileVersionInfoW.Call(uintptr(unsafe.Pointer(pPath)), 0, uintptr(size), uintptr(unsafe.Pointer(&buf[0])))
	if rGet == 0 {
		return
	}

	// Поиск таблиц языков и кодировок
	subBlock, _ := syscall.UTF16PtrFromString(`\VarFileInfo\Translation`)
	var pValue uintptr
	var valLen uint32
	r0, _, _ := procVerQueryValueW.Call(
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(unsafe.Pointer(subBlock)),
		uintptr(unsafe.Pointer(&pValue)),
		uintptr(unsafe.Pointer(&valLen)),
	)

	var pairs []translation
	if r0 != 0 && pValue != 0 && valLen >= 4 {
		count := valLen / 4
		for i := uint32(0); i < count; i++ {
			t := (*translation)(unsafe.Pointer(pValue + uintptr(i*4)))
			pairs = append(pairs, *t)
		}
	}

	// Стандартные кодировки по умолчанию
	pairs = append(pairs,
		translation{0x0409, 0x04b0}, // US English Unicode
		translation{0x0409, 0x04e4}, // US English Multilingual
		translation{0x0419, 0x04b0}, // Russian Unicode
		translation{0x0419, 0x04e3}, // Russian Cyrillic
		translation{0x0000, 0x04b0}, // Neutral Unicode
	)

	for _, p := range pairs {
		if prod == "" {
			prod = queryVerString(buf, p.Language, p.CodePage, "ProductName")
		}
		if comp == "" {
			comp = queryVerString(buf, p.Language, p.CodePage, "CompanyName")
		}
		if desc == "" {
			desc = queryVerString(buf, p.Language, p.CodePage, "FileDescription")
		}
		if ver == "" {
			ver = queryVerString(buf, p.Language, p.CodePage, "FileVersion")
		}
		if prodVer == "" {
			prodVer = queryVerString(buf, p.Language, p.CodePage, "ProductVersion")
		}
		if prod != "" && comp != "" && desc != "" && ver != "" {
			break
		}
	}
	return
}

func queryVerString(buf []byte, lang, codepage uint16, key string) string {
	subBlock := fmt.Sprintf(`\StringFileInfo\%04x%04x\%s`, lang, codepage, key)
	pSubBlock, err := syscall.UTF16PtrFromString(subBlock)
	if err != nil {
		return ""
	}
	var pValue uintptr
	var valLen uint32
	r0, _, _ := procVerQueryValueW.Call(
		uintptr(unsafe.Pointer(&buf[0])),
		uintptr(unsafe.Pointer(pSubBlock)),
		uintptr(unsafe.Pointer(&pValue)),
		uintptr(unsafe.Pointer(&valLen)),
	)
	if r0 == 0 || pValue == 0 || valLen == 0 {
		return ""
	}
	var strChars []uint16
	for i := uintptr(0); i < uintptr(valLen); i++ {
		ch := *(*uint16)(unsafe.Pointer(pValue + i*2))
		if ch == 0 {
			break
		}
		strChars = append(strChars, ch)
	}
	return syscall.UTF16ToString(strChars)
}

func regReadString(hKey syscall.Handle, name string) string {
	pName, err := syscall.UTF16PtrFromString(name)
	if err != nil {
		return ""
	}
	var valType uint32
	var size uint32
	err = syscall.RegQueryValueEx(hKey, pName, nil, &valType, nil, &size)
	if err != nil || size == 0 {
		return ""
	}
	buf := make([]byte, size)
	err = syscall.RegQueryValueEx(hKey, pName, nil, &valType, &buf[0], &size)
	if err != nil {
		return ""
	}
	if valType == 1 || valType == 2 { // REG_SZ, REG_EXPAND_SZ
		n := size / 2
		u16 := make([]uint16, n)
		for i := uint32(0); i < n; i++ {
			u16[i] = *(*uint16)(unsafe.Pointer(&buf[i*2]))
		}
		return syscall.UTF16ToString(u16)
	}
	return ""
}
