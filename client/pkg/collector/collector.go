package collector

import (
	"net"
	"path/filepath"
	"strings"
	"time"

	"sam-client/pkg/matcher"
	"sam-client/pkg/model"
)

// Options параметры сбора данных
type Options struct {
	IncludeStandalone bool   // Включать ли обнаруженные незарегистрированные запущенные программы
	Thorough          bool   // Тщательное сканирование: сканирование файловой системы (Program Files, AppData) и вычисление хэшей
	CustomSerial      string // Ручной оверрайд серийного номера ПК
	Verbose           bool   // Подробный вывод отладочных сообщений
}

// Collect выполняет полный цикл сбора данных:
// 1. Определение серийного номера, сетевых адресов и характеристик хоста (ОС, CPU, RAM)
// 2. Сбор списка установленных программ (из системного реестра)
// 3. Тщательное сканирование диска (если включен флаг Thorough)
// 4. Сбор списка запущенных процессов и их метаданных
// 5. Соотнесение (корреляция) процессов с ПО
// 6. Вычисление хэшей бинарников (SHA-256) и даты последнего запуска
func Collect(opts Options) (*model.ScanReport, error) {
	startTime := time.Now()
	ResetPrefetchCache()

	// 1. Сбор информации о машине
	machine, err := collectMachineInfo(opts.CustomSerial)
	if err != nil {
		machine = model.MachineInfo{
			SerialNumber: "UNKNOWN_HOST",
			Hostname:     "UNKNOWN",
			OS:           "Windows",
			Architecture: "amd64",
			ScanTime:     time.Now().UTC(),
		}
	}

	// Обогащаем сетевыми реквизитами (IP и MAC-адрес)
	if machine.IPAddress == "" || machine.MACAddress == "" {
		ip, mac := getPrimaryNetworkDetails()
		if machine.IPAddress == "" {
			machine.IPAddress = ip
		}
		if machine.MACAddress == "" {
			machine.MACAddress = mac
		}
	}

	// 2. Сбор установленного ПО из реестра
	installed, err := collectInstalledSoftware(machine.SerialNumber)
	if err != nil {
		installed = []model.SoftwareItem{}
	}

	diskFoundCount := 0
	// 3. Тщательное сканирование диска
	if opts.Thorough {
		diskItems, _ := scanDiskSoftware(machine.SerialNumber)
		diskFoundCount = len(diskItems)
		installed = mergeSoftwareLists(installed, diskItems)
	}

	// 4. Сбор запущенных процессов
	processes, err := collectRunningProcesses()
	if err != nil {
		processes = []model.ProcessItem{}
	}

	// Вычисляем хэши для запущенных процессов
	for i := range processes {
		if processes[i].ExePath != "" {
			hash, err := CalculateFileSHA256(processes[i].ExePath)
			if err == nil {
				processes[i].BinaryHash = hash
			}
			RecordProcessExecution(processes[i].ExePath, time.Now().UTC())
		}
	}

	// 5. Корреляция процессов с ПО (включая поиск запущенного софта и автономных утилит)
	installed, processes = matcher.Correlate(installed, processes, opts.IncludeStandalone, machine.SerialNumber)

	// 6. Обогащение установленного ПО путями к бинарникам, хэшами SHA-256 и датой последнего запуска
	for i := range installed {
		item := &installed[i]

		// Если путь к бинарнику не определен, пытаемся найти главный .exe
		if item.InstallPath == "" {
			if len(item.MatchedProcesses) > 0 {
				for _, p := range processes {
					if p.MatchedSoftware == item.DisplayName && p.ExePath != "" {
						item.InstallPath = p.ExePath
						break
					}
				}
			}
			if item.InstallPath == "" && item.InstallLocation != "" {
				item.InstallPath = FindMainExecutable(item.InstallLocation, item.DisplayName)
			}
		}

		// Вычисляем SHA-256 хэш бинарника
		if item.BinaryHash == "" && item.InstallPath != "" {
			hash, err := CalculateFileSHA256(item.InstallPath)
			if err == nil {
				item.BinaryHash = hash
			}
		}

		// Вычисляем дату последнего запуска бинарника
		item.LastLaunchedAt = GetLastLaunchedTime(item.InstallPath, item.IsRunning)
	}

	// Подсчет статистики
	runningSwCount := 0
	standaloneCount := 0
	for _, sw := range installed {
		if sw.IsRunning {
			runningSwCount++
		}
		if sw.IsStandalone {
			standaloneCount++
		}
	}

	duration := time.Since(startTime).Milliseconds()

	report := &model.ScanReport{
		Machine:           machine,
		InstalledSoftware: installed,
		RunningProcesses:  processes,
		Summary: model.ScanSummary{
			TotalInstalled:         len(installed),
			TotalRunningProcesses:  len(processes),
			TotalRunningSoftware:   runningSwCount,
			TotalStandaloneRunning: standaloneCount,
			TotalDiskScanFound:     diskFoundCount,
			ScanDurationMs:         duration,
		},
		CreatedAt: time.Now().UTC(),
	}

	return report, nil
}

// getPrimaryNetworkDetails находит первый активный non-loopback IPv4 и MAC адрес
func getPrimaryNetworkDetails() (string, string) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return "", ""
	}

	for _, iface := range ifaces {
		if iface.Flags&net.FlagLoopback != 0 || iface.Flags&net.FlagUp == 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			var ip net.IP
			switch v := addr.(type) {
			case *net.IPNet:
				ip = v.IP
			case *net.IPAddr:
				ip = v.IP
			}
			if ip != nil && ip.To4() != nil && !ip.IsLoopback() {
				return ip.String(), iface.HardwareAddr.String()
			}
		}
	}
	return "", ""
}

// mergeSoftwareLists объединяет список из реестра и список из сканирования диска без дублей
func mergeSoftwareLists(existing, diskItems []model.SoftwareItem) []model.SoftwareItem {
	seenNames := make(map[string]bool)
	for _, sw := range existing {
		seenNames[strings.ToLower(strings.TrimSpace(sw.DisplayName))] = true
		if sw.InstallLocation != "" {
			seenNames[strings.ToLower(filepath.Clean(sw.InstallLocation))] = true
		}
	}

	for _, item := range diskItems {
		nameKey := strings.ToLower(strings.TrimSpace(item.DisplayName))
		pathKey := ""
		if item.InstallLocation != "" {
			pathKey = strings.ToLower(filepath.Clean(item.InstallLocation))
		}

		if seenNames[nameKey] || (pathKey != "" && seenNames[pathKey]) {
			continue
		}

		seenNames[nameKey] = true
		if pathKey != "" {
			seenNames[pathKey] = true
		}
		existing = append(existing, item)
	}

	return existing
}
