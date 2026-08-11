<#
    fetch-payload.ps1 — Download and SHA256-verify offline installer payloads.
    Run on the build machine (requires internet). Output goes to installer\payload\.
#>
$ErrorActionPreference = "Stop"

$payloadDir = Join-Path $PSScriptRoot "payload"
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null

# Pinned versions. Update URLs + expected SHA256 together when bumping.
# Python: use the *embeddable* ZIP (not the full EXE installer) — reliable under Setup.
$artifacts = @(
    @{
        Name     = "python-3.12.10-embed-amd64.zip"
        Url      = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
        Sha256   = ""
        Required = $true
    },
    @{
        Name     = "get-pip.py"
        Url      = "https://bootstrap.pypa.io/get-pip.py"
        Sha256   = ""
        Required = $true
    },
    @{
        Name     = "VC_redist.x64.exe"
        Url      = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        Sha256   = ""
        Required = $true
    },
    @{
        Name     = "mysql-8.0.46-winx64.zip"
        Url      = "https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-8.0.46-winx64.zip"
        Sha256   = ""
        Required = $true
    },
    @{
        Name     = "WinSW-x64.exe"
        Url      = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
        Sha256   = ""
        Required = $true
    }
)

$checksumsFile = Join-Path $payloadDir "SHA256SUMS.txt"
$known = @{}
if (Test-Path $checksumsFile) {
    Get-Content $checksumsFile | ForEach-Object {
        if ($_ -match "^([A-Fa-f0-9]{64})\s+(\S+)$") {
            $known[$matches[2]] = $matches[1].ToLowerInvariant()
        }
    }
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

foreach ($a in $artifacts) {
    $dest = Join-Path $payloadDir $a.Name
    $expected = if ($a.Sha256) { $a.Sha256.ToLowerInvariant() } elseif ($known.ContainsKey($a.Name)) { $known[$a.Name] } else { "" }

    if (Test-Path $dest) {
        $actual = Get-FileSha256 $dest
        if ($expected -and $actual -ne $expected) {
            Write-Host "[PAYLOAD] Hash mismatch for $($a.Name); re-downloading..." -ForegroundColor Yellow
            Remove-Item $dest -Force
        }
        else {
            Write-Host "[PAYLOAD] OK (cached): $($a.Name)" -ForegroundColor Green
            if (-not $expected) { $known[$a.Name] = $actual }
            continue
        }
    }

    Write-Host "[PAYLOAD] Downloading $($a.Name) ..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $a.Url -OutFile $dest -UseBasicParsing
    }
    catch {
        if ($a.Name -like "mysql-*") {
            $alt = "https://dev.mysql.com/get/Downloads/MySQL-8.0/$($a.Name)"
            Write-Host "[PAYLOAD] Retry via $alt" -ForegroundColor Yellow
            Invoke-WebRequest -Uri $alt -OutFile $dest -UseBasicParsing
        }
        else {
            throw
        }
    }

    $actual = Get-FileSha256 $dest
    if ($expected -and $actual -ne $expected) {
        Remove-Item $dest -Force -ErrorAction SilentlyContinue
        throw "SHA256 mismatch for $($a.Name). Expected $expected, got $actual"
    }
    $known[$a.Name] = $actual
    Write-Host "[PAYLOAD] Downloaded $($a.Name) ($actual)" -ForegroundColor Green
}

# Drop obsolete full Python EXE if present (no longer used)
$oldExe = Get-ChildItem -Path $payloadDir -Filter "python-3.12*-amd64.exe" -ErrorAction SilentlyContinue
foreach ($f in $oldExe) {
    Write-Host "[PAYLOAD] Removing obsolete $($f.Name) (switched to embeddable ZIP)" -ForegroundColor Yellow
    Remove-Item $f.FullName -Force
    $known.Remove($f.Name) | Out-Null
}

$lines = $known.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Value)  $($_.Name)" }
Set-Content -Path $checksumsFile -Value $lines -Encoding ASCII

Write-Host ""
Write-Host "Payload ready in $payloadDir" -ForegroundColor Green
Write-Host "Checksums written to $checksumsFile" -ForegroundColor Green
