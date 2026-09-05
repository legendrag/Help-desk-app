from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

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


class LogoutClearsWebPushTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="push_user",
            email="push@test.local",
            password="str0ng-Passw0rd!",
        )

    def test_logout_clears_webpush_subscriptions(self):
        try:
            from webpush.models import PushInformation, SubscriptionInfo
        except Exception:
            self.skipTest("django-webpush is not installed")

        sub = SubscriptionInfo.objects.create(
            browser="Chrome",
            endpoint="https://example.com/push/endpoint-1",
            auth="authkey",
            p256dh="p256dhkey",
        )
        PushInformation.objects.create(user=self.user, subscription=sub)
        self.assertEqual(PushInformation.objects.filter(user=self.user).count(), 1)

        self.client.force_login(self.user)
        response = self.client.post(reverse("logout"))
        self.assertIn(response.status_code, (302, 301))
        self.assertEqual(PushInformation.objects.filter(user=self.user).count(), 0)
        self.assertFalse(SubscriptionInfo.objects.filter(id=sub.id).exists())

    def test_clear_helper_is_noop_for_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        from notifications.webpush_cleanup import clear_user_webpush_subscriptions

        self.assertEqual(clear_user_webpush_subscriptions(AnonymousUser()), 0)
        self.assertEqual(clear_user_webpush_subscriptions(None), 0)


class PasswordChangePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="changer",
            email="changer@test.local",
            password="str0ng-Passw0rd!",
        )

    def test_full_page_uses_auth_body_class(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("password_change"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "auth-body")
        self.assertContains(response, 'data-skeleton="password-change"')
        self.assertContains(response, 'id="modal-skeleton"')

    def test_htmx_partial_does_not_use_full_auth_chrome(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("password_change"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "auth-body")
        self.assertContains(response, "password-change-form")


class UserListQueryOptimizationTests(TestCase):
    def test_user_list_queryset_selects_related_org_fields(self):
        from accounts.management_views import UserListView
        from core.models import Branch, Department, Role

        branch = Branch.objects.create(code="UL", name="User List Branch")
        department = Department.objects.create(name="User List Dept")
        role = Role.objects.create(name="User List Role", can_access_settings=True)
        User.objects.create_user(
            username="ul_user",
            email="ul@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            branch=branch,
            department=department,
            role=role,
        )
        users = list(UserListView().get_queryset())
        listed = next(u for u in users if u.username == "ul_user")
        with self.assertNumQueries(0):
            self.assertEqual(listed.branch.name, "User List Branch")
            self.assertEqual(listed.department.name, "User List Dept")
            self.assertEqual(listed.role.name, "User List Role")


class UserListTemplateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="ul_admin",
            email="ul_admin@test.local",
            password="str0ng-Passw0rd!",
        )
        self.listed = User.objects.create_user(
            username="listed_agent",
            email="listed_agent@test.local",
            password="str0ng-Passw0rd!",
            user_type=User.UserType.SUPPORT,
        )
        self.client.force_login(self.admin)

    def test_full_page_user_list_renders_object_list_partial(self):
        response = self.client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/management/list_partial_v2.html")
        self.assertTemplateNotUsed(response, "accounts/management/list.html")
        self.assertContains(response, "listed_agent")
        self.assertContains(response, "mgmt-table")
        self.assertNotContains(response, "Manage Users")

    def test_htmx_user_list_uses_the_same_partial(self):
        response = self.client.get(reverse("user_list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/management/list_partial_v2.html")
        self.assertContains(response, "listed_agent")


class VendorStaticTests(TestCase):
    def test_login_page_uses_local_vendor_assets(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/tom-select.complete.min.js")
        self.assertContains(response, "vendor/htmx.min.js")
        self.assertContains(response, "vendor/tom-select.default.min.css")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/tom-select")
        self.assertNotContains(response, "unpkg.com/htmx")

    def test_chartjs_is_vendored_locally(self):
        chart = Path(settings.BASE_DIR) / "static" / "vendor" / "chart.umd.min.js"
        self.assertTrue(chart.is_file(), "Chart.js must be self-hosted for offline installs")
        self.assertGreater(chart.stat().st_size, 10_000)

    def test_tinymce_is_vendored_locally(self):
        tinymce = Path(settings.BASE_DIR) / "static" / "vendor" / "tinymce" / "tinymce.min.js"
        self.assertTrue(tinymce.is_file(), "TinyMCE must be self-hosted for offline installs")
        self.assertGreater(tinymce.stat().st_size, 10_000)


class ProductionStaticConfigTests(SimpleTestCase):
    def _settings_source(self):
        return (Path(settings.BASE_DIR) / "config" / "settings.py").read_text(encoding="utf-8")

    def test_whitenoise_finders_follow_debug(self):
        source = self._settings_source()
        self.assertRegex(
            source,
            r"WHITENOISE_USE_FINDERS\s*=\s*DEBUG",
            msg="WhiteNoise finders must be off in production (DEBUG=0) installs",
        )

    def test_production_uses_compressed_static_storage(self):
        source = self._settings_source()
        self.assertIn("whitenoise.storage.CompressedStaticFilesStorage", source)
