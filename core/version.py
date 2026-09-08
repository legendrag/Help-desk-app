from functools import lru_cache
from pathlib import Path

from django.conf import settings


@lru_cache(maxsize=1)
def get_app_version() -> str:
    path = Path(settings.BASE_DIR) / "VERSION"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
