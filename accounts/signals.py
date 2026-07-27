from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate
from django.dispatch import receiver

_WEAK_SUPERADMIN_PASSWORDS = frozenset({"", "admin", "password", "changeme", "12345678"})


def _is_weak_bootstrap_password(password: str) -> bool:
    return (password or "").strip().lower() in _WEAK_SUPERADMIN_PASSWORDS


@receiver(post_migrate)
def ensure_default_superadmin(sender, **kwargs):
    if sender.name != "accounts":
        return

    User = get_user_model()
    username = settings.DEFAULT_SUPERADMIN_USERNAME
    email = settings.DEFAULT_SUPERADMIN_EMAIL
    password = settings.DEFAULT_SUPERADMIN_PASSWORD

    if _is_weak_bootstrap_password(password):
        # Skip silent admin/admin creation; require an explicit strong env password.
        return

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="System",
            last_name="Admin",
            requires_password_change=True,
        )
