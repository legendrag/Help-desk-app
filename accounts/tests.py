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


class LogoutGetConfirmTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="logout_user",
            email="logout@test.local",
            password="str0ng-Passw0rd!",
        )
        self.logout_url = reverse("logout")
        self.login_url = reverse("login")
        self.home_url = reverse("tickets_list")

    def test_anonymous_get_redirects_to_login(self):
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_get_renders_post_form_and_stays_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/logout_confirm.html")
        self.assertContains(response, f'action="{self.logout_url}"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, f'href="{self.home_url}"')
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_cancel_uses_same_origin_referer(self):
        self.client.force_login(self.user)
        referer_path = "/kb/?q=reset"
        response = self.client.get(
            self.logout_url,
            HTTP_REFERER=f"http://testserver{referer_path}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/kb/?q=reset"')
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_cancel_falls_back_for_offsite_or_logout_referer(self):
        self.client.force_login(self.user)
        offsite = self.client.get(
            self.logout_url,
            HTTP_REFERER="https://evil.example/phish",
        )
        self.assertContains(offsite, f'href="{self.home_url}"')

        loop = self.client.get(
            self.logout_url,
            HTTP_REFERER="http://testserver/accounts/logout/",
        )
        self.assertContains(loop, f'href="{self.home_url}"')
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_post_logs_out_and_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.login_url)
        self.assertNotIn("_auth_user_id", self.client.session)


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


class LoginHtmxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login_user",
            email="login@test.local",
            password="str0ng-Passw0rd!",
        )

    def test_htmx_wrong_password_stays_on_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "wrong-password"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("HX-Redirect", response.headers)
        self.assertContains(response, "Incorrect username or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_htmx_success_redirects_to_tickets(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "str0ng-Passw0rd!"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("tickets_list"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_htmx_success_honors_next(self):
        next_url = reverse("tickets_list") + "?status=open"
        response = self.client.post(
            reverse("login"),
            {
                "username": "login_user",
                "password": "str0ng-Passw0rd!",
                "next": next_url,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], next_url)

    def test_htmx_password_change_required_skips_tickets(self):
        self.user.requires_password_change = True
        self.user.save(update_fields=["requires_password_change"])
        response = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "str0ng-Passw0rd!"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("password_change"))

    def test_html_post_still_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "str0ng-Passw0rd!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tickets_list"))

    def test_login_form_uses_htmx(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="login-form"')
        self.assertContains(response, 'hx-post')

    def test_inactive_status_cannot_sign_in(self):
        # Deactivation stores status=inactive and leaves Django's is_active flag set.
        User.objects.filter(pk=self.user.pk).update(
            status=User.Status.INACTIVE,
            is_active=True,
        )
        response = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "str0ng-Passw0rd!"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is inactive.")
        self.assertNotIn("HX-Redirect", response.headers)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_saving_inactive_status_clears_is_active(self):
        self.user.status = User.Status.INACTIVE
        self.user.save(update_fields=["status"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.status, User.Status.INACTIVE)

    def test_inactive_status_drops_existing_session(self):
        self.client.force_login(self.user)
        User.objects.filter(pk=self.user.pk).update(
            status=User.Status.INACTIVE,
            is_active=True,
        )
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])


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
        self.assertIn("whitenoise.storage.CompressedManifestStaticFilesStorage", source)


class LoginPageFromHtmxTests(TestCase):
    """An HTMX request that hits the login page after the session expired."""

    def test_htmx_get_redirects_the_whole_page_back_to_where_the_user_was(self):
        response = self.client.get(
            reverse("login") + "?next=/shifts/mine/check-in/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="http://testserver/shifts/mine/?tab=1",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("login") + "?next=%2Fshifts%2Fmine%2F%3Ftab%3D1")
        self.assertEqual(response.content, b"")

    def test_htmx_get_ignores_a_current_url_on_another_host(self):
        response = self.client.get(
            reverse("login") + "?next=/shifts/mine/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_CURRENT_URL="https://evil.example/steal",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], reverse("login") + "?next=/shifts/mine/")

    def test_plain_get_still_renders_the_login_page(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("HX-Redirect", response.headers)


class UserRoleEscalationTests(TestCase):
    """A user editor can't hand out, or take over, a role stronger than their own."""

    def setUp(self):
        from core.models import Department, Role

        self.department = Department.objects.create(name="Escalation Dept")
        self.editor_role = Role.objects.create(
            name="User editor", can_access_settings=True, can_update_user=True, can_create_user=True,
        )
        self.weak_role = Role.objects.create(name="Weak", can_access_settings=True)
        self.admin_role = Role.objects.create(name="Admin")  # save() turns every flag on
        self.editor = User.objects.create_user(
            username="user-editor", password="password123", user_type=User.UserType.SUPPORT,
            department=self.department, role=self.editor_role,
        )
        self.agent = User.objects.create_user(
            username="agent2", password="password123", user_type=User.UserType.SUPPORT,
            department=self.department, role=self.weak_role,
        )
        self.client.force_login(self.editor)

    def _edit(self, user, role, **extra):
        data = {
            "username": user.username, "user_type": user.user_type, "department": self.department.pk,
            "role": role.pk, "status": "on", **extra,
        }
        return self.client.post(reverse("user_update", args=[user.pk]), data, HTTP_HX_REQUEST="true")

    def test_cannot_make_self_or_others_admin(self):
        for target in (self.editor, self.agent):
            response = self._edit(target, self.admin_role)
            self.assertNotEqual(response.status_code, 204, target.username)
            target.refresh_from_db()
            self.assertNotEqual(target.role_id, self.admin_role.pk, target.username)

    def test_cannot_create_an_admin(self):
        from core.models import Role

        self.client.post(reverse("user_create"), {
            "username": "sneaky", "user_type": User.UserType.SUPPORT, "department": self.department.pk,
            "role": Role.objects.get(name="Admin").pk, "password1": "Sup3r-Secret-99", "password2": "Sup3r-Secret-99",
            "status": "on",
        }, HTTP_HX_REQUEST="true")
        self.assertFalse(User.objects.filter(username="sneaky", role=self.admin_role).exists())

    def test_can_still_assign_a_weaker_role(self):
        response = self._edit(self.agent, self.editor_role)
        self.assertEqual(response.status_code, 204)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role_id, self.editor_role.pk)

    def test_cannot_edit_or_reset_password_of_a_stronger_user(self):
        boss = User.objects.create_user(
            username="boss", password="password123", user_type=User.UserType.SUPPORT,
            department=self.department, role=self.admin_role,
        )
        response = self._edit(boss, self.admin_role, password1="Hijack-Pass-42", password2="Hijack-Pass-42")
        self.assertEqual(response.status_code, 403)
        boss.refresh_from_db()
        self.assertTrue(boss.check_password("password123"))
        self.assertEqual(self.client.get(reverse("user_update", args=[boss.pk])).status_code, 403)

    def test_role_dropdown_hides_stronger_roles(self):
        response = self.client.get(reverse("user_update", args=[self.agent.pk]), HTTP_HX_REQUEST="true")
        choices = list(response.context["form"].fields["role"].queryset)
        self.assertIn(self.weak_role, choices)
        self.assertNotIn(self.admin_role, choices)


class UserPreferenceTests(TestCase):
    """Language and theme are saved on the account, so they follow the user."""

    def setUp(self):
        self.user = User.objects.create_user(username="prefs", password="password123")

    def test_first_visit_adopts_the_browser_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ar"
        self.client.force_login(self.user)
        self.client.get(reverse("password_change"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, "ar")

    def test_saved_language_wins_on_another_device(self):
        self.user.language = "ar"
        self.user.save(update_fields=["language"])
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"  # a different browser
        self.client.force_login(self.user)
        response = self.client.get(reverse("password_change"))
        self.assertEqual(response.headers.get("Content-Language"), "ar")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "ar")

    def test_language_switch_saves_on_the_account(self):
        self.client.force_login(self.user)
        self.client.post(reverse("set_language"), {"language": "ar", "next": "/"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, "ar")

    def test_theme_is_saved_and_rendered(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("set_theme"), {"theme": "dark"}).status_code, 204)
        self.assertEqual(self.client.post(reverse("set_theme"), {"theme": "purple"}).status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "dark")
        self.assertContains(self.client.get(reverse("password_change")), 'data-user-theme="dark"')

    def test_theme_needs_a_signed_in_user(self):
        self.assertEqual(self.client.post(reverse("set_theme"), {"theme": "dark"}).status_code, 401)


class UserManagementRound14Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="r14-admin", password="password123")
        self.client.force_login(self.admin)

    def test_inactive_user_is_shown_unticked(self):
        gone = User.objects.create_user(username="r14-gone", password="password123", status=User.Status.INACTIVE)
        response = self.client.get(reverse("user_update", args=[gone.pk]), HTTP_HX_REQUEST="true")
        self.assertFalse(response.context["form"]["status"].value())
        self.assertNotIn("checked", str(response.context["form"]["status"]))

    def test_edit_page_keeps_the_signed_in_user_in_the_header(self):
        other = User.objects.create_user(username="r14-other", password="password123", first_name="Other")
        response = self.client.get(reverse("user_update", args=[other.pk]))
        self.assertEqual(response.context["user"], self.admin)
        self.assertEqual(response.context["target_user"], other)

    def test_users_tab_lists_everyone(self):
        for n in range(25):
            User.objects.create_user(username=f"r14-u{n:02d}", password="password123")
        response = self.client.get(reverse("user_list"), HTTP_HX_REQUEST="true")
        self.assertEqual(len(response.context["object_list"]), User.objects.count())
        self.assertContains(response, "r14-u24")


class LoginLockoutTests(TestCase):
    """Five wrong passwords lock a username for five minutes (round 16 M1)."""

    def setUp(self):
        self.user = User.objects.create_user(username="r16lock", email="lock@test.local", password="str0ng-Passw0rd!")

    def _login(self, username, password="wrong-password"):
        return self.client.post(reverse("login"), {"username": username, "password": password})

    def test_case_variants_share_one_lockout(self):
        for username in ("r16lock", "R16LOCK", "R16Lock", "r16LOCK", "r16lock"):
            self._login(username)
        locked = self._login("r16LOCK", "str0ng-Passw0rd!")
        self.assertContains(locked, "Too many failed login attempts")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_each_try_is_counted_before_the_password_is_checked(self):
        from accounts.forms import LOGIN_MAX_ATTEMPTS
        from accounts.models import LoginThrottle

        # As if four other requests already took their tries in parallel.
        LoginThrottle.objects.create(username="r16lock", failures=LOGIN_MAX_ATTEMPTS - 1)
        self.assertContains(self._login("r16lock"), "Incorrect username or password")
        self.assertEqual(LoginThrottle.objects.get().failures, LOGIN_MAX_ATTEMPTS)
        self.assertContains(self._login("r16lock", "str0ng-Passw0rd!"), "Too many failed login attempts")
        # A refused try does not add more.
        self.assertEqual(LoginThrottle.objects.get().failures, LOGIN_MAX_ATTEMPTS)

    def test_lock_ends_after_five_minutes_and_success_clears_it(self):
        from datetime import timedelta

        from django.utils import timezone

        from accounts.models import LoginThrottle

        for _ in range(5):
            self._login("r16lock")
        LoginThrottle.objects.update(last_failure_at=timezone.now() - timedelta(minutes=6))
        response = self._login("R16Lock", "str0ng-Passw0rd!")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(LoginThrottle.objects.exists())

    def test_unknown_names_do_not_fill_the_cache(self):
        from django.core.cache import cache

        from accounts.models import LoginThrottle

        cache.clear()
        for n in range(5):
            self._login(f"nobody-{n}")
        self.assertEqual(LoginThrottle.objects.count(), 5)
        self.assertIsNone(cache.get("login_attempts_nobody-0"))
