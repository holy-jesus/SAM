package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"sam-client/pkg/collector"
	"sam-client/pkg/exporter"
)

const version = "1.0.0"

func main() {
	var (
		csvPath           string
		jsonPath          string
		processesCsvPath  string
		format            string
		extended          bool
		includeStandalone bool
		customSerial      string
		silent            bool
		showVersion       bool
	)

	flag.StringVar(&csvPath, "csv", "software_dump.csv", "Путь к выходному CSV файлу (или '-' для stdout)")
	flag.StringVar(&jsonPath, "json", "", "Путь к выходному JSON файлу")
	flag.StringVar(&processesCsvPath, "processes-csv", "", "Опциональный путь к CSV файлу со списком всех запущенных процессов")
	flag.StringVar(&format, "format", "csv", "Формат вывода: csv, json или both")
	flag.BoolVar(&extended, "extended", false, "Включить расширенные колонки в CSV (IS_RUNNING, PIDS, PROCESS_NAMES)")
	flag.BoolVar(&includeStandalone, "include-standalone", true, "Обнаруживать и включать запущенные портативные / автономные программы")
	flag.StringVar(&customSerial, "serial", "", "Переопределить серийный номер компьютера вручную")
	flag.BoolVar(&silent, "silent", false, "Тихий режим (без вывода в консоль)")
	flag.BoolVar(&showVersion, "version", false, "Показать версию клиента")

	flag.Parse()

	if showVersion {
		fmt.Printf("SAM Windows Agent v%s\n", version)
		os.Exit(0)
	}

	if !silent {
		fmt.Println("==================================================")
		fmt.Println("     SAM (Software Asset Management) Agent")
		fmt.Println("==================================================")
		fmt.Println("[*] Сбор информации о системе...")
	}

	opts := collector.Options{
		IncludeStandalone: includeStandalone,
		CustomSerial:      customSerial,
		Verbose:           !silent,
	}

	report, err := collector.Collect(opts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[!] Ошибка сбора данных: %v\n", err)
		os.Exit(1)
	}

	if !silent {
		fmt.Printf("[+] Хост:            %s\n", report.Machine.Hostname)
		fmt.Printf("[+] Серийный номер:  %s\n", report.Machine.SerialNumber)
		fmt.Printf("[+] ОС:              %s\n", report.Machine.OS)
		fmt.Printf("[+] Найдено ПО:      %d (из них запущено: %d)\n", report.Summary.TotalInstalled, report.Summary.TotalRunningSoftware)
		fmt.Printf("[+] Процессов в ОС:  %d\n", report.Summary.TotalRunningProcesses)
		if report.Summary.TotalStandaloneRunning > 0 {
			fmt.Printf("[*] Найдено автономных/портативных программ: %d\n", report.Summary.TotalStandaloneRunning)
		}
		fmt.Println("--------------------------------------------------")
	}

	// 1. Экспорт в CSV
	if format == "csv" || format == "both" || csvPath != "" {
		if !silent && csvPath != "-" {
			absPath, _ := filepath.Abs(csvPath)
			fmt.Printf("[*] Сохранение CSV: %s\n", absPath)
		}
		if err := exporter.SaveCSVToFile(csvPath, report.InstalledSoftware, extended); err != nil {
			fmt.Fprintf(os.Stderr, "[!] Ошибка сохранения CSV: %v\n", err)
			os.Exit(1)
		}
	}

	// 2. Экспорт в JSON
	if format == "json" || format == "both" || jsonPath != "" {
		targetJSON := jsonPath
		if targetJSON == "" {
			targetJSON = "software_dump.json"
		}
		if !silent && targetJSON != "-" {
			absPath, _ := filepath.Abs(targetJSON)
			fmt.Printf("[*] Сохранение JSON: %s\n", absPath)
		}
		if err := exporter.SaveJSONToFile(targetJSON, report, true); err != nil {
			fmt.Fprintf(os.Stderr, "[!] Ошибка сохранения JSON: %v\n", err)
			os.Exit(1)
		}
	}

	// 3. Дополнительный экспорт списка процессов, если запрошено
	if processesCsvPath != "" {
		if !silent {
			absPath, _ := filepath.Abs(processesCsvPath)
			fmt.Printf("[*] Сохранение дампа процессов: %s\n", absPath)
		}
		if err := exporter.SaveProcessesCSVToFile(processesCsvPath, report.Machine.SerialNumber, report.RunningProcesses); err != nil {
			fmt.Fprintf(os.Stderr, "[!] Ошибка сохранения процессов в CSV: %v\n", err)
			os.Exit(1)
		}
	}

	if !silent {
		fmt.Println("[+] Готово! Дамп успешно сформирован.")
	}
}
