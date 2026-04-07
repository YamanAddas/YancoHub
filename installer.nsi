; YancoHub NSIS Installer Script
; Requires NSIS 3.x — https://nsis.sourceforge.io/
; Run: makensis installer.nsi (or use build.py which calls this automatically)

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ── App Info ──────────────────────────────────────────────────────────────────
!define APP_NAME "YancoHub"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "Yaman Addas"
!define APP_URL "https://github.com/YamanAddas/YancoHub"
!define APP_EXE "YancoHub.exe"
!define DIST_DIR "dist\YancoHub"

; ── Installer Settings ────────────────────────────────────────────────────────
Name "${APP_NAME} ${APP_VERSION}"
OutFile "dist\${APP_NAME}-${APP_VERSION}-setup.exe"
InstallDir "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

; ── UI Configuration ──────────────────────────────────────────────────────────
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APP_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT "This will install ${APP_NAME} ${APP_VERSION} on your computer.$\r$\n$\r$\nAll your games. One place. No clutter.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${APP_NAME}"

; Use app icon if it exists
!if /FileExists "assets\icon.ico"
    !define MUI_ICON "assets\icon.ico"
    !define MUI_UNICON "assets\icon.ico"
!endif

; ── Pages ─────────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ── Install Section ───────────────────────────────────────────────────────────
Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy all files from PyInstaller dist
    File /r "${DIST_DIR}\*.*"

    ; Create user data directories
    CreateDirectory "$INSTDIR\cache"
    CreateDirectory "$INSTDIR\logs"
    CreateDirectory "$INSTDIR\bios\user"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" \
        "" "$INSTDIR\${APP_EXE}" 0
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

    ; Desktop shortcut
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" \
        "" "$INSTDIR\${APP_EXE}" 0

    ; Registry — Add/Remove Programs entry
    WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "Publisher" "${APP_PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "URLInfoAbout" "${APP_URL}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "NoRepair" 1

    ; Protocol handler — yancohub:// URLs
    WriteRegStr HKCU "Software\Classes\yancohub" "" "URL:YancoHub Protocol"
    WriteRegStr HKCU "Software\Classes\yancohub" "URL Protocol" ""
    WriteRegStr HKCU "Software\Classes\yancohub\DefaultIcon" "" "$INSTDIR\${APP_EXE},0"
    WriteRegStr HKCU "Software\Classes\yancohub\shell\open\command" "" '"$INSTDIR\${APP_EXE}" "%1"'

    ; Launch on startup — removed by uninstaller
    ; (Actual toggle is managed by the app via winreg)

    ; Calculate installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
        "EstimatedSize" $0

SectionEnd

; ── Uninstall Section ─────────────────────────────────────────────────────────
Section "Uninstall"
    ; Remove app files (but preserve user data)
    RMDir /r "$INSTDIR\_internal"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\uninstall.exe"
    Delete "$INSTDIR\LICENSE"
    Delete "$INSTDIR\README.md"
    RMDir /r "$INSTDIR\templates"
    RMDir /r "$INSTDIR\static"
    RMDir /r "$INSTDIR\config"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Remove registry entries
    DeleteRegKey HKCU "Software\${APP_NAME}"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCU "Software\Classes\yancohub"
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APP_NAME}"

    ; Only remove install dir if empty (preserves user data)
    RMDir "$INSTDIR"

    ; Notify user about remaining data
    IfFileExists "$INSTDIR\*.*" 0 +2
        MessageBox MB_OK "Note: Your game library data (cache, userdata.json, BIOS files) was preserved in:$\r$\n$\r$\n$INSTDIR$\r$\n$\r$\nYou can delete this folder manually if you no longer need it."

SectionEnd
