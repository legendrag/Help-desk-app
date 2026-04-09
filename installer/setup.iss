; Help Desk — Inno Setup Script
; Builds HelpDeskSetup.exe for client distribution

#define MyAppName "Help Desk Ticket System"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Help Desk"
#define MyAppURL "http://localhost:8000"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\HelpDesk
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename=HelpDeskSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\static\favicon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Project files (excluding source control, venv, and cache)
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs; Excludes: ".git,.venv,__pycache__,*.pyc,db.sqlite3,node_modules,frontend,installer\Output"

; Config files
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"
Source: "..\run-helpdesk.ps1"; DestDir: "{app}"

; Installer scripts
Source: "install.ps1"; DestDir: "{app}\installer"

[Icons]
Name: "{group}\Help Desk — Start"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\run-helpdesk.ps1"""; WorkingDir: "{app}"; Comment: "Start Help Desk system"
Name: "{group}\Help Desk — Configure"; Filename: "notepad.exe"; Parameters: """{app}\.env"""; Comment: "Edit configuration"
Name: "{group}\Uninstall Help Desk"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Help Desk"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\run-helpdesk.ps1"""; WorkingDir: "{app}"; Comment: "Start Help Desk system"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\installer\install.ps1"" -InstallDir ""{app}"""; StatusMsg: "Setting up Help Desk (this may take a few minutes)..."; Flags: runhidden waituntilterminated
Filename: "notepad.exe"; Parameters: """{app}\.env"""; Description: "Review/edit configuration (.env)"; Flags: postinstall nowait skipifsilent
