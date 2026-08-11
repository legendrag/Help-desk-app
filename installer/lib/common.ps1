<#
    common.ps1 — Shared helpers for mlamehticket installer scripts.
#>

$script:AppServiceName = "mlamehticketApp"
$script:MySqlServiceName = "mlamehticketMySQL"
$script:RegistryPath = "HKLM:\Software\mlamehticket"
$script:FirewallRuleName = "mlamehticket HTTP"

function Write-InstallStep {
    param([string]$Message)
    Write-Host "[INSTALL] $Message" -ForegroundColor Cyan
    try { [Console]::Out.Flush() } catch { }
    Write-InstallStatus $Message
}

function Write-InstallWarn {
    param([string]$Message)
    Write-Host "[INSTALL] WARNING: $Message" -ForegroundColor Yellow
    try { [Console]::Out.Flush() } catch { }
    Write-InstallStatus "WARNING: $Message"
}

function Write-InstallError {
    param([string]$Message)
    Write-Host "[INSTALL] ERROR: $Message" -ForegroundColor Red
    try { [Console]::Out.Flush() } catch { }
    Write-InstallStatus "ERROR: $Message"
}

function Write-InstallStatus {
    param([string]$Message)
    # Short one-line status for Inno Setup StatusLabel (polled while install runs hidden)
    if ([string]::IsNullOrWhiteSpace($script:InstallDirForStatus)) { return }
    try {
        $logsDir = Join-Path $script:InstallDirForStatus "logs"
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        $line = ($Message -replace "[\r\n]+", " ").Trim()
        if ($line.Length -gt 120) { $line = $line.Substring(0, 117) + "..." }
        Set-Content -Path (Join-Path $logsDir "install-status.txt") -Value $line -Encoding ASCII -Force
        $mirror = Join-Path $env:ProgramData "mlamehticket\logs"
        New-Item -ItemType Directory -Force -Path $mirror | Out-Null
        Set-Content -Path (Join-Path $mirror "install-status.txt") -Value $line -Encoding ASCII -Force
    }
    catch { }
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-Administrator {
    if (-not (Test-IsAdministrator)) {
        throw "This script must run elevated (as Administrator)."
    }
}

function Start-InstallTranscript {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$Version
    )
    # Primary: ProgramData — survives if the install folder is wiped by a bad retry/uninstall
    $stableDir = Join-Path $env:ProgramData "mlamehticket\logs"
    New-Item -ItemType Directory -Force -Path $stableDir | Out-Null

    $appLogsDir = Join-Path $InstallDir "logs"
    New-Item -ItemType Directory -Force -Path $appLogsDir | Out-Null

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $name = "install-{0}-{1}.log" -f $Version, $stamp
    $logPath = Join-Path $stableDir $name
    Start-Transcript -Path $logPath -Force | Out-Null

    # Mirror path note into app logs so operators looking under {app}\logs still find a pointer
    $pointer = Join-Path $appLogsDir $name
    Set-Content -Path $pointer -Value "Install transcript is at:`r`n$logPath" -Encoding ASCII

    Get-ChildItem -Path $stableDir -Filter "install-*.log" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 10 |
        Remove-Item -Force -ErrorAction SilentlyContinue
    return $logPath
}

function Get-InstalledVersion {
    try {
        $value = Get-ItemProperty -Path $script:RegistryPath -Name Version -ErrorAction Stop
        return [string]$value.Version
    }
    catch {
        return $null
    }
}

function Compare-SemVer {
    param(
        [Parameter(Mandatory)][string]$Left,
        [Parameter(Mandatory)][string]$Right
    )
    $l = ($Left -split "[^0-9]") | Where-Object { $_ -ne "" } | ForEach-Object { [int]$_ }
    $r = ($Right -split "[^0-9]") | Where-Object { $_ -ne "" } | ForEach-Object { [int]$_ }
    $max = [Math]::Max($l.Count, $r.Count)
    for ($i = 0; $i -lt $max; $i++) {
        $lv = if ($i -lt $l.Count) { $l[$i] } else { 0 }
        $rv = if ($i -lt $r.Count) { $r[$i] } else { 0 }
        if ($lv -lt $rv) { return -1 }
        if ($lv -gt $rv) { return 1 }
    }
    return 0
}

function Get-InstallMode {
    param([Parameter(Mandatory)][string]$PackageVersion)
    $installed = Get-InstalledVersion
    if ([string]::IsNullOrWhiteSpace($installed)) {
        return "fresh"
    }
    $cmp = Compare-SemVer -Left $PackageVersion -Right $installed
    if ($cmp -lt 0) { return "downgrade" }
    if ($cmp -eq 0) { return "repair" }
    return "upgrade"
}

function Read-DotEnvValue {
    param(
        [Parameter(Mandatory)][string]$EnvFile,
        [Parameter(Mandatory)][string]$Key
    )
    if (-not (Test-Path $EnvFile)) { return $null }
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match "^\s*#") { continue }
        if ($line -match "^\s*$Key\s*=\s*(.*)$") {
            return $matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return $null
}

function Test-TcpPortOpen {
    param(
        [string]$HostName = "127.0.0.1",
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutMs = 1000
    )
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    }
    catch {
        return $false
    }
}

function Get-PrimaryIPv4Address {
    try {
        $addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -notlike "127.*" -and
                $_.PrefixOrigin -ne "WellKnown" -and
                $_.AddressState -eq "Preferred"
            } |
            Sort-Object InterfaceMetric
        if ($addrs) { return $addrs[0].IPAddress }
    }
    catch { }
    return "127.0.0.1"
}

function Add-MachinePathEntry {
    param([Parameter(Mandatory)][string]$Entry)
    $current = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $parts = $current -split ";" | Where-Object { $_ -ne "" }
    if ($parts -contains $Entry) {
        Write-InstallStep "PATH already contains $Entry"
        return
    }
    $newPath = ($parts + $Entry) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    $env:Path = "$env:Path;$Entry"
    Write-InstallStep "Added to machine PATH: $Entry"
}

function Remove-MachinePathEntry {
    param([Parameter(Mandatory)][string]$Entry)
    $current = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ([string]::IsNullOrWhiteSpace($current)) { return }
    $parts = $current -split ";" | Where-Object { $_ -ne "" -and $_ -ne $Entry }
    $newPath = $parts -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
}

function Ensure-FirewallRule {
    param([Parameter(Mandatory)][int]$Port)
    $existing = Get-NetFirewallRule -DisplayName $script:FirewallRuleName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $script:FirewallRuleName -ErrorAction SilentlyContinue
        Write-InstallStep "Removed existing firewall rule '$($script:FirewallRuleName)' (will recreate for TCP $Port)"
    }
    New-NetFirewallRule `
        -DisplayName $script:FirewallRuleName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any | Out-Null
    Write-InstallStep "Created firewall rule for TCP $Port"
}

function Remove-FirewallRule {
    $existing = Get-NetFirewallRule -DisplayName $script:FirewallRuleName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $script:FirewallRuleName -ErrorAction SilentlyContinue
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][int]$Port,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    # Prefer 127.0.0.1; also try localhost (SITE_URL may be either)
    $urls = @(
        "http://127.0.0.1:$Port/",
        "http://127.0.0.1:$Port/accounts/login/",
        "http://localhost:$Port/",
        "http://localhost:$Port/accounts/login/"
    )
    Write-InstallStep "Waiting for HTTP readiness on port $Port ..."

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        while ((Get-Date) -lt $deadline) {
            foreach ($url in $urls) {
                $code = $null
                try {
                    # HttpWebRequest: do not follow redirects; any 2xx/3xx means Daphne is up.
                    $req = [System.Net.HttpWebRequest]::Create($url)
                    $req.Method = "GET"
                    $req.AllowAutoRedirect = $false
                    $req.Timeout = 5000
                    $req.ReadWriteTimeout = 5000
                    $req.UserAgent = "mlamehticket-installer"
                    try {
                        $resp = $req.GetResponse()
                        $code = [int]$resp.StatusCode
                        $resp.Close()
                    }
                    catch [System.Net.WebException] {
                        if ($_.Exception.Response) {
                            $code = [int]$_.Exception.Response.StatusCode
                            try { $_.Exception.Response.Close() } catch { }
                        }
                    }
                }
                catch { }

                if ($null -ne $code -and $code -ge 200 -and $code -lt 500) {
                    Write-InstallStep "HTTP ready ($url -> $code)"
                    return $true
                }
            }
            Start-Sleep -Seconds 2
        }
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
    return $false
}

function Restrict-AclToAdministrators {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path $Path)) { return }
    $acl = Get-Acl $Path
    $acl.SetAccessRuleProtection($true, $false)
    $acl.Access | ForEach-Object { [void]$acl.RemoveAccessRule($_) }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "BUILTIN\Administrators", "FullControl", "Allow"
    )
    $acl.AddAccessRule($rule)
    $systemRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        "NT AUTHORITY\SYSTEM", "FullControl", "Allow"
    )
    $acl.AddAccessRule($systemRule)
    Set-Acl -Path $Path -AclObject $acl
}

function New-SecurePassword {
    param([int]$Length = 24)
    # Alphanumeric only — symbols like $ break PowerShell double-quoted SQL ("...$pass...")
    # and can leave MySQL with a different password than we store in memory / FIRST-LOGIN.txt.
    $chars = (48..57) + (65..90) + (97..122)
    -join (1..$Length | ForEach-Object { [char]($chars | Get-Random) })
}

function ConvertTo-ForwardSlashPath {
    param([Parameter(Mandatory)][string]$Path)
    return ($Path -replace "\\", "/")
}
