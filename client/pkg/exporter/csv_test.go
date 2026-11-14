package exporter

import (
	"bytes"
	"strings"
	"testing"

	"sam-client/pkg/model"
)

func TestExportStandardCSV(t *testing.T) {
	items := []model.SoftwareItem{
		{
			SerialNumber: "G69ZD5J",
			DisplayName:  "Google Chrome",
			Publisher:    "Google LLC",
			Version:      "67.208.108",
		},
		{
			SerialNumber: "B1RG0S2",
			DisplayName:  "WinRAR archiver",
			Publisher:    "", // should output <Null>
			Version:      "", // should output <Null>
		},
	}

	var buf bytes.Buffer
	err := ExportStandardCSV(&buf, items)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	lines := strings.Split(strings.TrimSpace(buf.String()), "\n")
	if len(lines) != 3 {
		t.Fatalf("expected 3 lines (1 header + 2 rows), got %d", len(lines))
	}

	if lines[0] != "COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION" {
		t.Errorf("unexpected header: %s", lines[0])
	}
	if lines[1] != "G69ZD5J,Google Chrome,Google LLC,67.208.108" {
		t.Errorf("unexpected row 1: %s", lines[1])
	}
	if lines[2] != "B1RG0S2,WinRAR archiver,<Null>,<Null>" {
		t.Errorf("unexpected row 2: %s", lines[2])
	}
}
