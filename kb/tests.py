from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from core.models import Branch, Department, Role
from core.models import Category as TicketCategory
from kb.models import Article, ArticleAttachment, Category
from kb.templatetags.kb_extras import basename, kb_attachment_kind
from tickets.access import user_can_view_ticket
from tickets.models import Ticket


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
        self.assertNotContains(response, 'id="kb-shell-pane"')
        self.assertNotContains(response, "<html")

    def test_htmx_kb_list_is_pane_only_and_still_private(self):
        full = self.client.get(reverse("kb_list"))
        response = self.client.get(reverse("kb_list"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "kb/list_shell_partial.html")
        self.assertContains(response, 'id="kb-shell-pane"')
        self.assertContains(response, "mountKbSearch")
        self.assertContains(response, "unmountTicketListWS")
        self.assertContains(full, "js/kb-search.js?v=1.1")
        self.assertContains(full, "<html")
        self.assertContains(full, "kb-search-page")
        self.assertNotContains(response, "<html")
        self.assertNotContains(response, 'id="shell-content"')
        self.assertEqual(response["Cache-Control"], full["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("HX-Request", response.get("Vary", ""))

    def test_history_restore_returns_kb_pane(self):
        response = self.client.get(
            reverse("kb_list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )
        self.assertTemplateUsed(response, "kb/list_shell_partial.html")
        self.assertContains(response, 'id="kb-shell-pane"')
        self.assertNotContains(response, "<html")

    def test_browse_home_skips_article_bodies(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.article_a1.content = "<p>SECRET-ARTICLE-HTML</p>" * 20
        self.article_a1.save(update_fields=["content"])

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("kb_list"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("all_articles_count", response.context)
        self.assertNotIn("has_active_filters", response.context)
        self.assertEqual(list(response.context["articles"]), [])
        recent = list(response.context["recent_articles"])
        self.assertIn(self.article_a1, recent)
        self.assertIn("content", recent[0].get_deferred_fields())
        with self.assertNumQueries(0):
            self.assertTrue(recent[0].category.name)
            self.assertTrue(recent[0].category.icon)
        for query in ctx.captured_queries:
            if "kb_article" in query["sql"]:
                self.assertNotIn("content", query["sql"].lower())
        self.assertContains(response, "Browse by category")
        self.assertContains(response, "Recently updated")
        self.assertContains(response, "mountKbSearch")
        self.assertNotContains(response, "SECRET-ARTICLE-HTML")
        self.assertContains(response, 'data-etag="')

        paged = self.client.get(reverse("kb_list"), {"page": "2"})
        self.assertEqual(paged.status_code, 200)
        self.assertContains(paged, "Browse by category")

    def test_search_still_loads_snippets_and_etag_tracks_filters(self):
        home = self.client.get(reverse("kb_list"))
        found = self.client.get(reverse("kb_list"), {"q": "password"})
        self.assertEqual(found.status_code, 200)
        self.assertNotEqual(found["ETag"], home["ETag"])
        article = found.context["articles"][0]
        self.assertNotIn("content", article.get_deferred_fields())
        self.assertContains(found, "Reset password")
        self.assertIn("no-store", found["Cache-Control"])
        self.assertIn("private", found["Cache-Control"])

        cached = self.client.get(
            reverse("kb_list"),
            {"q": "password"},
            HTTP_HX_REQUEST="true",
            HTTP_IF_NONE_MATCH=found["ETag"],
        )
        self.assertEqual(cached.status_code, 304)
        self.assertIn("HX-Request", cached.get("Vary", ""))
        self.assertIn("no-store", cached["Cache-Control"])
        self.assertEqual(cached.content, b"")

        restore = self.client.get(
            reverse("kb_list"),
            {"q": "password"},
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
            HTTP_IF_NONE_MATCH=found["ETag"],
        )
        self.assertEqual(restore.status_code, 200)
        self.assertContains(restore, "Reset password")
        self.assertContains(restore, 'id="kb-shell-pane"')

    def test_load_more_skips_category_context_and_etag(self):
        for i in range(10):
            Article.objects.create(
                title=f"Paged article {i}",
                category=self.cat_b,
                content="<p>Paged body.</p>",
                is_published=True,
                created_by=self.user,
            )
        listed = self.client.get(
            reverse("kb_list"),
            {"category": str(self.cat_b.id)},
        )
        response = self.client.get(
            reverse("kb_list"),
            {"category": str(self.cat_b.id), "page": "2", "append": "true"},
            HTTP_HX_REQUEST="true",
            HTTP_IF_NONE_MATCH=listed["ETag"],
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ETag", response)
        self.assertNotIn("categories", response.context)
        self.assertNotIn("recent_articles", response.context)
        self.assertContains(response, "Paged article")
        self.assertNotContains(response, 'id="kb-shell-pane"')

    def test_create_form_page_layout(self):
        response = self.client.get(reverse("kb_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New article")
        self.assertContains(response, "Publish")
        self.assertContains(response, "Save draft")
        self.assertContains(response, "kb-form-layout")
        self.assertContains(response, "kb-form-side-actions")
        self.assertContains(response, "vendor/tinymce/tinymce.min.js")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/tinymce")
        self.assertNotContains(response, "tickets-page")

    def test_attachment_kind_helpers(self):
        self.assertEqual(kb_attachment_kind("shot.png"), "image")
        self.assertEqual(kb_attachment_kind("guide.PDF"), "pdf")
        self.assertEqual(kb_attachment_kind("notes.docx"), "file")
        self.assertEqual(basename("kb/1/path/photo.jpg"), "photo.jpg")

    def test_detail_attachment_preview_markup(self):
        attachment = ArticleAttachment.objects.create(
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
        self.assertContains(response, reverse("kb_attachment", args=[attachment.pk]))
        self.assertNotContains(response, attachment.file.url)


class KnowledgeBaseVisibilityTests(TestCase):
    def setUp(self):
        self.dept_a = Department.objects.create(name="KB Dept A")
        self.dept_b = Department.objects.create(name="KB Dept B")
        self.branch_a = Branch.objects.create(code="KBA", name="KB Branch A")
        self.branch_b = Branch.objects.create(code="KBB", name="KB Branch B")
        self.ticket_category = TicketCategory.objects.create(
            department=self.dept_a,
            name="KB Ticket Cat",
            default_priority=Ticket.Priority.MEDIUM,
        )
        self.manage_role = Role.objects.create(
            name="KB Manager Visibility",
            can_access_kb=True,
            can_manage_kb=True,
        )
        self.read_role = Role.objects.create(
            name="KB Reader Visibility",
            can_access_kb=True,
            can_manage_kb=False,
        )
        self.author = User.objects.create_user(
            username="kb_vis_author",
            email="kb-vis-author@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_a,
            role=self.manage_role,
        )
        self.same_dept = User.objects.create_user(
            username="kb_vis_same",
            email="kb-vis-same@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_a,
            role=self.read_role,
        )
        self.other_dept = User.objects.create_user(
            username="kb_vis_other",
            email="kb-vis-other@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_b,
            role=self.read_role,
        )
        self.reader = User.objects.create_user(
            username="kb_vis_reader",
            email="kb-vis-reader@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_b,
            role=self.read_role,
        )
        self.branch_user = User.objects.create_user(
            username="kb_vis_branch",
            email="kb-vis-branch@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_b,
            role=self.manage_role,
        )
        self.category = Category.objects.create(name="Visibility Cat", icon="book")
        self.only_me = Article.objects.create(
            title="ONLYME-TOKEN private note",
            category=self.category,
            content="<p>Only the author.</p>",
            is_published=True,
            visibility=Article.Visibility.ONLY_ME,
            created_by=self.author,
        )
        self.department_article = Article.objects.create(
            title="DEPT-TOKEN department note",
            category=self.category,
            content="<p>Department only.</p>",
            is_published=True,
            visibility=Article.Visibility.DEPARTMENT,
            created_by=self.author,
        )
        self.shared = Article.objects.create(
            title="ALL-TOKEN shared note",
            category=self.category,
            content="<p>All support.</p>",
            is_published=True,
            visibility=Article.Visibility.ALL_SUPPORT,
            created_by=self.author,
        )
        self.draft = Article.objects.create(
            title="DRAFT-TOKEN unfinished",
            category=self.category,
            content="<p>Not published.</p>",
            is_published=False,
            visibility=Article.Visibility.ALL_SUPPORT,
            created_by=self.author,
        )
        self.ticket = Ticket.objects.create(
            ticket_number="TK-KB-VIS-1",
            title="<b>Injected ticket title</b>",
            description="desc",
            branch=self.branch_a,
            department=self.dept_a,
            category=self.ticket_category,
            created_by=self.author,
            status=Ticket.Status.OPEN,
            client_name="Client",
            client_phone="123",
        )
        self.outside_ticket = Ticket.objects.create(
            ticket_number="TK-KB-VIS-2",
            title="Outside org ticket",
            description="desc",
            branch=self.branch_b,
            department=self.dept_b,
            category=TicketCategory.objects.create(
                department=self.dept_b,
                name="KB Ticket Cat B",
                default_priority=Ticket.Priority.LOW,
            ),
            created_by=self.other_dept,
            status=Ticket.Status.OPEN,
            client_name="Client",
            client_phone="456",
        )
        self.shared.related_ticket = self.ticket
        self.shared.save(update_fields=["related_ticket"])

    def _login(self, username):
        self.client.logout()
        self.client.login(username=username, password="testpassword123")

    def test_branch_user_blocked_even_with_kb_permissions(self):
        self._login("kb_vis_branch")
        self.assertEqual(self.client.get(reverse("kb_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.shared.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("kb_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("kb_category_list")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("kb_search_suggest"), {"q": "ALL"}).status_code,
            403,
        )

    def test_reader_cannot_write_or_open_draft_by_id(self):
        self._login("kb_vis_reader")
        self.assertEqual(self.client.get(reverse("kb_create")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("kb_create"),
                {
                    "title": "Sneaky",
                    "content": "<p>no</p>",
                    "visibility": Article.Visibility.ALL_SUPPORT,
                    "action": "draft",
                },
            ).status_code,
            403,
        )
        self.assertEqual(self.client.get(reverse("kb_update", args=[self.shared.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("kb_delete", args=[self.shared.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("kb_category_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.draft.pk])).status_code, 404)
        listed = self.client.get(reverse("kb_list"), {"q": "DRAFT-TOKEN"})
        self.assertNotIn(self.draft, list(listed.context["articles"]))
        home = self.client.get(reverse("kb_list"))
        self.assertNotIn(self.draft, list(home.context["recent_articles"]))
        suggest = self.client.get(reverse("kb_search_suggest"), {"q": "DRAFT-TOKEN"})
        self.assertNotContains(suggest, "DRAFT-TOKEN")

    def test_only_me_and_department_hidden_from_other_departments(self):
        self._login("kb_vis_other")
        home = self.client.get(reverse("kb_list"))
        self.assertContains(home, self.shared.title)
        self.assertNotContains(home, self.only_me.title)
        self.assertNotContains(home, self.department_article.title)
        recent = list(home.context["recent_articles"])
        self.assertIn(self.shared, recent)
        self.assertNotIn(self.only_me, recent)
        self.assertNotIn(self.department_article, recent)
        category = next(row for row in home.context["categories"] if row.pk == self.category.pk)
        self.assertEqual(category.article_count, 1)
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.only_me.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("kb_detail", args=[self.department_article.pk])).status_code,
            404,
        )
        detail = self.client.get(reverse("kb_detail", args=[self.shared.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, self.only_me.title)
        self.assertNotContains(detail, self.department_article.title)
        suggest = self.client.get(reverse("kb_search_suggest"), {"q": "ONLYME"})
        self.assertNotContains(suggest, self.only_me.title)
        dept_suggest = self.client.get(reverse("kb_search_suggest"), {"q": "DEPT-TOKEN"})
        self.assertNotContains(dept_suggest, self.department_article.title)
        append = self.client.get(
            reverse("kb_list"),
            {"category": str(self.category.pk), "append": "true"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(append, self.shared.title)
        self.assertNotContains(append, self.only_me.title)
        self.assertNotContains(append, self.department_article.title)

        self._login("kb_vis_same")
        same = self.client.get(reverse("kb_list"))
        self.assertContains(same, self.department_article.title)
        self.assertContains(same, self.shared.title)
        self.assertNotContains(same, self.only_me.title)
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.only_me.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("kb_detail", args=[self.department_article.pk])).status_code,
            200,
        )

        self._login("kb_vis_author")
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.only_me.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("kb_detail", args=[self.draft.pk])).status_code, 200)

    def test_script_tag_does_not_round_trip(self):
        self._login("kb_vis_author")
        raw = '<script>alert(1)</script><p onclick="alert(1)">Hi</p><a href="javascript:alert(1)">x</a>'
        response = self.client.post(
            reverse("kb_create"),
            {
                "title": "XSS article",
                "content": raw,
                "visibility": Article.Visibility.ALL_SUPPORT,
                "action": "all_support",
            },
        )
        article = Article.objects.get(title="XSS article")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("<script", article.content.lower())
        self.assertNotIn("onclick", article.content.lower())
        self.assertNotIn("javascript:", article.content.lower())
        self.assertIn(">Hi<", article.content)
        detail = self.client.get(reverse("kb_detail", args=[article.pk]))
        rendered = detail.context["article"].content.lower()
        self.assertNotIn("<script", rendered)
        self.assertNotIn("onclick", rendered)
        self.assertNotIn("javascript:", rendered)
        self.assertNotContains(detail, "alert(1)", html=False)
        self.assertContains(detail, "Hi")

    def test_attachment_url_without_session_does_not_return_file(self):
        attachment = ArticleAttachment.objects.create(
            article=self.shared,
            file=SimpleUploadedFile("diagram.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"),
        )
        self.client.logout()
        media = self.client.get(attachment.file.url)
        guarded = self.client.get(reverse("kb_attachment", args=[attachment.pk]))
        self.assertNotEqual(media.status_code, 200)
        self.assertNotEqual(guarded.status_code, 200)
        self.assertNotIn(b"\x89PNG", media.content)
        self.assertNotIn(b"\x89PNG", guarded.content)

        self._login("kb_vis_other")
        allowed = self.client.get(reverse("kb_attachment", args=[attachment.pk]))
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b"\x89PNG", b"".join(allowed.streaming_content))
        hidden = ArticleAttachment.objects.create(
            article=self.only_me,
            file=SimpleUploadedFile("secret.png", b"\x89PNG\r\n\x1a\nsecret", content_type="image/png"),
        )
        denied = self.client.get(reverse("kb_attachment", args=[hidden.pk]))
        self.assertEqual(denied.status_code, 404)
        draft_file = ArticleAttachment.objects.create(
            article=self.draft,
            file=SimpleUploadedFile("draft.png", b"\x89PNG\r\n\x1a\ndraft", content_type="image/png"),
        )
        self._login("kb_vis_reader")
        self.assertEqual(self.client.get(reverse("kb_attachment", args=[draft_file.pk])).status_code, 404)

    def test_published_article_does_not_unlock_ticket_outside_org(self):
        self.assertFalse(user_can_view_ticket(self.other_dept, self.ticket))
        self.assertTrue(user_can_view_ticket(self.same_dept, self.ticket))
        self._login("kb_vis_other")
        ticket_page = self.client.get(reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))
        self.assertEqual(ticket_page.status_code, 403)
        article_page = self.client.get(reverse("kb_detail", args=[self.shared.pk]))
        self.assertContains(article_page, f"#{self.ticket.ticket_number}")
        self.assertNotContains(article_page, reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))

        self._login("kb_vis_same")
        linked = self.client.get(reverse("kb_detail", args=[self.shared.pk]))
        self.assertContains(linked, reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))

    def test_existing_articles_remain_visible_to_support_readers(self):
        legacy = Article.objects.create(
            title="Legacy published article",
            category=self.category,
            content="<p>Already in the library.</p>",
            is_published=True,
            created_by=self.author,
        )
        self.assertEqual(legacy.visibility, Article.Visibility.ALL_SUPPORT)
        self._login("kb_vis_other")
        response = self.client.get(reverse("kb_detail", args=[legacy.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, legacy.title)

    def test_form_can_save_draft_and_remove_attachment(self):
        self._login("kb_vis_author")
        created = self.client.post(
            reverse("kb_create"),
            {
                "title": "Draft with file",
                "content": "<p>Work in progress.</p>",
                "visibility": Article.Visibility.ALL_SUPPORT,
                "category": str(self.category.pk),
                "action": "draft",
            },
        )
        article = Article.objects.get(title="Draft with file")
        self.assertEqual(created.status_code, 302)
        self.assertFalse(article.is_published)
        attachment = ArticleAttachment.objects.create(
            article=article,
            file=SimpleUploadedFile("notes.pdf", b"%PDF-1.4", content_type="application/pdf"),
        )
        form_page = self.client.get(reverse("kb_update", args=[article.pk]))
        self.assertContains(form_page, "kb-dropzone")
        self.assertContains(form_page, "beforeunload")
        self.assertContains(form_page, "blocks | bullist numlist | link | code | table")
        self.assertContains(form_page, 'value="only_me"')
        self.assertContains(form_page, 'value="department"')
        self.assertContains(form_page, 'value="all_support"')
        self.assertContains(form_page, "kb-remove-existing")
        self.assertNotContains(form_page, "kb-ticket-modal")
        self.assertNotContains(form_page, "cdn.jsdelivr.net")
        removed = self.client.post(
            reverse("kb_update", args=[article.pk]),
            {
                "title": article.title,
                "content": "<p>Work in progress.</p>",
                "visibility": Article.Visibility.ALL_SUPPORT,
                "category": str(self.category.pk),
                "action": "draft",
                "remove_attachments": [str(attachment.pk)],
            },
        )
        article.refresh_from_db()
        self.assertEqual(removed.status_code, 302)
        self.assertFalse(article.is_published)
        self.assertFalse(ArticleAttachment.objects.filter(pk=attachment.pk).exists())

        no_dept = User.objects.create_user(
            username="kb_vis_nodept",
            email="kb-vis-nodept@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            role=self.manage_role,
        )
        self.client.logout()
        self.client.login(username="kb_vis_nodept", password="testpassword123")
        create_page = self.client.get(reverse("kb_create"))
        self.assertContains(create_page, "Publish")
        self.assertContains(create_page, "Save draft")
        self.assertNotContains(create_page, 'value="department"')

    def test_autosave_saves_a_draft_without_publishing(self):
        self._login("kb_vis_author")
        response = self.client.post(
            reverse("kb_create"),
            {
                "title": "Autosave note",
                "content": "<p>wip</p>",
                "visibility": Article.Visibility.ONLY_ME,
                "action": "draft",
            },
            HTTP_X_KB_AUTOSAVE="1",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        article = Article.objects.get(pk=payload["id"])
        self.assertFalse(article.is_published)
        self.assertEqual(article.visibility, Article.Visibility.ONLY_ME)
        self.assertIn(f"/kb/{article.pk}/edit/", payload["edit_url"])

    def test_ticket_search_requires_manager_and_escapes_titles(self):
        self._login("kb_vis_reader")
        denied = self.client.get(reverse("kb_ticket_search"), {"q": "Injected"})
        self.assertEqual(denied.status_code, 403)

        other_manager = User.objects.create_user(
            username="kb_vis_other_mgr",
            email="kb-vis-other-mgr@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_b,
            role=self.manage_role,
        )
        self.client.logout()
        self.client.login(username=other_manager.username, password="testpassword123")
        outside = self.client.get(reverse("kb_ticket_search"), {"q": "Injected"})
        self.assertEqual(outside.status_code, 200)
        self.assertNotContains(outside, self.ticket.ticket_number)

        self._login("kb_vis_author")
        found = self.client.get(reverse("kb_ticket_search"), {"q": "Injected"})
        self.assertEqual(found.status_code, 200)
        self.assertContains(found, self.ticket.ticket_number)
        self.assertNotContains(found, "<b>Injected ticket title</b>", html=False)
        self.assertContains(found, "&lt;b&gt;", html=False)
        missed = self.client.get(reverse("kb_ticket_search"), {"q": "Outside org"})
        self.assertNotContains(missed, self.outside_ticket.ticket_number)
