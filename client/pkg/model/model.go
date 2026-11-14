package model

import "time"

// MachineInfo содержит данные об идентифицируемом хосте
type MachineInfo struct {
	SerialNumber string    `json:"serial_number"`
	Hostname     string    `json:"hostname"`
	OS           string    `json:"os"`
	Architecture string    `json:"architecture"`
	ScanTime     time.Time `json:"scan_time"`
}

// SoftwareItem описывает единицу установленного ПО или обнаруженного автономного софта
type SoftwareItem struct {
	SerialNumber     string   `json:"serial_number"`
	DisplayName      string   `json:"display_name"`
	Publisher        string   `json:"publisher"`
	Version          string   `json:"version"`
	InstallLocation  string   `json:"install_location,omitempty"`
	InstallDate      string   `json:"install_date,omitempty"`
	SourceKey        string   `json:"source_key,omitempty"`
	IsRunning        bool     `json:"is_running"`
	MatchedPIDs      []uint32 `json:"matched_pids,omitempty"`
	MatchedProcesses []string `json:"matched_processes,omitempty"`
	IsStandalone     bool     `json:"is_standalone,omitempty"`
}

// ProcessItem описывает запущенный в ОС процесс и результат его соотнесения с ПО
type ProcessItem struct {
	PID              uint32 `json:"pid"`
	Name             string `json:"name"`
	ExePath          string `json:"exe_path,omitempty"`
	ProductName      string `json:"product_name,omitempty"`
	CompanyName      string `json:"company_name,omitempty"`
	FileDescription  string `json:"file_description,omitempty"`
	FileVersion      string `json:"file_version,omitempty"`
	ProductVersion   string `json:"product_version,omitempty"`
	MatchedSoftware  string `json:"matched_software,omitempty"`
	MatchedPublisher string `json:"matched_publisher,omitempty"`
}

// ScanSummary краткая статистика сканирования
type ScanSummary struct {
	TotalInstalled         int `json:"total_installed"`
	TotalRunningProcesses  int `json:"total_running_processes"`
	TotalRunningSoftware   int `json:"total_running_software"`
	TotalStandaloneRunning int `json:"total_standalone_running"`
}

// ScanReport полный отчёт о сканировании машины
type ScanReport struct {
	Machine           MachineInfo    `json:"machine"`
	InstalledSoftware []SoftwareItem `json:"installed_software"`
	RunningProcesses  []ProcessItem  `json:"running_processes"`
	Summary           ScanSummary    `json:"summary"`
}
