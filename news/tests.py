from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from news.models import Announcement
from news.views import NewsListView


class NewsListQueryOptimizationTests(TestCase):
    def test_news_list_queryset_selects_related_created_by(self):
        author = User.objects.create_user(
            username="news_author",
            email="news_author@test.com",
            password="password123",
        )
        Announcement.objects.create(title="Query opt news", content="Body", created_by=author)
        announcements = list(NewsListView().get_queryset())
        listed = next(a for a in announcements if a.title == "Query opt news")
        with self.assertNumQueries(0):
            self.assertEqual(listed.created_by.username, "news_author")


class NewsShellNavigationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="news_shell",
            email="news_shell@test.com",
            password="password123",
        )
        self.client.login(username="news_shell", password="password123")

    def test_cold_news_url_is_full_document(self):
        response = self.client.get(reverse("news_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<html")
        self.assertContains(response, 'id="shell-content"')
        self.assertContains(response, 'id="news-shell-pane"')
        self.assertContains(response, "No announcements found.")

    def test_htmx_news_is_pane_only_and_still_private(self):
        full = self.client.get(reverse("news_list"))
        response = self.client.get(reverse("news_list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/list_shell_partial.html")
        self.assertContains(response, 'id="news-shell-pane"')
        self.assertContains(response, "unmountTicketListWS")
        self.assertNotContains(response, "<html")
        self.assertNotContains(response, 'id="shell-content"')
        self.assertEqual(response["Cache-Control"], full["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("HX-Request", response.get("Vary", ""))

    def test_history_restore_returns_news_pane(self):
        response = self.client.get(
            reverse("news_list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
        self.assertTemplateUsed(response, "news/list_shell_partial.html")
        self.assertContains(response, 'id="news-shell-pane"')
        self.assertNotContains(response, "<html")
