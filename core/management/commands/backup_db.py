"""
Management command to back up the database.

Supports both SQLite (file copy) and MySQL (mysqldump).
Keeps the last N backups (default 7) and auto-deletes older ones.

Usage:
    python manage.py backup_db
    python manage.py backup_db --keep 14
    python manage.py backup_db --dir /custom/backup/path
"""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a timestamped database backup and enforce retention policy."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            type=str,
            default=os.getenv("BACKUP_DIR", ""),
            help="Directory to store backups (default: ./backups or BACKUP_DIR env var).",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=int(os.getenv("BACKUP_KEEP", 7)),
            help="Number of recent backups to keep (default: 7 or BACKUP_KEEP env var).",
        )

    def handle(self, *args, **options):
        backup_dir = options["dir"] or os.path.join(settings.BASE_DIR, "backups")
        keep = options["keep"]

        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        db_settings = settings.DATABASES["default"]
        engine = db_settings["ENGINE"]
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        if "sqlite3" in engine:
            backup_file = self._backup_sqlite(db_settings, backup_path, timestamp)
        elif "mysql" in engine:
            backup_file = self._backup_mysql(db_settings, backup_path, timestamp)
        else:
            raise CommandError(f"Unsupported database engine: {engine}")

        self.stdout.write(self.style.SUCCESS(f"Backup created: {backup_file}"))

        # Enforce retention policy
        self._cleanup_old_backups(backup_path, keep)

    def _backup_sqlite(self, db_settings, backup_path, timestamp):
        """Back up SQLite by copying the database file."""
        db_file = Path(db_settings["NAME"])
        if not db_file.exists():
            raise CommandError(f"SQLite database file not found: {db_file}")

        backup_file = backup_path / f"backup_{timestamp}.sqlite3"
        shutil.copy2(str(db_file), str(backup_file))

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        self.stdout.write(f"  Source: {db_file}")
        self.stdout.write(f"  Size:   {size_mb:.2f} MB")

        return backup_file

    def _backup_mysql(self, db_settings, backup_path, timestamp):
        """Back up MySQL using mysqldump."""
        backup_file = backup_path / f"backup_{timestamp}.sql"

        cmd = [
            "mysqldump",
            f"--host={db_settings.get('HOST', 'localhost')}",
            f"--port={db_settings.get('PORT', '3306')}",
            f"--user={db_settings.get('USER', 'root')}",
            "--single-transaction",
            "--routines",
            "--triggers",
            db_settings["NAME"],
        ]

        env = os.environ.copy()
        password = db_settings.get("PASSWORD", "")
        if password:
            env["MYSQL_PWD"] = password

        self.stdout.write(f"  Running mysqldump for database '{db_settings['NAME']}'...")

        try:
            with open(backup_file, "w", encoding="utf-8") as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=300,
                    check=True,
                )
        except FileNotFoundError:
            raise CommandError(
                "mysqldump not found. Ensure MySQL client tools are installed "
                "and mysqldump is on your PATH."
            )
        except subprocess.CalledProcessError as e:
            # Clean up the partial file
            if backup_file.exists():
                backup_file.unlink()
            raise CommandError(f"mysqldump failed: {e.stderr.decode().strip()}")
        except subprocess.TimeoutExpired:
            if backup_file.exists():
                backup_file.unlink()
            raise CommandError("mysqldump timed out after 300 seconds.")

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        self.stdout.write(f"  Size:   {size_mb:.2f} MB")

        return backup_file

    def _cleanup_old_backups(self, backup_path, keep):
        """Delete the oldest backups, keeping only the most recent `keep` files."""
        backup_files = sorted(
            [
                f
                for f in backup_path.iterdir()
                if f.is_file() and f.name.startswith("backup_")
            ],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        if len(backup_files) <= keep:
            self.stdout.write(f"  Retention: {len(backup_files)} backup(s) kept (limit: {keep}).")
            return

        to_delete = backup_files[keep:]
        for f in to_delete:
            f.unlink()
            self.stdout.write(f"  Deleted old backup: {f.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"  Retention: kept {keep}, deleted {len(to_delete)} old backup(s)."
            )
        )
