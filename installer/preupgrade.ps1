<#
    preupgrade.ps1 — Stop service, archive code, backup database before file replace.
#>
param(
    [Parameter(Mandatory)][string]$InstallDir,
    [string]$OldVersion = ""
)

$ErrorActionPreference = "Stop"

$libDir = Join-Path $PSScriptRoot "lib"
if (-not (Test-Path (Join-Path $libDir "common.ps1"))) {
    # When extracted flat by Inno to {tmp}, helpers may sit beside this script
    $alt = Join-Path $PSScriptRoot "common.ps1"
    if (Test-Path $alt) {
        New-Item -ItemType Directory -Force -Path $libDir | Out-Null
        Copy-Item (Join-Path $PSScriptRoot "common.ps1") (Join-Path $libDir "common.ps1") -Force
        Copy-Item (Join-Path $PSScriptRoot "service.ps1") (Join-Path $libDir "service.ps1") -Force -ErrorAction SilentlyContinue
    }
}
. (Join-Path $libDir "common.ps1")
. (Join-Path $libDir "service.ps1")

Assert-Administrator
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)

if ([string]::IsNullOrWhiteSpace($OldVersion)) {
    $OldVersion = Get-InstalledVersion
    if (-not $OldVersion) { $OldVersion = "unknown" }
}

Write-InstallStep "Pre-upgrade for version $OldVersion at $InstallDir"

Stop-AppService -InstallDir $InstallDir

$backupsDir = Join-Path $InstallDir "backups"
New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null

# Archive application code (exclude runtime/data)
$codeZip = Join-Path $backupsDir ("code-{0}.zip" -f $OldVersion)
if (Test-Path $codeZip) {
    $codeZip = Join-Path $backupsDir ("code-{0}-{1}.zip" -f $OldVersion, (Get-Date -Format "yyyyMMddHHmmss"))
}

Write-InstallStep "Archiving code to $codeZip ..."
$tempList = Join-Path $env:TEMP ("mlameh-code-archive-{0}" -f [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tempList | Out-Null

$excludeDirs = @(
    ".venv", "python", "mysql", "mysqldata", "media", "backups", "logs",
    "staticfiles", "installer\payload", "installer\Output", ".git",
    "node_modules", "frontend", "__pycache__"
)

Get-ChildItem -Path $InstallDir -Force | ForEach-Object {
    $name = $_.Name
    $skip = $false
    foreach ($ex in $excludeDirs) {
        $leaf = Split-Path $ex -Leaf
        if ($name -eq $leaf -or $name -eq $ex) { $skip = $true; break }
    }
    if (-not $skip) {
        Copy-Item -Path $_.FullName -Destination (Join-Path $tempList $name) -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Compress-Archive -Path (Join-Path $tempList "*") -DestinationPath $codeZip -Force
Remove-Item $tempList -Recurse -Force -ErrorAction SilentlyContinue
Write-InstallStep "Code archive ready: $codeZip"

# Database backup via manage.py
$venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-InstallStep "Running manage.py backup_db ..."
    Push-Location $InstallDir
    try {
        & $venvPython manage.py backup_db --dir ./backups
        if ($LASTEXITCODE -ne 0) {
            throw "backup_db failed with exit code $LASTEXITCODE"
        }
        # Tag latest backup with old version in a sidecar marker
        $latest = Get-ChildItem (Join-Path $InstallDir "backups") -Filter "backup_*" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($latest) {
            Set-Content -Path (Join-Path $backupsDir ("preupgrade-{0}.txt" -f $OldVersion)) -Value $latest.FullName
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-InstallWarn "venv python not found; skipped database backup."
}

Write-InstallStep "Pre-upgrade complete."
exit 0
