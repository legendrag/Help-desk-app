from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.management_views import CategoryListView
from core.models import Category, Department


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
