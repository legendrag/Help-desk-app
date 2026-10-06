from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from config.settings import mysql_connect_host
from core.management_views import CategoryListView
from core.models import Category, Department, Role
from core.version import get_app_version
from tickets.models import Ticket


class MysqlConnectHostTests(SimpleTestCase):
    def test_windows_localhost_uses_ipv4(self):
        self.assertEqual(mysql_connect_host("localhost", "nt"), "127.0.0.1")
        self.assertEqual(mysql_connect_host(" LocalHost ", "nt"), "127.0.0.1")
        self.assertEqual(mysql_connect_host("", "nt"), "127.0.0.1")
        self.assertEqual(mysql_connect_host(None, "nt"), "127.0.0.1")

    def test_posix_localhost_stays_socket_name(self):
        self.assertEqual(mysql_connect_host("localhost", "posix"), "localhost")
        self.assertEqual(mysql_connect_host("  localhost  ", "posix"), "localhost")

    def test_explicit_hosts_are_unchanged(self):
        self.assertEqual(mysql_connect_host("127.0.0.1", "nt"), "127.0.0.1")
        self.assertEqual(mysql_connect_host("db.internal", "nt"), "db.internal")
        self.assertEqual(mysql_connect_host("db.internal", "posix"), "db.internal")


class CategoryListQueryOptimizationTests(TestCase):
    def test_category_list_queryset_selects_related_department(self):
        department = Department.objects.create(name="Cat List Dept")
        Category.objects.create(department=department, name="Cat List Category")
        categories = list(CategoryListView().get_queryset())
        listed = next(c for c in categories if c.name == "Cat List Category")
        with self.assertNumQueries(0):
            self.assertEqual(listed.department.name, "Cat List Dept")


class ServiceWorkerFetchGuardTests(SimpleTestCase):
    def setUp(self):
        self.source = (Path(settings.BASE_DIR) / "templates" / "sw.js").read_text(
            encoding="utf-8"
        )

    def test_skips_document_and_empty_destination(self):
        self.assertIn("event.request.destination", self.source)
        self.assertIn("'document'", self.source)
        self.assertIn("!dest", self.source)

    def test_skips_htmx_html_polls(self):
        self.assertIn("HX-Request", self.source)
        self.assertIn("text/html", self.source)

    def test_respondwith_catches_failed_fetch(self):
        self.assertRegex(self.source, r"respondWith\([\s\S]*?\.catch\s*\(")


class ServiceWorkerViewTests(TestCase):
    def test_sw_js_is_served_with_fetch_handler(self):
        response = self.client.get(reverse("sw.js"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"addEventListener('fetch'", response.content)
        self.assertEqual(response["Service-Worker-Allowed"], "/")


class AppVersionTests(SimpleTestCase):
    def tearDown(self):
        get_app_version.cache_clear()

    def test_reads_version_file(self):
        get_app_version.cache_clear()
        expected = (Path(settings.BASE_DIR) / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(get_app_version(), expected)
        self.assertTrue(expected)

    def test_missing_version_file_returns_empty(self):
        with TemporaryDirectory() as tmp:
            with override_settings(BASE_DIR=Path(tmp)):
                get_app_version.cache_clear()
                self.assertEqual(get_app_version(), "")


class LanguageSwitchLoadingTests(SimpleTestCase):
    def setUp(self):
        base = Path(settings.BASE_DIR)
        self.loading_js = (base / "static" / "js" / "loading.js").read_text(
            encoding="utf-8"
        )
        self.base_html = (base / "templates" / "base.html").read_text(encoding="utf-8")
        self.app_shell = (base / "static" / "js" / "app-shell.js").read_text(
            encoding="utf-8"
        )

    def test_exports_bar_only_progress_navigation(self):
        self.assertIn("window.beginProgressNavigation", self.loading_js)
        self.assertIn("options.skeleton === false", self.loading_js)
        self.assertIn("beginFullPageNavigation(null, '', { skeleton: false })", self.loading_js)

    def test_language_switch_starts_progress_then_submits(self):
        self.assertIn('id="lang-switch-form" data-no-loading', self.base_html)
        self.assertIn("js/app-shell.js' %}?v=10", self.base_html)
        self.assertIn("window.beginProgressNavigation()", self.app_shell)
        self.assertIn("requestAnimationFrame(function () { form.submit(); })", self.app_shell)
        self.assertIn("loading.js' %}?v=23", self.base_html)

    def test_ordinary_full_page_nav_still_shows_skeleton(self):
        self.assertIn("showNavSkeleton(classifyNavSkeleton(destination))", self.loading_js)
        self.assertIn("setPageNavigating(true)", self.loading_js)
        self.assertIn("if (withSkeleton)", self.loading_js)
        self.assertIn("SKELETON_DELAY_MS = 450", self.loading_js)
        self.assertIn("clearSkeletonDelayTimer()", self.loading_js)
        # Bar and skeleton are scheduled, not painted in the same turn as the click.
        nav_fn = self.loading_js.split("function beginFullPageNavigation", 1)[1]
        nav_fn = nav_fn.split("function reloadWithLoading", 1)[0]
        before_timer = nav_fn.split("setTimeout", 1)[0]
        self.assertNotIn("showNavSkeleton(", before_timer)
        self.assertNotIn("startProgress(", before_timer)
        self.assertNotIn("consumeFullPageLoadingFlag() || isReloadNavigation()", self.loading_js)

    def test_replaced_shell_trigger_still_finishes_the_progress_bar(self):
        self.assertIn("xhr.__loadingElt = elt", self.loading_js)
        settled = self.loading_js.split("function onHtmxSettled", 1)[1]
        settled = settled.split("document.body.addEventListener('htmx:afterRequest'", 1)[0]
        self.assertIn("xhr.__loadingElt", settled)
        self.assertIn("cleanupRequest(tracked)", settled)

    def test_leaving_chat_does_not_smooth_scroll_the_shell(self):
        self.assertIn("function useInstantShellScroll()", self.app_shell)
        self.assertIn('scrollBehavior = "auto"', self.app_shell)
        self.assertIn("htmx:historyRestore", self.app_shell)
        notifications = (
            Path(settings.BASE_DIR) / "static" / "js" / "notifications.js"
        ).read_text(encoding="utf-8")
        ready = notifications.split("navigator.serviceWorker.register(swUrl)", 1)[1]
        ready = ready.split("pushManager.subscribe", 1)[0]
        self.assertIn("navigator.serviceWorker.ready", ready)
        css = (Path(settings.BASE_DIR) / "static" / "css" / "modern.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("html:active-view-transition", css)
        self.assertIn("scroll-behavior: auto", css)

    def test_shell_swap_locks_extra_menu_and_ticket_clicks(self):
        self.assertIn("function armShellSwapLock", self.app_shell)
        self.assertIn("htmx:afterSettle", self.app_shell)
        self.assertIn("htmx:responseError", self.app_shell)
        self.assertIn("htmx:sendError", self.app_shell)
        self.assertIn("htmx:sendAbort", self.app_shell)
        self.assertIn("htmx:swapError", self.app_shell)
        self.assertIn("htmx:timeout", self.app_shell)
        self.assertIn('node.id === "shell-content"', self.app_shell)
        self.assertIn('a[data-shell-nav]', self.app_shell)
        self.assertIn('hx-target") !== "#shell-content"', self.app_shell)
        self.assertIn("armShellSwapSkeleton", self.app_shell)
        self.assertIn("clearShellSwapSkeleton", self.app_shell)
        # Modifier clicks are not locked; Dashboard is not a shell-nav link.
        lock_fn = self.app_shell.split("document.addEventListener(\"click\", function (event) {", 1)[1]
        lock_fn = lock_fn.split("document.addEventListener(\"click\"", 1)[0]
        self.assertIn("if (!activeShellSwap || !isPlainPrimaryClick(event)) return;", lock_fn)
        self.assertIn("action-cell", lock_fn)
        self.assertNotIn("data-nav-key=\"dashboard\"", lock_fn)
        skeleton = self.loading_js.split("window.armShellSwapSkeleton", 1)[1]
        skeleton = skeleton.split("window.clearShellSwapSkeleton", 1)[0]
        self.assertIn("fullPageNavPending", skeleton)
        self.assertNotIn("fullPageNavPending = true", skeleton)
        self.assertIn("showNavSkeleton(classifyNavSkeleton", skeleton)

    def test_unchanged_ticket_poll_skips_dom_swap(self):
        partial = (
            Path(settings.BASE_DIR) / "templates" / "tickets" / "list_live_partial.html"
        ).read_text(encoding="utf-8")
        self.assertIn("every 20s", partial)
        self.assertIn("target.id !== 'tickets-live'", self.app_shell)
        self.assertIn("evt.detail.shouldSwap = false", self.app_shell)

    def test_sidebar_prefs_css_is_not_arabic_only(self):
        base = Path(settings.BASE_DIR)
        style = (base / "static" / "css" / "style.css").read_text(encoding="utf-8")
        rtl = (base / "static" / "css" / "rtl.css").read_text(encoding="utf-8")
        self.assertIn(".sidebar-prefs {", style)
        self.assertIn(".lang-switch-track {", style)
        self.assertNotIn(".sidebar-prefs {", rtl)


class LanguageSwitchRenderedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lang_switch_user",
            email="langswitch@test.local",
            password="testpassword123",
        )
        self.client.force_login(self.user)

    def test_tickets_list_wires_progress_bar_on_language_switch(self):
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("js/app-shell.js?v=10", html)
        self.assertIn("js/loading.js?v=23", html)
        self.assertIn('id="lang-switch-form"', html)
        self.assertIn("data-no-loading", html)
        self.assertNotIn("rtl.css", html)

    def test_arabic_pages_still_load_rtl_css(self):
        response = self.client.get(reverse("tickets_list"), HTTP_ACCEPT_LANGUAGE="ar")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "rtl.css")


class SidebarVersionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="version_user",
            email="version@test.local",
            password="testpassword123",
        )
        self.client.force_login(self.user)

    def test_sidebar_shows_app_version_under_preferences(self):
        get_app_version.cache_clear()
        version = get_app_version()
        self.assertTrue(version)
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, 200)
        prefs = response.content.decode()
        prefs = prefs[prefs.index('class="sidebar-prefs"'):]
        self.assertLess(prefs.index("Language"), prefs.index('class="sidebar-version"'))
        snippet = prefs[prefs.index('class="sidebar-version"'):]
        snippet = snippet[: snippet.find("</")]
        self.assertIn(version, snippet)


class SeedDemoDataTests(TestCase):
    def test_seed_demo_data_without_ticket_count_creates_curated_tickets(self):
        out = StringIO()
        call_command("seed_demo_data", "--clear", stdout=out)
        
        ticket_count = Ticket.objects.count()
        self.assertEqual(ticket_count, 8)
        
        self.assertTrue(Ticket.objects.filter(title__contains="Printer not responding").exists())
        self.assertTrue(Ticket.objects.filter(title__contains="VPN disconnects").exists())

    def test_seed_demo_data_with_ticket_count_creates_additional_tickets(self):
        out = StringIO()
        call_command("seed_demo_data", "--clear", "--ticket-count", "10", stdout=out)
        
        ticket_count = Ticket.objects.count()
        self.assertGreaterEqual(ticket_count, 18)
        self.assertLessEqual(ticket_count, 20)
        
        self.assertTrue(Ticket.objects.filter(title__contains="Printer not responding").exists())

    def test_seed_demo_data_ticket_count_varies_attributes(self):
        out = StringIO()
        call_command("seed_demo_data", "--clear", "--ticket-count", "20", stdout=out)
        
        statuses = set(Ticket.objects.values_list("status", flat=True))
        self.assertGreater(len(statuses), 1)
        
        priorities = set(Ticket.objects.values_list("priority", flat=True))
        self.assertGreater(len(priorities), 1)
        
        branches = set(Ticket.objects.values_list("branch__code", flat=True))
        self.assertGreater(len(branches), 1)


class ManageShiftsFlagTests(TestCase):
    def test_admin_role_name_forces_the_flag(self):
        role = Role(name=" Admin ", can_manage_shifts=False)
        role.save()
        role.refresh_from_db()
        self.assertTrue(role.can_manage_shifts)
        self.assertTrue(role.can_check_in)

    def test_other_role_keeps_false(self):
        role = Role.objects.create(name="Desk agent", can_manage_shifts=False)
        self.assertFalse(role.can_manage_shifts)
        self.assertFalse(role.can_check_in)
