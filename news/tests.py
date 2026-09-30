from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Branch
from news.models import Announcement
from news.views import NewsListView


class NewsListQueryOptimizationTests(TestCase):
    def test_news_list_queryset_selects_related_created_by(self):
        author = User.objects.create_user(
            username="news_author",
            email="news_author@test.com",
            password="password123",
        )
        branch = Branch.objects.create(code="NW", name="News Branch")
        Announcement.objects.create(
            title="Query opt news",
            content="<p>Body HTML that the list does not paint</p>",
            created_by=author,
            target_branch=branch,
        )
        announcements = list(NewsListView().get_queryset())
        listed = next(a for a in announcements if a.title == "Query opt news")
        self.assertIn("content", listed.get_deferred_fields())
        with self.assertNumQueries(0):
            self.assertEqual(listed.created_by.username, "news_author")
            self.assertEqual(listed.target_branch.name, "News Branch")


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

    def test_news_shell_etag_304_keeps_no_store_and_needs_a_body_on_restore(self):
        Announcement.objects.create(
            title="Visible notice",
            content="<p>not in the table</p>",
            is_active=True,
            created_by=self.user,
        )
        full = self.client.get(reverse("news_list"))
        etag = full["ETag"]
        self.assertIn("no-store", full["Cache-Control"])
        self.assertIn("private", full["Cache-Control"])
        self.assertContains(full, "Visible notice")
        self.assertNotContains(full, "not in the table")

        cached = self.client.get(
            reverse("news_list"),
            HTTP_HX_REQUEST="true",
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(cached.status_code, 304)
        self.assertEqual(cached["ETag"], etag)
        self.assertIn("HX-Request", cached.get("Vary", ""))
        self.assertIn("no-store", cached["Cache-Control"])
        self.assertEqual(cached.content, b"")

        mismatch = self.client.get(
            reverse("news_list"),
            HTTP_HX_REQUEST="true",
            HTTP_IF_NONE_MATCH='"stale"',
        )
        self.assertEqual(mismatch.status_code, 200)
        self.assertContains(mismatch, 'id="news-shell-pane"')
        self.assertContains(mismatch, "unmountTicketListWS")
        self.assertIn("no-store", mismatch["Cache-Control"])
        self.assertEqual(mismatch["Cache-Control"], full["Cache-Control"])

        restore = self.client.get(
            reverse("news_list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
            HTTP_IF_NONE_MATCH=etag,
        )
        self.assertEqual(restore.status_code, 200)
        self.assertContains(restore, "Visible notice")
        self.assertContains(restore, 'id="news-shell-pane"')

    def test_news_etag_changes_when_an_announcement_expires_without_a_save(self):
        announcement = Announcement.objects.create(
            title="Expiring notice",
            content="Body",
            is_active=True,
            created_by=self.user,
            expires_at=timezone.now() + timedelta(days=1),
        )
        etag = self.client.get(reverse("news_list"))["ETag"]
        Announcement.objects.filter(pk=announcement.pk).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        changed = self.client.get(reverse("news_list"))
        self.assertNotEqual(changed["ETag"], etag)
        self.assertContains(changed, "Expired")
