<#
    python.ps1 — Private Python via Windows embeddable ZIP (not the EXE installer).

    The full python-*-amd64.exe MSI wrapper is unreliable under elevated/hidden Setup
    (empty python.exe, ignored TargetDir). Embeddable extract is deterministic.
#>

function Get-InstallDiagLogDir {
    param([Parameter(Mandatory)][string]$InstallDir)
    $appLogs = Join-Path $InstallDir "logs"
    $mirror = Join-Path $env:ProgramData "mlamehticket\logs"
    New-Item -ItemType Directory -Force -Path $appLogs | Out-Null
    New-Item -ItemType Directory -Force -Path $mirror | Out-Null
    return [pscustomobject]@{ App = $appLogs; Mirror = $mirror }
}

function Write-InstallDiagFile {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Content
    )
    $dirs = Get-InstallDiagLogDir -InstallDir $InstallDir
    foreach ($dir in @($dirs.App, $dirs.Mirror)) {
        Set-Content -Path (Join-Path $dir $Name) -Value $Content -Encoding UTF8
    }
}

function Invoke-PythonCapture {
    param(
        [Parameter(Mandatory)][string]$PythonExe,
        [Parameter(Mandatory)][string[]]$Arguments,
        [int]$TimeoutSeconds = 30
    )
    # Prefer the call operator over Start-Process -ArgumentList (which splits on spaces).
    # Still avoid embedding double-quotes in -c strings: Windows PowerShell strips them
    # when invoking native exes. Prefer a temp .py file for non-trivial snippets.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & $PythonExe @Arguments 2>&1
        $code = $LASTEXITCODE
        $text = @(
            $raw | ForEach-Object {
                if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() }
                else { "$_" }
            }
        ) -join "`n"
        return [pscustomobject]@{
            ExitCode = $code
            StdOut   = $text
            StdErr   = ""
            Combined = $text.Trim()
        }
    }
    catch {
        return [pscustomobject]@{
            ExitCode = 1
            StdOut   = ""
            StdErr   = $_.Exception.Message
            Combined = $_.Exception.Message
        }
    }
    finally {
        $ErrorActionPreference = $prevEap
    }
}

function Invoke-PythonSnippet {
    param(
        [Parameter(Mandatory)][string]$PythonExe,
        [Parameter(Mandatory)][string]$Code
    )
    $tmp = Join-Path $env:TEMP ("mlameh-py-{0}.py" -f [guid]::NewGuid().ToString("n"))
    try {
        # UTF8 no BOM — avoids embeddable choking on BOM
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($tmp, $Code, $utf8)
        return Invoke-PythonCapture -PythonExe $PythonExe -Arguments @($tmp)
    }
    finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}

function Test-PythonVersionOk {
    param([Parameter(Mandatory)][string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe)) { return $false }
    try {
        $result = Invoke-PythonSnippet -PythonExe $PythonExe -Code @'
import sys
print("%d.%d" % sys.version_info[:2])
'@
        if ($result.ExitCode -ne 0) { return $false }
        if ($result.Combined -notmatch "(\d+)\.(\d+)") { return $false }
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        return ($major -gt 3) -or ($major -eq 3 -and $minor -ge 12)
    }
    catch {
        return $false
    }
}

function Test-IsWindowsStorePythonStub {
    param([Parameter(Mandatory)][string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe)) { return $true }
    return ($PythonExe -match '(?i)\\WindowsApps\\')
}

function Find-PythonInterpreter {
    param([Parameter(Mandatory)][string]$InstallDir)

    $private = Join-Path $InstallDir "python\python.exe"
    if (Test-PythonVersionOk $private) {
        Write-InstallStep "Using private Python: $private"
        return $private
    }

    # Prefer private runtime only for production installs; system Python is a last resort.
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py -and -not (Test-IsWindowsStorePythonStub $py.Source)) {
        try {
            $tmp = Join-Path $env:TEMP ("mlameh-py-{0}.py" -f [guid]::NewGuid().ToString("n"))
            $utf8 = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($tmp, "import sys`r`nprint(sys.executable)`r`n", $utf8)
            try {
                $result = Invoke-PythonCapture -PythonExe $py.Source -Arguments @('-3.12', $tmp)
            }
            finally {
                Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
            }
            $candidate = $result.Combined.Trim()
            if ($result.ExitCode -eq 0 -and $candidate -and (Test-PythonVersionOk $candidate)) {
                Write-InstallStep "Using system Python (py -3.12): $candidate"
                return $candidate
            }
        }
        catch { }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and -not (Test-IsWindowsStorePythonStub $pythonCmd.Source) -and (Test-PythonVersionOk $pythonCmd.Source)) {
        Write-InstallStep "Using system Python: $($pythonCmd.Source)"
        return $pythonCmd.Source
    }

    return $null
}

function Install-VcRedistIfPresent {
    param(
        [Parameter(Mandatory)][string]$PayloadDir,
        [Parameter(Mandatory)][string]$InstallDir
    )
    $redist = Get-ChildItem -Path $PayloadDir -Filter "VC_redist.x64.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $redist) {
        Write-InstallWarn "VC_redist.x64.exe not in payload; skipping (python.exe may fail without VC++ runtime)."
        return
    }

    Write-InstallStep "Installing Visual C++ redistributable (quiet) ..."
    $proc = Start-Process -FilePath $redist.FullName -ArgumentList "/install /quiet /norestart" -Wait -PassThru
    # 0 = ok, 1638 = newer already installed, 3010 = success reboot required
    if ($proc.ExitCode -notin @(0, 1638, 3010)) {
        Write-InstallDiagFile -InstallDir $InstallDir -Name "vc-redist-exit.txt" -Content "exit=$($proc.ExitCode)"
        throw "VC_redist.x64.exe failed with exit code $($proc.ExitCode)."
    }
    Write-InstallStep "VC++ redistributable OK (exit $($proc.ExitCode))."
}

function Enable-EmbeddableSite {
    param([Parameter(Mandatory)][string]$PythonDir)
    $pth = Get-ChildItem -Path $PythonDir -Filter "python*._pth" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $pth) {
        throw "Embeddable Python missing python*._pth under $PythonDir"
    }

    $lines = Get-Content -LiteralPath $pth.FullName
    $out = foreach ($line in $lines) {
        if ($line -match '^\s*#\s*import\s+site\s*$') { "import site" }
        else { $line }
    }
    if ($out -notcontains "import site") {
        $out += "import site"
    }
    if ($out -notcontains "Lib\site-packages") {
        $out += "Lib\site-packages"
    }
    Set-Content -LiteralPath $pth.FullName -Value $out -Encoding ASCII
    Write-InstallStep "Enabled site-packages in $($pth.Name)"
}

function Install-PipForEmbeddable {
    param(
        [Parameter(Mandatory)][string]$PythonExe,
        [Parameter(Mandatory)][string]$PayloadDir,
        [Parameter(Mandatory)][string]$InstallDir
    )
    $getPip = Join-Path $PayloadDir "get-pip.py"
    if (-not (Test-Path -LiteralPath $getPip)) {
        throw "get-pip.py not found in payload. Run fetch-payload.ps1 on the build machine."
    }

    # Copy beside python.exe so relative imports/paths behave
    $localGetPip = Join-Path (Split-Path $PythonExe -Parent) "get-pip.py"
    Copy-Item -LiteralPath $getPip -Destination $localGetPip -Force

    Write-InstallStep "Bootstrapping pip via get-pip.py (needs network once unless wheels are cached) ..."
    $result = Invoke-PythonCapture -PythonExe $PythonExe -Arguments @($localGetPip, "--no-warn-script-location") -TimeoutSeconds 600
    Write-InstallDiagFile -InstallDir $InstallDir -Name "get-pip-last.txt" -Content @"
exit=$($result.ExitCode)
$($result.Combined)
"@
    if ($result.ExitCode -ne 0) {
        throw "get-pip.py failed (exit $($result.ExitCode)). See logs\get-pip-last.txt and ProgramData\mlamehticket\logs\. Output: $($result.Combined)"
    }

    $pipCheck = Invoke-PythonCapture -PythonExe $PythonExe -Arguments @("-m", "pip", "--version")
    if ($pipCheck.ExitCode -ne 0) {
        throw "pip not usable after get-pip.py: $($pipCheck.Combined)"
    }
    Write-InstallStep "pip ready: $($pipCheck.Combined)"
}

function Install-BundledPython {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir
    )

    $targetDir = Join-Path $InstallDir "python"
    $null = Get-InstallDiagLogDir -InstallDir $InstallDir

    Install-VcRedistIfPresent -PayloadDir $PayloadDir -InstallDir $InstallDir

    $zip = Get-ChildItem -Path $PayloadDir -Filter "python-3.12*-embed-amd64.zip" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $zip) {
        throw "Bundled embeddable Python ZIP not found in $PayloadDir (expected python-3.12*-embed-amd64.zip). Run fetch-payload.ps1."
    }

    Write-InstallStep "Extracting private Python from $($zip.Name) to $targetDir ..."
    if (Test-Path -LiteralPath $targetDir) {
        Remove-Item -LiteralPath $targetDir -Recurse -Force -ErrorAction Stop
    }
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Expand-Archive -Path $zip.FullName -DestinationPath $targetDir -Force

    $pythonExe = Join-Path $targetDir "python.exe"
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        $listing = (Get-ChildItem -LiteralPath $targetDir -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name) -join ", "
        throw "Embeddable ZIP extracted but python.exe missing. Contents: $listing"
    }

    Enable-EmbeddableSite -PythonDir $targetDir

    $size = (Get-Item -LiteralPath $pythonExe).Length
    $probe = Invoke-PythonCapture -PythonExe $pythonExe -Arguments @('-V')
    if (-not (Test-PythonVersionOk $pythonExe)) {
        $codeProbe = Invoke-PythonSnippet -PythonExe $pythonExe -Code @'
import sys
print("%d.%d" % sys.version_info[:2])
'@
        $msg = "Embeddable python.exe failed version check (size=$size, -V exit=$($probe.ExitCode) text=[$($probe.Combined)], snippet exit=$($codeProbe.ExitCode) text=[$($codeProbe.Combined)])."
        Write-InstallDiagFile -InstallDir $InstallDir -Name "python-probe-fail.txt" -Content $msg
        throw $msg
    }

    Install-PipForEmbeddable -PythonExe $pythonExe -PayloadDir $PayloadDir -InstallDir $InstallDir

    Write-InstallStep "Private Python ready: $pythonExe"
    return $pythonExe
}

function Ensure-Python {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir
    )
    $found = Find-PythonInterpreter -InstallDir $InstallDir
    if ($found) {
        # Private embed may already exist from a partial prior run — ensure pip
        $private = Join-Path $InstallDir "python\python.exe"
        if ($found -eq $private) {
            $pipCheck = Invoke-PythonCapture -PythonExe $found -Arguments @("-m", "pip", "--version")
            if ($pipCheck.ExitCode -ne 0) {
                Install-PipForEmbeddable -PythonExe $found -PayloadDir $PayloadDir -InstallDir $InstallDir
            }
        }
        return $found
    }
    return Install-BundledPython -InstallDir $InstallDir -PayloadDir $PayloadDir
}

function Ensure-Venv {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PythonExe,
        [string]$PayloadDir = ""
    )
    <#
      Embeddable Python has no stdlib venv. Use virtualenv instead when the interpreter
      is our private embed; otherwise use stdlib venv for a full system Python.
    #>
    $venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        Write-InstallStep "Virtual environment already present."
        return $venvPython
    }

    $venvDir = Join-Path $InstallDir ".venv"
    $privateExe = [System.IO.Path]::GetFullPath((Join-Path $InstallDir "python\python.exe"))
    $resolvedExe = [System.IO.Path]::GetFullPath($PythonExe)
    $isPrivateEmbed = ($resolvedExe -ieq $privateExe)

    Write-InstallStep "Creating virtual environment at .venv ..."
    if ($isPrivateEmbed) {
        if ([string]::IsNullOrWhiteSpace($PayloadDir)) {
            $PayloadDir = Join-Path $InstallDir "installer\payload"
        }
        $wheelhouse = Join-Path $PayloadDir "wheels"
        $installArgs = @("-m", "pip", "install", "--disable-pip-version-check", "virtualenv")
        if (Test-Path -LiteralPath $wheelhouse) {
            $installArgs = @("-m", "pip", "install", "--disable-pip-version-check", "--no-index", "--find-links", $wheelhouse, "virtualenv")
        }
        $pipVirt = Invoke-PythonCapture -PythonExe $PythonExe -Arguments $installArgs -TimeoutSeconds 600
        if ($pipVirt.ExitCode -ne 0) {
            throw "Failed to install virtualenv for embeddable Python. Exit=$($pipVirt.ExitCode) $($pipVirt.Combined)"
        }
        $created = Invoke-PythonCapture -PythonExe $PythonExe -Arguments @("-m", "virtualenv", $venvDir) -TimeoutSeconds 180
        if ($created.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
            throw "virtualenv failed. Exit=$($created.ExitCode) $($created.Combined)"
        }
    }
    else {
        $result = Invoke-PythonCapture -PythonExe $PythonExe -Arguments @("-m", "venv", $venvDir) -TimeoutSeconds 180
        if (-not (Test-Path -LiteralPath $venvPython)) {
            throw "Failed to create virtual environment. Exit=$($result.ExitCode) Output=$($result.Combined)"
        }
    }

    return $venvPython
}

function Install-PythonRequirements {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$VenvPython
    )
    $req = Join-Path $InstallDir "requirements.txt"
    if (-not (Test-Path -LiteralPath $req)) {
        throw "requirements.txt not found at $req"
    }
    Write-InstallStep "Installing Python dependencies ..."

    $upgrade = Invoke-PythonCapture -PythonExe $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") -TimeoutSeconds 300
    if ($upgrade.ExitCode -ne 0) {
        throw "pip upgrade failed. Exit=$($upgrade.ExitCode) Output=$($upgrade.Combined)"
    }

    $install = Invoke-PythonCapture -PythonExe $VenvPython -Arguments @("-m", "pip", "install", "-r", $req) -TimeoutSeconds 1800
    if ($install.ExitCode -ne 0) {
        throw "pip install -r requirements.txt failed. Exit=$($install.ExitCode) Output=$($install.Combined)"
    }
}
