from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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


class VendorStaticTests(TestCase):
    def test_login_page_uses_local_vendor_assets(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor/tom-select.complete.min.js")
        self.assertContains(response, "vendor/htmx.min.js")
        self.assertContains(response, "vendor/tom-select.default.min.css")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/tom-select")
        self.assertNotContains(response, "unpkg.com/htmx")
