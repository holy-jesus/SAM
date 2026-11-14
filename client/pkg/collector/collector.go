package collector

import (
	"time"

	"sam-client/pkg/matcher"
	"sam-client/pkg/model"
)

// Options параметры сбора данных
type Options struct {
	IncludeStandalone bool   // Включать ли обнаруженные незарегистрированные запущенные программы в общий список ПО
	CustomSerial      string // Ручной оверрайд серийного номера ПК
	Verbose           bool   // Подробный вывод отладочных сообщений
}

// Collect выполняет полный цикл сбора данных:
// 1. Определение серийного номера и характеристик хоста
// 2. Сбор списка установленных программ (из системного реестра)
// 3. Сбор списка запущенных процессов и их исполняемых файлов
// 4. Соотнесение (корреляция) процессов с ПО
func Collect(opts Options) (*model.ScanReport, error) {
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

	// 2. Сбор установленного ПО из реестра
	installed, err := collectInstalledSoftware(machine.SerialNumber)
	if err != nil {
		installed = []model.SoftwareItem{}
	}

	// 3. Сбор запущенных процессов
	processes, err := collectRunningProcesses()
	if err != nil {
		processes = []model.ProcessItem{}
	}

	// 4. Корреляция процессов с ПО (включая поиск запущенного софта и автономных утилит)
	installed, processes = matcher.Correlate(installed, processes, opts.IncludeStandalone, machine.SerialNumber)

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

	report := &model.ScanReport{
		Machine:           machine,
		InstalledSoftware: installed,
		RunningProcesses:  processes,
		Summary: model.ScanSummary{
			TotalInstalled:         len(installed),
			TotalRunningProcesses:  len(processes),
			TotalRunningSoftware:   runningSwCount,
			TotalStandaloneRunning: standaloneCount,
		},
	}

	return report, nil
}
