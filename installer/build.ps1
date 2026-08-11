<#
    build.ps1 — Build mlamehticket offline installer.
    Prerequisites: Inno Setup 6; installer\payload\ populated via fetch-payload.ps1.
    Output: installer\Output\mlamehticketSetup.exe (+ .sha256)
#>
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[BUILD] $Message" -ForegroundColor Cyan
}

$installerDir = $PSScriptRoot
$repoRoot = Split-Path -Parent $installerDir
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$payloadDir = Join-Path $installerDir "payload"
$versionFile = Join-Path $repoRoot "VERSION"

Write-Step "Repository root: $repoRoot"

if (-not (Test-Path $versionFile)) {
    throw "VERSION file missing at $versionFile"
}
$version = (Get-Content $versionFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "VERSION file is empty."
}
Write-Step "Version: $version"

# ── Payload completeness ──────────────────────────────────────────
$required = @(
    @{ Pattern = "python-3.12*-embed-amd64.zip"; Label = "Python 3.12 embeddable ZIP" },
    @{ Pattern = "get-pip.py"; Label = "get-pip.py" },
    @{ Pattern = "VC_redist.x64.exe"; Label = "VC++ redistributable" },
    @{ Pattern = "mysql-8*-winx64.zip"; Label = "MySQL 8 ZIP" },
    @{ Pattern = "WinSW*.exe"; Label = "WinSW" }
)
$missing = @()
foreach ($r in $required) {
    $hit = Get-ChildItem -Path $payloadDir -Filter $r.Pattern -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $hit) { $missing += $r.Label }
}
if ($missing.Count -gt 0) {
    throw @"
Installer payload incomplete. Missing: $($missing -join ', ').
Run:  .\installer\fetch-payload.ps1
Then rebuild.
"@
}
Write-Step "Payload OK."

# Optional checksum verify
$sums = Join-Path $payloadDir "SHA256SUMS.txt"
if (Test-Path $sums) {
    Write-Step "Verifying payload SHA256SUMS.txt ..."
    Get-Content $sums | ForEach-Object {
        if ($_ -match "^([A-Fa-f0-9]{64})\s+(\S+)$") {
            $hash = $matches[1].ToLowerInvariant()
            $name = $matches[2]
            $file = Join-Path $payloadDir $name
            if (Test-Path $file) {
                $actual = (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actual -ne $hash) {
                    throw "Checksum mismatch for $name"
                }
            }
        }
    }
    Write-Step "Checksums verified."
}

# ── Collect static ────────────────────────────────────────────────
Write-Step "Collecting static files (Django collectstatic)..."
if (!(Test-Path $pythonPath)) {
    throw "Python virtual environment not found at .venv\. Run test-local.ps1 -InstallDeps first."
}
Set-Location $repoRoot
& $pythonPath manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { throw "collectstatic failed." }
Write-Step "Static files collected."

# ── Find Inno Setup ───────────────────────────────────────────────
$isccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$isccPath = $null
foreach ($p in $isccPaths) {
    if ($p -and (Test-Path $p)) { $isccPath = $p; break }
}
if (-not $isccPath) {
    throw "Inno Setup 6 not found. Install from https://jrsoftware.org/isdl.php"
}
Write-Step "Found Inno Setup: $isccPath"

# ── Compile ───────────────────────────────────────────────────────
Write-Step "Compiling installer..."
$issFile = Join-Path $installerDir "setup.iss"
& $isccPath "/DMyAppVersion=$version" $issFile
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

$outputExe = Join-Path $installerDir "Output\mlamehticketSetup.exe"
if (-not (Test-Path $outputExe)) {
    throw "Expected output not found at $outputExe"
}

# ── SHA256 sidecar ────────────────────────────────────────────────
$hash = (Get-FileHash -Path $outputExe -Algorithm SHA256).Hash.ToLowerInvariant()
$hashFile = "$outputExe.sha256"
Set-Content -Path $hashFile -Value "$hash  mlamehticketSetup.exe" -Encoding ASCII

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Installer built successfully!" -ForegroundColor Green
Write-Host "  $outputExe" -ForegroundColor Green
Write-Host "  SHA256: $hash" -ForegroundColor Green
Write-Host "  $hashFile" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
