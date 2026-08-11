<#
    mysql.ps1 — Detect existing MySQL/MariaDB or install a private bundled instance.
#>

function Test-ExistingMySql {
    $services = Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "^(MySQL|MariaDB|mysql|mariadb)" -or $_.DisplayName -match "MySQL|MariaDB" }
    $portOpen = Test-TcpPortOpen -HostName "127.0.0.1" -Port 3306
    return [pscustomobject]@{
        HasService = [bool]$services
        Services   = @($services)
        PortOpen   = $portOpen
        Detected   = ([bool]$services -or $portOpen)
    }
}

function Test-MySqlAdminConnection {
    param(
        [Parameter(Mandatory)][string]$MysqlExe,
        [Parameter(Mandatory)][string]$User,
        [string]$Password = "",
        [string]$HostName = "127.0.0.1",
        [int]$Port = 3306
    )
    $env:MYSQL_PWD = $Password
    try {
        $args = @(
            "--protocol=TCP",
            "--host=$HostName",
            "--port=$Port",
            "--user=$User",
            "--batch",
            "--connect-timeout=10",
            "-e", "SELECT 1;"
        )
        $null = "" | & $MysqlExe @args 2>&1
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
    }
}

function Test-AppDatabaseReady {
    param(
        [Parameter(Mandatory)][string]$MysqlExe,
        [Parameter(Mandatory)][string]$DbUser,
        [string]$DbPassword = "",
        [Parameter(Mandatory)][string]$DbName,
        [string]$HostName = "127.0.0.1",
        [int]$Port = 3306
    )
    $env:MYSQL_PWD = $DbPassword
    try {
        $sql = "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='$DbName';"
        $args = @(
            "--protocol=TCP",
            "--host=$HostName",
            "--port=$Port",
            "--user=$DbUser",
            "--batch",
            "--connect-timeout=10",
            "-N",
            "-e", $sql
        )
        $output = "" | & $MysqlExe @args 2>&1
        if ($LASTEXITCODE -ne 0) { return $false }
        $name = ($output | Out-String).Trim()
        return ($name -eq $DbName)
    }
    finally {
        Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
    }
}

function Get-BundledMySqlRootPassword {
    param([Parameter(Mandatory)][string]$InstallDir)
    $path = Join-Path $InstallDir "FIRST-LOGIN.txt"
    if (-not (Test-Path $path)) { return $null }
    foreach ($line in Get-Content $path) {
        if ($line -match "^MySQL root password \(bundled server only\):\s*(.+)$") {
            return $matches[1].Trim()
        }
    }
    return $null
}

function Find-MysqlClient {
    param([string]$InstallDir = "")
    $candidates = @()
    if ($InstallDir) {
        $candidates += (Join-Path $InstallDir "mysql\bin\mysql.exe")
    }
    $cmd = Get-Command mysql -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $candidates += @(
        "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe",
        "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
        "C:\Program Files\MariaDB*\bin\mysql.exe",
        "C:\xampp\mysql\bin\mysql.exe"
    )
    foreach ($c in $candidates) {
        $resolved = Get-Item $c -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($resolved -and (Test-Path $resolved.FullName)) {
            return $resolved.FullName
        }
    }
    return $null
}

function Install-BundledMySql {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir
    )

    $mysqlHome = Join-Path $InstallDir "mysql"
    $dataDir = Join-Path $InstallDir "mysqldata"
    $logsDir = Join-Path $InstallDir "logs"
    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

    if (Get-Service -Name $script:MySqlServiceName -ErrorAction SilentlyContinue) {
        Write-InstallStep "Bundled MySQL service already registered."
        if ((Get-Service -Name $script:MySqlServiceName).Status -ne "Running") {
            Start-Service -Name $script:MySqlServiceName
        }
        $existingRoot = Get-BundledMySqlRootPassword -InstallDir $InstallDir
        if ([string]::IsNullOrWhiteSpace($existingRoot)) {
            Write-InstallWarn "Private MySQL is running but FIRST-LOGIN.txt has no root password; admin DDL may fail until credentials are supplied."
        }
        return [pscustomobject]@{
            InstalledByUs = $true
            MysqlHome     = $mysqlHome
            RootPassword  = [string]$existingRoot
            MysqlExe      = (Join-Path $mysqlHome "bin\mysql.exe")
            MysqldExe     = (Join-Path $mysqlHome "bin\mysqld.exe")
        }
    }

    $zip = Get-ChildItem -Path $PayloadDir -Filter "mysql-8*-winx64.zip" -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $zip) {
        throw "Bundled MySQL ZIP not found in $PayloadDir (expected mysql-8*-winx64.zip)."
    }

    if (-not (Test-Path (Join-Path $mysqlHome "bin\mysqld.exe"))) {
        Write-InstallStep "Extracting MySQL from $($zip.Name) ..."
        $extractTemp = Join-Path $InstallDir "_mysql_extract"
        if (Test-Path $extractTemp) { Remove-Item $extractTemp -Recurse -Force }
        Expand-Archive -Path $zip.FullName -DestinationPath $extractTemp -Force
        $inner = Get-ChildItem $extractTemp -Directory | Select-Object -First 1
        if (-not $inner) { throw "MySQL ZIP did not contain a top-level directory." }
        if (Test-Path $mysqlHome) { Remove-Item $mysqlHome -Recurse -Force }
        Move-Item -Path $inner.FullName -Destination $mysqlHome
        Remove-Item $extractTemp -Recurse -Force -ErrorAction SilentlyContinue
    }

    $mysqld = Join-Path $mysqlHome "bin\mysqld.exe"
    $mysqlExe = Join-Path $mysqlHome "bin\mysql.exe"
    if (-not (Test-Path $mysqld)) { throw "mysqld.exe missing after extract." }

    $myIni = Join-Path $mysqlHome "my.ini"
    $dataFwd = ConvertTo-ForwardSlashPath $dataDir
    $logFwd = ConvertTo-ForwardSlashPath (Join-Path $logsDir "mysql-error.log")
    $basedirFwd = ConvertTo-ForwardSlashPath $mysqlHome

    @"
[mysqld]
basedir=$basedirFwd
datadir=$dataFwd
port=3306
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
default-authentication-plugin=mysql_native_password
log_error=$logFwd
binlog_expire_logs_seconds=604800
max_allowed_packet=64M

[client]
port=3306
default-character-set=utf8mb4
"@ | Set-Content -Path $myIni -Encoding ASCII

    if (-not (Test-Path $dataDir) -or -not (Get-ChildItem $dataDir -ErrorAction SilentlyContinue)) {
        Write-InstallStep "Initializing MySQL data directory ..."
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        & $mysqld --defaults-file="$myIni" --initialize-insecure --console
        if ($LASTEXITCODE -ne 0) {
            throw "mysqld --initialize-insecure failed with exit code $LASTEXITCODE"
        }
    }

    Write-InstallStep "Registering Windows service $($script:MySqlServiceName) ..."
    & $mysqld --install $script:MySqlServiceName --defaults-file="$myIni"
    if ($LASTEXITCODE -ne 0) {
        # Service may already exist from a partial prior run
        Write-InstallWarn "mysqld --install returned $LASTEXITCODE (continuing if service exists)"
    }

    Start-Service -Name $script:MySqlServiceName
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPortOpen -Port 3306) { break }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-TcpPortOpen -Port 3306)) {
        throw "MySQL service started but port 3306 is not accepting connections."
    }

    $rootPassword = New-SecurePassword -Length 28
    Write-InstallStep "Setting MySQL root password ..."
    # Build SQL with concatenation so PowerShell cannot expand $ inside the password
    $sql = "ALTER USER 'root'@'localhost' IDENTIFIED BY '" + $rootPassword + "'; FLUSH PRIVILEGES;"
    $env:MYSQL_PWD = ""
    try {
        $out = "" | & $mysqlExe --protocol=TCP --host=127.0.0.1 --port=3306 --user=root --batch --connect-timeout=10 -e $sql 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to set MySQL root password: $out"
        }
    }
    finally {
        Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
    }

    # Marker so uninstall knows we own this instance
    Set-Content -Path (Join-Path $InstallDir "mysql\.mlamehticket-owned") -Value "1" -Encoding ASCII

    Add-MachinePathEntry -Entry (Join-Path $mysqlHome "bin")

    return [pscustomobject]@{
        InstalledByUs = $true
        MysqlHome     = $mysqlHome
        RootPassword  = $rootPassword
        MysqlExe      = $mysqlExe
        MysqldExe     = $mysqld
    }
}

function Ensure-MySql {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$PayloadDir,
        [string]$Mode = "fresh",
        [string]$ExistingAdminUser = "",
        [string]$ExistingAdminPassword = "",
        [switch]$ForcePrivateInstance
    )

    $detection = Test-ExistingMySql
    $ownedMarker = Join-Path $InstallDir "mysql\.mlamehticket-owned"
    $privateExists = Test-Path $ownedMarker

    if ($privateExists -or (Get-Service -Name $script:MySqlServiceName -ErrorAction SilentlyContinue)) {
        Write-InstallStep "Using previously installed private MySQL."
        $svc = Get-Service -Name $script:MySqlServiceName -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -ne "Running") { Start-Service $script:MySqlServiceName }
        $mysqlHome = Join-Path $InstallDir "mysql"
        Add-MachinePathEntry -Entry (Join-Path $mysqlHome "bin")
        return [pscustomobject]@{
            InstalledByUs = $true
            MysqlHome     = $mysqlHome
            RootPassword  = [string](Get-BundledMySqlRootPassword -InstallDir $InstallDir)
            MysqlExe      = (Join-Path $mysqlHome "bin\mysql.exe")
            MysqldExe     = (Join-Path $mysqlHome "bin\mysqld.exe")
            AdminUser     = "root"
            AdminPassword = [string](Get-BundledMySqlRootPassword -InstallDir $InstallDir)
            UseExisting   = $false
        }
    }

    if ($ForcePrivateInstance) {
        if ($detection.PortOpen -and -not (Get-Service -Name $script:MySqlServiceName -ErrorAction SilentlyContinue)) {
            throw "Port 3306 is already in use. Stop the existing MySQL service or provide its admin credentials."
        }
        $result = Install-BundledMySql -InstallDir $InstallDir -PayloadDir $PayloadDir
        return [pscustomobject]@{
            InstalledByUs = $true
            MysqlHome     = $result.MysqlHome
            RootPassword  = $result.RootPassword
            MysqlExe      = $result.MysqlExe
            MysqldExe     = $result.MysqldExe
            AdminUser     = "root"
            AdminPassword = $result.RootPassword
            UseExisting   = $false
        }
    }

    if (-not $detection.Detected) {
        $result = Install-BundledMySql -InstallDir $InstallDir -PayloadDir $PayloadDir
        return [pscustomobject]@{
            InstalledByUs = $true
            MysqlHome     = $result.MysqlHome
            RootPassword  = $result.RootPassword
            MysqlExe      = $result.MysqlExe
            MysqldExe     = $result.MysqldExe
            AdminUser     = "root"
            AdminPassword = $result.RootPassword
            UseExisting   = $false
        }
    }

    # Use existing MySQL (fresh install with credentials, or repair/upgrade with .env)
    Write-InstallStep "Using existing MySQL/MariaDB on this machine."
    $mysqlExe = Find-MysqlClient -InstallDir $InstallDir
    if (-not $mysqlExe) {
        throw "mysql.exe client not found. Install MySQL client tools or choose a private instance."
    }
    if ($Mode -eq "fresh") {
        if ([string]::IsNullOrWhiteSpace($ExistingAdminUser)) {
            throw "Existing MySQL detected but no admin credentials were provided."
        }
        if (-not (Test-MySqlAdminConnection -MysqlExe $mysqlExe -User $ExistingAdminUser -Password $ExistingAdminPassword)) {
            throw "Could not connect to existing MySQL as '$ExistingAdminUser'. Check credentials or choose a private instance."
        }
    }
    return [pscustomobject]@{
        InstalledByUs = $false
        MysqlHome     = ""
        RootPassword  = ""
        MysqlExe      = $mysqlExe
        MysqldExe     = ""
        AdminUser     = $ExistingAdminUser
        AdminPassword = $ExistingAdminPassword
        UseExisting   = $true
    }
}
