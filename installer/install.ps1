<#
    install.ps1 — Post-installation script for Help Desk.
    Run automatically by Inno Setup after file extraction.
    Sets up Python venv, installs deps, configures DB, runs migrations.
#>
param(
    [string]$InstallDir = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[INSTALL] $Message" -ForegroundColor Cyan
}

Write-Step "Starting Help Desk post-install setup..."
Write-Step "Install directory: $InstallDir"

# ── Create .env from template ──────────────────────────────────────
$envFile = Join-Path $InstallDir ".env"
$envExample = Join-Path $InstallDir ".env.example"

if (!(Test-Path $envFile)) {
    Write-Step "Creating .env from .env.example"
    Copy-Item $envExample $envFile

    # Set DB_ENGINE to mysql for production
    $content = Get-Content $envFile -Raw
    $content = $content -replace "(?m)^DB_ENGINE=.*$", "DB_ENGINE=mysql"
    Set-Content -Path $envFile -Value $content -Encoding UTF8
    Write-Step ".env configured with DB_ENGINE=mysql"
}

# ── Create Python virtual environment ──────────────────────────────
$venvDir = Join-Path $InstallDir ".venv"
$pythonPath = Join-Path $venvDir "Scripts\python.exe"

if (!(Test-Path $pythonPath)) {
    Write-Step "Creating Python virtual environment..."
    python -m venv $venvDir
}

if (!(Test-Path $pythonPath)) {
    Write-Host "[INSTALL] ERROR: Python venv creation failed." -ForegroundColor Red
    Write-Host "[INSTALL] Make sure Python 3.12+ is installed and in PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Install Python dependencies ────────────────────────────────────
Write-Step "Installing Python dependencies..."
$requirementsFile = Join-Path $InstallDir "requirements.txt"
& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r $requirementsFile

# ── Run Django migrations ──────────────────────────────────────────
Write-Step "Running database migrations..."
$env:DB_ENGINE = "mysql"
Set-Location $InstallDir
& $pythonPath manage.py migrate

# ── Seed initial data ─────────────────────────────────────────────
Write-Step "Seeding initial data..."
# & $pythonPath manage.py seed_demo_data

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Help Desk installation completed!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT: Before first run, edit .env file:"
Write-Host "  - Set DB_PASSWORD to your MySQL password"
Write-Host "  - Set SECRET_KEY to a random string"
Write-Host ""
Read-Host "Press Enter to close"
