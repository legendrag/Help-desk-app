<#
    database.ps1 — Create database and app user (idempotent).
#>

function Invoke-MysqlSql {
    param(
        [Parameter(Mandatory)][string]$MysqlExe,
        [Parameter(Mandatory)][string]$User,
        [string]$Password = "",
        [Parameter(Mandatory)][string]$Sql,
        [string]$HostName = "127.0.0.1",
        [int]$Port = 3306
    )
    $env:MYSQL_PWD = $Password
    try {
        # --batch: never prompt (hidden Setup cannot answer a password prompt → apparent hang)
        # --connect-timeout: fail fast if server is up but auth/network is wrong
        $args = @(
            "--protocol=TCP",
            "--host=$HostName",
            "--port=$Port",
            "--user=$User",
            "--batch",
            "--connect-timeout=10",
            "-e", $Sql
        )
        # Drain stdin so a stray password prompt cannot block forever
        $output = "" | & $MysqlExe @args 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "MySQL command failed: $output"
        }
        return $output
    }
    finally {
        Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
    }
}

function Ensure-AppDatabase {
    param(
        [Parameter(Mandatory)][string]$MysqlExe,
        [Parameter(Mandatory)][string]$AdminUser,
        [string]$AdminPassword = "",
        [Parameter(Mandatory)][string]$DbName,
        [Parameter(Mandatory)][string]$DbUser,
        [Parameter(Mandatory)][string]$DbPassword,
        [string]$HostName = "127.0.0.1",
        [int]$Port = 3306
    )

    Write-InstallStep "Ensuring database '$DbName' and user '$DbUser' ..."

    # Escape single quotes in password for SQL string literals
    $safePass = $DbPassword -replace "'", "''"

    $sql = @"
CREATE DATABASE IF NOT EXISTS ``$DbName`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DbUser'@'localhost' IDENTIFIED BY '$safePass';
CREATE USER IF NOT EXISTS '$DbUser'@'127.0.0.1' IDENTIFIED BY '$safePass';
ALTER USER '$DbUser'@'localhost' IDENTIFIED BY '$safePass';
ALTER USER '$DbUser'@'127.0.0.1' IDENTIFIED BY '$safePass';
GRANT ALL PRIVILEGES ON ``$DbName``.* TO '$DbUser'@'localhost';
GRANT ALL PRIVILEGES ON ``$DbName``.* TO '$DbUser'@'127.0.0.1';
FLUSH PRIVILEGES;
"@

    Invoke-MysqlSql `
        -MysqlExe $MysqlExe `
        -User $AdminUser `
        -Password $AdminPassword `
        -Sql $sql `
        -HostName $HostName `
        -Port $Port

    Write-InstallStep "Database and user ready."
}
