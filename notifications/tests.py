from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.models import (
    Branch,
    Category,
    Department,
    EmailAppearance,
    EmailSetting,
    EmailTemplate,
    Role,
)
from news.models import Announcement
from notifications.email_content import (
    render_notification_email,
    render_template_string,
    resolve_email_copy,
)
from notifications.email_defaults import ensure_email_format_defaults
from notifications.email_jobs import send_announcement_email, send_new_ticket_email
from notifications.models import InAppNotification
from notifications.services import notify_announcement_created
from tickets.models import Ticket


class AnnouncementNotificationTests(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(code="BR-A", name="Branch A")
        self.branch_b = Branch.objects.create(code="BR-B", name="Branch B")

        self.creator = User.objects.create_user(
            username="news_creator",
            email="news_creator@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            is_superuser=True,
            is_staff=True,
        )
        self.branch_user_a = User.objects.create_user(
            username="ann_branch_a",
            email="ann_a@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_a,
        )
        self.branch_user_b = User.objects.create_user(
            username="ann_branch_b",
            email="ann_b@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_b,
        )
        self.support_user = User.objects.create_user(
            username="ann_support",
            email="ann_support@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
        )
        self.inactive_user = User.objects.create_user(
            username="ann_inactive",
            email="ann_inactive@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_a,
            status=User.Status.INACTIVE,
        )
        EmailSetting.objects.create(
            smtp_host="smtp.test.local",
            smtp_port=587,
            smtp_email="noreply@test.local",
            smtp_password="secret",
            encryption="tls",
            from_name="mlamehticket Test",
            from_email="noreply@test.local",
            is_active=True,
            notify_announcement=True,
        )

    def _recipients_for(self, title):
        return set(
            InAppNotification.objects.filter(
                notification_type="announcement",
                title=title,
            ).values_list("recipient_id", flat=True)
        )

    @patch("notifications.services._enqueue")
    def test_global_announcement_notifies_all_active_users_except_actor(self, _enqueue):
        announcement = Announcement.objects.create(
            title="System update",
            content="Maintenance tonight.",
            created_by=self.creator,
            is_active=True,
        )

        notify_announcement_created(announcement, actor=self.creator)

        recipients = self._recipients_for("Announcement: System update")
        self.assertIn(self.branch_user_a.id, recipients)
        self.assertIn(self.branch_user_b.id, recipients)
        self.assertIn(self.support_user.id, recipients)
        self.assertNotIn(self.creator.id, recipients)
        self.assertNotIn(self.inactive_user.id, recipients)
        _enqueue.assert_called_once()

    @patch("notifications.services._enqueue")
    def test_branch_announcement_skips_other_branch_and_support(self, _enqueue):
        announcement = Announcement.objects.create(
            title="Branch notice",
            content="Branch A only.",
            created_by=self.creator,
            is_active=True,
            target_branch=self.branch_a,
        )

        notify_announcement_created(announcement, actor=self.creator)

        recipients = self._recipients_for("Announcement: Branch notice")
        self.assertIn(self.branch_user_a.id, recipients)
        self.assertNotIn(self.branch_user_b.id, recipients)
        self.assertNotIn(self.support_user.id, recipients)
        self.assertNotIn(self.creator.id, recipients)

    @patch("notifications.services._enqueue")
    def test_inactive_announcement_does_not_notify(self, _enqueue):
        announcement = Announcement.objects.create(
            title="Draft",
            content="Not live.",
            created_by=self.creator,
            is_active=False,
        )

        notify_announcement_created(announcement, actor=self.creator)

        self.assertFalse(
            InAppNotification.objects.filter(
                notification_type="announcement",
                title="Announcement: Draft",
            ).exists()
        )
        _enqueue.assert_not_called()

    @patch("notifications.email_jobs.send_with_retries")
    def test_announcement_email_sends_to_active_users_with_emails(self, send_with_retries):
        send_with_retries.return_value = True
        announcement = Announcement.objects.create(
            title="Office closed",
            content="We will be closed Friday.",
            created_by=self.creator,
            is_active=True,
        )

        sent = send_announcement_email(announcement.id, actor_id=self.creator.id)

        self.assertTrue(sent)
        send_with_retries.assert_called_once()
        subject, body, recipients = send_with_retries.call_args.args[:3]
        html_body = send_with_retries.call_args.kwargs.get("html_body")
        self.assertIn("Announcement: Office closed", subject)
        self.assertIn(self.branch_user_a.email, recipients)
        self.assertIn(self.support_user.email, recipients)
        self.assertNotIn(self.creator.email, recipients)
        self.assertNotIn(self.inactive_user.email, recipients)
        self.assertIn("We will be closed Friday.", body)
        self.assertIn("View announcements", body)
        self.assertTrue(html_body)
        self.assertIn("Office closed", html_body)


class EmailContentTests(TestCase):
    def test_render_notification_email_includes_cta_and_details(self):
        text_body, html_body = render_notification_email(
            headline="New ticket #TK-1",
            intro="A new request was submitted.",
            details=[("Ticket", "TK-1"), ("Priority", "High")],
            message_title="Request",
            message_body="Printer is offline.",
            cta_url="https://helpdesk.example.com/tickets/1/",
            cta_label="View ticket",
        )
        self.assertIn("New ticket #TK-1", text_body)
        self.assertIn("Ticket: TK-1", text_body)
        self.assertIn("Printer is offline.", text_body)
        self.assertIn("https://helpdesk.example.com/tickets/1/", text_body)
        self.assertIn("View ticket", html_body)
        self.assertIn("Printer is offline.", html_body)

    @override_settings(SITE_URL="https://helpdesk.example.com")
    @patch("notifications.email_jobs.send_with_retries")
    def test_new_ticket_email_content(self, send_with_retries):
        send_with_retries.return_value = True
        branch = Branch.objects.create(code="EM", name="Email Branch")
        department = Department.objects.create(name="Email Dept")
        category = Category.objects.create(
            department=department,
            name="Email Cat",
            default_priority=Ticket.Priority.HIGH,
        )
        creator = User.objects.create_user(
            username="email_creator",
            email="creator@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=branch,
        )
        User.objects.create_user(
            username="email_support",
            email="support_email@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=department,
        )
        EmailSetting.objects.create(
            smtp_host="smtp.test.local",
            smtp_port=587,
            smtp_email="noreply@test.local",
            smtp_password="secret",
            encryption="tls",
            from_name="mlamehticket Test",
            from_email="noreply@test.local",
            is_active=True,
            notify_new_ticket=True,
        )
        ticket = Ticket.objects.create(
            ticket_number="TK-EMAIL-1",
            title="Cannot print",
            description="The lobby printer is jammed.",
            branch=branch,
            department=department,
            category=category,
            created_by=creator,
            priority=Ticket.Priority.HIGH,
            client_name="Client",
            client_phone="555",
        )

        sent = send_new_ticket_email(ticket.id)

        self.assertTrue(sent)
        subject, body, recipients = send_with_retries.call_args.args[:3]
        html_body = send_with_retries.call_args.kwargs["html_body"]
        self.assertIn("New ticket #TK-EMAIL-1", subject)
        self.assertIn("support_email@test.com", recipients)
        self.assertNotIn("creator@test.com", recipients)
        self.assertIn("The lobby printer is jammed.", body)
        self.assertIn("https://helpdesk.example.com/tickets/", body)
        self.assertIn("View ticket", html_body)
        self.assertIn("High", body)


class EmailFormatTests(TestCase):
    def setUp(self):
        ensure_email_format_defaults()
        self.appearance = EmailAppearance.load()
        self.appearance.brand_name = "AcmeDesk"
        self.appearance.accent_color = "#0d9488"
        self.appearance.footer_note = "Custom footer note."
        self.appearance.save()

        self.template = EmailTemplate.objects.get(event_type="new_ticket")
        self.template.subject = "[{{ brand_name }}] OPEN #{{ ticket_number }}"
        self.template.headline = "Opened #{{ ticket_number }}"
        self.template.intro = "{{ actor_name }} filed {{ ticket_title }}."
        self.template.cta_label = "Inspect ticket"
        self.template.is_active = True
        self.template.save()

        self.branch = Branch.objects.create(code="EF", name="Format Branch")
        self.department = Department.objects.create(name="Format Dept")
        self.category = Category.objects.create(
            department=self.department,
            name="Format Cat",
            default_priority=Ticket.Priority.MEDIUM,
        )
        self.creator = User.objects.create_user(
            username="format_creator",
            email="format_creator@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch,
            first_name="Sam",
            last_name="Requester",
        )
        User.objects.create_user(
            username="format_support",
            email="format_support@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.department,
        )
        EmailSetting.objects.create(
            smtp_host="smtp.test.local",
            smtp_port=587,
            smtp_email="noreply@test.local",
            smtp_password="secret",
            encryption="tls",
            from_name="Test",
            from_email="noreply@test.local",
            is_active=True,
            notify_new_ticket=True,
        )
        self.ticket = Ticket.objects.create(
            ticket_number="TK-FORMAT-1",
            title="VPN down",
            description="Cannot connect to VPN.",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.creator,
            priority=Ticket.Priority.MEDIUM,
            client_name="Client",
            client_phone="555",
        )

    def test_render_template_string_and_fallback(self):
        self.assertEqual(
            render_template_string("Hello {{ name }}", {"name": "Ada"}, fallback="x"),
            "Hello Ada",
        )
        self.assertEqual(render_template_string("", {"name": "Ada"}, fallback="fallback"), "fallback")
        self.assertEqual(
            render_template_string(
                "{{ name|not_a_real_filter }}", {"name": "Ada"}, fallback="fallback"
            ),
            "fallback",
        )
        self.assertEqual(
            render_template_string("{% if name %}x{% endif %}", {"name": "Ada"}, fallback="fallback"),
            "fallback",
        )

    def test_custom_template_used_in_new_ticket_email(self):
        with patch("notifications.email_jobs.send_with_retries") as send_with_retries:
            send_with_retries.return_value = True
            sent = send_new_ticket_email(self.ticket.id)

        self.assertTrue(sent)
        subject, body, _recipients = send_with_retries.call_args.args[:3]
        html_body = send_with_retries.call_args.kwargs["html_body"]
        self.assertEqual(subject, "[AcmeDesk] OPEN #TK-FORMAT-1")
        self.assertIn("Opened #TK-FORMAT-1", body)
        self.assertIn("Sam Requester filed VPN down.", body)
        self.assertIn("Inspect ticket", html_body)
        self.assertIn("#0d9488", html_body)
        self.assertIn("AcmeDesk", html_body)
        self.assertIn("Custom footer note.", html_body)

    def test_inactive_template_falls_back_to_defaults(self):
        self.template.is_active = False
        self.template.save(update_fields=["is_active"])

        with patch("notifications.email_jobs.send_with_retries") as send_with_retries:
            send_with_retries.return_value = True
            send_new_ticket_email(self.ticket.id)

        subject = send_with_retries.call_args.args[0]
        self.assertIn("New ticket #TK-FORMAT-1", subject)
        self.assertNotIn("OPEN #", subject)

    def test_broken_template_falls_back_to_defaults(self):
        self.template.subject = "{{ ticket_number|not_a_real_filter }}"
        self.template.save(update_fields=["subject"])

        copy = resolve_email_copy(
            "new_ticket",
            {"ticket_number": "1", "ticket_title": "t", "actor_name": "A", "department_suffix": ""},
            defaults={
                "subject": "FALLBACK SUBJECT",
                "headline": "h",
                "intro": "i",
                "message_title": "m",
                "cta_label": "c",
            },
        )
        self.assertEqual(copy["subject"], "FALLBACK SUBJECT")
        self.assertEqual(copy["brand_name"], "AcmeDesk")
        self.assertEqual(copy["accent_color"], "#0d9488")

    def test_render_notification_email_uses_branding(self):
        _text, html_body = render_notification_email(
            headline="Hello",
            intro="Intro",
            brand_name="AcmeDesk",
            accent_color="#0d9488",
            footer_note="Custom footer note.",
        )
        self.assertIn("AcmeDesk", html_body)
        self.assertIn("#0d9488", html_body)
        self.assertIn("Custom footer note.", html_body)


class EmailFormatPermissionTests(TestCase):
    def setUp(self):
        ensure_email_format_defaults()
        self.client = Client()
        self.settings_role = Role.objects.create(
            name="Settings Viewer",
            can_access_settings=True,
            can_manage_email=False,
        )
        self.email_role = Role.objects.create(
            name="Email Manager",
            can_access_settings=True,
            can_manage_email=True,
        )
        self.viewer = User.objects.create_user(
            username="settings_viewer",
            email="viewer@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            role=self.settings_role,
        )
        self.manager = User.objects.create_user(
            username="email_manager",
            email="manager@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            role=self.email_role,
        )
        EmailAppearance.load()
        self.template = EmailTemplate.objects.get(event_type="new_ticket")

    def test_viewer_cannot_post_appearance(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("email_appearance_update"),
            {
                "brand_name": "Hacked",
                "accent_color": "#111111",
                "footer_note": "nope",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(EmailAppearance.load().brand_name, "Hacked")

    def test_manager_can_post_appearance(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("email_appearance_update"),
            {
                "brand_name": "ManagedBrand",
                "accent_color": "#abcdef",
                "footer_note": "Managed footer",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        appearance = EmailAppearance.load()
        self.assertEqual(appearance.brand_name, "ManagedBrand")
        self.assertEqual(appearance.accent_color, "#abcdef")

    def test_viewer_cannot_post_template(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse("email_template_update", kwargs={"event_type": "new_ticket"}),
            {
                "subject": "Hacked subject",
                "headline": "Hacked headline",
                "intro": "intro",
                "message_title": "Request",
                "cta_label": "Go",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.template.refresh_from_db()
        self.assertNotEqual(self.template.subject, "Hacked subject")
