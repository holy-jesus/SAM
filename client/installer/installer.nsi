; =========================================================================
; SAM Agent — NSIS Installer Script
; Software Asset Management Client & Service Installer for Windows x64
; =========================================================================

!include "MUI2.nsh"
!include "x64.nsh"

; Имя программы и версия
!define PRODUCT_NAME "SAM Agent"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "SAM (Software Asset Management)"
!define PRODUCT_WEB_SITE "http://localhost:8000"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\sam-agent.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; Настройки инсталлятора
Name "${PRODUCT_NAME} v${PRODUCT_VERSION}"
OutFile "..\bin\sam-agent-setup-v${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES64\SAM Agent"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
RequestExecutionLevel admin
SetCompressor /SOLID lzma

; Интерфейс Modern UI
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Страницы установки
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\sam-gui.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить панель управления SAM Agent (GUI)"
!insertmacro MUI_PAGE_FINISH

; Страницы удаления
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Язык
!insertmacro MUI_LANGUAGE "Russian"

; -------------------------------------------------------------------------
; Секция установки
; -------------------------------------------------------------------------
Section "MainSection" SEC01
  ${If} ${RunningX64}
    SetRegView 64
  ${EndIf}

  ; Остановка службы, если она уже была установлена ранее
  DetailPrint "Остановка предыдущей версии службы (если есть)..."
  ExecWait '"$INSTDIR\sam-agent.exe" -service stop'
  Sleep 1000

  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; Копирование бинарных файлов
  File "..\bin\sam-agent.exe"
  File "..\bin\sam-gui.exe"

  ; Копирование конфигурации по умолчанию (если ещё не существует)
  IfFileExists "$INSTDIR\config.json" skip_config
    File "..\config.json"
  skip_config:

  ; Создание ярлыков в меню Пуск
  CreateDirectory "$SMPROGRAMS\SAM Agent"
  CreateShortCut "$SMPROGRAMS\SAM Agent\SAM Agent GUI.lnk" "$INSTDIR\sam-gui.exe" "" "$INSTDIR\sam-gui.exe" 0
  CreateShortCut "$SMPROGRAMS\SAM Agent\Удалить SAM Agent.lnk" "$INSTDIR\uninst.exe" "" "$INSTDIR\uninst.exe" 0

  ; Создание деинсталлятора
  WriteUninstaller "$INSTDIR\uninst.exe"

  ; Запись информации об установке в реестр Windows
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\sam-agent.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\sam-agent.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"

  ; Регистрация и запуск агента как системной службы Windows
  DetailPrint "Регистрация службы SAMAgent в Windows Service Control Manager..."
  ExecWait '"$INSTDIR\sam-agent.exe" -service install'
  DetailPrint "Запуск фоновой службы SAMAgent..."
  ExecWait '"$INSTDIR\sam-agent.exe" -service start'

SectionEnd

; -------------------------------------------------------------------------
; Секция деинсталляции
; -------------------------------------------------------------------------
Section Uninstall
  ${If} ${RunningX64}
    SetRegView 64
  ${EndIf}

  DetailPrint "Остановка и удаление системной службы SAMAgent..."
  ExecWait '"$INSTDIR\sam-agent.exe" -service stop'
  Sleep 1000
  ExecWait '"$INSTDIR\sam-agent.exe" -service uninstall'
  Sleep 1000

  ; Удаление ярлыков
  Delete "$SMPROGRAMS\SAM Agent\SAM Agent GUI.lnk"
  Delete "$SMPROGRAMS\SAM Agent\Удалить SAM Agent.lnk"
  RMDir "$SMPROGRAMS\SAM Agent"

  ; Удаление файлов
  Delete "$INSTDIR\sam-agent.exe"
  Delete "$INSTDIR\sam-gui.exe"
  Delete "$INSTDIR\config.json"
  Delete "$INSTDIR\uninst.exe"
  RMDir "$INSTDIR"

  ; Очистка реестра
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"

  SetAutoClose true
SectionEnd
