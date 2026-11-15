package collector

import (
	"encoding/json"
	"net"
	"os"
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
	DemoMode          bool   // Демонстрационный режим: подмешивание софта для хакатона
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

	// Опциональное подмешивание демо-софта (из demo_software.json или при opts.DemoMode)
	demoItems := loadDemoSoftware(machine.SerialNumber, opts.DemoMode)
	if len(demoItems) > 0 {
		installed = mergeSoftwareLists(installed, demoItems)
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

// loadDemoSoftware загружает демо-софт из файла demo_software.json либо генерирует типовой набор для хакатона
func loadDemoSoftware(serialNumber string, forceDemo bool) []model.SoftwareItem {
	var items []model.SoftwareItem

	// 1. Попытка загрузить из внешнего файла demo_software.json (если он лежит рядом с агентом)
	candidatePaths := []string{
		"demo_software.json",
		"data/demo_software.json",
		"../data/demo_software.json",
		"../demo_software.json",
	}

	for _, p := range candidatePaths {
		if data, err := os.ReadFile(p); err == nil && len(data) > 0 {
			var parsed []struct {
				DisplayName     string `json:"display_name"`
				Publisher       string `json:"publisher"`
				Version         string `json:"version"`
				InstallLocation string `json:"install_location"`
			}
			if err := json.Unmarshal(data, &parsed); err == nil && len(parsed) > 0 {
				for _, it := range parsed {
					items = append(items, model.SoftwareItem{
						SerialNumber:    serialNumber,
						DisplayName:     it.DisplayName,
						Publisher:       it.Publisher,
						Version:         it.Version,
						InstallLocation: it.InstallLocation,
						Source:          "registry",
					})
				}
				return items
			}
		}
	}

	// 2. Если включен флаг forceDemo (-demo) и файла demo_software.json нет — возвращаем эталонный демо-набор
	if forceDemo {
		items = []model.SoftwareItem{
			{
				SerialNumber:    serialNumber,
				DisplayName:     "Microsoft Office Professional Plus 2021",
				Publisher:       "Microsoft Corporation",
				Version:         "16.0.14332",
				InstallLocation: `C:\Program Files\Microsoft Office\root\Office16`,
				Source:          "registry",
			},
			{
				SerialNumber:    serialNumber,
				DisplayName:     "7-Zip 19.00 (x64 edition)",
				Publisher:       "Igor Pavlov",
				Version:         "19.00.00.0",
				InstallLocation: `C:\Program Files\7-Zip`,
				Source:          "registry",
			},
			{
				SerialNumber:    serialNumber,
				DisplayName:     "МойОфис Стандартный 2",
				Publisher:       "ООО \"НОВЫЕ ОБЛАЧНЫЕ ТЕХНОЛОГИИ\"",
				Version:         "2.4.0",
				InstallLocation: `C:\Program Files\MyOffice\Standard`,
				Source:          "registry",
			},
		}
	}

	return items
}
