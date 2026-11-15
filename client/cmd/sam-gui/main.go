package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"runtime"
	"time"
)

func main() {
	var (
		agentAddr string
		noBrowser bool
	)

	flag.StringVar(&agentAddr, "addr", "127.0.0.1:8765", "Адрес работающего демона агента SAM")
	flag.BoolVar(&noBrowser, "no-browser", false, "Не открывать веб-панель в браузере автоматически")
	flag.Parse()

	url := fmt.Sprintf("http://%s/api/v1/status", agentAddr)
	guiURL := fmt.Sprintf("http://%s/gui", agentAddr)

	fmt.Println("==================================================")
	fmt.Println("    SAM Agent Manager (GUI & Console Controller)   ")
	fmt.Println("==================================================")
	fmt.Printf("[*] Проверка соединения с агентом на %s...\n", agentAddr)

	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(url)

	if err != nil {
		fmt.Printf("[!] Агент не отвечает на %s\n", agentAddr)
		fmt.Println("[*] Попытка автоматического запуска демона sam-agent в фоне...")

		agentBin := "sam-agent"
		if runtime.GOOS == "windows" {
			agentBin = "sam-agent.exe"
		}

		cmd := exec.Command(agentBin, "-daemon", "-listen", agentAddr)
		if err := cmd.Start(); err != nil {
			fmt.Printf("[!] Не удалось запустить %s: %v\n", agentBin, err)
			fmt.Println("[*] Убедитесь, что служба SAM запущена или выполните: sam-agent -daemon")
		} else {
			fmt.Println("[+] Демон агента успешно запущен в фоновом режиме.")
			time.Sleep(1500 * time.Millisecond)
		}
	} else {
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		var status map[string]interface{}
		if err := json.Unmarshal(body, &status); err == nil {
			fmt.Printf("[+] Агент активен (онлайн)!\n")
			fmt.Printf("    - Хост:            %v\n", status["hostname"])
			fmt.Printf("    - Серийный номер:  %v\n", status["serial_number"])
			fmt.Printf("    - IP:              %v\n", status["ip_address"])
			fmt.Printf("    - Установлено ПО:  %v\n", status["total_installed"])
			fmt.Printf("    - Запущено ПО:     %v\n", status["total_running_software"])
			fmt.Printf("    - Процессов в ОС:  %v\n", status["total_running_processes"])
			fmt.Printf("    - Сервер SAM:      %v\n", status["server_url"])
			fmt.Printf("    - Последняя выгрузка: %v (%v)\n", status["last_upload_time"], status["last_upload_status"])
		}
	}

	if !noBrowser {
		fmt.Printf("[*] Открытие графической панели управления: %s\n", guiURL)
		openBrowser(guiURL)
	}

	fmt.Println("\nДоступные быстрые команды:")
	fmt.Printf("  1. Браузерный GUI:    %s\n", guiURL)
	fmt.Printf("  2. Скачать CSV дамп:  http://%s/api/v1/export/csv\n", agentAddr)
	fmt.Printf("  3. Скачать JSON дамп: http://%s/api/v1/export/json\n", agentAddr)
	fmt.Printf("  4. Запуск сканирования: curl -X POST http://%s/api/v1/scan\n", agentAddr)
	fmt.Printf("  5. Выгрузка на сервер:  curl -X POST http://%s/api/v1/upload\n", agentAddr)
	fmt.Println("==================================================")
}

func openBrowser(targetURL string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", targetURL)
	case "darwin":
		cmd = exec.Command("open", targetURL)
	default:
		cmd = exec.Command("xdg-open", targetURL)
	}
	_ = cmd.Start()
}
