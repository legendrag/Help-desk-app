<# 
    test-local.ps1 — Run DeskPlus locally with SQLite for development/testing.
    Usage: .\test-local.ps1 [-InstallDeps] [-Fresh] [-NoBrowser]
#>
param(
    [switch]$InstallDeps,
    [switch]$Fresh,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[DESKPLUS] $Message" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

Write-Step "Mode: LOCAL TEST (SQLite)"
Write-Step "Repository root: $repoRoot"

# ── Ensure .env exists ─────────────────────────────────────────────
$envFile = Join-Path $repoRoot ".env"
$envExample = Join-Path $repoRoot ".env.example"

if (!(Test-Path $envFile)) {
    Write-Step "Creating .env from .env.example"
    Copy-Item $envExample $envFile
}

# ── Python venv ────────────────────────────────────────────────────
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonPath)) {
    Write-Step "Creating Python virtual environment (.venv)"
    python -m venv .venv
}

# ── Install deps ───────────────────────────────────────────────────
if ($InstallDeps -or !(Test-Path (Join-Path $repoRoot ".venv\Lib\site-packages\django"))) {
    Write-Step "Installing dependencies from requirements.txt"
    & $pythonPath -m pip install -r requirements.txt
}

# ── Database Setup ────────────────────────────────────────────────
$sqlitePath = Join-Path $repoRoot "db.sqlite3"
$isDbFresh = $false

if ($Fresh -and (Test-Path $sqlitePath)) {
    Write-Step "Performing fresh reset..."
    Remove-Item -Force $sqlitePath
    $isDbFresh = $true
}
elseif (!(Test-Path $sqlitePath)) {
    $isDbFresh = $true
}

Write-Step "Running database migrations (SQLite)"
& $pythonPath manage.py migrate

if ($isDbFresh) {
    Write-Step "Seeding demo data"
    & $pythonPath manage.py seed_demo_data
}

# ── Start Server ──────────────────────────────────────────────────
Write-Step "Starting Django server (runserver) on 0.0.0.0:8000"
$env:DB_ENGINE = "sqlite"

if (-not $NoBrowser) {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8000"
}

& $pythonPath manage.py runserver 0.0.0.0:8000
