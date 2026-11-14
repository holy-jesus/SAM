# SAM Windows Agent (Go)

Легковесный клиент-агент для ОС Windows, разработанный на языке Go для сбора инвентаризационных данных об установленном программном обеспечении и запущенных процессах в рамках системы **Software Asset Management (SAM)**.

Выходной CSV полностью совместим с эталонным форматом из `data/Пример дампа с компов.xlsx`.

---

## 🚀 Возможности

1. **Идентификация компьютера**:
   - Автоматическое чтение аппаратного серийного номера (BIOS / Motherboard Serial Number) через реестр `HKLM\HARDWARE\DESCRIPTION\System\BIOS`.
   - Резервные механизмы: PowerShell CIM/WMI (`Win32_BIOS.SerialNumber`), `wmic`, `MachineGuid`, `Hostname`.
   - Возможность ручного переопределения ключом `-serial`.

2. **Инвентаризация установленного ПО**:
   - Сканирование системного реестра Windows (64-bit и 32-bit/WOW64 ветки, а также ветка текущего пользователя):
     - `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` (64-bit)
     - `HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall` (32-bit)
     - `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall` (User scope)
   - Извлечение полей: `DisplayName`, `Publisher`, `DisplayVersion`, `InstallLocation`, `InstallDate`.
   - Корректная обработка отсутствующих значений (`<Null>`, аналогично эталонному дампу).
   - Дедупликация повторных записей.

3. **Сбор запущенных процессов и соотнесение (корреляция) с ПО**:
   - Снятие снимка процессов через Win32 Toolhelp32 Snapshot API (`CreateToolhelp32Snapshot`).
   - Получение пути к исполняемому файлу через `QueryFullProcessImageNameW`.
   - Чтение метаданных PE-заголовков через `version.dll` (`GetFileVersionInfoW`, `VerQueryValueW`):
     - `ProductName`
     - `CompanyName`
     - `FileDescription`
     - `FileVersion`
     - `ProductVersion`
   - **Алгоритм соотнесения (мэтчинга)**:
     1. **По путям**: проверка вхождения пути исполняемого файла в директорию `InstallLocation` программы.
     2. **По метаданным PE**: сопоставление `ProductName` и `FileDescription` с `DisplayName` программы.
     3. **По алиасам и эвристикам**: сопоставление известных процессов (`code.exe` → Visual Studio Code, `idea64.exe` → IntelliJ IDEA, `excel.exe` → Microsoft Excel, `7zfm.exe` → 7-Zip, `telegram.exe` → Telegram Desktop и др.).
     4. **Обнаружение автономного софта**: фиксация запущенных программ, не зарегистрированных в реестре (портативный софт, утилиты в Downloads/Temp), исключая системные процессы ядра Windows.

4. **Экспорт данных**:
   - **CSV (по умолчанию)**: эталонный формат из 4 колонок (`COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION`).
   - **Расширенный CSV (`-extended`)**: добавляет колонки `IS_RUNNING`, `PIDS`, `PROCESS_NAMES`, `IS_STANDALONE`.
   - **Дамп процессов (`-processes-csv <path>`)**: детальный список всех запущенных процессов с путями и результатом соотнесения.
   - **JSON (`-format json` или `-format both`)**: иерархический отчёт с метаданными хоста, списком ПО и запущенных процессов.

---

## 🛠 Сборка

Клиент использует только стандартную библиотеку Go (`syscall`, `unsafe`, `encoding/csv`, `encoding/json`) и **не требует внешних зависимостей или интернета**.

### Кросс-компиляция для Windows (из Linux/macOS):
```bash
cd client
make build
# или напрямую:
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o bin/sam-agent.exe ./cmd/sam-agent
```
Скомпилированный бинарный файл: `client/bin/sam-agent.exe`.

### Сборка для локального тестирования (Linux):
```bash
make build-linux
./bin/sam-agent -csv test.csv
```

### Запуск тестов:
```bash
make test
```

---

## 💻 Использование на Windows

### 1. Стандартный запуск (формирование дампа как в примере):
```cmd
sam-agent.exe
```
Создаст файл `software_dump.csv` в текущей директории.

### 2. Указание своего пути для CSV:
```cmd
sam-agent.exe -csv "C:\SAM\host_dump.csv"
```

### 3. Экспорт в JSON и CSV одновременно:
```cmd
sam-agent.exe -format both -csv "dump.csv" -json "dump.json"
```

### 4. Расширенный CSV (с флагом активности и PID):
```cmd
sam-agent.exe -extended -csv "dump_extended.csv"
```

### 5. Экспорт отдельного дампа запущенных процессов:
```cmd
sam-agent.exe -csv "dump.csv" -processes-csv "processes.csv"
```

### 6. Тихий режим (для автоматизации через планировщик / GPO / SCCM):
```cmd
sam-agent.exe -silent -csv "C:\Share\SAM\dump_%COMPUTERNAME%.csv"
```

---

## 📋 Формат данных

### Стандартный CSV (полная совместимость с `Пример дампа с компов.xlsx`):
```csv
COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION
G69ZD5J,Google Chrome,Google LLC,67.208.108
B1RG0S2,7-Zip 19.00 (x64 edition),Igor Pavlov,19.00.00.0
B1RG0S2,WinRAR archiver,<Null>,<Null>
```

### Расширенный CSV (`-extended`):
```csv
COMPUTERS.SERIAL_NUMBER,SOFTWARE.DISPLAYNAME,SOFTWARE.PUBLISHER,SOFTWARE.VERSION,IS_RUNNING,PIDS,PROCESS_NAMES,IS_STANDALONE
G69ZD5J,Google Chrome,Google LLC,67.208.108,TRUE,12480;12512,chrome.exe,FALSE
B1RG0S2,7-Zip 19.00 (x64 edition),Igor Pavlov,19.00.00.0,FALSE,,,FALSE
```
