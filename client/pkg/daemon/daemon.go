package daemon

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"

	"sam-client/pkg/client"
	"sam-client/pkg/collector"
	"sam-client/pkg/model"
	"sam-client/pkg/server"
	"sam-client/pkg/watcher"
)

// Daemon центральный оркестратор агента SAM
type Daemon struct {
	config        model.AgentConfig
	configPath    string
	backendClient *client.BackendClient
	httpServer    *server.HTTPServer
	watcherMgr    *watcher.WatcherManager

	latestReport     *model.ScanReport
	latestReportMu   sync.RWMutex
	lastScanTime     time.Time
	lastUploadTime   time.Time
	lastUploadStatus string
	lastMatchedCount int
	startTime        time.Time

	cancelFunc context.CancelFunc
	wg         sync.WaitGroup
	mu         sync.RWMutex
}

// NewDaemon инициализирует демон агента
func NewDaemon(cfg model.AgentConfig, configPath string) *Daemon {
	d := &Daemon{
		config:        cfg,
		configPath:    configPath,
		backendClient: client.NewBackendClient(cfg.ServerURL, cfg.APIKey),
		startTime:     time.Now(),
	}

	d.httpServer = server.NewHTTPServer(cfg.ListenAddr, d)
	d.watcherMgr = watcher.NewWatcherManager(
		d.onProcessStarted,
		d.onRegistryChanged,
	)

	return d
}

// Run запускает все подсистемы демона агента
func (d *Daemon) Run(ctx context.Context) error {
	daemonCtx, cancel := context.WithCancel(ctx)
	d.cancelFunc = cancel

	log.Printf("[*] [Daemon] Запуск агента SAM v1.0.0 на адресе %s...", d.config.ListenAddr)
	log.Printf("[*] [Daemon] Адрес центрального сервера: %s", d.config.ServerURL)

	// 1. Первоначальный сбор данных
	log.Println("[*] [Daemon] Выполнение первоначального инвентаризационного сканирования...")
	report, err := d.TriggerScan(false)
	if err != nil {
		log.Printf("[!] [Daemon] Ошибка первоначального сканирования: %v", err)
	} else {
		log.Printf("[+] [Daemon] Обнаружено ПО: %d (запущено: %d, процессов в ОС: %d)",
			report.Summary.TotalInstalled, report.Summary.TotalRunningSoftware, report.Summary.TotalRunningProcesses)
	}

	// 2. Первоначальная выгрузка на сервер (если включен auto_upload)
	if d.config.AutoUpload {
		go func() {
			time.Sleep(2 * time.Second)
			log.Println("[*] [Daemon] Выполнение первоначальной отправки отчёта на сервер...")
			upCtx, upCancel := context.WithTimeout(context.Background(), 60*time.Second)
			defer upCancel()
			if _, err := d.TriggerUpload(upCtx); err != nil {
				log.Printf("[!] [Daemon] Не удалось отправить отчёт на сервер: %v", err)
			}
		}()
	}

	// 3. Запуск локального HTTP сервера управления и веб-интерфейса
	d.wg.Add(1)
	go func() {
		defer d.wg.Done()
		log.Printf("[+] [Daemon] Локальный GUI и API доступны по адресу: http://%s", d.config.ListenAddr)
		if err := d.httpServer.Start(); err != nil && err.Error() != "http: Server closed" {
			log.Printf("[!] [Daemon] Ошибка HTTP сервера: %v", err)
		}
	}()

	// 4. Запуск наблюдателя в реальном времени (процессы и реестр)
	if d.config.EnableRealtimeWatcher {
		log.Println("[*] [Daemon] Запуск мониторинга процессов и реестра в реальном времени...")
		d.watcherMgr.Start(daemonCtx)
	}

	// 5. Запуск периодических таймеров (Heartbeat, Quick Scan, Thorough Scan)
	d.wg.Add(1)
	go d.runScheduledTasks(daemonCtx)

	// Ожидание сигнала остановки
	<-daemonCtx.Done()
	log.Println("[*] [Daemon] Завершение работы агента...")

	if d.config.EnableRealtimeWatcher {
		d.watcherMgr.Stop()
	}

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()
	_ = d.httpServer.Stop(shutdownCtx)

	d.wg.Wait()
	log.Println("[+] [Daemon] Агент успешно остановлен.")
	return nil
}

// Stop корректно завершает демон
func (d *Daemon) Stop() {
	if d.cancelFunc != nil {
		d.cancelFunc()
	}
}

func (d *Daemon) runScheduledTasks(ctx context.Context) {
	defer d.wg.Done()

	hbInterval := time.Duration(d.config.HeartbeatIntervalSec) * time.Second
	if hbInterval < 5*time.Second {
		hbInterval = 30 * time.Second
	}
	hbTicker := time.NewTicker(hbInterval)
	defer hbTicker.Stop()

	quickScanInterval := time.Duration(d.config.QuickScanIntervalMin) * time.Minute
	if quickScanInterval < time.Minute {
		quickScanInterval = 60 * time.Minute
	}
	quickTicker := time.NewTicker(quickScanInterval)
	defer quickTicker.Stop()

	thoroughInterval := time.Duration(d.config.ThoroughScanIntervalHours) * time.Hour
	if thoroughInterval < time.Hour {
		thoroughInterval = 24 * time.Hour
	}
	thoroughTicker := time.NewTicker(thoroughInterval)
	defer thoroughTicker.Stop()

	for {
		select {
		case <-ctx.Done():
			return

		case <-hbTicker.C:
			d.sendPeriodicHeartbeat(ctx)

		case <-quickTicker.C:
			log.Println("[*] [Daemon] Запуск планового быстрого сканирования...")
			if _, err := d.TriggerScan(false); err == nil && d.config.AutoUpload {
				upCtx, upCancel := context.WithTimeout(ctx, 60*time.Second)
				_, _ = d.TriggerUpload(upCtx)
				upCancel()
			}

		case <-thoroughTicker.C:
			log.Println("[*] [Daemon] Запуск планового тщательного сканирования диска...")
			if _, err := d.TriggerScan(true); err == nil && d.config.AutoUpload {
				upCtx, upCancel := context.WithTimeout(ctx, 90*time.Second)
				_, _ = d.TriggerUpload(upCtx)
				upCancel()
			}
		}
	}
}

func (d *Daemon) sendPeriodicHeartbeat(ctx context.Context) {
	rep := d.GetLatestReport()
	serial := d.config.CustomSerial
	hostname := ""
	if rep != nil {
		if serial == "" {
			serial = rep.Machine.SerialNumber
		}
		hostname = rep.Machine.Hostname
	}
	if serial == "" {
		return
	}

	hbCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	resp, err := d.backendClient.SendHeartbeat(hbCtx, model.AgentHeartbeatRequest{
		SerialNumber: serial,
		Hostname:     hostname,
	})
	if err != nil {
		return
	}

	// Обработка команд от сервера, если они переданы в ответе пинга
	if resp != nil && len(resp.Commands) > 0 {
		for _, cmd := range resp.Commands {
			d.executeServerCommand(ctx, cmd)
		}
	}
}

func (d *Daemon) executeServerCommand(ctx context.Context, cmd model.AgentCommand) {
	log.Printf("[*] [Daemon] Получена команда от сервера: %s (ID: %s)", cmd.Action, cmd.ID)
	switch cmd.Action {
	case "scan":
		thorough := cmd.Args["thorough"] == "true"
		_, _ = d.TriggerScan(thorough)
	case "upload":
		upCtx, cancel := context.WithTimeout(ctx, 60*time.Second)
		_, _ = d.TriggerUpload(upCtx)
		cancel()
	}
}

func (d *Daemon) onProcessStarted(proc model.ProcessItem) {
	log.Printf("[*] [Watcher] Запущен процесс: %s (PID: %d)", proc.Name, proc.PID)
}

func (d *Daemon) onRegistryChanged() {
	log.Println("[*] [Watcher] Зафиксированы изменения в реестре ПО. Запуск пересканирования...")
	if _, err := d.TriggerScan(false); err == nil && d.config.AutoUpload {
		ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
		defer cancel()
		_, _ = d.TriggerUpload(ctx)
	}
}

// TriggerScan выполняет сканирование системы и сохраняет результат в памяти
func (d *Daemon) TriggerScan(thorough bool) (*model.ScanReport, error) {
	opts := collector.Options{
		IncludeStandalone: true,
		Thorough:          thorough,
		CustomSerial:      d.config.CustomSerial,
		Verbose:           false,
		DemoMode:          d.config.DemoMode,
	}

	report, err := collector.Collect(opts)
	if err != nil {
		return nil, err
	}

	d.latestReportMu.Lock()
	d.latestReport = report
	d.lastScanTime = time.Now()
	d.latestReportMu.Unlock()

	return report, nil
}

// TriggerUpload отправляет текущий снимок инвентаризации на FastAPI бэкенд
func (d *Daemon) TriggerUpload(ctx context.Context) (*model.AgentReportResponse, error) {
	rep := d.GetLatestReport()
	if rep == nil {
		var err error
		rep, err = d.TriggerScan(false)
		if err != nil {
			return nil, fmt.Errorf("failed to collect report before upload: %w", err)
		}
	}

	req := rep.ToAgentReportRequest()
	resp, err := d.backendClient.SendReport(ctx, req)

	d.mu.Lock()
	d.lastUploadTime = time.Now()
	if err != nil {
		d.lastUploadStatus = "error: " + err.Error()
	} else {
		d.lastUploadStatus = "success"
		d.lastMatchedCount = resp.MatchedCount
	}
	d.mu.Unlock()

	if err != nil {
		return nil, err
	}

	log.Printf("[+] [Daemon] Отчёт успешно выгружен на сервер! Хост ID: %s, сопоставлено ПО: %d/%d",
		resp.ComputerID, resp.MatchedCount, resp.TotalSoftwareReported)
	return resp, nil
}

// GetLatestReport возвращает последний сформированный отчёт
func (d *Daemon) GetLatestReport() *model.ScanReport {
	d.latestReportMu.RLock()
	defer d.latestReportMu.RUnlock()
	return d.latestReport
}

// GetStatus возвращает состояние демона
func (d *Daemon) GetStatus() map[string]interface{} {
	d.mu.RLock()
	defer d.mu.RUnlock()

	rep := d.GetLatestReport()
	sn := d.config.CustomSerial
	hostname := ""
	ip := ""
	mac := ""
	totalInstalled := 0
	totalRunning := 0
	totalProcs := 0

	if rep != nil {
		if sn == "" {
			sn = rep.Machine.SerialNumber
		}
		hostname = rep.Machine.Hostname
		ip = rep.Machine.IPAddress
		mac = rep.Machine.MACAddress
		totalInstalled = rep.Summary.TotalInstalled
		totalRunning = rep.Summary.TotalRunningSoftware
		totalProcs = rep.Summary.TotalRunningProcesses
	}

	return map[string]interface{}{
		"is_running":               true,
		"uptime_seconds":           int(time.Since(d.startTime).Seconds()),
		"serial_number":            sn,
		"hostname":                 hostname,
		"ip_address":               ip,
		"mac_address":              mac,
		"server_url":               d.config.ServerURL,
		"listen_addr":              d.config.ListenAddr,
		"last_scan_time":           d.lastScanTime,
		"total_installed":          totalInstalled,
		"total_running_software":   totalRunning,
		"total_running_processes":  totalProcs,
		"last_upload_time":         d.lastUploadTime,
		"last_upload_status":       d.lastUploadStatus,
		"matched_count":            d.lastMatchedCount,
		"auto_upload":              d.config.AutoUpload,
		"enable_realtime_watcher":  d.config.EnableRealtimeWatcher,
		"quick_scan_interval_min":  d.config.QuickScanIntervalMin,
		"thorough_scan_interval_h": d.config.ThoroughScanIntervalHours,
	}
}

// GetConfig возвращает конфигурацию
func (d *Daemon) GetConfig() model.AgentConfig {
	d.mu.RLock()
	defer d.mu.RUnlock()
	return d.config
}

// UpdateConfig обновляет параметры конфигурации
func (d *Daemon) UpdateConfig(cfg model.AgentConfig) error {
	d.mu.Lock()
	d.config = cfg
	d.backendClient = client.NewBackendClient(cfg.ServerURL, cfg.APIKey)
	d.mu.Unlock()

	if d.configPath != "" {
		data, err := json.MarshalIndent(cfg, "", "  ")
		if err == nil {
			_ = os.WriteFile(d.configPath, data, 0644)
		}
	}
	return nil
}

// SaveConfigToFile сохраняет конфигурацию в JSON
func SaveConfigToFile(path string, cfg model.AgentConfig) error {
	dir := filepath.Dir(path)
	if dir != "" {
		_ = os.MkdirAll(dir, 0755)
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

// LoadConfigFromFile загружает конфигурацию из JSON
func LoadConfigFromFile(path string) (model.AgentConfig, error) {
	cfg := model.DefaultConfig()
	data, err := os.ReadFile(path)
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(data, &cfg); err != nil {
		return cfg, err
	}
	return cfg, nil
}
