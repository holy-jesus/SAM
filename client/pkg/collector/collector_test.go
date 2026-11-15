package collector

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestCalculateFileSHA256(t *testing.T) {
	tmpDir := t.TempDir()
	testFile := filepath.Join(tmpDir, "test.bin")
	content := []byte("hello world sam agent")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}

	hash1, err := CalculateFileSHA256(testFile)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(hash1) != 64 {
		t.Errorf("expected 64 char hex string, got %d (%s)", len(hash1), hash1)
	}

	// Проверяем кэширование
	hash2, err := CalculateFileSHA256(testFile)
	if err != nil {
		t.Fatalf("unexpected error on second call: %v", err)
	}
	if hash1 != hash2 {
		t.Errorf("cached hash mismatch: %s != %s", hash1, hash2)
	}
}

func TestFindMainExecutable(t *testing.T) {
	tmpDir := t.TempDir()
	appDir := filepath.Join(tmpDir, "MyCoolApp")
	_ = os.MkdirAll(appDir, 0755)

	exe1 := filepath.Join(appDir, "unins000.exe")
	exe2 := filepath.Join(appDir, "MyCoolApp.exe")
	_ = os.WriteFile(exe1, []byte("uninstall"), 0755)
	_ = os.WriteFile(exe2, []byte("app"), 0755)

	found := FindMainExecutable(appDir, "My Cool App")
	if filepath.Base(found) != "MyCoolApp.exe" {
		t.Errorf("expected MyCoolApp.exe, got %s", found)
	}
}

func TestLastLaunchedRecord(t *testing.T) {
	p := "/test/path/app.exe"
	now := time.Now().UTC()
	RecordProcessExecution(p, now)

	ts := GetLastLaunchedTime(p, false)
	if ts == nil {
		t.Fatalf("expected non-nil timestamp")
	}
	if !ts.Equal(now) {
		t.Errorf("expected %v, got %v", now, *ts)
	}
}

func TestCollectIntegration(t *testing.T) {
	opts := Options{
		IncludeStandalone: true,
		Thorough:          false,
		CustomSerial:      "TEST-SERIAL-42",
		Verbose:           false,
	}

	report, err := Collect(opts)
	if err != nil {
		t.Fatalf("Collect failed: %v", err)
	}

	if report.Machine.SerialNumber != "TEST-SERIAL-42" {
		t.Errorf("expected serial TEST-SERIAL-42, got %s", report.Machine.SerialNumber)
	}
	if len(report.InstalledSoftware) == 0 {
		t.Errorf("expected installed software to be non-empty")
	}
	if report.Summary.TotalInstalled != len(report.InstalledSoftware) {
		t.Errorf("summary mismatch: %d != %d", report.Summary.TotalInstalled, len(report.InstalledSoftware))
	}
}
