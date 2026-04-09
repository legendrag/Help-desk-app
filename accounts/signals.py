from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def ensure_default_superadmin(sender, **kwargs):
    if sender.name != "accounts":
        return

    User = get_user_model()
    username = settings.DEFAULT_SUPERADMIN_USERNAME
    email = settings.DEFAULT_SUPERADMIN_EMAIL
    password = settings.DEFAULT_SUPERADMIN_PASSWORD

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="System",
            last_name="Admin",
        )
