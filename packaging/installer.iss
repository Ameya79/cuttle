; Inno Setup 6 Script for Cuttle
; Offline Windows Right-Click File Converter
; Build with: iscc packaging/installer.iss

#define MyAppName "Cuttle"
#define MyAppVersion "0.2.0"
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
OutputBaseFilename=CuttleSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\cuttle.ico
UninstallIconFile=..\assets\cuttle.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Launch Cuttle in background on Windows startup"; GroupDescription: "Additional options:"; Flags: unchecked

[Files]
Source: "..\dist\Cuttle\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppWorkerExe}"

[Run]
; 1. Dynamically register Explorer right-click context menus
Filename: "{app}\{#MyAppExeName}"; Parameters: "install-shell"; Flags: runhidden
; 2. Start the worker daemon immediately
Filename: "{app}\{#MyAppWorkerExe}"; Description: "Start Cuttle in the background"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 1. Cleanly unregister 100% of Explorer context menus
Filename: "{app}\{#MyAppExeName}"; Parameters: "uninstall-shell"; Flags: runhidden
