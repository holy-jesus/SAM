# SAM Windows Agent (Go) & Service Manager

Высокопроизводительный клиент-агент для системы **Software Asset Management (SAM)**, разработанный на языке **Go**. Агент предназначен для непрерывного мониторинга рабочих станций, сбора инвентаризационных данных об установленном ПО, запущенных процессах, вычисления контрольных сумм исполняемых файлов (SHA-256), фиксации дат последних запусков программ и автоматической выгрузки отчётов на центральный сервер SAM (FastAPI).

---

## 🌟 Ключевые возможности

1. **Идентификация компьютера и оборудования**:
   - Чтение аппаратного серийного номера BIOS/материнской платы (`HKLM\HARDWARE\DESCRIPTION\System\BIOS\SystemSerialNumber`, резервные механизмы: PowerShell CIM/WMI `Win32_BIOS.SerialNumber`, `wmic`, `MachineGuid`).
   - Сбор имени хоста (`Hostname`), активного IP-адреса и MAC-адреса сетевого интерфейса.
   - Определение точной версии Windows (`ProductName`, `DisplayVersion`, `BuildNumber`).
   - Сбор характеристик процессора (`CPU`) и объёма оперативной памяти (`RAM_MB`).

2. **Источники обнаружения ПО**:
   - **Системный реестр Windows**:
     - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` (64-bit)
     - `HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall` (32-bit)
     - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall` (User scope)
   - **Тщательное сканирование диска (`-thorough`)**:
     - Сканирование `Program Files`, `Program Files (x86)`, `%LocalAppData%\Programs`, `%AppData%`.
     - Обнаружение автономных и портативных программ, не зарегистрированных в реестре.
   - **Запущенные процессы**:
     - Win32 Toolhelp32 Snapshot API (`CreateToolhelp32Snapshot`).
     - Чтение метаданных PE-заголовков через `version.dll` (`ProductName`, `CompanyName`, `FileDescription`, `FileVersion`).

3. **Сбор даты последнего запуска бинарника (для выявления «зомби-софта»)**:
   - Отслеживание активных процессов в реальном времени.
   - Чтение артефактов Windows Prefetch (`C:\Windows\Prefetch\*.pf`).
   - Анализ времени последней модификации и обращения к файлу.

4. **Вычисление SHA-256 хэшей исполняемых файлов**:
   - Потоковое вычисление контрольных сумм с потокобезопасным кэшированием по `(mtime, size)`.

5. **Мониторинг в реальном времени (Real-Time Watcher)**:
   - **Наблюдатель за процессами**: мгновенная фиксация запуска новых процессов в ОС.
   - **Наблюдатель за реестром**: регистрация системных уведомлений через Win32 API `RegNotifyChangeKeyValue` для немедленного реагирования на установку/удаление программ.

6. **Связь с центральным сервером SAM**:
   - Клиент сам инициирует исходящие соединения к бэкенду (работает за NAT / Firewall):
     - `POST /api/v1/connector/agent/heartbeat` (периодический пинг онлайна каждые 30 секунд).
     - `POST /api/v1/connector/agent/report` (полная выгрузка инвентаризации одним запросом).

7. **Локальный HTTP сервер управления и встроенный GUI**:
   - Агент запускает локальный REST API (`http://127.0.0.1:8765`):
     - `GET /` или `/gui` — современная веб-панель управления со списком ПО, статусом и кнопками ручного запуска.
     - `GET /api/v1/status` — состояние демона, хоста и последней выгрузки.
     - `POST /api/v1/scan` — запуск немедленного сканирования (`{"thorough": true/false}`).
     - `POST /api/v1/upload` — запуск немедленной отправки отчёта на сервер.
     - `GET /api/v1/export/csv` — скачивание дампа в формате CSV.
     - `GET /api/v1/export/json` — скачивание дампа в формате JSON.
     - `GET /api/v1/file?path=...` — безопасное чтение файла с хоста по запросу администратора.

8. **Управление системной службой Windows**:
   - Регистрация, запуск, остановка и удаление службы Windows Service (`sam-agent.exe -service install|start|stop|uninstall`).
   - Автоматический перезапуск при сбоях.

9. **Отдельный GUI менеджер (`sam-gui.exe`)**:
   - Вынесен в отдельный исполняемый файл для удобной демонстрации. Позволяет управлять демоном или подключаться к нему без изменения самого сервиса.

10. **NSIS Installer**:
    - Готовый скрипт `installer/installer.nsi` для сборки установщика Windows с интеграцией в Service Control Manager.

---

## 🛠 Сборка

Клиент использует стандартную библиотеку Go и Win32 API (`advapi32.dll`, `kernel32.dll`, `version.dll`) и **собирается полностью автономно без внешних зависимостей**.

### Сборка под Windows (из Linux / macOS / Windows):
```bash
cd client
make build-windows
```
Скомпилированные бинарники будут помещены в `client/bin/`:
- `sam-agent.exe` — основной агент (CLI, демон и служба).
- `sam-gui.exe` — графический менеджер для управления демоном.

### Сборка под Linux (для локальной разработки и тестирования):
```bash
make build-linux
```
Бинарники: `client/bin/sam-agent` и `client/bin/sam-gui`.

### Запуск тестов:
```bash
make test
```

### Сборка инсталлятора NSIS:
```bash
make installer
# Требуется установленный makensis (apt-get install nsis)
```

---

## 🚀 Режимы использования

### 1. Запуск как системной службы Windows
```cmd
# 1. Установка службы с автозапуском
sam-agent.exe -service install

# 2. Запуск службы
sam-agent.exe -service start

# 3. Остановка службы
sam-agent.exe -service stop

# 4. Удаление службы
sam-agent.exe -service uninstall
```

### 2. Запуск как фонового демона (консоль или планировщик)
```cmd
sam-agent.exe -daemon -server "http://sam.company.local:8000"
```

### 3. Запуск отдельного GUI менеджера
```cmd
sam-gui.exe
```
Подключается к работающему агенту, выводит сводку и автоматически открывает визуальную веб-панель `http://127.0.0.1:8765/gui`.

### 4. Однократный сбор и немедленная выгрузка на сервер (One-Shot)
```cmd
sam-agent.exe -upload -server "http://sam.company.local:8000"
```

### 5. Локальный экспорт в CSV и JSON
```cmd
# Стандартный CSV (полная совместимость с "Пример дампа с компов.xlsx")
sam-agent.exe -csv "dump.csv"

# Одновременный экспорт в CSV и JSON с тщательным сканированием диска
sam-agent.exe -thorough -format both -csv "dump.csv" -json "dump.json"

# Расширенный CSV (с флагом активности, хэшами SHA-256 и датой последнего запуска)
sam-agent.exe -extended -csv "dump_extended.csv"
```

---

## ⚙️ Конфигурационный файл (`config.json`)

```json
{
  "server_url": "http://localhost:8000",
  "api_key": "",
  "listen_addr": "127.0.0.1:8765",
  "heartbeat_interval_sec": 30,
  "quick_scan_interval_min": 60,
  "thorough_scan_interval_hours": 24,
  "enable_realtime_watcher": true,
  "enable_disk_scanner": true,
  "auto_upload": true,
  "custom_serial": ""
}
```

---

## 📋 Форматы данных

### Стандартный CSV (`software_dump.csv`):
```csv
COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION
G69ZD5J,Google Chrome,Google LLC,67.208.108
B1RG0S2,7-Zip 19.00 (x64 edition),Igor Pavlov,19.00.00.0
B1RG0S2,WinRAR archiver,<Null>,<Null>
```

### Расширенный CSV (`-extended`):
```csv
COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION,IS_RUNNING,PIDS,PROCESS_NAMES,IS_STANDALONE,INSTALL_PATH,BINARY_HASH,LAST_LAUNCHED_AT
G69ZD5J,Google Chrome,Google LLC,67.208.108,TRUE,12480;12512,chrome.exe,FALSE,C:\Program Files\Google\Chrome\Application\chrome.exe,e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855,2026-11-15T04:10:00Z
```
