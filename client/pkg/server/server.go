package server

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"

	"sam-client/pkg/exporter"
	"sam-client/pkg/model"
)

// AgentController интерфейс управления демоном агента
type AgentController interface {
	GetStatus() map[string]interface{}
	TriggerScan(thorough bool) (*model.ScanReport, error)
	TriggerUpload(ctx context.Context) (*model.AgentReportResponse, error)
	GetLatestReport() *model.ScanReport
	GetConfig() model.AgentConfig
	UpdateConfig(cfg model.AgentConfig) error
}

// HTTPServer локальный веб-сервер управления агентом
type HTTPServer struct {
	listenAddr string
	controller AgentController
	server     *http.Server
	mu         sync.RWMutex
}

// NewHTTPServer создает новый локальный сервер управления
func NewHTTPServer(listenAddr string, ctrl AgentController) *HTTPServer {
	return &HTTPServer{
		listenAddr: listenAddr,
		controller: ctrl,
	}
}

// Start запускает HTTP-сервер
func (s *HTTPServer) Start() error {
	mux := http.NewServeMux()

	// API маршруты
	mux.HandleFunc("/api/v1/status", s.handleStatus)
	mux.HandleFunc("/api/v1/scan", s.handleScan)
	mux.HandleFunc("/api/v1/upload", s.handleUpload)
	mux.HandleFunc("/api/v1/report", s.handleReport)
	mux.HandleFunc("/api/v1/export/csv", s.handleExportCSV)
	mux.HandleFunc("/api/v1/export/json", s.handleExportJSON)
	mux.HandleFunc("/api/v1/processes", s.handleProcesses)
	mux.HandleFunc("/api/v1/file", s.handleGetFile)
	mux.HandleFunc("/api/v1/config", s.handleConfig)

	// Встроенный GUI интерфейс
	mux.HandleFunc("/", s.handleGUI)
	mux.HandleFunc("/gui", s.handleGUI)

	s.server = &http.Server{
		Addr:         s.listenAddr,
		Handler:      corsMiddleware(mux),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
	}

	return s.server.ListenAndServe()
}

// Stop останавливает HTTP-сервер
func (s *HTTPServer) Stop(ctx context.Context) error {
	if s.server != nil {
		return s.server.Shutdown(ctx)
	}
	return nil
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *HTTPServer) handleStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	status := s.controller.GetStatus()
	writeJSON(w, http.StatusOK, status)
}

func (s *HTTPServer) handleScan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Thorough bool `json:"thorough"`
	}
	_ = json.NewDecoder(r.Body).Decode(&req)

	report, err := s.controller.TriggerScan(req.Thorough)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]interface{}{
			"success": false,
			"error":   err.Error(),
		})
		return
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"summary": report.Summary,
		"machine": report.Machine,
	})
}

func (s *HTTPServer) handleUpload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 60*time.Second)
	defer cancel()

	resp, err := s.controller.TriggerUpload(ctx)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]interface{}{
			"success": false,
			"error":   err.Error(),
		})
		return
	}

	writeJSON(w, http.StatusOK, resp)
}

func (s *HTTPServer) handleReport(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	report := s.controller.GetLatestReport()
	if report == nil {
		http.Error(w, "No scan report available yet", http.StatusNotFound)
		return
	}

	writeJSON(w, http.StatusOK, report)
}

func (s *HTTPServer) handleExportCSV(w http.ResponseWriter, r *http.Request) {
	report := s.controller.GetLatestReport()
	if report == nil {
		http.Error(w, "No scan report available yet", http.StatusNotFound)
		return
	}

	extended := r.URL.Query().Get("extended") == "true"
	filename := fmt.Sprintf("software_dump_%s.csv", report.Machine.SerialNumber)

	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	var buf bytes.Buffer
	if extended {
		_ = exporter.ExportExtendedCSV(&buf, report.InstalledSoftware)
	} else {
		_ = exporter.ExportStandardCSV(&buf, report.InstalledSoftware)
	}

	_, _ = w.Write(buf.Bytes())
}

func (s *HTTPServer) handleExportJSON(w http.ResponseWriter, r *http.Request) {
	report := s.controller.GetLatestReport()
	if report == nil {
		http.Error(w, "No scan report available yet", http.StatusNotFound)
		return
	}

	filename := fmt.Sprintf("software_dump_%s.json", report.Machine.SerialNumber)
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filename))

	var buf bytes.Buffer
	_ = exporter.ExportJSON(&buf, report, true)
	_, _ = w.Write(buf.Bytes())
}

func (s *HTTPServer) handleProcesses(w http.ResponseWriter, r *http.Request) {
	report := s.controller.GetLatestReport()
	if report == nil {
		http.Error(w, "No data available", http.StatusNotFound)
		return
	}
	writeJSON(w, http.StatusOK, report.RunningProcesses)
}

// handleGetFile безопасно отдает файл по запросу сервера (Requirement 22: получение файла)
func (s *HTTPServer) handleGetFile(w http.ResponseWriter, r *http.Request) {
	filePath := r.URL.Query().Get("path")
	if filePath == "" {
		http.Error(w, "Query parameter 'path' is required", http.StatusBadRequest)
		return
	}

	cleanPath := filepath.Clean(filePath)
	fi, err := os.Stat(cleanPath)
	if err != nil {
		http.Error(w, fmt.Sprintf("File not found or inaccessible: %v", err), http.StatusNotFound)
		return
	}

	if fi.IsDir() {
		http.Error(w, "Path is a directory, not a file", http.StatusBadRequest)
		return
	}

	// Ограничение максимального размера читаемого файла (100 MB)
	if fi.Size() > 100*1024*1024 {
		http.Error(w, "File is too large (> 100 MB)", http.StatusRequestEntityTooLarge)
		return
	}

	f, err := os.Open(cleanPath)
	if err != nil {
		http.Error(w, fmt.Sprintf("Failed to open file: %v", err), http.StatusInternalServerError)
		return
	}
	defer f.Close()

	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment; filename=\"%s\"", filepath.Base(cleanPath)))
	w.Header().Set("Content-Type", "application/octet-stream")
	_, _ = io.Copy(w, f)
}

func (s *HTTPServer) handleConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		writeJSON(w, http.StatusOK, s.controller.GetConfig())
		return
	}

	if r.Method == http.MethodPost {
		var cfg model.AgentConfig
		if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if err := s.controller.UpdateConfig(cfg); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, http.StatusOK, map[string]interface{}{"success": true})
		return
	}

	http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

// handleGUI отдаёт встроенную HTML-панель управления агентом
func (s *HTTPServer) handleGUI(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" && r.URL.Path != "/gui" {
		http.NotFound(w, r)
		return
	}

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write([]byte(embeddedHTMLDashboard))
}

const embeddedHTMLDashboard = `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAM Agent — Панель Управления</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }
    h1 { font-size: 24px; font-weight: 700; display: flex; align-items: center; gap: 10px; }
    .badge {
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(16, 185, 129, 0.2);
      color: var(--success);
      font-weight: 600;
    }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }
    .card-title { font-size: 13px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; margin-bottom: 8px; }
    .card-value { font-size: 24px; font-weight: 700; }
    .actions { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }
    button {
      background: var(--primary);
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 8px;
      font-weight: 600;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    button:hover { background: var(--primary-hover); transform: translateY(-1px); }
    button.secondary { background: #334155; }
    button.secondary:hover { background: #475569; }
    button.success { background: var(--success); }
    button.success:hover { background: #059669; }
    .search-box {
      width: 100%;
      padding: 10px 14px;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 14px;
      margin-bottom: 16px;
    }
    .table-container {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow-x: auto;
    }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
    th {
      background: #1e293b;
      padding: 12px 16px;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
    }
    td { padding: 12px 16px; border-bottom: 1px solid var(--border); }
    tr:last-child td { border-bottom: none; }
    tr:hover { background: rgba(255, 255, 255, 0.02); }
    .pill {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
    }
    .pill-running { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .pill-stopped { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }
    .pill-standalone { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    #msg { padding: 10px; border-radius: 8px; margin-bottom: 16px; display: none; font-size: 13px; }
    .code-hash { font-family: monospace; font-size: 11px; color: #cbd5e1; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🛡️ SAM Client Agent <span class="badge" id="status-badge">Работает (Онлайн)</span></h1>
        <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;" id="host-subinfo">Загрузка данных хоста...</p>
      </div>
      <div>
        <a href="/api/v1/export/csv" style="text-decoration:none;"><button class="secondary">📥 Скачать CSV</button></a>
        <a href="/api/v1/export/json" style="text-decoration:none;"><button class="secondary">📄 Скачать JSON</button></a>
      </div>
    </header>

    <div id="msg"></div>

    <div class="grid">
      <div class="card">
        <div class="card-title">Установленного ПО</div>
        <div class="card-value" id="stat-installed">-</div>
      </div>
      <div class="card">
        <div class="card-title">Запущенных программ</div>
        <div class="card-value" style="color: var(--success);" id="stat-running">-</div>
      </div>
      <div class="card">
        <div class="card-title">Процессов в ОС</div>
        <div class="card-value" id="stat-procs">-</div>
      </div>
      <div class="card">
        <div class="card-title">Статус выгрузки на сервер</div>
        <div class="card-value" style="font-size: 16px; margin-top: 6px;" id="stat-upload">Не выгружалось</div>
      </div>
    </div>

    <div class="actions">
      <button onclick="triggerScan(false)">🔄 Быстрое сканирование</button>
      <button onclick="triggerScan(true)" class="secondary">🔍 Тщательное сканирование диска</button>
      <button onclick="triggerUpload()" class="success">🚀 Выгрузить на сервер SAM</button>
    </div>

    <input type="text" class="search-box" id="search" placeholder="Поиск по названию ПО, издателю или пути..." oninput="filterTable()">

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>Название ПО</th>
            <th>Издатель</th>
            <th>Версия</th>
            <th>Статус</th>
            <th>Хэш бинарника (SHA-256)</th>
            <th>Последний запуск</th>
          </tr>
        </thead>
        <tbody id="software-rows">
          <tr><td colspan="6" style="text-align:center; padding: 24px; color: var(--text-muted);">Загрузка установленного ПО...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <script>
    let softwareList = [];

    async function loadData() {
      try {
        const resStatus = await fetch('/api/v1/status');
        const st = await resStatus.json();
        document.getElementById('host-subinfo').innerText = 
          'Хост: ' + (st.hostname || '-') + ' | SN: ' + (st.serial_number || '-') + ' | IP: ' + (st.ip_address || '-') + ' | Сервер: ' + (st.server_url || '-');
        
        document.getElementById('stat-installed').innerText = st.total_installed || 0;
        document.getElementById('stat-running').innerText = st.total_running_software || 0;
        document.getElementById('stat-procs').innerText = st.total_running_processes || 0;
        if (st.last_upload_time) {
          document.getElementById('stat-upload').innerText = 'Успешно: ' + new Date(st.last_upload_time).toLocaleTimeString() + ' (сопоставлено: ' + (st.matched_count || 0) + ')';
        }

        const resRep = await fetch('/api/v1/report');
        if (resRep.ok) {
          const rep = await resRep.json();
          softwareList = rep.installed_software || [];
          renderTable(softwareList);
        }
      } catch (e) {
        console.error(e);
      }
    }

    function renderTable(items) {
      const tbody = document.getElementById('software-rows');
      if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 24px;">ПО не найдено</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(sw => {
        let statusBadge = sw.is_running 
          ? '<span class="pill pill-running">Запущено</span>' 
          : '<span class="pill pill-stopped">Остановлено</span>';
        if (sw.is_standalone) {
          statusBadge += ' <span class="pill pill-standalone">Standalone</span>';
        }
        const lastRun = sw.last_launched_at ? new Date(sw.last_launched_at).toLocaleString() : '-';
        const hash = sw.binary_hash ? '<span class="code-hash">' + sw.binary_hash.substring(0, 16) + '...</span>' : '-';

        return '<tr>' +
          '<td><strong>' + escapeHtml(sw.display_name) + '</strong>' + 
            (sw.install_path ? '<div style="font-size:11px; color:#64748b;">' + escapeHtml(sw.install_path) + '</div>' : '') +
          '</td>' +
          '<td>' + escapeHtml(sw.publisher || '<Null>') + '</td>' +
          '<td>' + escapeHtml(sw.version || '<Null>') + '</td>' +
          '<td>' + statusBadge + '</td>' +
          '<td>' + hash + '</td>' +
          '<td>' + lastRun + '</td>' +
        '</tr>';
      }).join('');
    }

    function filterTable() {
      const q = document.getElementById('search').value.toLowerCase();
      const filtered = softwareList.filter(s => 
        (s.display_name && s.display_name.toLowerCase().includes(q)) ||
        (s.publisher && s.publisher.toLowerCase().includes(q)) ||
        (s.install_path && s.install_path.toLowerCase().includes(q))
      );
      renderTable(filtered);
    }

    function showMsg(text, isError) {
      const el = document.getElementById('msg');
      el.style.display = 'block';
      el.style.background = isError ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)';
      el.style.color = isError ? '#f87171' : '#34d399';
      el.innerText = text;
      setTimeout(() => { el.style.display = 'none'; }, 5000);
    }

    async function triggerScan(thorough) {
      showMsg('Запущено сканирование (' + (thorough ? 'тщательное' : 'быстрое') + ')...', false);
      const res = await fetch('/api/v1/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thorough: thorough })
      });
      const data = await res.json();
      if (data.success) {
        showMsg('Сканирование успешно завершено! Найдено ПО: ' + data.summary.total_installed, false);
        loadData();
      } else {
        showMsg('Ошибка сканирования: ' + data.error, true);
      }
    }

    async function triggerUpload() {
      showMsg('Отправка инвентаризационного отчёта на сервер SAM...', false);
      try {
        const res = await fetch('/api/v1/upload', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showMsg('Отчёт успешно выгружен на сервер! Распознано софта: ' + data.matched_count + ' из ' + data.total_software_reported, false);
          loadData();
        } else {
          showMsg('Ошибка выгрузки: ' + (data.error || 'сервер вернул ошибку'), true);
        }
      } catch (e) {
        showMsg('Ошибка подключения к серверу: ' + e, true);
      }
    }

    function escapeHtml(s) {
      if (!s) return '';
      return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    loadData();
    setInterval(loadData, 10000);
  </script>
</body>
</html>`
