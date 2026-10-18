import json
from unittest.mock import PropertyMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.models import Branch, Category, Department, EmailSetting, EmailTemplate
from news.models import Announcement
from notifications.email_content import render_notification_email
from notifications.email_jobs import send_announcement_email, send_new_ticket_email
from notifications.email_templates import (
    ensure_email_templates,
    merge_fields_for_event,
    render_tokens,
    resolve_template,
    sample_context_for_event,
    ticket_merge_context,
)
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
        email_calls = [
            call
            for call in _enqueue.call_args_list
            if call.args and getattr(call.args[0], "__name__", "") == "send_announcement_email"
        ]
        self.assertEqual(len(email_calls), 1)

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

    def test_merge_fields_new_ticket_includes_name_and_phone_after_requester(self):
        keys = [key for key, _label in merge_fields_for_event("new_ticket")]
        self.assertIn("client_name", keys)
        self.assertIn("client_phone", keys)
        self.assertEqual(keys[keys.index("requester") + 1], "client_name")
        self.assertEqual(keys[keys.index("requester") + 2], "client_phone")

    def test_merge_fields_other_ticket_events_include_name_and_phone_after_title(self):
        for event_type in (
            "ticket_picked",
            "ticket_message",
            "ticket_status",
            "ticket_update",
            "transfer_requested",
            "transfer_accepted",
            "transfer_denied",
        ):
            keys = [key for key, _label in merge_fields_for_event(event_type)]
            self.assertIn("client_name", keys, event_type)
            self.assertIn("client_phone", keys, event_type)
            self.assertEqual(keys[keys.index("title") + 1], "client_name", event_type)
            self.assertEqual(keys[keys.index("title") + 2], "client_phone", event_type)

    def test_merge_fields_announcement_excludes_client_fields(self):
        keys = [key for key, _label in merge_fields_for_event("announcement")]
        self.assertNotIn("client_name", keys)
        self.assertNotIn("client_phone", keys)

    def test_ticket_merge_context_includes_client_name_and_phone(self):
        branch = Branch.objects.create(code="MF", name="Merge Branch")
        department = Department.objects.create(name="Merge Dept")
        category = Category.objects.create(department=department, name="Merge Cat")
        creator = User.objects.create_user(
            username="merge_creator",
            email="merge_creator@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=branch,
        )
        ticket = Ticket.objects.create(
            ticket_number="TK-MERGE-1",
            title="Lobby printer",
            description="Offline",
            branch=branch,
            department=department,
            category=category,
            created_by=creator,
            client_name="Reception Desk",
            client_phone="+201111111101",
        )
        ctx = ticket_merge_context(ticket)
        self.assertEqual(ctx["client_name"], "Reception Desk")
        self.assertEqual(ctx["client_phone"], "+201111111101")

    def test_ticket_merge_context_empty_client_fields_are_blank(self):
        branch = Branch.objects.create(code="MF2", name="Merge Branch 2")
        department = Department.objects.create(name="Merge Dept 2")
        category = Category.objects.create(department=department, name="Merge Cat 2")
        creator = User.objects.create_user(
            username="merge_creator2",
            email="merge_creator2@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=branch,
        )
        ticket = Ticket.objects.create(
            ticket_number="TK-MERGE-2",
            title="No contact",
            description="Missing contact",
            branch=branch,
            department=department,
            category=category,
            created_by=creator,
            client_name="Temp Name",
            client_phone="0500000000",
        )
        ticket.client_name = ""
        ticket.client_phone = ""
        ctx = ticket_merge_context(ticket)
        self.assertEqual(ctx["client_name"], "")
        self.assertEqual(ctx["client_phone"], "")
        rendered = render_tokens(
            "Name: {{ client_name }} Phone: {{ client_phone }}",
            ctx,
        )
        self.assertEqual(rendered, "Name:  Phone: ")

    def test_custom_template_resolves_client_name_and_phone(self):
        ensure_email_templates()
        EmailTemplate.objects.filter(event_type="new_ticket").update(
            subject="Call {{ client_name }}",
            body="Phone {{ client_phone }} for {{ title }}",
        )
        subject, body, _cta = resolve_template(
            "new_ticket",
            {
                "client_name": "Reception Desk",
                "client_phone": "+201111111101",
                "title": "Printer",
            },
        )
        self.assertEqual(subject, "Call Reception Desk")
        self.assertEqual(body, "Phone +201111111101 for Printer")

    def test_sample_context_includes_client_name_and_phone(self):
        sample = sample_context_for_event("new_ticket")
        self.assertEqual(sample["client_name"], "Reception Desk")
        self.assertEqual(sample["client_phone"], "+201111111101")

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


class EmailTemplateFormPartialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="email_admin",
            email="admin@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_htmx_partial_avoids_sandboxed_iframe_and_json_script(self):
        ensure_email_templates()
        response = self.client.get(
            "/core/email-templates/form/",
            {"email_type": "new_ticket"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn("<iframe", html)
        self.assertNotIn("sandbox=", html)
        self.assertNotIn('<script id="email-template-meta"', html)
        self.assertIn('<template id="email-template-meta">', html)
        self.assertIn('id="email-template-preview-frame"', html)
        meta_start = html.index('<template id="email-template-meta">') + len(
            '<template id="email-template-meta">'
        )
        meta_end = html.index("</template>", meta_start)
        meta = json.loads(html[meta_start:meta_end])
        self.assertEqual(meta["event_type"], "new_ticket")
        self.assertIn("sample", meta)


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

        row = InAppNotification.objects.filter(
            link=f"/tickets/{ticket.id}/", recipient=self.agent
        ).get()
        self.assertTrue(row.title.startswith("New Ticket #"))
        self.assertTrue(row.title_ar)  # Arabic parallel filled at create
        self.assertNotEqual(row.title, row.title_ar)

        self.client.force_login(self.agent)
        response = self.client.get("/notifications/api/?limit=20")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        match = next(n for n in payload["notifications"] if n["id"] == row.id)
        self.assertEqual(match["title"], row.title)
        self.assertEqual(match["title_ar"], row.title_ar)
        self.assertGreaterEqual(payload["unread_count"], 1)


class PushOffBannerMarkupTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code="POB", name="Push Off Branch")
        self.user = User.objects.create_user(
            username="push_off_user",
            email="push_off@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch,
        )

    def test_authenticated_page_includes_banner_and_modal(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tickets_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="push-off-banner"')
        self.assertContains(response, 'id="push-allow-modal"')
        self.assertContains(response, 'data-push-guide="site-settings"')
        self.assertContains(response, 'data-push-guide="app-settings"')
        self.assertContains(response, 'data-push-guide="install"')

    def test_login_page_omits_banner_and_modal(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="push-off-banner"')
        self.assertNotContains(response, 'id="push-allow-modal"')


class WebPushQueuedTests(TestCase):
    def test_web_push_is_queued_after_in_app_notification(self):
        user = User.objects.create_user(
            username="push_user",
            email="push@test.com",
            password="password123",
        )
        order = []
        sent = []

        def fake_enqueue(func, **kwargs):
            order.append("enqueue")
            self.assertTrue(
                InAppNotification.objects.filter(recipient=user, title="Hello").exists()
            )
            func(**kwargs)

        with (
            patch("notifications.services._broadcast_notification"),
            patch("notifications.services._enqueue", side_effect=fake_enqueue),
            patch("notifications.services.webpush") as wp,
        ):
            wp.send_user_notification = lambda **kwargs: sent.append(kwargs)
            from notifications.services import _notify_users

            _notify_users(
                [user],
                "Hello",
                "Body",
                "/tickets/1/",
                notification_type="new_ticket",
            )

        self.assertEqual(order, ["enqueue"])
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["user"], user)
        self.assertEqual(sent[0]["ttl"], 1000)
        self.assertIn("Hello", sent[0]["payload"])

    def test_web_push_still_queues_when_bulk_insert_cannot_return_ids(self):
        """Oracle MySQL bulk_create leaves pk empty, which used to skip push."""
        from django.db import connection

        user = User.objects.create_user(
            username="push_mysql_user",
            email="push-mysql@test.com",
            password="password123",
        )
        sent = []
        broadcasts = []

        def fake_enqueue(func, **kwargs):
            func(**kwargs)

        with (
            patch.object(
                type(connection.features),
                "can_return_rows_from_bulk_insert",
                new_callable=PropertyMock,
                return_value=False,
            ),
            patch(
                "notifications.services._broadcast_notification",
                side_effect=broadcasts.append,
            ),
            patch("notifications.services._enqueue", side_effect=fake_enqueue),
            patch("notifications.services.webpush") as wp,
        ):
            wp.send_user_notification = lambda **kwargs: sent.append(kwargs)
            from notifications.services import _notify_users

            _notify_users(
                [user],
                "Hello",
                "Body",
                "/tickets/1/",
                notification_type="new_ticket",
            )

        row = InAppNotification.objects.get(recipient=user, title="Hello")
        self.assertIsNotNone(row.pk)
        self.assertEqual(len(broadcasts), 1)
        self.assertEqual(broadcasts[0].pk, row.pk)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["user"], user)
        self.assertIn("Hello", sent[0]["payload"])


class NotificationDeliveryFixTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="fix_user", email="fix@test.com", password="pw123456")

    @patch("notifications.services._enqueue")
    @patch("notifications.services._broadcast_notification")
    def test_second_event_with_same_title_is_not_dropped(self, _broadcast, _enqueue):
        from notifications.services import _notify_users

        _notify_users([self.user], "Status Changed: #1", "a updated the status to Pending.", "/tickets/1/")
        _notify_users([self.user], "Status Changed: #1", "a updated the status to Closed.", "/tickets/1/")
        self.assertEqual(InAppNotification.objects.filter(recipient=self.user).count(), 2)
        # The exact same event firing twice is still collapsed.
        _notify_users([self.user], "Status Changed: #1", "a updated the status to Closed.", "/tickets/1/")
        self.assertEqual(InAppNotification.objects.filter(recipient=self.user).count(), 2)

    def test_bad_limit_does_not_500_and_is_capped(self):
        self.client.force_login(self.user)
        for raw in ("abc", "-1", "1e3", ""):
            response = self.client.get(f"/notifications/api/?limit={raw}")
            self.assertEqual(response.status_code, 200, raw)
        InAppNotification.objects.bulk_create(
            [InAppNotification(recipient=self.user, title=f"t{i}", message="m", link="/") for i in range(105)]
        )
        payload = self.client.get("/notifications/api/?limit=100000").json()
        self.assertEqual(len(payload["notifications"]), 100)
        self.assertTrue(payload["has_more"])
        older = self.client.get(f"/notifications/api/?before={payload['notifications'][-1]['id']}").json()
        self.assertEqual(len(older["notifications"]), 5)


class EmailSendingFixTests(TestCase):
    def setUp(self):
        self.setting = EmailSetting.objects.create(
            smtp_host="smtp.test.local", smtp_port=587, smtp_email="noreply@test.local",
            smtp_password="secret", encryption="tls", from_name="Test", from_email="noreply@test.local",
            is_active=True,
        )

    def test_each_recipient_gets_their_own_message(self):
        from django.core import mail
        from notifications.email_service import send_with_retries

        self.assertTrue(send_with_retries("Hello", "Body", ["a@test.com", "b@test.com", "a@test.com"]))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["a@test.com", "b@test.com"])
        self.assertTrue(all(len(m.to) == 1 for m in mail.outbox))

    def test_line_break_in_subject_still_sends(self):
        from django.core import mail
        from notifications.email_service import send_with_retries

        self.assertTrue(send_with_retries("Printer\r\ndown", "Body", ["a@test.com"]))
        self.assertEqual(mail.outbox[0].subject, "Printer down")

    def test_temporary_and_permanent_errors(self):
        import smtplib
        from notifications.email_service import _is_temporary

        self.assertTrue(_is_temporary(smtplib.SMTPResponseException(451, b"try later")))
        self.assertFalse(_is_temporary(smtplib.SMTPResponseException(554, b"rejected")))
        self.assertTrue(_is_temporary(ConnectionRefusedError()))
        self.assertTrue(_is_temporary(smtplib.SMTPServerDisconnected()))

    def test_plain_text_has_no_html_entities(self):
        text, _html = render_notification_email(body='Tom & Jerry said "hi"')
        self.assertIn('Tom & Jerry said "hi"', text)
        self.assertNotIn("&amp;", text)
        self.assertNotIn("&quot;", text)

    @patch("notifications.email_jobs.send_with_retries", return_value=True)
    def test_deactivated_user_gets_no_transfer_email(self, send):
        from notifications.email_jobs import send_transfer_event_email

        branch = Branch.objects.create(code="EF-BR", name="EF Branch")
        department = Department.objects.create(name="EF Dept")
        actor = User.objects.create_user(username="ef_actor", email="actor@test.com", password="pw123456",
                                         user_type=User.UserType.SUPPORT, department=department)
        gone = User.objects.create_user(username="ef_gone", email="gone@test.com", password="pw123456",
                                        user_type=User.UserType.SUPPORT, department=department,
                                        status=User.Status.INACTIVE)
        ticket = Ticket.objects.create(
            title="T", description="D", branch=branch, department=department,
            category=Category.objects.create(name="EF Cat", department=department),
            created_by=actor, client_name="C", client_phone="0500000000",
        )
        self.assertFalse(send_transfer_event_email(ticket.id, actor.id, gone.id, "requested"))
        send.assert_not_called()


class WebPushFixTests(TestCase):
    def test_endpoint_must_be_a_public_https_url(self):
        from notifications.apps import _is_public_push_endpoint

        self.assertTrue(_is_public_push_endpoint("https://fcm.googleapis.com/fcm/send/abc"))
        for bad in (
            "http://fcm.googleapis.com/x", "https://169.254.169.254/latest", "https://localhost/x",
            "https://10.0.0.5/x", "https://[::1]/x", "https://printer.local/x", "not a url",
        ):
            self.assertFalse(_is_public_push_endpoint(bad), bad)

    def _subscription(self, user):
        from webpush.models import PushInformation, SubscriptionInfo

        sub = SubscriptionInfo.objects.create(
            browser="chrome", endpoint="https://fcm.googleapis.com/fcm/send/x", auth="a", p256dh="p",
        )
        PushInformation.objects.create(user=user, subscription=sub)
        return sub

    def _push_error(self, status):
        from types import SimpleNamespace

        from pywebpush import WebPushException

        return WebPushException("failed", response=SimpleNamespace(status_code=status))

    def test_403_keeps_subscription_but_410_removes_it(self):
        import webpush
        from webpush.models import SubscriptionInfo

        user = User.objects.create_user(username="wp_user", password="pw123456")
        sub = self._subscription(user)
        with patch("notifications.apps._send_push", side_effect=self._push_error(403)):
            webpush.send_user_notification(user=user, payload="{}", ttl=0)
        self.assertTrue(SubscriptionInfo.objects.filter(pk=sub.pk).exists())
        with patch("notifications.apps._send_push", side_effect=self._push_error(410)):
            webpush.send_user_notification(user=user, payload="{}", ttl=0)
        self.assertFalse(SubscriptionInfo.objects.filter(pk=sub.pk).exists())

    def _save(self, extra=None):
        import json

        body = {
            "status_type": "subscribe", "browser": "chrome",
            "subscription": {"endpoint": "https://fcm.googleapis.com/fcm/send/shared",
                             "keys": {"auth": "a", "p256dh": "p"}},
            **(extra or {}),
        }
        return self.client.post(reverse("save_webpush_info"), json.dumps(body), content_type="application/json")

    def test_subscription_moves_to_the_user_who_registered_it_last(self):
        from webpush.models import PushInformation

        for name in ("wp_first", "wp_second"):
            self.client.force_login(User.objects.create_user(username=name, password="pw123456"))
            self.assertEqual(self._save().status_code, 201)
        owners = set(PushInformation.objects.values_list("user__username", flat=True))
        self.assertEqual(owners, {"wp_second"})

    def test_anonymous_group_subscription_is_refused(self):
        from webpush.models import PushInformation

        self._save({"group": "everyone"})
        self.assertFalse(PushInformation.objects.exists())


class HtmxMessagesMiddlewareTests(TestCase):
    def test_messages_from_an_htmx_204_become_a_toast_trigger(self):
        import json

        from django.contrib.messages import get_messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import HtmxMessagesMiddleware

        request = RequestFactory().post("/x", HTTP_HX_REQUEST="true")
        request.session = self.client.session
        request._messages = FallbackStorage(request)

        def view(req):
            from django.contrib import messages

            messages.success(req, "Ticket updated successfully.")
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "closeModal,refreshTickets"
            return response

        response = HtmxMessagesMiddleware(view)(request)
        events = json.loads(response["HX-Trigger"])
        self.assertIn("closeModal", events)
        self.assertIn("refreshTickets", events)
        self.assertEqual(events["flashMessages"][0]["message"], "Ticket updated successfully.")
        # Marked as shown, so MessageMiddleware won't keep it for a later page.
        self.assertTrue(get_messages(request).used)


class EmailTemplateFieldValidationTests(TestCase):
    def _form(self, body):
        from core.forms import EmailTemplateForm

        return EmailTemplateForm({"subject": "Hi {{ ticket_number }}", "body": body}, event_type="new_ticket")

    def test_known_fields_are_accepted(self):
        self.assertTrue(self._form("{{ requester }} wrote {{ description }}").is_valid())

    def test_broken_and_unknown_fields_are_refused(self):
        for body in ("Hello {{ requester", "Hello {{ requester.name }}", "Hello {{ nonsense }}"):
            self.assertFalse(self._form(body).is_valid(), body)


class WebPushLanguageTests(TestCase):
    @patch("notifications.services._broadcast_notification")
    def test_push_uses_the_recipients_language(self, _broadcast):
        from notifications.services import _notify_users

        arabic = User.objects.create_user(username="push_ar", password="pw123456", language="ar")
        english = User.objects.create_user(username="push_en", password="pw123456", language="en")
        pushed = {}
        with patch("notifications.services._enqueue_web_push",
                   side_effect=lambda user, title, message, link: pushed.__setitem__(user.username, title)):
            _notify_users([arabic, english], "Hello", "Body", "/x/", title_ar="مرحبا", message_ar="نص")
        self.assertEqual(pushed, {"push_ar": "مرحبا", "push_en": "Hello"})


@override_settings(EMAIL_QUEUE_SYNC=False)
class EmailQueueShutdownTests(TestCase):
    """A normal server stop sends what is queued or delayed instead of dropping it."""

    def tearDown(self):
        from notifications import email_queue

        email_queue._shutting_down = False

    def test_queued_and_delayed_jobs_are_sent_before_exit(self):
        import threading

        from notifications import email_queue

        sent = []
        lock = threading.Lock()

        def job(n):
            with lock:
                sent.append(n)

        with patch("notifications.email_queue.close_old_connections"):
            for n in range(10):
                email_queue.enqueue_email(job, n)
            # e.g. the 2-minute reply email, still waiting on its timer
            email_queue.enqueue_email(job, "delayed", delay_seconds=120)
            left = email_queue.drain_on_shutdown(timeout=10)

        self.assertEqual(left, 0)
        self.assertEqual(sorted(map(str, sent)), sorted([str(n) for n in range(10)] + ["delayed"]))
