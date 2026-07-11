import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
print("WEBPUSH_SETTINGS:", settings.WEBPUSH_SETTINGS)
