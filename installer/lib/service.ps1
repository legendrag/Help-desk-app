<#
    service.ps1 — Register / reconfigure / restart the mlamehticketApp WinSW service.
#>

function Get-WinSwPaths {
    param([Parameter(Mandatory)][string]$InstallDir)
    return [pscustomobject]@{
        Exe  = Join-Path $InstallDir "installer\winsw\mlamehticketApp.exe"
        Xml  = Join-Path $InstallDir "installer\winsw\mlamehticketApp.xml"
        Dir  = Join-Path $InstallDir "installer\winsw"
    }
}

function Write-WinSwConfig {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][int]$Port,
        [switch]$DependOnBundledMySql
    )

    $paths = Get-WinSwPaths -InstallDir $InstallDir
    New-Item -ItemType Directory -Force -Path $paths.Dir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $InstallDir "logs") | Out-Null

    $venvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
    $privatePython = Join-Path $InstallDir "python\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        $python = $venvPython
    }
    elseif (Test-Path -LiteralPath $privatePython) {
        $python = $privatePython
    }
    else {
        throw "No Python runtime found (.venv or python\python.exe) under $InstallDir."
    }
    $dependXml = ""
    if ($DependOnBundledMySql) {
        $dependXml = "  <depend>$($script:MySqlServiceName)</depend>"
    }

    # Escape & in paths for XML — rare but spaces are fine unescaped in element text
    $xml = @"
<service>
  <id>$($script:AppServiceName)</id>
  <name>mlamehticket</name>
  <description>mlamehticket help-desk (Daphne ASGI)</description>
  <executable>$python</executable>
  <arguments>-m daphne -b 0.0.0.0 -p $Port config.asgi:application</arguments>
  <workingdirectory>$InstallDir</workingdirectory>
  <logpath>$(Join-Path $InstallDir "logs")</logpath>
  <log mode="roll-by-time">
    <pattern>yyyyMMdd</pattern>
    <autoRollAtTime>00:00:00</autoRollAtTime>
    <keepFiles>30</keepFiles>
  </log>
  <env name="ASGI_THREADS" value="200"/>
  <env name="PYTHONIOENCODING" value="utf-8"/>
  <env name="PYTHONUNBUFFERED" value="1"/>
  <env name="LOG_TO_FILE" value="1"/>
  <startmode>Automatic</startmode>
  <delayedAutoStart>true</delayedAutoStart>
  <onfailure action="restart" delay="10 sec"/>
$dependXml
</service>
"@
    Set-Content -Path $paths.Xml -Value $xml -Encoding UTF8
    return $paths
}

function Ensure-WinSwBinary {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir
    )
    $paths = Get-WinSwPaths -InstallDir $InstallDir
    New-Item -ItemType Directory -Force -Path $paths.Dir | Out-Null

    $src = Join-Path $PayloadDir "WinSW-x64.exe"
    if (-not (Test-Path $src)) {
        $alt = Get-ChildItem -Path $PayloadDir -Filter "WinSW*.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($alt) { $src = $alt.FullName }
    }
    if (-not (Test-Path $src)) {
        throw "WinSW executable not found in $PayloadDir (expected WinSW-x64.exe)."
    }
    Copy-Item -Path $src -Destination $paths.Exe -Force
    return $paths
}

function Test-PortFreeOrOurs {
    param(
        [Parameter(Mandatory)][int]$Port,
        [string]$ServiceName = "mlamehticketApp"
    )
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { return $true }
    foreach ($l in $listeners) {
        try {
            $proc = Get-Process -Id $l.OwningProcess -ErrorAction Stop
            # Allow our service's python
            if ($proc.ProcessName -match "python|mlamehticketApp") {
                return $true
            }
        }
        catch { }
    }
    return $false
}

function Ensure-AppService {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir,
        [Parameter(Mandatory)][int]$Port,
        [switch]$DependOnBundledMySql
    )

    if (-not (Test-PortFreeOrOurs -Port $Port)) {
        throw "Port $Port is already in use by another process. Choose a different port or stop the conflicting service."
    }

    $paths = Ensure-WinSwBinary -InstallDir $InstallDir -PayloadDir $PayloadDir
    Write-WinSwConfig -InstallDir $InstallDir -Port $Port -DependOnBundledMySql:$DependOnBundledMySql | Out-Null

    $svc = Get-Service -Name $script:AppServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-InstallStep "Installing Windows service $($script:AppServiceName) ..."
        & $paths.Exe install
        if ($LASTEXITCODE -ne 0) { throw "WinSW install failed with exit code $LASTEXITCODE" }
    }
    else {
        Write-InstallStep "Refreshing Windows service configuration ..."
        if ($svc.Status -eq "Running") {
            & $paths.Exe stop
            Start-Sleep -Seconds 2
        }
        # Re-install config by stop/uninstall/install is safer for XML changes
        & $paths.Exe uninstall
        Start-Sleep -Seconds 1
        & $paths.Exe install
        if ($LASTEXITCODE -ne 0) { throw "WinSW reinstall failed with exit code $LASTEXITCODE" }
    }

    Write-InstallStep "Starting $($script:AppServiceName) ..."
    & $paths.Exe start
    Start-Sleep -Seconds 3
    $svc = Get-Service -Name $script:AppServiceName -ErrorAction SilentlyContinue
    if (-not $svc -or $svc.Status -ne "Running") {
        Write-InstallWarn "Service not running yet; will rely on health check."
    }
}

function Stop-AppService {
    param([Parameter(Mandatory)][string]$InstallDir)
    $paths = Get-WinSwPaths -InstallDir $InstallDir
    $svc = Get-Service -Name $script:AppServiceName -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") {
        Write-InstallStep "Stopping $($script:AppServiceName) ..."
        if (Test-Path $paths.Exe) {
            & $paths.Exe stop
        }
        else {
            Stop-Service -Name $script:AppServiceName -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }
}

function Remove-AppService {
    param([Parameter(Mandatory)][string]$InstallDir)
    $paths = Get-WinSwPaths -InstallDir $InstallDir
    Stop-AppService -InstallDir $InstallDir
    if (Test-Path $paths.Exe) {
        & $paths.Exe uninstall
    }
    elseif (Get-Service -Name $script:AppServiceName -ErrorAction SilentlyContinue) {
        sc.exe delete $script:AppServiceName | Out-Null
    }
}
