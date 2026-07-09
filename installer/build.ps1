<#
    build.ps1 — Build DeskPlus installer (Monolithic version).
    Prerequisites: Inno Setup 6 installed.
    Output: installer\Output\DeskPlusSetup.exe
#>

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[BUILD] $Message" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$installerDir = Join-Path $repoRoot "installer"
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"

Write-Step "Repository root: $repoRoot"

# ── Prepare Static Files ───────────────────────────────────────────
Write-Step "Collecting static files (Django collectstatic)..."
if (!(Test-Path $pythonPath)) {
    throw "Python virtual environment not found at .venv\. Run test-local.ps1 -InstallDeps first."
}

Set-Location $repoRoot
& $pythonPath manage.py collectstatic --noinput

Write-Step "Static files collected."

# ── Find Inno Setup compiler ──────────────────────────────────────
$isccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
foreach ($p in $isccPaths) {
    if (Test-Path $p) {
        $isccPath = $p
        break
    }
}

if (-not $isccPath) {
    throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php"
}

Write-Step "Found Inno Setup: $isccPath"

# ── Compile installer ─────────────────────────────────────────────
Write-Step "Compiling installer..."
$issFile = Join-Path $installerDir "setup.iss"

& $isccPath $issFile

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

$outputExe = Join-Path $installerDir "Output\DeskPlusSetup.exe"
if (Test-Path $outputExe) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Installer built successfully!" -ForegroundColor Green
    Write-Host "  $outputExe" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
}
else {
    Write-Host "[BUILD] Warning: Expected output not found at $outputExe" -ForegroundColor Yellow
}
