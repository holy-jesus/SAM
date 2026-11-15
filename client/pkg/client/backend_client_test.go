package client

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"sam-client/pkg/model"
)

func TestBackendClient_SendHeartbeat(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/connector/agent/heartbeat" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var req model.AgentHeartbeatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode req: %v", err)
		}
		if req.SerialNumber != "SN-123" {
			t.Errorf("expected serial SN-123, got %s", req.SerialNumber)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(model.AgentHeartbeatResponse{
			Status:     "ok",
			Recognized: true,
		})
	}))
	defer ts.Close()

	bc := NewBackendClient(ts.URL, "secret-token")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := bc.SendHeartbeat(ctx, model.AgentHeartbeatRequest{
		SerialNumber: "SN-123",
		Hostname:     "HOST-1",
	})
	if err != nil {
		t.Fatalf("SendHeartbeat failed: %v", err)
	}
	if !resp.Recognized || resp.Status != "ok" {
		t.Errorf("unexpected response: %+v", resp)
	}
}

func TestBackendClient_SendReport(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/connector/agent/report" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var req model.AgentReportRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode req: %v", err)
		}
		if req.SerialNumber != "SN-999" || len(req.InstalledSoftware) != 1 {
			t.Errorf("unexpected payload: %+v", req)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(model.AgentReportResponse{
			Success:               true,
			ComputerID:            "uuid-123",
			TotalSoftwareReported: 1,
			MatchedCount:          1,
		})
	}))
	defer ts.Close()

	bc := NewBackendClient(ts.URL, "")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := bc.SendReport(ctx, model.AgentReportRequest{
		SerialNumber: "SN-999",
		Hostname:     "HOST-999",
		InstalledSoftware: []model.AgentSoftwareReportItem{
			{
				DisplayName: "Google Chrome",
				Publisher:   "Google LLC",
				Version:     "124.0",
			},
		},
	})
	if err != nil {
		t.Fatalf("SendReport failed: %v", err)
	}
	if !resp.Success || resp.MatchedCount != 1 {
		t.Errorf("unexpected response: %+v", resp)
	}
}

func TestBackendClient_Register(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/connector/agent/register" {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		var req model.AgentRegisterRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Fatalf("failed to decode req: %v", err)
		}
		if req.SerialNumber != "SN-NEW-1" {
			t.Errorf("expected serial SN-NEW-1, got %s", req.SerialNumber)
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(model.AgentAuthResponse{
			SerialNumber:     req.SerialNumber,
			Hostname:         req.Hostname,
			EnrollmentStatus: "pending",
			CanSendData:      false,
			Message:          "Заявка на добавление ПК принята",
			ServerTime:       time.Now(),
		})
	}))
	defer ts.Close()

	bc := NewBackendClient(ts.URL, "")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	resp, err := bc.Register(ctx, model.AgentRegisterRequest{
		SerialNumber: "SN-NEW-1",
		Hostname:     "HOST-NEW-1",
		OSName:       "Windows 11 Pro",
		RAM_MB:       16384,
	})
	if err != nil {
		t.Fatalf("Register failed: %v", err)
	}
	if resp.EnrollmentStatus != "pending" || resp.CanSendData {
		t.Errorf("unexpected auth response: %+v", resp)
	}
}

