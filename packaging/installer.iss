; Inno Setup 6 Script for Cuttle
; Offline Windows Right-Click File Converter
; Build with: iscc packaging/installer.iss

#define MyAppName "Cuttle"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Cuttle Contributors"
#define MyAppURL "https://github.com/Ameya79/cuttle"
#define MyAppExeName "cuttlectl.exe"
#define MyAppWorkerExe "cuttle-worker.exe"

[Setup]
AppId={{5E4790E5-99D3-4A2D-B912-70F4F7A6973E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Cuttle-Setup-x64
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\cuttle.ico
UninstallIconFile=..\assets\cuttle.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Launch Cuttle in background on Windows startup"; GroupDescription: "Additional options:"; Flags: checkedonce

[Files]
Source: "..\dist\Cuttle\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppWorkerExe}"
Name: "{autostartup}\{#MyAppName}"; Filename: "{app}\{#MyAppWorkerExe}"; Tasks: autostart

[Run]
; 1. Register classic context menus
Filename: "{app}\cuttle.exe"; Parameters: "install-shell"; Flags: runhidden
; 2. On Windows 11 (build 22000+), register sparse MSIX package for top-level menu
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\scripts\register_sparse_package.ps1"""; Flags: runhidden; MinVersion: 10.0.22000
; 3. Start the worker daemon in the background
Filename: "{app}\{#MyAppWorkerExe}"; Description: "Start Cuttle in the background"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 1. Unregister Windows 11 sparse package
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\scripts\unregister_sparse_package.ps1"""; Flags: runhidden; MinVersion: 10.0.22000
; 2. Cleanly unregister classic Explorer context menus
Filename: "{app}\cuttle.exe"; Parameters: "uninstall-shell"; Flags: runhidden
; 3. Terminate running background worker process
Filename: "taskkill.exe"; Parameters: "/F /IM cuttle-worker.exe"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\Cuttle"
