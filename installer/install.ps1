<#
    install.ps1 — Fresh / repair / upgrade orchestrator for mlamehticket.
    Invoked by Inno Setup after files are copied.
#>
param(
    [string]$InstallDir = "",
    [ValidateSet("fresh", "repair", "upgrade", "auto")]
    [string]$Mode = "auto",
    [string]$ServerAddress = "",
    [int]$Port = 8000,
    [string]$AdminEmail = "admin@mlamehticket.local",
    [string]$DbName = "mlamehticket",
    [string]$DbUser = "mlamehticket_user",
    [string]$DbPassword = "",
    [string]$WizardSecretsFile = "",
    [string]$ExistingMySqlUser = "",
    [string]$ExistingMySqlPassword = "",
    [switch]$ForcePrivateMySql,
    [switch]$AutoRollback,
    [string]$PackageVersion = ""
)

$ErrorActionPreference = "Stop"

$libDir = Join-Path $PSScriptRoot "lib"
. (Join-Path $libDir "common.ps1")
. (Join-Path $libDir "python.ps1")
. (Join-Path $libDir "mysql.ps1")
. (Join-Path $libDir "database.ps1")
. (Join-Path $libDir "envfile.ps1")
. (Join-Path $libDir "service.ps1")

Assert-Administrator

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Split-Path -Parent $PSScriptRoot
}
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$script:InstallDirForStatus = $InstallDir

function Write-InstallExitCode {
    param([int]$Code)
    try {
        $logsDir = Join-Path $InstallDir "logs"
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        Set-Content -Path (Join-Path $logsDir "install-exitcode.txt") -Value "$Code" -Encoding ASCII -Force
        $mirror = Join-Path $env:ProgramData "mlamehticket\logs"
        New-Item -ItemType Directory -Force -Path $mirror | Out-Null
        Set-Content -Path (Join-Path $mirror "install-exitcode.txt") -Value "$Code" -Encoding ASCII -Force
    }
    catch { }
}

$exitCode = 1
try {
if ([string]::IsNullOrWhiteSpace($PackageVersion)) {
    $verFile = Join-Path $InstallDir "VERSION"
    if (Test-Path $verFile) {
        $PackageVersion = (Get-Content $verFile -Raw).Trim()
    }
    else {
        $PackageVersion = "0.0.0"
    }
}

if ($Mode -eq "auto") {
    $Mode = Get-InstallMode -PackageVersion $PackageVersion
}
if ($Mode -eq "downgrade") {
    throw "Downgrade blocked. Installed version is newer than package $PackageVersion."
}

if ([string]::IsNullOrWhiteSpace($ServerAddress)) {
    $ServerAddress = Get-PrimaryIPv4Address
}

if ([string]::IsNullOrWhiteSpace($DbName)) { $DbName = "mlamehticket" }
if ([string]::IsNullOrWhiteSpace($DbUser)) { $DbUser = "mlamehticket_user" }

if (-not [string]::IsNullOrWhiteSpace($WizardSecretsFile) -and (Test-Path -LiteralPath $WizardSecretsFile)) {
    foreach ($line in Get-Content -LiteralPath $WizardSecretsFile) {
        if ($line -match '^\s*DbName=(.*)$') { $DbName = $matches[1].Trim() }
        elseif ($line -match '^\s*DbUser=(.*)$') { $DbUser = $matches[1].Trim() }
        elseif ($line -match '^\s*DbPassword=(.*)$') { $DbPassword = $matches[1] }
    }
    Remove-Item -LiteralPath $WizardSecretsFile -Force -ErrorAction SilentlyContinue
}

if ($Mode -eq "fresh" -and [string]::IsNullOrWhiteSpace($DbPassword)) {
    throw "Database password was not provided by the setup wizard."
}

$payloadDir = Join-Path $InstallDir "installer\payload"
if (-not (Test-Path $payloadDir)) {
    $payloadDir = Join-Path $PSScriptRoot "payload"
}

$transcriptPath = Start-InstallTranscript -InstallDir $InstallDir -Version $PackageVersion
Write-InstallStatus "Starting $Mode install ($PackageVersion)..."
Write-InstallStep "Mode: $Mode"
Write-InstallStep "Install directory: $InstallDir"
Write-InstallStep "Package version: $PackageVersion"
Write-InstallStep "Transcript: $transcriptPath"

# ── Python ────────────────────────────────────────────────────
Write-InstallStatus "1/6 Python runtime..."
Write-InstallStep "Python runtime ..."
$pythonExe = Ensure-Python -InstallDir $InstallDir -PayloadDir $payloadDir

# ── MySQL ─────────────────────────────────────────────────────
Write-InstallStatus "2/6 MySQL..."
Write-InstallStep "MySQL ..."
$mysqlInfo = Ensure-MySql `
        -InstallDir $InstallDir `
        -PayloadDir $payloadDir `
        -Mode $Mode `
        -ExistingAdminUser $ExistingMySqlUser `
        -ExistingAdminPassword $ExistingMySqlPassword `
        -ForcePrivateInstance:$ForcePrivateMySql

    # ── .env ──────────────────────────────────────────────────────
    Write-InstallStatus "3/6 Configuration (.env) + database..."
    Write-InstallStep "Configuration (.env) + database user ..."
    $envPath = Join-Path $InstallDir ".env"
    if ($Mode -eq "fresh") {
        $envValues = New-ProductionEnv `
            -InstallDir $InstallDir `
            -ServerAddress $ServerAddress `
            -Port $Port `
            -AdminEmail $AdminEmail `
            -DbName $DbName `
            -DbUser $DbUser `
            -DbPassword $DbPassword
    }
    else {
        if (-not (Test-Path $envPath)) {
            throw ".env is missing during $Mode. Restore it from backup or uninstall and reinstall."
        }
        Merge-EnvFromExample -InstallDir $InstallDir -PackageVersion $PackageVersion
        $envValues = @{
            DEBUG                       = (Read-DotEnvValue $envPath "DEBUG")
            SECRET_KEY                  = (Read-DotEnvValue $envPath "SECRET_KEY")
            ALLOWED_HOSTS               = (Read-DotEnvValue $envPath "ALLOWED_HOSTS")
            CSRF_TRUSTED_ORIGINS        = (Read-DotEnvValue $envPath "CSRF_TRUSTED_ORIGINS")
            SITE_URL                    = (Read-DotEnvValue $envPath "SITE_URL")
            DB_ENGINE                   = (Read-DotEnvValue $envPath "DB_ENGINE")
            DB_NAME                     = (Read-DotEnvValue $envPath "DB_NAME")
            DB_USER                     = (Read-DotEnvValue $envPath "DB_USER")
            DB_PASSWORD                 = (Read-DotEnvValue $envPath "DB_PASSWORD")
            DB_HOST                     = (Read-DotEnvValue $envPath "DB_HOST")
            DB_PORT                     = (Read-DotEnvValue $envPath "DB_PORT")
            DEFAULT_SUPERADMIN_USERNAME = (Read-DotEnvValue $envPath "DEFAULT_SUPERADMIN_USERNAME")
            DEFAULT_SUPERADMIN_EMAIL    = (Read-DotEnvValue $envPath "DEFAULT_SUPERADMIN_EMAIL")
            DEFAULT_SUPERADMIN_PASSWORD = (Read-DotEnvValue $envPath "DEFAULT_SUPERADMIN_PASSWORD")
            BACKUP_DIR                  = (Read-DotEnvValue $envPath "BACKUP_DIR")
            BACKUP_KEEP                 = (Read-DotEnvValue $envPath "BACKUP_KEEP")
            TIME_ZONE                   = (Read-DotEnvValue $envPath "TIME_ZONE")
            LOG_LEVEL                   = (Read-DotEnvValue $envPath "LOG_LEVEL")
            LOG_TO_FILE                 = (Read-DotEnvValue $envPath "LOG_TO_FILE")
        }
        # Prefer port from .env SITE_URL if present
        if ($envValues.SITE_URL -match ":(\d+)\s*$") {
            $Port = [int]$matches[1]
        }
    }

    # ── Database / user ───────────────────────────────────────────
    $dbHost = if ($envValues.DB_HOST) { $envValues.DB_HOST } else { "127.0.0.1" }
    $dbPort = if ($envValues.DB_PORT) { [int]$envValues.DB_PORT } else { 3306 }

    if ($Mode -eq "fresh") {
        Ensure-AppDatabase `
            -MysqlExe $mysqlInfo.MysqlExe `
            -AdminUser $mysqlInfo.AdminUser `
            -AdminPassword $mysqlInfo.AdminPassword `
            -DbName $envValues.DB_NAME `
            -DbUser $envValues.DB_USER `
            -DbPassword $envValues.DB_PASSWORD `
            -HostName $dbHost `
            -Port $dbPort
    }
    else {
        # Repair/upgrade: app user first (true no-op when DB is fine), then root from FIRST-LOGIN.txt
        if (Test-AppDatabaseReady `
                -MysqlExe $mysqlInfo.MysqlExe `
                -DbUser $envValues.DB_USER `
                -DbPassword $envValues.DB_PASSWORD `
                -DbName $envValues.DB_NAME `
                -HostName $dbHost `
                -Port $dbPort) {
            Write-InstallStep "Database '$($envValues.DB_NAME)' reachable as app user; skipping admin DDL."
        }
        else {
            $adminUser = $mysqlInfo.AdminUser
            $adminPass = $mysqlInfo.AdminPassword
            if ([string]::IsNullOrWhiteSpace($adminPass) -and $mysqlInfo.InstalledByUs) {
                $adminPass = Get-BundledMySqlRootPassword -InstallDir $InstallDir
                if ($adminPass) {
                    Write-InstallStep "Using bundled MySQL root password from FIRST-LOGIN.txt."
                    $adminUser = "root"
                }
            }
            if ([string]::IsNullOrWhiteSpace($adminPass) -and -not [string]::IsNullOrWhiteSpace($ExistingMySqlPassword)) {
                $adminUser = $ExistingMySqlUser
                $adminPass = $ExistingMySqlPassword
            }
            if ([string]::IsNullOrWhiteSpace($adminUser) -or [string]::IsNullOrWhiteSpace($adminPass)) {
                throw "Cannot ensure database: app user connection failed and no MySQL admin password is available. Re-run Setup with MySQL admin credentials, or restore FIRST-LOGIN.txt (bundled MySQL)."
            }
            Ensure-AppDatabase `
                -MysqlExe $mysqlInfo.MysqlExe `
                -AdminUser $adminUser `
                -AdminPassword $adminPass `
                -DbName $envValues.DB_NAME `
                -DbUser $envValues.DB_USER `
                -DbPassword $envValues.DB_PASSWORD `
                -HostName $dbHost `
                -Port $dbPort
        }
    }

    # ── venv + deps ─────────────────────────────────────────────
    Write-InstallStatus "4/6 Virtualenv + Python packages (this can take several minutes)..."
    Write-InstallStep "Virtualenv + Python packages ..."
    $venvPython = Ensure-Venv -InstallDir $InstallDir -PythonExe $pythonExe -PayloadDir $payloadDir
    Install-PythonRequirements -InstallDir $InstallDir -VenvPython $venvPython

    # ── migrate + collectstatic ───────────────────────────────────
    Write-InstallStatus "5/6 Django migrate + collectstatic..."
    Write-InstallStep "Running migrations ..."
    Set-Location $InstallDir
    & $venvPython manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "manage.py migrate failed." }

    Write-InstallStep "Collecting static files ..."
    & $venvPython manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { throw "manage.py collectstatic failed." }

    # ── Windows service ───────────────────────────────────────────
    Write-InstallStatus "6/6 Windows service + firewall + health check..."
    Write-InstallStep "Windows service + firewall + health check ..."
    Ensure-AppService `
        -InstallDir $InstallDir `
        -PayloadDir $payloadDir `
        -Port $Port `
        -DependOnBundledMySql:$mysqlInfo.InstalledByUs

    # ── Firewall ──────────────────────────────────────────────────
    Ensure-FirewallRule -Port $Port

    # ── Health check ──────────────────────────────────────────────
    if (-not (Wait-HttpReady -Port $Port -TimeoutSeconds 90)) {
        throw "Service did not become ready on port $Port within timeout."
    }

    # ── FIRST-LOGIN (fresh only) ──────────────────────────────────
    if ($Mode -eq "fresh") {
        $firstLogin = Write-FirstLoginFile `
            -InstallDir $InstallDir `
            -EnvValues $envValues `
            -MySqlRootPassword $mysqlInfo.RootPassword `
            -WeInstalledMySql:$mysqlInfo.InstalledByUs
        try { Start-Process notepad.exe $firstLogin } catch { }
    }

    # ── Registry stamp ────────────────────────────────────────────
    if (-not (Test-Path $script:RegistryPath)) {
        New-Item -Path $script:RegistryPath -Force | Out-Null
    }
    Set-ItemProperty -Path $script:RegistryPath -Name Version -Value $PackageVersion -Type String
    Set-ItemProperty -Path $script:RegistryPath -Name InstallPath -Value $InstallDir -Type String
    Set-ItemProperty -Path $script:RegistryPath -Name Port -Value $Port -Type DWord
    Set-ItemProperty -Path $script:RegistryPath -Name BundledMySql -Value ([int]$mysqlInfo.InstalledByUs) -Type DWord

    $success = $true
    $exitCode = 0
    Write-InstallStatus "Setup completed successfully."
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  mlamehticket $Mode completed ($PackageVersion)" -ForegroundColor Green
    Write-Host "  URL: http://127.0.0.1:$Port/" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
}
catch {
    $exitCode = 1
    Write-InstallError $_.Exception.Message
    try { Stop-AppService -InstallDir $InstallDir } catch { }

    $backupsDir = Join-Path $InstallDir "backups"
    Write-Host ""
    Write-Host "Installation failed. The service has been left stopped." -ForegroundColor Red
    if (Test-Path $backupsDir) {
        Write-Host "Pre-upgrade artifacts (if any) are under: $backupsDir" -ForegroundColor Yellow
        Write-Host "  See installer\README.md (Failed upgrade — manual restore) for exact steps." -ForegroundColor Yellow
        Write-Host "  Restore DB:  mysql ... < backups\backup_*.sql" -ForegroundColor Yellow
        Write-Host "  Restore code: expand backups\code-*.zip over the install dir" -ForegroundColor Yellow
    }

    if ($AutoRollback -and $Mode -eq "upgrade") {
        Write-InstallWarn "AutoRollback requested but automated restore is best-effort; check backups\ manually."
    }
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
    Write-InstallExitCode -Code $exitCode
}

exit $exitCode
