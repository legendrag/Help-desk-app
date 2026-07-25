from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from core.models import Role
from kb.models import Article, ArticleAttachment, Category
from kb.templatetags.kb_extras import basename, kb_attachment_kind


class KnowledgeBasePolishTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(
            name="KB Agent",
            can_access_kb=True,
            can_manage_kb=True,
            can_create_ticket=True,
        )
        self.user = User.objects.create_user(
            username="kb_agent",
            email="kb@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            role=self.role,
        )
        self.client = Client()
        self.client.login(username="kb_agent", password="testpassword123")

        self.cat_a = Category.objects.create(
            name="Troubleshooting",
            description="Fix common issues",
            icon="wrench",
        )
        self.cat_b = Category.objects.create(
            name="Getting Started",
            description="Onboarding notes",
            icon="book",
        )
        self.article_a1 = Article.objects.create(
            title="Reset password",
            category=self.cat_a,
            content="<p>Steps to reset a password.</p>",
            is_published=True,
            created_by=self.user,
        )
        self.article_a2 = Article.objects.create(
            title="Unlock account",
            category=self.cat_a,
            content="<p>Unlock a locked account.</p>",
            is_published=True,
            created_by=self.user,
        )
        self.article_b1 = Article.objects.create(
            title="First login",
            category=self.cat_b,
            content="<p>How to log in the first time.</p>",
            is_published=True,
            created_by=self.user,
        )

    def test_browse_home_shows_categories_and_recent(self):
        response = self.client.get(reverse("kb_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_browse_home"])
        self.assertContains(response, "Browse by category")
        self.assertContains(response, "Recently updated")
        self.assertContains(response, self.cat_a.name)
        self.assertContains(response, self.cat_a.description)
        self.assertContains(response, "Team actions")
        self.assertContains(response, "Create ticket")
        self.assertNotContains(response, "Suggested")
        self.assertNotContains(response, "Back to Tickets")
        self.assertNotIn("suggested_articles", response.context)
        recent = list(response.context["recent_articles"])
        self.assertGreaterEqual(len(recent), 1)
        self.assertIn(self.article_a1, recent)

    def test_search_mode_hides_browse_home(self):
        response = self.client.get(reverse("kb_list"), {"q": "password"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_browse_home"])
        self.assertNotContains(response, "Browse by category")
        self.assertContains(response, "Reset password")
        self.assertContains(response, "result")

    def test_category_filter_shows_results_not_browse(self):
        response = self.client.get(
            reverse("kb_list"), {"category": str(self.cat_a.id)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_browse_home"])
        self.assertContains(response, self.article_a1.title)
        self.assertContains(response, self.article_a2.title)
        self.assertNotContains(response, self.article_b1.title)

    def test_detail_related_articles_same_category(self):
        response = self.client.get(reverse("kb_detail", args=[self.article_a1.pk]))
        self.assertEqual(response.status_code, 200)
        related = list(response.context["related_articles"])
        self.assertIn(self.article_a2, related)
        self.assertNotIn(self.article_a1, related)
        self.assertNotIn(self.article_b1, related)
        self.assertContains(response, "More in this category")
        self.assertContains(response, self.article_a2.title)
        self.assertContains(response, "Knowledge Base")
        self.assertContains(response, self.cat_a.name)
        self.assertContains(response, "kb-detail-layout")
        self.assertContains(response, "kb-detail-side-actions")
        self.assertContains(response, "Edit")

    def test_load_more_append_partial(self):
        for i in range(10):
            Article.objects.create(
                title=f"Extra article {i}",
                category=self.cat_b,
                content="<p>Extra content.</p>",
                is_published=True,
                created_by=self.user,
            )
        response = self.client.get(
            reverse("kb_list"),
            {"category": str(self.cat_b.id), "page": "2", "append": "true"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "kb/partials/results_append.html")

    def test_create_form_page_layout(self):
        response = self.client.get(reverse("kb_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New article")
        self.assertContains(response, "Publish")
        self.assertContains(response, "Save draft")
        self.assertContains(response, "kb-form-layout")
        self.assertContains(response, "kb-form-side-actions")
        self.assertNotContains(response, "tickets-page")

    def test_attachment_kind_helpers(self):
        self.assertEqual(kb_attachment_kind("shot.png"), "image")
        self.assertEqual(kb_attachment_kind("guide.PDF"), "pdf")
        self.assertEqual(kb_attachment_kind("notes.docx"), "file")
        self.assertEqual(basename("kb/1/path/photo.jpg"), "photo.jpg")

    def test_detail_attachment_preview_markup(self):
        ArticleAttachment.objects.create(
            article=self.article_a1,
            file=SimpleUploadedFile(
                "diagram.png",
                b"\x89PNG\r\n\x1a\n",
                content_type="image/png",
            ),
        )
        response = self.client.get(reverse("kb_detail", args=[self.article_a1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "kb-attachment-preview")
        self.assertContains(response, "kb-attachment-preview-close")
        self.assertContains(response, "openKbAttachmentPreview")
        self.assertContains(response, 'data-kb-preview-kind="image"')
        self.assertContains(response, "diagram")
        self.assertNotContains(response, "Open / download")
        self.assertNotContains(response, "kb-attachment-preview-download")
