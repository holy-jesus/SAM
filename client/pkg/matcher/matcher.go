package matcher

import (
	"path/filepath"
	"strings"

	"sam-client/pkg/model"
)

// Известные соответствия исполняемых файлов популярному корпоративному и пользовательскому ПО
var knownAliases = map[string][]string{
	"code":            {"Visual Studio Code", "VS Code"},
	"devenv":          {"Visual Studio", "Microsoft Visual Studio"},
	"idea64":          {"IntelliJ IDEA"},
	"idea":            {"IntelliJ IDEA"},
	"datagrip64":      {"DataGrip", "JetBrains DataGrip"},
	"datagrip":        {"DataGrip", "JetBrains DataGrip"},
	"webstorm64":      {"WebStorm", "JetBrains WebStorm"},
	"webstorm":        {"WebStorm", "JetBrains WebStorm"},
	"pycharm64":       {"PyCharm", "JetBrains PyCharm"},
	"pycharm":         {"PyCharm", "JetBrains PyCharm"},
	"goland64":        {"GoLand", "JetBrains GoLand"},
	"goland":          {"GoLand", "JetBrains GoLand"},
	"rider64":         {"Rider", "JetBrains Rider"},
	"rider":           {"Rider", "JetBrains Rider"},
	"clion64":         {"CLion", "JetBrains CLion"},
	"clion":           {"CLion", "JetBrains CLion"},
	"winword":         {"Microsoft Word", "Microsoft Office", "Office 16", "Word"},
	"excel":           {"Microsoft Excel", "Microsoft Office", "Excel"},
	"powerpnt":        {"Microsoft PowerPoint", "Microsoft Office", "PowerPoint"},
	"outlook":         {"Microsoft Outlook", "Microsoft Office", "Outlook"},
	"msaccess":        {"Microsoft Access", "Microsoft Office"},
	"onenote":         {"Microsoft OneNote", "OneNote"},
	"teams":           {"Microsoft Teams"},
	"ms-teams":        {"Microsoft Teams"},
	"7zfm":            {"7-Zip"},
	"7zg":             {"7-Zip"},
	"winrar":          {"WinRAR"},
	"notepad++":       {"Notepad++"},
	"telegram":        {"Telegram Desktop", "Telegram"},
	"slack":           {"Slack"},
	"discord":         {"Discord"},
	"spotify":         {"Spotify"},
	"steam":           {"Steam"},
	"postman":         {"Postman"},
	"figma":           {"Figma"},
	"zoom":            {"Zoom Workplace", "Zoom", "Zoom Video Communications"},
	"chrome":          {"Google Chrome"},
	"msedge":          {"Microsoft Edge"},
	"firefox":         {"Mozilla Firefox", "Firefox"},
	"opera":           {"Opera"},
	"brave":           {"Brave"},
	"vlc":             {"VLC media player", "VLC"},
	"dbeaver":         {"DBeaver"},
	"git-gui":         {"Git"},
	"git-bash":        {"Git"},
	"git":             {"Git"},
	"python":          {"Python"},
	"pythonw":         {"Python"},
	"node":            {"Node.js"},
	"javaw":           {"Java", "Java SE Development Kit", "Java 8", "Java 7", "JDK", "JRE"},
	"java":            {"Java", "Java SE Development Kit", "Java 8", "Java 7", "JDK", "JRE"},
	"vmware":          {"VMware Workstation", "VMware Player"},
	"virtualbox":      {"Oracle VM VirtualBox"},
	"anydesk":         {"AnyDesk"},
	"teamviewer":      {"TeamViewer"},
	"putty":           {"PuTTY"},
	"filezilla":       {"FileZilla Client", "FileZilla"},
	"totalcmd":        {"Total Commander"},
	"totalcmd64":      {"Total Commander"},
	"acrobt32":        {"Adobe Acrobat"},
	"acrobat":         {"Adobe Acrobat"},
	"acrord32":        {"Adobe Acrobat Reader", "Adobe Reader"},
	"photoshop":       {"Adobe Photoshop"},
	"illustrator":     {"Adobe Illustrator"},
	"indesign":        {"Adobe InDesign"},
	"docker desktop":  {"Docker Desktop"},
	"com.docker.cli":  {"Docker Desktop"},
	"wireguard":       {"WireGuard"},
	"openvpn":         {"OpenVPN"},
	"kaspersky":       {"Kaspersky"},
	"1cv8":            {"1C:Предприятие", "1C:Enterprise"},
	"1cv8c":           {"1C:Предприятие", "1C:Enterprise"},
	"directum":        {"DIRECTUM", "DirectumRX"},
}

// Системные процессы Windows, которые не следует регистрировать как стороннее прикладное ПО
var systemProcesses = map[string]bool{
	"system":                true,
	"smss.exe":              true,
	"csrss.exe":             true,
	"wininit.exe":           true,
	"services.exe":          true,
	"lsass.exe":             true,
	"lsm.exe":               true,
	"svchost.exe":           true,
	"fontdrvhost.exe":       true,
	"dwm.exe":               true,
	"memory compression":    true,
	"spoolsv.exe":           true,
	"explorer.exe":          true,
	"taskhostw.exe":         true,
	"sihost.exe":            true,
	"ctfmon.exe":            true,
	"runtimebroker.exe":     true,
	"shellexperiencehost.exe": true,
	"searchhost.exe":        true,
	"startmenuexperiencehost.exe": true,
	"wudfhost.exe":          true,
	"conhost.exe":           true,
	"werfault.exe":          true,
	"winlogon.exe":          true,
	"dllhost.exe":           true,
	"dashost.exe":           true,
	"smartscreen.exe":       true,
	"securityhealthservice.exe": true,
	"securityhealthsystray.exe": true,
	"audiodg.exe":           true,
	"wmiapsrv.exe":          true,
	"wmiprvse.exe":          true,
}

// Correlate соотносит запущенные процессы со списком установленного ПО
func Correlate(installed []model.SoftwareItem, processes []model.ProcessItem, includeStandalone bool, serialNumber string) ([]model.SoftwareItem, []model.ProcessItem) {
	// Создаем копию installed для мутаций
	resultInstalled := make([]model.SoftwareItem, len(installed))
	copy(resultInstalled, installed)

	// Копия processes для заполнения соотнесений
	resultProcesses := make([]model.ProcessItem, len(processes))
	copy(resultProcesses, processes)

	// Карта соответствия для быстрого обновления
	// Индекс в resultInstalled по DisplayName в нижнем регистре
	installedMap := make(map[string]int)
	for i, sw := range resultInstalled {
		installedMap[strings.ToLower(sw.DisplayName)] = i
	}

	for pIdx := range resultProcesses {
		proc := &resultProcesses[pIdx]
		matchedIdx := -1

		// 1. Поиск по путям (если известен ExePath и InstallLocation)
		if proc.ExePath != "" {
			procCleanPath := strings.ToLower(filepath.Clean(proc.ExePath))
			for i, sw := range resultInstalled {
				if sw.InstallLocation != "" {
					locClean := strings.ToLower(filepath.Clean(sw.InstallLocation))
					// Исключаем тривиальные корневые папки
					if len(locClean) > 6 && !isGenericFolder(locClean) {
						if strings.HasPrefix(procCleanPath, locClean) {
							matchedIdx = i
							break
						}
					}
				}
			}
		}

		// 2. Поиск по метаданным PE-файла (ProductName, FileDescription)
		if matchedIdx == -1 {
			if proc.ProductName != "" {
				prodNameLower := strings.ToLower(proc.ProductName)
				for i, sw := range resultInstalled {
					swNameLower := strings.ToLower(sw.DisplayName)
					if swNameLower == prodNameLower || strings.Contains(swNameLower, prodNameLower) || strings.Contains(prodNameLower, swNameLower) {
						matchedIdx = i
						break
					}
				}
			}
		}

		if matchedIdx == -1 {
			if proc.FileDescription != "" {
				descLower := strings.ToLower(proc.FileDescription)
				if len(descLower) >= 4 {
					for i, sw := range resultInstalled {
						swNameLower := strings.ToLower(sw.DisplayName)
						if swNameLower == descLower || strings.Contains(swNameLower, descLower) || strings.Contains(descLower, swNameLower) {
							matchedIdx = i
							break
						}
					}
				}
			}
		}

		// 3. Поиск по алиасам и названию исполняемого файла
		if matchedIdx == -1 {
			baseName := strings.ToLower(strings.TrimSuffix(proc.Name, filepath.Ext(proc.Name)))
			if aliases, ok := knownAliases[baseName]; ok {
				for _, alias := range aliases {
					aliasLower := strings.ToLower(alias)
					for i, sw := range resultInstalled {
						swNameLower := strings.ToLower(sw.DisplayName)
						if strings.Contains(swNameLower, aliasLower) {
							matchedIdx = i
							break
						}
					}
					if matchedIdx != -1 {
						break
					}
				}
			}

			// Поиск вхождения базового имени процесса в DisplayName ПО (если имя >= 4 букв)
			if matchedIdx == -1 && len(baseName) >= 4 {
				for i, sw := range resultInstalled {
					swNameLower := strings.ToLower(sw.DisplayName)
					if containsWord(swNameLower, baseName) {
						matchedIdx = i
						break
					}
				}
			}
		}

		// Если процесс соотнесён с установленным ПО
		if matchedIdx != -1 {
			sw := &resultInstalled[matchedIdx]
			sw.IsRunning = true
			if !containsUint32(sw.MatchedPIDs, proc.PID) {
				sw.MatchedPIDs = append(sw.MatchedPIDs, proc.PID)
			}
			if !containsString(sw.MatchedProcesses, proc.Name) {
				sw.MatchedProcesses = append(sw.MatchedProcesses, proc.Name)
			}
			proc.MatchedSoftware = sw.DisplayName
			proc.MatchedPublisher = sw.Publisher
		}
	}

	// 4. Опционально: обнаружение автономных / портативных незарегистрированных программ
	if includeStandalone {
		for _, proc := range resultProcesses {
			if proc.MatchedSoftware != "" {
				continue
			}
			procNameLower := strings.ToLower(proc.Name)
			if systemProcesses[procNameLower] {
				continue
			}
			// Определяем имя автономного софта
			dispName := proc.ProductName
			if dispName == "" {
				dispName = proc.FileDescription
			}
			if dispName == "" {
				dispName = proc.Name
			}

			pub := proc.CompanyName
			if pub == "" {
				pub = "<Null>"
			}
			ver := proc.FileVersion
			if ver == "" {
				ver = proc.ProductVersion
			}
			if ver == "" {
				ver = "<Null>"
			}

			// Проверяем, нет ли уже такого ПО в списке
			exists := false
			for _, sw := range resultInstalled {
				if strings.EqualFold(sw.DisplayName, dispName) {
					exists = true
					break
				}
			}

			if !exists {
				standaloneItem := model.SoftwareItem{
					SerialNumber:     serialNumber,
					DisplayName:      dispName,
					Publisher:        pub,
					Version:          ver,
					InstallLocation:  filepath.Dir(proc.ExePath),
					IsRunning:        true,
					MatchedPIDs:      []uint32{proc.PID},
					MatchedProcesses: []string{proc.Name},
					IsStandalone:     true,
				}
				resultInstalled = append(resultInstalled, standaloneItem)
			}
		}
	}

	return resultInstalled, resultProcesses
}

func isGenericFolder(p string) bool {
	p = strings.ToLower(filepath.Clean(p))
	generic := []string{
		"c:\\",
		"c:\\program files",
		"c:\\program files (x86)",
		"c:\\windows",
		"c:\\windows\\system32",
		"c:\\users",
	}
	for _, g := range generic {
		if p == g {
			return true
		}
	}
	return false
}

func containsWord(s, word string) bool {
	fields := strings.FieldsFunc(s, func(r rune) bool {
		return r == ' ' || r == '-' || r == '_' || r == '(' || r == ')' || r == '.'
	})
	for _, f := range fields {
		if strings.EqualFold(f, word) {
			return true
		}
	}
	return false
}

func containsUint32(slice []uint32, val uint32) bool {
	for _, item := range slice {
		if item == val {
			return true
		}
	}
	return false
}

func containsString(slice []string, val string) bool {
	for _, item := range slice {
		if strings.EqualFold(item, val) {
			return true
		}
	}
	return false
}
