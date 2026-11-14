package exporter

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"sam-client/pkg/model"
)

// ExportJSON сериализует полный отчёт о сканировании в формат JSON
func ExportJSON(w io.Writer, report *model.ScanReport, pretty bool) error {
	encoder := json.NewEncoder(w)
	if pretty {
		encoder.SetIndent("", "  ")
	}
	if err := encoder.Encode(report); err != nil {
		return fmt.Errorf("failed to encode json: %w", err)
	}
	return nil
}

// SaveJSONToFile сохраняет отчёт в JSON файл
func SaveJSONToFile(filePath string, report *model.ScanReport, pretty bool) error {
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

	return ExportJSON(file, report, pretty)
}
