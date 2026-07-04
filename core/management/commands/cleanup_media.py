"""
Management command to find and optionally remove orphaned media files.

Scans MEDIA_ROOT for files not referenced by any FileField in the database.

Usage:
    python manage.py cleanup_media             # dry-run by default
    python manage.py cleanup_media --delete     # actually delete orphans
"""

import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models


class Command(BaseCommand):
    help = "Find media files not referenced by any FileField and optionally delete them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Actually delete orphaned files. Without this flag, only a report is printed.",
        )

    def handle(self, *args, **options):
        delete = options["delete"]
        media_root = str(settings.MEDIA_ROOT)

        if not os.path.exists(media_root):
            self.stderr.write("MEDIA_ROOT does not exist.")
            return

        # 1) Collect all file paths referenced in the database
        referenced = set()
        for model in apps.get_models():
            file_fields = [
                f for f in model._meta.get_fields()
                if isinstance(f, (models.FileField, models.ImageField))
            ]
            if not file_fields:
                continue

            for field in file_fields:
                values = (
                    model.objects
                    .exclude(**{field.attname: ""})
                    .exclude(**{field.attname: None})
                    .values_list(field.attname, flat=True)
                )
                for val in values.iterator():
                    if val:
                        # Normalise to forward slashes for comparison
                        referenced.add(val.replace("\\", "/"))

        # 2) Walk MEDIA_ROOT and find orphans
        orphans = []
        total_size = 0

        for dirpath, _dirnames, filenames in os.walk(media_root):
            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, media_root).replace("\\", "/")

                if rel_path not in referenced:
                    size = os.path.getsize(abs_path)
                    orphans.append((abs_path, rel_path, size))
                    total_size += size

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphaned media files found."))
            return

        self.stdout.write(f"\nFound {len(orphans)} orphaned file(s) ({total_size / (1024*1024):.2f} MB):\n")

        for abs_path, rel_path, size in orphans:
            size_kb = size / 1024
            self.stdout.write(f"  {rel_path}  ({size_kb:.1f} KB)")

        if delete:
            deleted = 0
            for abs_path, rel_path, _ in orphans:
                try:
                    os.remove(abs_path)
                    deleted += 1
                except OSError as e:
                    self.stderr.write(f"  Failed to delete {rel_path}: {e}")

            # Remove empty directories left behind
            for dirpath, dirnames, filenames in os.walk(media_root, topdown=False):
                if dirpath == media_root:
                    continue
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)

            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDeleted {deleted}/{len(orphans)} orphaned file(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDry run: no files deleted. Re-run with --delete to remove them."
                )
            )
