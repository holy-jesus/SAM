package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	"sam-client/pkg/client"
	"sam-client/pkg/collector"
	"sam-client/pkg/daemon"
	"sam-client/pkg/exporter"
	"sam-client/pkg/model"
	"sam-client/pkg/service"
)

const version = "1.0.0"

func main() {
	var (
		// Режимы запуска
		isDaemon       bool
		serviceAction  string
		openGUI        bool
		triggerUpload  bool
		thoroughScan   bool

		// Конфигурация и сеть
		configPath     string
		serverURL      string
		apiKey         string
		listenAddr     string

		// Экспорт файлов
		csvPath          string
		jsonPath         string
		processesCsvPath string
		format           string
		extended         bool
		includeStandalone bool
		customSerial     string
		silent           bool
		showVersion      bool
		demoMode         bool
	)

	// Флаги управления службой и демоном
	flag.BoolVar(&isDaemon, "daemon", false, "Запустить клиент как фоновый демон/сервис с HTTP-сервером управления")
	flag.StringVar(&serviceAction, "service", "", "Управление службой: install, uninstall, start, stop, run")
	flag.BoolVar(&openGUI, "gui", false, "Открыть локальный графический интерфейс управления в браузере")
	flag.BoolVar(&triggerUpload, "upload", false, "Выгрузить собранный отчёт на центральный сервер SAM")
	flag.BoolVar(&thoroughScan, "thorough", false, "Выполнить тщательное сканирование (включая сканирование диска Program Files и хэширование)")
	flag.BoolVar(&demoMode, "demo", false, "Включить демонстрационный режим (подмешать софт для показа комплаенса, уязвимостей и импортозамещения)")

	// Конфигурационные флаги
	flag.StringVar(&configPath, "config", "config.json", "Путь к файлу конфигурации JSON")
	flag.StringVar(&serverURL, "server", "", "URL центрального сервера SAM (по умолчанию: http://localhost:8000)")
	flag.StringVar(&apiKey, "api-key", "", "API-ключ / токен для авторизации агента на сервере")
	flag.StringVar(&listenAddr, "listen", "", "Адрес локального HTTP API и GUI (по умолчанию: 127.0.0.1:8765)")

	// Флаги экспорта файлов
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
		fmt.Printf("SAM Windows Agent v%s (%s/%s)\n", version, runtime.GOOS, runtime.GOARCH)
		os.Exit(0)
	}

	// 1. Управление системной службой (install, uninstall, start, stop, run)
	if serviceAction != "" {
		exePath, _ := os.Executable()
		err := service.HandleServiceCommand(serviceAction, exePath, func(ctx context.Context) error {
			cfg := loadOrInitConfig(configPath, serverURL, apiKey, listenAddr, customSerial, demoMode)
			d := daemon.NewDaemon(cfg, configPath)
			return d.Run(ctx)
		})
		if err != nil {
			fmt.Fprintf(os.Stderr, "[!] Ошибка службы (%s): %v\n", serviceAction, err)
			os.Exit(1)
		}
		if serviceAction != "run" {
			fmt.Printf("[+] Команда службы '%s' успешно выполнена.\n", serviceAction)
		}
		os.Exit(0)
	}

	// 2. Открытие GUI
	if openGUI {
		guiURL := "http://127.0.0.1:8765/gui"
		if listenAddr != "" {
			guiURL = fmt.Sprintf("http://%s/gui", listenAddr)
		}
		fmt.Printf("[*] Открытие панели управления агентом: %s\n", guiURL)
		openBrowser(guiURL)
		if !isDaemon {
			// Если флаг -daemon не указан, запускаем демон в текущей консоли
			isDaemon = true
		}
	}

	// 3. Запуск агента в режиме постоянного фонового демона
	if isDaemon {
		cfg := loadOrInitConfig(configPath, serverURL, apiKey, listenAddr, customSerial, demoMode)
		d := daemon.NewDaemon(cfg, configPath)

		err := service.RunWithGracefulShutdown(func(ctx context.Context) error {
			return d.Run(ctx)
		})
		if err != nil {
			log.Fatalf("[!] Ошибка работы демона: %v", err)
		}
		os.Exit(0)
	}

	// 4. Однократный режим сканирования (CLI утилита)
	if !silent {
		fmt.Println("==================================================")
		fmt.Println("     SAM (Software Asset Management) Agent v" + version)
		fmt.Println("==================================================")
		fmt.Println("[*] Сбор информации о системе и установленном ПО...")
	}

	opts := collector.Options{
		IncludeStandalone: includeStandalone,
		Thorough:          thoroughScan,
		CustomSerial:      customSerial,
		Verbose:           !silent,
		DemoMode:          demoMode,
	}

	report, err := collector.Collect(opts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[!] Ошибка сбора данных: %v\n", err)
		os.Exit(1)
	}

	if !silent {
		fmt.Printf("[+] Хост:            %s\n", report.Machine.Hostname)
		fmt.Printf("[+] Серийный номер:  %s\n", report.Machine.SerialNumber)
		fmt.Printf("[+] IP / MAC:        %s / %s\n", report.Machine.IPAddress, report.Machine.MACAddress)
		fmt.Printf("[+] ОС:              %s %s\n", report.Machine.OS, report.Machine.OSVersion)
		if report.Machine.CPU != "" {
			fmt.Printf("[+] CPU / RAM:       %s / %d MB\n", report.Machine.CPU, report.Machine.RAM_MB)
		}
		fmt.Printf("[+] Найдено ПО:      %d (из них запущено: %d)\n", report.Summary.TotalInstalled, report.Summary.TotalRunningSoftware)
		fmt.Printf("[+] Процессов в ОС:  %d\n", report.Summary.TotalRunningProcesses)
		if report.Summary.TotalDiskScanFound > 0 {
			fmt.Printf("[*] Найдено на диске (Program Files): %d\n", report.Summary.TotalDiskScanFound)
		}
		if report.Summary.TotalStandaloneRunning > 0 {
			fmt.Printf("[*] Автономных / портативных программ: %d\n", report.Summary.TotalStandaloneRunning)
		}
		fmt.Printf("[*] Время сканирования: %d мс\n", report.Summary.ScanDurationMs)
		fmt.Println("--------------------------------------------------")
	}

	// Экспорт в CSV
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

	// Экспорт в JSON
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

	// Экспорт процессов
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

	// Выгрузка на сервер SAM при наличии флага -upload
	if triggerUpload {
		targetServer := serverURL
		if targetServer == "" {
			targetServer = "http://localhost:8000"
		}
		if !silent {
			fmt.Printf("[*] Отправка инвентаризационного отчёта на сервер %s...\n", targetServer)
		}

		backendCl := client.NewBackendClient(targetServer, apiKey)
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()

		req := report.ToAgentReportRequest()
		resp, err := backendCl.SendReport(ctx, req)
		if err != nil {
			fmt.Fprintf(os.Stderr, "[!] Ошибка выгрузки на сервер: %v\n", err)
			os.Exit(1)
		}

		if !silent {
			fmt.Printf("[+] Отчёт успешно принят сервером!\n")
			fmt.Printf("    - ID хоста:             %s\n", resp.ComputerID)
			fmt.Printf("    - Передано записей ПО:  %d\n", resp.TotalSoftwareReported)
			fmt.Printf("    - Сопоставлено каталогу: %d\n", resp.MatchedCount)
		}
	}

	if !silent {
		fmt.Println("[+] Завершено успешно.")
	}
}

func loadOrInitConfig(path, serverURL, apiKey, listenAddr, customSerial string, demoMode bool) model.AgentConfig {
	cfg, err := daemon.LoadConfigFromFile(path)
	if err != nil {
		cfg = model.DefaultConfig()
		_ = daemon.SaveConfigToFile(path, cfg)
	}

	if serverURL != "" {
		cfg.ServerURL = serverURL
	}
	if apiKey != "" {
		cfg.APIKey = apiKey
	}
	if listenAddr != "" {
		cfg.ListenAddr = listenAddr
	}
	if customSerial != "" {
		cfg.CustomSerial = customSerial
	}
	if demoMode {
		cfg.DemoMode = true
	}

	return cfg
}

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	_ = cmd.Start()
}
