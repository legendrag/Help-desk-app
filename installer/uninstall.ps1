<#
    uninstall.ps1 — Tear down services and installer-created artifacts.
    Data (mysqldata, media, backups, logs, .env, *.pem) is preserved unless -RemoveData.
#>
param(
    [string]$InstallDir = "",
    [switch]$RemoveData
)

$ErrorActionPreference = "Continue"

$libDir = Join-Path $PSScriptRoot "lib"
. (Join-Path $libDir "common.ps1")
. (Join-Path $libDir "service.ps1")

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Split-Path -Parent $PSScriptRoot
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

Write-InstallStep "Uninstalling mlamehticket from $InstallDir"

try { Assert-Administrator } catch {
    Write-InstallWarn "Not elevated; some cleanup steps may fail."
}

# Stop / remove app service
try { Remove-AppService -InstallDir $InstallDir } catch {
    Write-InstallWarn "App service removal: $($_.Exception.Message)"
}

# Remove bundled MySQL only if we installed it
$bundled = $false
try {
    $prop = Get-ItemProperty -Path $script:RegistryPath -Name BundledMySql -ErrorAction SilentlyContinue
    if ($prop -and $prop.BundledMySql -eq 1) { $bundled = $true }
}
catch { }
if (-not $bundled -and (Test-Path (Join-Path $InstallDir "mysql\.mlamehticket-owned"))) {
    $bundled = $true
}

if ($bundled) {
    Write-InstallStep "Removing bundled MySQL service..."
    $svc = Get-Service -Name $script:MySqlServiceName -ErrorAction SilentlyContinue
    if ($svc) {
        if ($svc.Status -eq "Running") {
            Stop-Service -Name $script:MySqlServiceName -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
        $mysqld = Join-Path $InstallDir "mysql\bin\mysqld.exe"
        if (Test-Path $mysqld) {
            & $mysqld --remove $script:MySqlServiceName
        }
        else {
            sc.exe delete $script:MySqlServiceName | Out-Null
        }
    }
    Remove-MachinePathEntry -Entry (Join-Path $InstallDir "mysql\bin")
}

Remove-FirewallRule

# Remove installer-created trees Inno does not track
$toDelete = @(
    ".venv",
    "python",
    "mysql",
    "staticfiles",
    "FIRST-LOGIN.txt",
    "installer\winsw"
)
foreach ($rel in $toDelete) {
    $path = Join-Path $InstallDir $rel
    if (Test-Path $path) {
        Write-InstallStep "Removing $path"
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($RemoveData) {
    foreach ($rel in @("mysqldata", "media", "backups", "logs", ".env")) {
        $path = Join-Path $InstallDir $rel
        if (Test-Path $path) {
            Write-InstallStep "Removing data: $path"
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -Path $InstallDir -Filter "*.pem" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
else {
    Write-InstallStep "Preserved data folders (mysqldata, media, backups, logs, .env, *.pem)."
}

# Registry
if (Test-Path $script:RegistryPath) {
    Remove-Item -Path $script:RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
}

Write-InstallStep "Uninstall helper finished."
exit 0
