package model

import (
	"strings"
	"time"
)

// MachineInfo содержит расширенные данные об идентифицируемом хосте
type MachineInfo struct {
	SerialNumber string    `json:"serial_number"`
	Hostname     string    `json:"hostname"`
	IPAddress    string    `json:"ip_address,omitempty"`
	MACAddress   string    `json:"mac_address,omitempty"`
	OS           string    `json:"os"`
	OSVersion    string    `json:"os_version,omitempty"`
	Architecture string    `json:"architecture"`
	CPU          string    `json:"cpu,omitempty"`
	RAM_MB       int       `json:"ram_mb,omitempty"`
	ScanTime     time.Time `json:"scan_time"`
}

// SoftwareItem описывает единицу установленного ПО или обнаруженного автономного софта
type SoftwareItem struct {
	SerialNumber     string     `json:"serial_number"`
	DisplayName      string     `json:"display_name"`
	Publisher        string     `json:"publisher"`
	Version          string     `json:"version"`
	InstallLocation  string     `json:"install_location,omitempty"`
	InstallPath      string     `json:"install_path,omitempty"`      // Путь к исполняемому файлу
	BinaryHash       string     `json:"binary_hash,omitempty"`       // SHA-256 хэш исполняемого файла
	LastLaunchedAt   *time.Time `json:"last_launched_at,omitempty"`  // Дата/время последнего запуска
	InstallDate      string     `json:"install_date,omitempty"`
	SourceKey        string     `json:"source_key,omitempty"`
	Source           string     `json:"source,omitempty"`            // registry, disk_scan, process, standalone
	IsRunning        bool       `json:"is_running"`
	MatchedPIDs      []uint32   `json:"matched_pids,omitempty"`
	MatchedProcesses []string   `json:"matched_processes,omitempty"`
	IsStandalone     bool       `json:"is_standalone,omitempty"`
}

// ProcessItem описывает запущенный в ОС процесс и результат его соотнесения с ПО
type ProcessItem struct {
	PID              uint32     `json:"pid"`
	Name             string     `json:"name"`
	ExePath          string     `json:"exe_path,omitempty"`
	CommandLine      string     `json:"command_line,omitempty"`
	ProductName      string     `json:"product_name,omitempty"`
	CompanyName      string     `json:"company_name,omitempty"`
	FileDescription  string     `json:"file_description,omitempty"`
	FileVersion      string     `json:"file_version,omitempty"`
	ProductVersion   string     `json:"product_version,omitempty"`
	BinaryHash       string     `json:"binary_hash,omitempty"`
	StartTime        *time.Time `json:"start_time,omitempty"`
	MatchedSoftware  string     `json:"matched_software,omitempty"`
	MatchedPublisher string     `json:"matched_publisher,omitempty"`
}

// ScanSummary краткая статистика сканирования
type ScanSummary struct {
	TotalInstalled         int   `json:"total_installed"`
	TotalRunningProcesses  int   `json:"total_running_processes"`
	TotalRunningSoftware   int   `json:"total_running_software"`
	TotalStandaloneRunning int   `json:"total_standalone_running"`
	TotalDiskScanFound     int   `json:"total_disk_scan_found"`
	ScanDurationMs         int64 `json:"scan_duration_ms"`
}

// ScanReport полный отчёт о сканировании машины
type ScanReport struct {
	Machine           MachineInfo    `json:"machine"`
	InstalledSoftware []SoftwareItem `json:"installed_software"`
	RunningProcesses  []ProcessItem  `json:"running_processes"`
	Summary           ScanSummary    `json:"summary"`
	CreatedAt         time.Time      `json:"created_at"`
}

// AgentSoftwareReportItem элемент списка ПО для выгрузки на FastAPI сервер
type AgentSoftwareReportItem struct {
	DisplayName    string     `json:"display_name"`
	Publisher      string     `json:"publisher,omitempty"`
	Version        string     `json:"version,omitempty"`
	InstallPath    string     `json:"install_path,omitempty"`
	BinaryHash     string     `json:"binary_hash,omitempty"`
	LastLaunchedAt *time.Time `json:"last_launched_at,omitempty"`
	IsRunning      bool       `json:"is_running"`
}

// AgentReportRequest тело запроса выгрузки данных на сервер (POST /api/v1/connector/agent/report)
type AgentReportRequest struct {
	SerialNumber      string                    `json:"serial_number"`
	Hostname          string                    `json:"hostname"`
	IPAddress         string                    `json:"ip_address,omitempty"`
	MACAddress        string                    `json:"mac_address,omitempty"`
	OSName            string                    `json:"os_name,omitempty"`
	OSVersion         string                    `json:"os_version,omitempty"`
	CPU               string                    `json:"cpu,omitempty"`
	RAM_MB            int                       `json:"ram_mb,omitempty"`
	InstalledSoftware []AgentSoftwareReportItem `json:"installed_software"`
}

// ToAgentReportRequest конвертирует внутренний ScanReport в формат API бэкенда
func (r *ScanReport) ToAgentReportRequest() AgentReportRequest {
	swList := make([]AgentSoftwareReportItem, 0, len(r.InstalledSoftware))
	for _, item := range r.InstalledSoftware {
		pub := item.Publisher
		if pub == "<Null>" || pub == "Null" {
			pub = ""
		}
		ver := item.Version
		if ver == "<Null>" || ver == "Null" {
			ver = ""
		}

		path := item.InstallPath
		if path == "" {
			path = item.InstallLocation
		}

		swList = append(swList, AgentSoftwareReportItem{
			DisplayName:    item.DisplayName,
			Publisher:      pub,
			Version:        ver,
			InstallPath:    path,
			BinaryHash:     item.BinaryHash,
			LastLaunchedAt: item.LastLaunchedAt,
			IsRunning:      item.IsRunning,
		})
	}

	return AgentReportRequest{
		SerialNumber:      strings.TrimSpace(r.Machine.SerialNumber),
		Hostname:          strings.TrimSpace(r.Machine.Hostname),
		IPAddress:         r.Machine.IPAddress,
		MACAddress:        r.Machine.MACAddress,
		OSName:            r.Machine.OS,
		OSVersion:         r.Machine.OSVersion,
		CPU:               r.Machine.CPU,
		RAM_MB:            r.Machine.RAM_MB,
		InstalledSoftware: swList,
	}
}

// AgentHeartbeatRequest тело запроса пинга сервера (POST /api/v1/connector/agent/heartbeat)
type AgentHeartbeatRequest struct {
	SerialNumber string `json:"serial_number"`
	Hostname     string `json:"hostname,omitempty"`
}

// AgentHeartbeatResponse ответ от сервера на пинг
type AgentHeartbeatResponse struct {
	Status           string         `json:"status"`
	Recognized       bool           `json:"recognized"`
	EnrollmentStatus string         `json:"enrollment_status,omitempty"`
	CanSendData      bool           `json:"can_send_data"`
	Message          string         `json:"message,omitempty"`
	Commands         []AgentCommand `json:"commands,omitempty"`
}

// AgentRegisterRequest тело запроса первичной регистрации агента (POST /api/v1/connector/agent/register)
type AgentRegisterRequest struct {
	SerialNumber string `json:"serial_number"`
	Hostname     string `json:"hostname"`
	IPAddress    string `json:"ip_address,omitempty"`
	MACAddress   string `json:"mac_address,omitempty"`
	OSName       string `json:"os_name,omitempty"`
	OSVersion    string `json:"os_version,omitempty"`
	CPU          string `json:"cpu,omitempty"`
	RAM_MB       int    `json:"ram_mb,omitempty"`
}

// AgentAuthResponse ответ от сервера на регистрацию или проверку прав
type AgentAuthResponse struct {
	SerialNumber     string    `json:"serial_number"`
	Hostname         string    `json:"hostname"`
	EnrollmentStatus string    `json:"enrollment_status"`
	CanSendData      bool      `json:"can_send_data"`
	Message          string    `json:"message"`
	ServerTime       time.Time `json:"server_time"`
}


// AgentReportResponse ответ от сервера на выгрузку отчёта
type AgentReportResponse struct {
	Success               bool   `json:"success"`
	ComputerID            string `json:"computer_id"`
	TotalSoftwareReported int    `json:"total_software_reported"`
	MatchedCount          int    `json:"matched_count"`
	Error                 string `json:"error,omitempty"`
}

// AgentCommand команда от сервера клиенту
type AgentCommand struct {
	ID        string            `json:"id"`
	Action    string            `json:"action"` // scan, upload, get_file, status
	Args      map[string]string `json:"args,omitempty"`
	CreatedAt time.Time         `json:"created_at,omitempty"`
}

// AgentCommandResult результат выполнения команды
type AgentCommandResult struct {
	ID        string    `json:"id"`
	Action    string    `json:"action"`
	Success   bool      `json:"success"`
	Output    string    `json:"output,omitempty"`
	Error     string    `json:"error,omitempty"`
	Completed time.Time `json:"completed"`
}

// AgentConfig конфигурация клиента-агента
type AgentConfig struct {
	ServerURL                 string `json:"server_url"`
	APIKey                    string `json:"api_key,omitempty"`
	ListenAddr                string `json:"listen_addr"`
	HeartbeatIntervalSec      int    `json:"heartbeat_interval_sec"`
	QuickScanIntervalMin      int    `json:"quick_scan_interval_min"`
	ThoroughScanIntervalHours int    `json:"thorough_scan_interval_hours"`
	EnableRealtimeWatcher     bool   `json:"enable_realtime_watcher"`
	EnableDiskScanner         bool   `json:"enable_disk_scanner"`
	AutoUpload                bool   `json:"auto_upload"`
	CustomSerial              string `json:"custom_serial,omitempty"`
}

// DefaultConfig возвращает конфигурацию по умолчанию
func DefaultConfig() AgentConfig {
	return AgentConfig{
		ServerURL:                 "http://localhost:8000",
		ListenAddr:                "127.0.0.1:8765",
		HeartbeatIntervalSec:      30,
		QuickScanIntervalMin:      60,
		ThoroughScanIntervalHours: 24,
		EnableRealtimeWatcher:     true,
		EnableDiskScanner:         true,
		AutoUpload:                true,
	}
}
