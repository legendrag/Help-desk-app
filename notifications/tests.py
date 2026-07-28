from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.models import User
from core.models import Branch, Category, Department, EmailSetting, EmailTemplate
from news.models import Announcement
from notifications.email_content import render_notification_email
from notifications.email_jobs import send_announcement_email, send_new_ticket_email
from notifications.email_templates import ensure_email_templates, render_tokens, resolve_template
from notifications.models import InAppNotification
from notifications.services import notify_announcement_created, notify_new_ticket
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
            from_name="MlamehTicket Test",
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
        self.assertNotIn("<td style=\"width:38%", html_body)


class EmailContentTests(TestCase):
    def test_render_notification_email_is_table_free_shell(self):
        text_body, html_body = render_notification_email(
            body="New ticket #TK-1\n\nPrinter is offline.",
            cta_url="https://helpdesk.example.com/tickets/1/",
            cta_label="View ticket",
        )
        self.assertIn("New ticket #TK-1", text_body)
        self.assertIn("Printer is offline.", text_body)
        self.assertIn("https://helpdesk.example.com/tickets/1/", text_body)
        self.assertIn("View ticket", html_body)
        self.assertIn("Printer is offline.", html_body)
        self.assertNotIn("Priority", html_body)
        self.assertNotIn('width:38%', html_body)

    def test_render_tokens_and_fallback_defaults(self):
        rendered = render_tokens(
            "Hello {{ requester }} — #{{ ticket_number }}",
            {"requester": "Ada", "ticket_number": "TK-9"},
        )
        self.assertEqual(rendered, "Hello Ada — #TK-9")

        EmailTemplate.objects.all().delete()
        subject, body, cta = resolve_template(
            "new_ticket",
            {
                "brand_name": "MlamehTicket",
                "ticket_number": "TK-9",
                "title": "Printer",
                "requester": "Ada",
                "department": "IT",
                "description": "Jammed",
            },
        )
        self.assertIn("TK-9", subject)
        self.assertIn("Ada", body)
        self.assertEqual(cta, "View ticket")

    def test_custom_template_overrides_defaults(self):
        ensure_email_templates()
        EmailTemplate.objects.filter(event_type="new_ticket").update(
            subject="CUSTOM {{ ticket_number }}",
            body="Body for {{ title }}",
        )
        subject, body, _cta = resolve_template(
            "new_ticket",
            {"ticket_number": "TK-1", "title": "Outage"},
        )
        self.assertEqual(subject, "CUSTOM TK-1")
        self.assertEqual(body, "Body for Outage")

    @override_settings(SITE_URL="https://helpdesk.example.com")
    @patch("notifications.email_jobs.send_with_retries")
    def test_new_ticket_email_content(self, send_with_retries):
        send_with_retries.return_value = True
        ensure_email_templates()
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
            from_name="MlamehTicket Test",
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
        self.assertNotIn('width:38%', html_body)

    @override_settings(SITE_URL="https://helpdesk.example.com")
    @patch("notifications.email_jobs.send_with_retries")
    def test_custom_new_ticket_template_is_used(self, send_with_retries):
        send_with_retries.return_value = True
        ensure_email_templates()
        EmailTemplate.objects.filter(event_type="new_ticket").update(
            subject="ALERT {{ ticket_number }}",
            body="Please help with {{ title }}",
        )
        branch = Branch.objects.create(code="EM2", name="Email Branch 2")
        department = Department.objects.create(name="Email Dept 2")
        category = Category.objects.create(
            department=department,
            name="Email Cat 2",
            default_priority=Ticket.Priority.HIGH,
        )
        creator = User.objects.create_user(
            username="email_creator2",
            email="creator2@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=branch,
        )
        User.objects.create_user(
            username="email_support2",
            email="support2@test.com",
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
            from_name="MlamehTicket Test",
            from_email="noreply@test.local",
            is_active=True,
            notify_new_ticket=True,
        )
        ticket = Ticket.objects.create(
            ticket_number="TK-CUSTOM-1",
            title="VPN down",
            description="Cannot connect",
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
        subject, body, _recipients = send_with_retries.call_args.args[:3]
        self.assertEqual(subject, "ALERT TK-CUSTOM-1")
        self.assertIn("Please help with VPN down", body)


class EmailTemplateTestSendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="email_admin",
            email="admin@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            is_superuser=True,
            is_staff=True,
        )
        EmailSetting.objects.create(
            smtp_host="smtp.test.local",
            smtp_port=587,
            smtp_email="noreply@test.local",
            smtp_password="secret",
            encryption="tls",
            from_name="MlamehTicket Test",
            from_email="noreply@test.local",
            is_active=True,
        )
        self.client.force_login(self.user)

    @patch("core.management_views.send_with_retries")
    def test_send_test_email_uses_form_and_sample_data(self, send_with_retries):
        send_with_retries.return_value = True
        response = self.client.post(
            "/core/email-templates/new_ticket/test/",
            {
                "subject": "[{{ brand_name }}] Test #{{ ticket_number }}",
                "body": "Hello {{ requester }}\n\n{{ description }}",
            },
        )
        self.assertEqual(response.status_code, 204)
        send_with_retries.assert_called_once()
        subject, body, recipients = send_with_retries.call_args.args[:3]
        self.assertTrue(subject.startswith("[TEST]"))
        self.assertIn("TK-1001", subject)
        self.assertIn("Alex Requester", body)
        self.assertEqual(recipients, ["admin@test.com"])
        trigger = response.headers.get("HX-Trigger", "")
        self.assertIn("emailTemplateTestResult", trigger)
        self.assertIn("admin@test.com", trigger)

    @patch("core.management_views.send_with_retries")
    def test_send_test_email_requires_active_smtp(self, send_with_retries):
        send_with_retries.return_value = False
        response = self.client.post(
            "/core/email-templates/new_ticket/test/",
            {
                "subject": "Subject",
                "body": "Body",
            },
        )
        self.assertEqual(response.status_code, 200)
        trigger = response.headers.get("HX-Trigger", "")
        self.assertIn("Could not send", trigger)


class NewTicketInAppNotificationTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code="NT-BR", name="Notify Branch")
        self.department = Department.objects.create(name="Notify Dept")
        self.category = Category.objects.create(name="Notify Cat", department=self.department)
        self.creator = User.objects.create_user(
            username="ticket_creator",
            email="ticket_creator@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch,
        )
        self.agent = User.objects.create_user(
            username="ticket_agent",
            email="ticket_agent@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.department,
        )
        self.admin = User.objects.create_user(
            username="ticket_admin",
            email="ticket_admin@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            is_superuser=True,
            is_staff=True,
        )

    @patch("notifications.services._enqueue")
    @patch("notifications.services._broadcast_notification")
    def test_new_ticket_excludes_creator_and_lists_for_agent(self, _broadcast, _enqueue):
        ticket = Ticket.objects.create(
            title="Printer down",
            description="Cannot print",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.creator,
            client_name="Client",
            client_phone="0500000000",
        )
        InAppNotification.objects.filter(link=f"/tickets/{ticket.id}/").delete()

        notify_new_ticket(ticket)

        recipients = set(
            InAppNotification.objects.filter(link=f"/tickets/{ticket.id}/").values_list(
                "recipient_id", flat=True
            )
        )
        self.assertNotIn(self.creator.id, recipients)
        self.assertIn(self.agent.id, recipients)
        self.assertIn(self.admin.id, recipients)

        self.client.force_login(self.agent)
        response = self.client.get("/notifications/api/?limit=20")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        titles = [n["title"] for n in payload["notifications"]]
        self.assertTrue(any(t.startswith("New Ticket #") for t in titles))
        self.assertGreaterEqual(payload["unread_count"], 1)
