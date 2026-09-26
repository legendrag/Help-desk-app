; mlamehticket — Offline Inno Setup Script
; Build with: .\installer\build.ps1  (passes /DMyAppVersion=...)

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "mlamehticket"
#define MyAppPublisher "mlamehticket"
#define MyAppURL "http://localhost:8000"
#define MyAppId "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={sd}\mlamehticket
AppendDefaultDirName=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=mlamehticketSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DirExistsWarning=auto
ExtraDiskSpaceRequired=2500000000
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\static\images\mlameh-icon-maskable.png
SetupLogging=yes
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Application tree (never ship .env, pem keys, runtime data, or build outputs)
Source: "..\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; \
  Excludes: ".git,.venv,__pycache__,*.pyc,db.sqlite3,node_modules,frontend,.env,*.pem,media,backups,logs,mysqldata,installer\Output,installer\payload,.cursor"
; Offline payload (Python, MySQL ZIP, WinSW)
Source: "payload\*"; DestDir: "{app}\installer\payload"; Flags: recursesubdirs ignoreversion
; Scripts also extracted to {tmp} for pre-upgrade before file replace
Source: "preupgrade.ps1"; DestDir: "{tmp}"; Flags: dontcopy
Source: "lib\common.ps1"; DestDir: "{tmp}\lib"; Flags: dontcopy
Source: "lib\service.ps1"; DestDir: "{tmp}\lib"; Flags: dontcopy

[Icons]
Name: "{group}\mlamehticket — Open"; Filename: "{cmd}"; Parameters: "/C start http://localhost:{code:GetPort}"; Comment: "Open mlamehticket"
Name: "{group}\mlamehticket — Restart service"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command ""Restart-Service mlamehticketApp"""; Comment: "Restart the help-desk service"
Name: "{group}\mlamehticket — Open logs"; Filename: "{app}\logs"; Comment: "Open log folder"
Name: "{group}\Uninstall mlamehticket"; Filename: "{uninstallexe}"
Name: "{commondesktop}\mlamehticket"; Filename: "{cmd}"; Parameters: "/C start http://localhost:{code:GetPort}"; Comment: "Open mlamehticket"

[Code]
var
  ConfigPage: TInputQueryWizardPage;
  DbPage: TInputQueryWizardPage;
  MySqlPage: TInputQueryWizardPage;
  ForcePrivateCheck: TNewCheckBox;
  InstallMode: string;
  DetectedMySql: Boolean;
  ServerAddressValue: string;
  PortValue: string;
  AdminEmailValue: string;
  DbNameValue: string;
  DbUserValue: string;
  DbPasswordValue: string;
  MySqlUserValue: string;
  MySqlPasswordValue: string;
  ForcePrivateMySql: Boolean;
  WarnedProgramFiles: Boolean;
  InstallExitCode: Integer;

function GetPort(Param: string): string;
begin
  if PortValue = '' then Result := '8000' else Result := PortValue;
end;

function GetServerAddress(Param: string): string;
begin
  Result := ServerAddressValue;
end;

function GetAdminEmail(Param: string): string;
begin
  Result := AdminEmailValue;
end;

function GetMySqlUser(Param: string): string;
begin
  if ForcePrivateMySql then Result := '' else Result := MySqlUserValue;
end;

function GetMySqlPassword(Param: string): string;
begin
  if ForcePrivateMySql then Result := '' else Result := MySqlPasswordValue;
end;

function GetInstallMode(Param: string): string;
begin
  Result := InstallMode;
end;

function GetForcePrivateSwitch(Param: string): string;
begin
  if ForcePrivateMySql then Result := '-ForcePrivateMySql' else Result := '';
end;

function ReadInstallStatus(const StatusFile: string): string;
var
  Lines: TArrayOfString;
begin
  Result := '';
  if LoadStringsFromFile(StatusFile, Lines) then
    if GetArrayLength(Lines) > 0 then
      Result := Trim(Lines[0]);
end;

function ReadExitCodeFile(const ExitFile: string): Integer;
var
  Lines: TArrayOfString;
begin
  Result := 1;
  if LoadStringsFromFile(ExitFile, Lines) then
    if GetArrayLength(Lines) > 0 then
      Result := StrToIntDef(Trim(Lines[0]), 1);
end;

function WriteWizardSecretsFile(const FilePath: string): Boolean;
var
  Content: string;
begin
  Content :=
    'DbName=' + DbNameValue + #13#10 +
    'DbUser=' + DbUserValue + #13#10 +
    'DbPassword=' + DbPasswordValue + #13#10;
  Result := SaveStringToFile(FilePath, Content, False);
end;

function CompareVersionParts(const A, B: string): Integer;
var
  AList, BList: TStringList;
  i, Av, Bv, MaxC: Integer;
begin
  AList := TStringList.Create;
  BList := TStringList.Create;
  try
    AList.Delimiter := '.';
    AList.StrictDelimiter := True;
    AList.DelimitedText := A;
    BList.Delimiter := '.';
    BList.StrictDelimiter := True;
    BList.DelimitedText := B;
    if AList.Count > BList.Count then MaxC := AList.Count else MaxC := BList.Count;
    for i := 0 to MaxC - 1 do
    begin
      if i < AList.Count then Av := StrToIntDef(AList[i], 0) else Av := 0;
      if i < BList.Count then Bv := StrToIntDef(BList[i], 0) else Bv := 0;
      if Av < Bv then begin Result := -1; Exit; end;
      if Av > Bv then begin Result := 1; Exit; end;
    end;
    Result := 0;
  finally
    AList.Free;
    BList.Free;
  end;
end;

function GetInstalledVersionFromRegistry: string;
begin
  if not RegQueryStringValue(HKLM, 'Software\mlamehticket', 'Version', Result) then
    Result := '';
end;

function DetectExistingMySql: Boolean;
var
  ResultCode: Integer;
begin
  if Exec('sc.exe', 'query MySQL80', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if ResultCode = 0 then begin Result := True; Exit; end;
  if Exec('sc.exe', 'query MySQL', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if ResultCode = 0 then begin Result := True; Exit; end;
  if Exec('sc.exe', 'query MariaDB', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if ResultCode = 0 then begin Result := True; Exit; end;
  if Exec('sc.exe', 'query mlamehticketMySQL', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    if ResultCode = 0 then begin Result := True; Exit; end;
  if Exec('powershell.exe',
      '-NoProfile -Command "if (Get-NetTCPConnection -LocalPort 3306 -State Listen -EA SilentlyContinue) { exit 0 } else { exit 1 }"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := (ResultCode = 0);
    Exit;
  end;
  Result := False;
end;

function GetDefaultLanIp: string;
var
  TmpFile: string;
  Lines: TArrayOfString;
  ResultCode: Integer;
begin
  Result := '127.0.0.1';
  TmpFile := ExpandConstant('{tmp}\mlameh-ip.txt');
  if Exec('powershell.exe',
      '-NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike ''127.*'' -and $_.AddressState -eq ''Preferred'' } | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress) | Out-File -Encoding ascii ''' + TmpFile + '''"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if LoadStringsFromFile(TmpFile, Lines) then
      if GetArrayLength(Lines) > 0 then
        if Trim(Lines[0]) <> '' then
          Result := Trim(Lines[0]);
  end;
end;

function PathHasNonAscii(const S: string): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to Length(S) do
    if Ord(S[i]) > 127 then begin Result := True; Exit; end;
end;

function IsUncPath(const S: string): Boolean;
begin
  Result := (Length(S) >= 2) and (S[1] = '\') and (S[2] = '\');
end;

const
  DRIVE_FIXED = 3;

function GetDriveType(lpRootPathName: string): UINT;
  external 'GetDriveTypeW@kernel32.dll stdcall';

function DriveIsFixed(const Dir: string): Boolean;
var
  Root: string;
begin
  Result := True;
  if Length(Dir) >= 2 then
  begin
    Root := Copy(Dir, 1, 2);
    if Root[2] = ':' then
      Result := (GetDriveType(Root + '\') = DRIVE_FIXED);
  end;
end;

function InitializeSetup: Boolean;
var
  Installed: string;
  Cmp: Integer;
begin
  Result := True;
  WarnedProgramFiles := False;
  ForcePrivateMySql := False;
  InstallExitCode := 0;
  InstallMode := 'fresh';
  PortValue := '8000';
  AdminEmailValue := 'admin@mlamehticket.local';
  DbNameValue := 'mlamehticket';
  DbUserValue := 'mlamehticket_user';
  DbPasswordValue := '';
  MySqlUserValue := 'root';
  MySqlPasswordValue := '';
  ServerAddressValue := GetDefaultLanIp();
  DetectedMySql := DetectExistingMySql();

  Installed := GetInstalledVersionFromRegistry();
  if Installed <> '' then
  begin
    Cmp := CompareVersionParts('{#MyAppVersion}', Installed);
    if Cmp < 0 then
    begin
      MsgBox('A newer version (' + Installed + ') is already installed. Downgrade to {#MyAppVersion} is not supported.',
        mbError, MB_OK);
      Result := False;
      Exit;
    end
    else if Cmp = 0 then
      InstallMode := 'repair'
    else
      InstallMode := 'upgrade';
  end;
end;

procedure InitializeWizard;
begin
  ConfigPage := CreateInputQueryPage(wpSelectDir,
    'Server configuration',
    'How users will reach this help desk',
    'Enter the address and port clients will use, plus the bootstrap admin email.');
  ConfigPage.Add('Server address (IP or hostname):', False);
  ConfigPage.Add('Port:', False);
  ConfigPage.Add('Admin email:', False);
  ConfigPage.Values[0] := ServerAddressValue;
  ConfigPage.Values[1] := PortValue;
  ConfigPage.Values[2] := AdminEmailValue;

  DbPage := CreateInputQueryPage(ConfigPage.ID,
    'Database settings',
    'MySQL database the application will use',
    'Choose the database name, application user, and password. These are written to .env.');
  DbPage.Add('Database name:', False);
  DbPage.Add('Database username:', False);
  DbPage.Add('Database password:', True);
  DbPage.Values[0] := DbNameValue;
  DbPage.Values[1] := DbUserValue;
  DbPage.Values[2] := '';

  MySqlPage := CreateInputQueryPage(DbPage.ID,
    'Existing MySQL credentials',
    'An existing MySQL/MariaDB server was detected',
    'Provide an admin account that can CREATE DATABASE and CREATE USER, or install a private instance.');
  MySqlPage.Add('MySQL admin username:', False);
  MySqlPage.Add('MySQL admin password:', True);
  MySqlPage.Values[0] := 'root';
  MySqlPage.Values[1] := '';

  ForcePrivateCheck := TNewCheckBox.Create(MySqlPage);
  ForcePrivateCheck.Parent := MySqlPage.Surface;
  ForcePrivateCheck.Caption := 'Install a private MySQL instance instead (requires free port 3306)';
  ForcePrivateCheck.Top := MySqlPage.Edits[1].Top + MySqlPage.Edits[1].Height + ScaleY(16);
  ForcePrivateCheck.Left := MySqlPage.Edits[0].Left;
  ForcePrivateCheck.Width := MySqlPage.SurfaceWidth;
  ForcePrivateCheck.Checked := False;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = MySqlPage.ID then
    if (InstallMode <> 'fresh') or (not DetectedMySql) then
      Result := True;
  if (PageID = DbPage.ID) and (InstallMode <> 'fresh') then
    Result := True;
  if (PageID = ConfigPage.ID) and (InstallMode <> 'fresh') then
    Result := True;
  if (PageID = wpSelectDir) and (InstallMode <> 'fresh') then
    Result := True;
end;

function TestMySqlCredentials(const UserName, Password: string): Boolean;
var
  ResultCode: Integer;
  Cmd: string;
begin
  Cmd := '-NoProfile -Command "$env:MYSQL_PWD=''' + Password + '''; ' +
         '$c=Get-Command mysql -EA SilentlyContinue; if(-not $c){ exit 2 }; ' +
         '& mysql --user=''' + UserName + ''' --host=127.0.0.1 --port=3306 -e \"SELECT 1;\" | Out-Null; exit $LASTEXITCODE"';
  if not Exec('powershell.exe', Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := False;
    Exit;
  end;
  Result := (ResultCode = 0);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir, Pf: string;
  PortNum: Integer;
  FreeBytes, TotalBytes: Int64;
begin
  Result := True;

  if CurPageID = wpSelectDir then
  begin
    Dir := WizardDirValue;
    if IsUncPath(Dir) then
    begin
      MsgBox('UNC/network paths are not supported. Choose a local fixed drive.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if not DriveIsFixed(Dir) then
    begin
      MsgBox('Please choose a folder on a fixed local drive (not removable/network).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if PathHasNonAscii(Dir) then
    begin
      MsgBox('The install path must contain only ASCII characters (no Arabic or accented letters in folder names).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    Pf := ExpandConstant('{pf}');
    if (not WarnedProgramFiles) and (Pos(AnsiUppercase(Pf), AnsiUppercase(Dir)) = 1) then
    begin
      if MsgBox('Installing under Program Files mixes program and data files (uploads, MySQL data, logs). Continue anyway?',
           mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
        Exit;
      end;
      WarnedProgramFiles := True;
    end;
    if GetSpaceOnDisk64(ExtractFileDrive(Dir) + '\', FreeBytes, TotalBytes) then
    begin
      if FreeBytes < 2500000000 then
      begin
        MsgBox('At least 2.5 GB of free disk space is required.', mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;
  end;

  if CurPageID = ConfigPage.ID then
  begin
    ServerAddressValue := Trim(ConfigPage.Values[0]);
    PortValue := Trim(ConfigPage.Values[1]);
    AdminEmailValue := Trim(ConfigPage.Values[2]);
    if ServerAddressValue = '' then
    begin
      MsgBox('Server address is required.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    PortNum := StrToIntDef(PortValue, -1);
    if (PortNum < 1) or (PortNum > 65535) then
    begin
      MsgBox('Port must be a number between 1 and 65535.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if (AdminEmailValue = '') or (Pos('@', AdminEmailValue) = 0) then
    begin
      MsgBox('Enter a valid admin email address.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = DbPage.ID then
  begin
    DbNameValue := Trim(DbPage.Values[0]);
    DbUserValue := Trim(DbPage.Values[1]);
    DbPasswordValue := DbPage.Values[2];
    if DbNameValue = '' then
    begin
      MsgBox('Database name is required.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if DbUserValue = '' then
    begin
      MsgBox('Database username is required.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Length(DbPasswordValue) < 8 then
    begin
      MsgBox('Database password must be at least 8 characters.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if (Pos(' ', DbPasswordValue) > 0) or (Pos(#9, DbPasswordValue) > 0) then
    begin
      MsgBox('Database password cannot contain spaces.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;

  if CurPageID = MySqlPage.ID then
  begin
    ForcePrivateMySql := ForcePrivateCheck.Checked;
    MySqlUserValue := Trim(MySqlPage.Values[0]);
    MySqlPasswordValue := MySqlPage.Values[1];
    if not ForcePrivateMySql then
    begin
      if MySqlUserValue = '' then
      begin
        MsgBox('MySQL admin username is required (or check "Install a private MySQL instance").', mbError, MB_OK);
        Result := False;
        Exit;
      end;
      if not TestMySqlCredentials(MySqlUserValue, MySqlPasswordValue) then
      begin
        MsgBox('Could not connect to MySQL with those credentials (or mysql.exe client is missing). Correct them or choose a private instance.',
          mbError, MB_OK);
        Result := False;
        Exit;
      end;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  Params: string;
  TmpPre, TmpLib: string;
begin
  NeedsRestart := False;
  Result := '';
  if InstallMode = 'upgrade' then
  begin
    ExtractTemporaryFile('preupgrade.ps1');
    ExtractTemporaryFile('common.ps1');
    ExtractTemporaryFile('service.ps1');
    TmpPre := ExpandConstant('{tmp}\preupgrade.ps1');
    TmpLib := ExpandConstant('{tmp}\lib');
    ForceDirectories(TmpLib);
    // ExtractTemporaryFile drops files flat in tmp; copy helpers into lib\
    if FileExists(ExpandConstant('{tmp}\common.ps1')) then
      CopyFile(ExpandConstant('{tmp}\common.ps1'), TmpLib + '\common.ps1', False);
    if FileExists(ExpandConstant('{tmp}\service.ps1')) then
      CopyFile(ExpandConstant('{tmp}\service.ps1'), TmpLib + '\service.ps1', False);

    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + TmpPre +
              '" -InstallDir "' + ExpandConstant('{app}') + '"';
    if not Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      Result := 'Failed to launch pre-upgrade script.';
      Exit;
    end;
    if ResultCode <> 0 then
    begin
      Result := 'Pre-upgrade failed (exit code ' + IntToStr(ResultCode) + '). See logs\preupgrade.log in the install directory.';
      Exit;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: string;
  LogHint: string;
  SecretsFile: string;
  StatusFile: string;
  ExitFile: string;
  StatusText: string;
  WaitTicks: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    InstallExitCode := 0;
    WizardForm.StatusLabel.Caption := 'Starting setup...';
    WizardForm.ProgressGauge.Style := npbstMarquee;

    ForceDirectories(ExpandConstant('{app}\logs'));
    StatusFile := ExpandConstant('{app}\logs\install-status.txt');
    ExitFile := ExpandConstant('{app}\logs\install-exitcode.txt');
    DeleteFile(ExitFile);
    SaveStringToFile(StatusFile, 'Starting setup...', False);

    SecretsFile := ExpandConstant('{tmp}\mlameh-wizard-db.txt');
    if InstallMode = 'fresh' then
    begin
      if not WriteWizardSecretsFile(SecretsFile) then
      begin
        InstallExitCode := 1;
        MsgBox('Failed to write temporary database settings.', mbError, MB_OK);
        Exit;
      end;
    end;

    Params := '-NoProfile -ExecutionPolicy Bypass -File "' +
              ExpandConstant('{app}\installer\install.ps1') +
              '" -InstallDir "' + ExpandConstant('{app}') +
              '" -Mode "' + InstallMode +
              '" -ServerAddress "' + ServerAddressValue +
              '" -Port ' + GetPort('') +
              ' -AdminEmail "' + AdminEmailValue +
              '" -ExistingMySqlUser "' + GetMySqlUser('') +
              '" -ExistingMySqlPassword "' + GetMySqlPassword('') +
              '" ' + GetForcePrivateSwitch('') +
              ' -PackageVersion "{#MyAppVersion}"';
    if InstallMode = 'fresh' then
      Params := Params + ' -WizardSecretsFile "' + SecretsFile + '"';

    { Hidden console. Do NOT WaitForSingleObject on Exec's handle — that can crash
      Setup on some Windows builds. Instead poll install-exitcode.txt written by install.ps1. }
    if not Exec('powershell.exe', Params, '', SW_HIDE, ewNoWait, ResultCode) then
    begin
      InstallExitCode := 1;
      MsgBox('Failed to launch the install script (powershell.exe).' + #13#10#13#10 +
             'Check logs under:' + #13#10 +
             ExpandConstant('{commonappdata}\mlamehticket\logs'),
        mbError, MB_OK);
      Exit;
    end;

    WaitTicks := 0;
    while not FileExists(ExitFile) do
    begin
      Sleep(400);
      WaitTicks := WaitTicks + 1;
      StatusText := ReadInstallStatus(StatusFile);
      if StatusText <> '' then
        WizardForm.StatusLabel.Caption := StatusText;
      WizardForm.Refresh;
      { ~3 hours safety cap so Setup never spins forever }
      if WaitTicks > 27000 then
      begin
        SaveStringToFile(StatusFile, 'ERROR: install timed out waiting for install.ps1', False);
        SaveStringToFile(ExitFile, '1', False);
      end;
    end;

    ResultCode := ReadExitCodeFile(ExitFile);
    DeleteFile(SecretsFile);

    if ResultCode <> 0 then
    begin
      InstallExitCode := ResultCode;
      LogHint := ExpandConstant('{commonappdata}\mlamehticket\logs') +
                 '\install-{#MyAppVersion}-*.log';
      MsgBox('Installation failed (exit code ' + IntToStr(ResultCode) + ').' + #13#10#13#10 +
             'The service has been left stopped.' + #13#10#13#10 +
             'Last status: ' + ReadInstallStatus(StatusFile) + #13#10#13#10 +
             'Install transcript:' + #13#10 +
             LogHint + #13#10#13#10 +
             'Also check: ' + ExpandConstant('{app}\logs'),
        mbError, MB_OK);
    end
    else
      WizardForm.StatusLabel.Caption := 'Setup completed successfully.';

    WizardForm.ProgressGauge.Style := npbstNormal;
  end;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := InstallExitCode;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Params: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\installer\uninstall.ps1') +
              '" -InstallDir "' + ExpandConstant('{app}') + '"';
    if MsgBox('Also delete application data (database files, uploads, backups, logs, .env)? Choose No to keep data for a future reinstall.',
         mbConfirmation, MB_YESNO) = IDYES then
      Params := Params + ' -RemoveData';
    Exec('powershell.exe', Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
