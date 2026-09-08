from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.management_views import CategoryListView
from core.models import Category, Department
from core.version import get_app_version


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
