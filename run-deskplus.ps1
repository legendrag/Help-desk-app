<#
    run-deskplus.ps1 — Production launcher for the monolithic DeskPlus system.
    This script starts the Daphne ASGI server which supports both HTTP and WebSockets.
    Usage: .\run-deskplus.ps1 [-NoBrowser]
#>
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[DESKPLUS] $Message" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

# ── Load .env to ensure environment variables are ready ───────────
$envFile = Join-Path $repoRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

# ── Locate Python ──────────────────────────────────────────────────
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonPath)) {
    Write-Error "Python virtual environment not found at .venv\. Please run install.ps1 or test-local.ps1 first."
    exit 1
}

# ── Start Server ──────────────────────────────────────────────────
Write-Step "Starting DeskPlus Production Server (Daphne)..."
Write-Step "Address: http://0.0.0.0:8000"
Write-Step "(Supports Real-time Chat & Notifications)"

# Open browser after a short delay to allow server to bind
if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        Start-Sleep -Seconds 3
        Start-Process "http://localhost:8000"
    } | Out-Null
}

# Increase ASGI threadpool to allow concurrent static file serving without blocking
[System.Environment]::SetEnvironmentVariable("ASGI_THREADS", "200", "Process")

# Start Daphne bound to all interfaces
# -b 0.0.0.0 allows access from other devices in the same network
& $pythonPath -m daphne -b 0.0.0.0 -p 8000 config.asgi:application
