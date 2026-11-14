package matcher

import (
	"testing"

	"sam-client/pkg/model"
)

func TestCorrelatePathMatch(t *testing.T) {
	installed := []model.SoftwareItem{
		{
			SerialNumber:    "TEST-SN-1",
			DisplayName:     "Google Chrome",
			Publisher:       "Google LLC",
			Version:         "124.0.0.0",
			InstallLocation: `C:\Program Files\Google\Chrome\Application`,
		},
		{
			SerialNumber:    "TEST-SN-1",
			DisplayName:     "7-Zip 19.00 (x64 edition)",
			Publisher:       "Igor Pavlov",
			Version:         "19.00.00.0",
			InstallLocation: `C:\Program Files\7-Zip`,
		},
	}

	processes := []model.ProcessItem{
		{
			PID:     1234,
			Name:    "chrome.exe",
			ExePath: `C:\Program Files\Google\Chrome\Application\chrome.exe`,
		},
	}

	updatedInstalled, updatedProcesses := Correlate(installed, processes, false, "TEST-SN-1")

	if !updatedInstalled[0].IsRunning {
		t.Errorf("expected Chrome to be running")
	}
	if len(updatedInstalled[0].MatchedPIDs) != 1 || updatedInstalled[0].MatchedPIDs[0] != 1234 {
		t.Errorf("expected PID 1234, got %v", updatedInstalled[0].MatchedPIDs)
	}
	if updatedInstalled[1].IsRunning {
		t.Errorf("expected 7-Zip to NOT be running")
	}
	if updatedProcesses[0].MatchedSoftware != "Google Chrome" {
		t.Errorf("expected process matched software to be 'Google Chrome', got %s", updatedProcesses[0].MatchedSoftware)
	}
}

func TestCorrelateAliasMatch(t *testing.T) {
	installed := []model.SoftwareItem{
		{
			SerialNumber: "TEST-SN-2",
			DisplayName:  "Visual Studio Code",
			Publisher:    "Microsoft Corporation",
			Version:      "1.88.0",
		},
	}

	processes := []model.ProcessItem{
		{
			PID:  5678,
			Name: "code.exe",
		},
	}

	updatedInstalled, updatedProcesses := Correlate(installed, processes, false, "TEST-SN-2")

	if !updatedInstalled[0].IsRunning {
		t.Errorf("expected VS Code to be running via alias")
	}
	if updatedProcesses[0].MatchedSoftware != "Visual Studio Code" {
		t.Errorf("expected matched software 'Visual Studio Code', got %s", updatedProcesses[0].MatchedSoftware)
	}
}

func TestCorrelateStandalone(t *testing.T) {
	installed := []model.SoftwareItem{}

	processes := []model.ProcessItem{
		{
			PID:         9999,
			Name:        "custom_tool.exe",
			ExePath:     `C:\Users\User\Downloads\custom_tool.exe`,
			ProductName: "My Custom Tool",
			CompanyName: "Acme Corp",
			FileVersion: "2.1.0",
		},
	}

	updatedInstalled, _ := Correlate(installed, processes, true, "TEST-SN-3")

	if len(updatedInstalled) != 1 {
		t.Fatalf("expected 1 standalone item, got %d", len(updatedInstalled))
	}
	item := updatedInstalled[0]
	if item.DisplayName != "My Custom Tool" || item.Publisher != "Acme Corp" || item.Version != "2.1.0" {
		t.Errorf("unexpected item: %+v", item)
	}
	if !item.IsRunning || !item.IsStandalone {
		t.Errorf("item should be running and standalone")
	}
}
