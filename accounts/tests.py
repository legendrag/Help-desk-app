from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from accounts.signals import ensure_default_superadmin, _is_weak_bootstrap_password

User = get_user_model()


class BootstrapSuperadminTests(TestCase):
    def test_weak_password_helper(self):
        self.assertTrue(_is_weak_bootstrap_password(""))
        self.assertTrue(_is_weak_bootstrap_password("admin"))
        self.assertTrue(_is_weak_bootstrap_password("PASSWORD"))
        self.assertFalse(_is_weak_bootstrap_password("str0ng-Passw0rd!"))

    @override_settings(
        DEFAULT_SUPERADMIN_USERNAME="bootadmin",
        DEFAULT_SUPERADMIN_EMAIL="boot@test.local",
        DEFAULT_SUPERADMIN_PASSWORD="",
    )
    def test_skip_create_when_password_empty(self):
        class Sender:
            name = "accounts"

        ensure_default_superadmin(sender=Sender())
        self.assertFalse(User.objects.filter(username="bootadmin").exists())

    @override_settings(
        DEFAULT_SUPERADMIN_USERNAME="bootadmin2",
        DEFAULT_SUPERADMIN_EMAIL="boot2@test.local",
        DEFAULT_SUPERADMIN_PASSWORD="str0ng-Passw0rd!",
    )
    def test_create_with_strong_password_requires_change(self):
        class Sender:
            name = "accounts"

        ensure_default_superadmin(sender=Sender())
        user = User.objects.get(username="bootadmin2")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.requires_password_change)
        self.assertTrue(user.check_password("str0ng-Passw0rd!"))
