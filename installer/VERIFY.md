# Offline installer verification checklist

Run on a clean Windows VM with network disabled after copying `mlamehticketSetup.exe` and its `.sha256` file.

## Pre-flight

- [ ] `Get-FileHash mlamehticketSetup.exe -Algorithm SHA256` matches `.sha256`
- [ ] SmartScreen: More info → Run anyway (unsigned build)
- [ ] Build machine: Inno Setup 6 (`ISCC.exe`) present so `.\installer\build.ps1` compiles `setup.iss` (required after `[Code]` post-install changes). If ISCC was missing during development, treat the Pascal compile as unverified until the first successful build.

## Fresh install (no Python / no MySQL)

- [ ] Choose install dir (default `C:\mlamehticket`)
- [ ] Set address / port / admin email
- [ ] Both `mlamehticketApp` and `mlamehticketMySQL` are Running + Automatic
- [ ] `http://localhost:<port>/` loads
- [ ] `.env` has `DEBUG=0` and a non-placeholder `SECRET_KEY`
- [ ] `FIRST-LOGIN.txt` opens; admin forced password change works
- [ ] `{app}\python\python.exe -V` works (embeddable + VC++ redist)
- [ ] `logs\` contains `app.log`, `mlamehticketApp_YYYYMMDD.out.log` (and `.err.log`), `mysql-error.log`
- [ ] Install transcript under `%ProgramData%\mlamehticket\logs\install-*.log`

## Existing MySQL

- [ ] Credentials page appears; wrong password rejected
- [ ] Correct password proceeds; bundled MySQL skipped
- [ ] Database/user created in existing instance

## Repair / upgrade / downgrade

- [ ] Same EXE again → repair; after deleting service + `.venv`, both restored; `.env`/data intact
- [ ] Newer `VERSION` build → upgrade; `.env`, media, `private_key.pem`, tickets survive; `backups\code-*.zip` + SQL dump present
- [ ] Older EXE over newer install → blocked

## Failure path (exit code)

- [ ] Stop bundled MySQL (`Stop-Service mlamehticketMySQL`), run Setup again → Setup shows an error dialog (does **not** claim success), returns non-zero; transcript under `%ProgramData%\mlamehticket\logs\`
- [ ] Start MySQL again and repair/re-run to recover

## Lifecycle

- [ ] Reboot → help desk up without interactive login
- [ ] `Restart-Service mlamehticketApp` three times; no orphaned python / port conflict
- [ ] Kill python → WinSW restarts within ~10s
- [ ] Non-default port (8080): firewall, shortcuts, `SITE_URL` match
- [ ] Path with spaces (e.g. `D:\Help Desk\mlamehticket`): service and uninstall work
- [ ] Uninstall: services/firewall/PATH gone; data preserved unless confirmed
- [ ] `installer\payload\` remains after install (~300 MB; intentional for repair)
