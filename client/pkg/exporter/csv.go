package exporter

import (
	"encoding/csv"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"

	"sam-client/pkg/model"
)

// ExportStandardCSV записывает CSV в точном соответствии с форматом "Пример дампа с компов.xlsx"
// Заголовок: COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION
func ExportStandardCSV(w io.Writer, items []model.SoftwareItem) error {
	writer := csv.NewWriter(w)
	defer writer.Flush()

	header := []string{
		"COMPUTERS.SERIAL_NUMBER",
		"SOFTWARE.DISPLAYNAME",
		"SOFTWARE.PUBLISHER",
		"SOFTWARE.VERSION",
	}
	if err := writer.Write(header); err != nil {
		return fmt.Errorf("failed to write csv header: %w", err)
	}

	for _, item := range items {
		pub := item.Publisher
		if pub == "" {
			pub = "<Null>"
		}
		ver := item.Version
		if ver == "" {
			ver = "<Null>"
		}

		row := []string{
			item.SerialNumber,
			item.DisplayName,
			pub,
			ver,
		}
		if err := writer.Write(row); err != nil {
			return fmt.Errorf("failed to write csv record: %w", err)
		}
	}

	return nil
}

// ExportExtendedCSV записывает расширенный CSV с флагом активности и связанными процессами
func ExportExtendedCSV(w io.Writer, items []model.SoftwareItem) error {
	writer := csv.NewWriter(w)
	defer writer.Flush()

	header := []string{
		"COMPUTERS.SERIAL_NUMBER",
		"SOFTWARE.DISPLAYNAME",
		"SOFTWARE.PUBLISHER",
		"SOFTWARE.VERSION",
		"IS_RUNNING",
		"PIDS",
		"PROCESS_NAMES",
		"IS_STANDALONE",
	}
	if err := writer.Write(header); err != nil {
		return fmt.Errorf("failed to write extended csv header: %w", err)
	}

	for _, item := range items {
		pub := item.Publisher
		if pub == "" {
			pub = "<Null>"
		}
		ver := item.Version
		if ver == "" {
			ver = "<Null>"
		}

		var pidStrs []string
		for _, pid := range item.MatchedPIDs {
			pidStrs = append(pidStrs, strconv.FormatUint(uint64(pid), 10))
		}

		isRunningStr := "FALSE"
		if item.IsRunning {
			isRunningStr = "TRUE"
		}

		isStandaloneStr := "FALSE"
		if item.IsStandalone {
			isStandaloneStr = "TRUE"
		}

		row := []string{
			item.SerialNumber,
			item.DisplayName,
			pub,
			ver,
			isRunningStr,
			strings.Join(pidStrs, ";"),
			strings.Join(item.MatchedProcesses, ";"),
			isStandaloneStr,
		}
		if err := writer.Write(row); err != nil {
			return fmt.Errorf("failed to write extended csv record: %w", err)
		}
	}

	return nil
}

// ExportProcessesCSV записывает список всех обнаруженных процессов и результат их сопоставления
func ExportProcessesCSV(w io.Writer, serialNumber string, procs []model.ProcessItem) error {
	writer := csv.NewWriter(w)
	defer writer.Flush()

	header := []string{
		"COMPUTERS.SERIAL_NUMBER",
		"PID",
		"PROCESS_NAME",
		"EXECUTABLE_PATH",
		"PRODUCT_NAME",
		"COMPANY_NAME",
		"FILE_VERSION",
		"MATCHED_SOFTWARE",
	}
	if err := writer.Write(header); err != nil {
		return fmt.Errorf("failed to write processes csv header: %w", err)
	}

	for _, p := range procs {
		row := []string{
			serialNumber,
			strconv.FormatUint(uint64(p.PID), 10),
			p.Name,
			p.ExePath,
			p.ProductName,
			p.CompanyName,
			p.FileVersion,
			p.MatchedSoftware,
		}
		if err := writer.Write(row); err != nil {
			return fmt.Errorf("failed to write process csv record: %w", err)
		}
	}

	return nil
}

// SaveCSVToFile сохраняет стандартный или расширенный CSV в указанный файл
func SaveCSVToFile(filePath string, items []model.SoftwareItem, extended bool) error {
	var file *os.File
	var err error

	if filePath == "-" {
		file = os.Stdout
	} else {
		file, err = os.Create(filePath)
		if err != nil {
			return fmt.Errorf("failed to create file %s: %w", filePath, err)
		}
		defer file.Close()
	}

	if extended {
		return ExportExtendedCSV(file, items)
	}
	return ExportStandardCSV(file, items)
}

// SaveProcessesCSVToFile сохраняет дамп процессов в отдельный файл
func SaveProcessesCSVToFile(filePath string, serialNumber string, procs []model.ProcessItem) error {
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Errorf("failed to create file %s: %w", filePath, err)
	}
	defer file.Close()

	return ExportProcessesCSV(file, serialNumber, procs)
}
