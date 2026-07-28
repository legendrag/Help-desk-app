<# 
    test-local.ps1 — Run mlamehticket locally with SQLite for development/testing.
    Usage: .\test-local.ps1 [-InstallDeps] [-Fresh] [-NoBrowser] [-SkipI18nCheck]
#>
param(
    [switch]$InstallDeps,
    [switch]$Fresh,
    [switch]$NoBrowser,
    [switch]$SkipI18nCheck
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[mlamehticket] $Message" -ForegroundColor Cyan
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

# ── Translation catalog ───────────────────────────────────────────
# gettext has no concept of a missing translation, so drift renders English
# silently. This gate makes it fail loudly instead.
if (-not $SkipI18nCheck) {
    $poFile = Join-Path $repoRoot "locale\ar\LC_MESSAGES\django.po"
    $moFile = Join-Path $repoRoot "locale\ar\LC_MESSAGES\django.mo"

    $hasPolib = & $pythonPath -c "import importlib.util; print('yes' if importlib.util.find_spec('polib') else 'no')"

    if ($hasPolib.Trim() -ne "yes") {
        Write-Host "[mlamehticket] Skipping translation check - polib not installed." -ForegroundColor Yellow
        Write-Host "[mlamehticket] Enable it with: .venv\Scripts\python.exe -m pip install -r requirements-dev.txt" -ForegroundColor DarkGray
    }
    else {
        # Recompile only when the catalog actually changed, so the tracked .mo
        # does not churn on every run.
        if (!(Test-Path $moFile) -or ((Get-Item $poFile).LastWriteTime -gt (Get-Item $moFile).LastWriteTime)) {
            Write-Step "Catalog changed since last compile - rebuilding django.mo"
            & $pythonPath scripts\i18n.py compile
        }

        Write-Step "Verifying translation coverage"
        $prevPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $pythonPath scripts\i18n.py check
        $i18nExit = $LASTEXITCODE
        $ErrorActionPreference = $prevPreference

        if ($i18nExit -ne 0) {
            Write-Host ""
            Write-Host "[mlamehticket] Translation check FAILED - those strings would render in English." -ForegroundColor Red
            Write-Host "[mlamehticket] Fix:    python scripts\i18n.py update   (translate the new entries, then 'compile')" -ForegroundColor Red
            Write-Host "[mlamehticket] Detail: python scripts\i18n.py check --verbose" -ForegroundColor DarkGray
            Write-Host "[mlamehticket] Bypass: .\test-local.ps1 -SkipI18nCheck" -ForegroundColor DarkGray
            exit 1
        }
    }
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
