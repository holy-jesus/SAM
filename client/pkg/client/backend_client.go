package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"sam-client/pkg/model"
)

// BackendClient клиент для взаимодействия с FastAPI бэкендом SAM
type BackendClient struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// NewBackendClient создает новый экземпляр HTTP клиента к бэкенду
func NewBackendClient(serverURL, apiKey string) *BackendClient {
	cleanURL := strings.TrimRight(serverURL, "/")
	return &BackendClient{
		baseURL: cleanURL,
		apiKey:  apiKey,
		httpClient: &http.Client{
			Timeout: 45 * time.Second,
		},
	}
}

// Register выполняет первичную регистрацию агента в системе (заявка со статусом pending)
func (c *BackendClient) Register(ctx context.Context, req model.AgentRegisterRequest) (*model.AgentAuthResponse, error) {
	endpoint := c.baseURL + "/api/v1/connector/agent/register"

	bodyBytes, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal register request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create http request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send register request to %s: %w", endpoint, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read register response body: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("register failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	var authResp model.AgentAuthResponse
	if err := json.Unmarshal(respBody, &authResp); err != nil {
		return nil, fmt.Errorf("failed to decode register response (%s): %w", string(respBody), err)
	}

	return &authResp, nil
}

// SendHeartbeat отправляет пинг на сервер для фиксации онлайна ПК
func (c *BackendClient) SendHeartbeat(ctx context.Context, req model.AgentHeartbeatRequest) (*model.AgentHeartbeatResponse, error) {
	endpoint := c.baseURL + "/api/v1/connector/agent/heartbeat"

	bodyBytes, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal heartbeat request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create http request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to send heartbeat to %s: %w", endpoint, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("heartbeat failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	var hbResp model.AgentHeartbeatResponse
	if err := json.NewDecoder(resp.Body).Decode(&hbResp); err != nil {
		return nil, fmt.Errorf("failed to decode heartbeat response: %w", err)
	}

	return &hbResp, nil
}

// SendReport отправляет полный инвентаризационный отчёт на сервер одним запросом
func (c *BackendClient) SendReport(ctx context.Context, req model.AgentReportRequest) (*model.AgentReportResponse, error) {
	endpoint := c.baseURL + "/api/v1/connector/agent/report"

	bodyBytes, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal report request: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create http request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	if c.apiKey != "" {
		httpReq.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to upload report to %s: %w", endpoint, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("report upload failed with status %d: %s", resp.StatusCode, string(respBody))
	}

	var repResp model.AgentReportResponse
	if err := json.Unmarshal(respBody, &repResp); err != nil {
		return nil, fmt.Errorf("failed to decode report response (%s): %w", string(respBody), err)
	}

	return &repResp, nil
}
