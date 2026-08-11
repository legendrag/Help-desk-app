# Windows installer

Offline Inno Setup packaging for mlamehticket: bundles Python 3.12, MySQL 8 (ZIP), and WinSW; installs the app as a Windows service; supports fresh / repair / in-place upgrade.

## Build (developer machine)

1. Install [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Ensure a project venv exists (`.\test-local.ps1 -InstallDeps`).
3. Download offline payload (needs internet once):

```powershell
.\installer\fetch-payload.ps1
```

4. Build:

```powershell
.\installer\build.ps1
```

Output:

- `installer\Output\mlamehticketSetup.exe`
- `installer\Output\mlamehticketSetup.exe.sha256`

## Layout

| Path | Role |
|------|------|
| `build.ps1` | collectstatic + ISCC compile + SHA256 |
| `fetch-payload.ps1` | Download/verify embeddable Python, VC++ redist, get-pip, MySQL ZIP, WinSW |
| `setup.iss` | Inno script (wizard, version modes, files) |
| `install.ps1` | Fresh / repair / upgrade orchestrator |
| `preupgrade.ps1` | Stop service, archive code, `backup_db` |
| `uninstall.ps1` | Remove services and installer-created trees |
| `lib\*.ps1` | Python, MySQL, database, env, service helpers |
| `payload\` | Git-ignored offline binaries |

## Modes

Decided from `HKLM\Software\mlamehticket\Version` vs package `VERSION`:

- **fresh** — no registry version
- **repair** — same version (re-verify / fix without touching `.env` or data)
- **upgrade** — newer package (preupgrade backup, then migrate)
- **downgrade** — blocked

## Client install notes

- **`payload\` stays on the client** (~300 MB under `{app}\installer\payload\`). That is intentional: repair can reprovision Python/MySQL/WinSW without the original Setup EXE.
- **Private Python is the embeddable ZIP** (extracted to `{app}\python`), plus `VC_redist.x64.exe`. We do **not** run the full Python EXE installer (it was unreliable under Setup).
- **Prefer the private Python.** If a system Python 3.12+ already exists, the installer may reuse it for `.venv`. Upgrading or removing that system Python later can break the service.
- **Install transcripts** are written to `%ProgramData%\mlamehticket\logs\` (survives if `{app}` is deleted). `{app}\logs\` gets a pointer file.
- **WinSW logs** land as `{app}\logs\mlamehticketApp_YYYYMMDD.out.log` and `.err.log` (date is part of the filename under `roll-by-time` mode).
- **First install needs network** for `get-pip.py` / `pip install -r requirements.txt` (Python/MySQL binaries themselves are offline).

## Failed upgrade — manual restore

`preupgrade.ps1` writes `{app}\backups\code-*.zip` and a SQL dump before files are replaced. If Setup fails after that:

```powershell
Stop-Service mlamehticketApp -ErrorAction SilentlyContinue

# Prefer the dump path in backups\preupgrade-<oldversion>.txt when present
$env:MYSQL_PWD = "<DB_PASSWORD from .env>"
Get-Content .\backups\<newest-backup>.sql | & .\mysql\bin\mysql.exe -u <DB_USER> -h 127.0.0.1 <DB_NAME>
Remove-Item Env:\MYSQL_PWD

Expand-Archive -Path .\backups\code-<oldversion>.zip -DestinationPath .\ -Force
Start-Service mlamehticketApp
```

See also [docs/operations/installation.md](../docs/operations/installation.md).
