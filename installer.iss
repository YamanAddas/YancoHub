; YancoHub — Inno Setup Installer Script
; Requires Inno Setup 6.6+ — https://jrsoftware.org/isinfo.php
; Run: ISCC installer.iss (or use build.py which calls this automatically)

[Setup]
AppName=YancoHub
AppVersion=1.0.0
AppPublisher=Yaman Addas
AppPublisherURL=https://github.com/YamanAddas/YancoHub
AppSupportURL=https://github.com/YamanAddas/YancoHub/issues
DefaultDirName={localappdata}\YancoHub
DefaultGroupName=YancoHub
OutputDir=dist
OutputBaseFilename=YancoHub-1.0.0-setup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\YancoHub.exe
LicenseFile=LICENSE
DisableWelcomePage=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=All your games. One place. No clutter.%n%nThis will install [name/ver] on your computer.%n%nClick Next to continue.

[Files]
Source: "dist\YancoHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Cache and logs live under %LOCALAPPDATA%\YancoHub (managed by paths.py).
; Only the bundled BIOS user drop-folder lives next to the install.
Name: "{app}\bios\user"

[Icons]
Name: "{group}\YancoHub"; Filename: "{app}\YancoHub.exe"
Name: "{group}\Uninstall YancoHub"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YancoHub"; Filename: "{app}\YancoHub.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Registry]
; Protocol handler — yancohub:// URLs
Root: HKCU; Subkey: "Software\Classes\yancohub"; ValueData: "URL:YancoHub Protocol"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\yancohub"; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\yancohub\DefaultIcon"; ValueData: "{app}\YancoHub.exe,0"
Root: HKCU; Subkey: "Software\Classes\yancohub\shell\open\command"; ValueData: """{app}\YancoHub.exe"" ""%1"""
; App registry key
Root: HKCU; Subkey: "Software\YancoHub"; ValueName: "InstallDir"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\YancoHub.exe"; Description: "Launch YancoHub"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill"; Parameters: "/f /im YancoHub.exe"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; Clean up startup registry if set
Type: dirifempty; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Remove startup entry if present
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'YancoHub');
    // Check if user data remains
    if DirExists(ExpandConstant('{app}')) then
      MsgBox('Your game library data (cache, userdata.json, BIOS files) was preserved in:' + #13#10 + #13#10 + ExpandConstant('{app}') + #13#10 + #13#10 + 'You can delete this folder manually if you no longer need it.', mbInformation, MB_OK);
  end;
end;
