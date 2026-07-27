from django.test import TestCase
from django.conf import settings
from accounts.models import User
from core.models import Branch, Department, Category
from tickets.models import Ticket, TicketMessage


class UnpickedTicketNoticeTests(TestCase):
    def setUp(self):
        # Create Branch, Department, Category
        self.branch = Branch.objects.create(code="TEST", name="Test Branch")
        self.department = Department.objects.create(name="Test Department")
        self.category = Category.objects.create(
            department=self.department,
            name="Test Category",
            default_priority=Ticket.Priority.MEDIUM
        )

        # Create branch user
        self.branch_user = User.objects.create_user(
            username="branch_user",
            email="branch@test.com",
            password="testpassword123",
            user_type=User.UserType.BRANCH,
            branch=self.branch
        )

        # Create support user
        self.support_user = User.objects.create_user(
            username="support_user",
            email="support@test.com",
            password="testpassword123",
            user_type=User.UserType.SUPPORT,
            department=self.department
        )

        # Create unassigned ticket
        self.ticket = Ticket.objects.create(
            ticket_number="TK-1001",
            title="Need assistance",
            description="Trouble logging in.",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.branch_user,
            client_name="Test Client",
            client_phone="123456789"
        )

    def test_first_message_no_system_message(self):
        # When branch user sends first message, count is 1. No system message is expected.
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Hello? Anyone there?"
        )
        
        system_msgs = TicketMessage.objects.filter(ticket=self.ticket, is_system_message=True)
        self.assertEqual(system_msgs.count(), 0)

    def test_second_message_creates_system_message(self):
        # First message
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Hello? Anyone there?"
        )
        
        # Second message
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="I still need help."
        )

        # Verify that the system message was created
        system_msgs = TicketMessage.objects.filter(ticket=self.ticket, is_system_message=True)
        self.assertEqual(system_msgs.count(), 1)
        
        expected_text = getattr(settings, "TICKET_UNPICKED_SYSTEM_MESSAGE", "Someone will help you soon.")
        self.assertEqual(system_msgs.first().message, expected_text)

    def test_third_message_no_duplicate_system_message(self):
        # Send 3 messages
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Msg 1"
        )
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Msg 2"
        )
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Msg 3"
        )

        # Verify that ONLY ONE system message was created
        system_msgs = TicketMessage.objects.filter(ticket=self.ticket, is_system_message=True)
        self.assertEqual(system_msgs.count(), 1)

    def test_assigned_ticket_no_system_message(self):
        # Assign the ticket to support user
        self.ticket.assigned_to = self.support_user
        self.ticket.status = Ticket.Status.IN_PROGRESS
        self.ticket.save()

        # Send 2 messages from the branch user
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Msg 1"
        )
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.branch_user,
            message="Msg 2"
        )

        # Verify no system message was created since the ticket is assigned
        system_msgs = TicketMessage.objects.filter(ticket=self.ticket, is_system_message=True)
        self.assertEqual(system_msgs.count(), 0)

    def test_closed_ticket_creates_system_message(self):
        from tickets.models import TicketStatusHistory
        # Close the ticket
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.save()
        TicketStatusHistory.objects.create(
            ticket=self.ticket,
            status=Ticket.Status.CLOSED,
            event_type=TicketStatusHistory.EventType.STATUS_CHANGE,
            changed_by=self.support_user
        )

        # Verify that the closed system message was created
        system_msgs = TicketMessage.objects.filter(
            ticket=self.ticket, 
            is_system_message=True,
            message=f"Ticket closed by {self.support_user.username}"
        )
        self.assertEqual(system_msgs.count(), 1)

    def test_reopened_ticket_creates_system_message(self):
        from tickets.models import TicketStatusHistory
        # First close the ticket
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.save()
        TicketStatusHistory.objects.create(
            ticket=self.ticket,
            status=Ticket.Status.CLOSED,
            event_type=TicketStatusHistory.EventType.STATUS_CHANGE,
            changed_by=self.support_user
        )

        # Now reopen the ticket
        self.ticket.status = Ticket.Status.IN_PROGRESS
        self.ticket.save()
        TicketStatusHistory.objects.create(
            ticket=self.ticket,
            status=Ticket.Status.IN_PROGRESS,
            event_type=TicketStatusHistory.EventType.REOPENED,
            changed_by=self.branch_user
        )

        # Verify that the reopened system message was created
        system_msgs = TicketMessage.objects.filter(
            ticket=self.ticket, 
            is_system_message=True,
            message=f"Ticket reopened by {self.branch_user.username}"
        )
        self.assertEqual(system_msgs.count(), 1)


from django.urls import reverse
from core.models import Role

class TicketAuthorizationViewTests(TestCase):
    def setUp(self):
        # Create Branches
        self.branch_a = Branch.objects.create(code="BR-A", name="Branch A")
        self.branch_b = Branch.objects.create(code="BR-B", name="Branch B")

        # Create Departments
        self.dept_a = Department.objects.create(name="Dept A")
        self.dept_b = Department.objects.create(name="Dept B")

        # Create Categories
        self.category_a = Category.objects.create(
            department=self.dept_a,
            name="Category A",
            default_priority=Ticket.Priority.MEDIUM
        )
        self.category_b = Category.objects.create(
            department=self.dept_b,
            name="Category B",
            default_priority=Ticket.Priority.MEDIUM
        )

        # Create Role
        self.role_with_edit = Role.objects.create(
            name="Support Agent with Edit",
            can_update_ticket=True
        )

        # Create Users
        self.branch_user_a = User.objects.create_user(
            username="branch_user_a",
            email="branch_a@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_a
        )
        self.branch_user_b = User.objects.create_user(
            username="branch_user_b",
            email="branch_b@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_b
        )

        self.support_user_a = User.objects.create_user(
            username="support_user_a",
            email="support_a@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_a,
            role=self.role_with_edit
        )
        self.support_user_b = User.objects.create_user(
            username="support_user_b",
            email="support_b@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_b,
            role=self.role_with_edit
        )

        # Create Tickets
        self.ticket_a = Ticket.objects.create(
            ticket_number="TK-A",
            title="Ticket A",
            description="Branch A Ticket",
            branch=self.branch_a,
            department=self.dept_a,
            category=self.category_a,
            created_by=self.branch_user_a,
            client_name="Client A",
            client_phone="123456789"
        )
        self.ticket_b = Ticket.objects.create(
            ticket_number="TK-B",
            title="Ticket B",
            description="Branch B Ticket",
            branch=self.branch_b,
            department=self.dept_b,
            category=self.category_b,
            created_by=self.branch_user_b,
            client_name="Client B",
            client_phone="987654321"
        )

    def test_detail_view_branch_user_authorized(self):
        self.client.login(username="branch_user_a", password="password123")
        url = reverse("ticket_detail", kwargs={"ticket_id": self.ticket_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail_view_branch_user_unauthorized(self):
        self.client.login(username="branch_user_a", password="password123")
        url = reverse("ticket_detail", kwargs={"ticket_id": self.ticket_b.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_detail_view_support_user_authorized(self):
        self.client.login(username="support_user_a", password="password123")
        url = reverse("ticket_detail", kwargs={"ticket_id": self.ticket_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_detail_view_support_user_unauthorized(self):
        self.client.login(username="support_user_a", password="password123")
        url = reverse("ticket_detail", kwargs={"ticket_id": self.ticket_b.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_detail_view_nonexistent_ticket(self):
        self.client.login(username="branch_user_a", password="password123")
        url = reverse("ticket_detail", kwargs={"ticket_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_edit_view_support_user_authorized(self):
        self.client.login(username="support_user_a", password="password123")
        url = reverse("ticket_update", kwargs={"ticket_id": self.ticket_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_view_support_user_unauthorized(self):
        self.client.login(username="support_user_a", password="password123")
        url = reverse("ticket_update", kwargs={"ticket_id": self.ticket_b.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_edit_view_nonexistent_ticket(self):
        self.client.login(username="support_user_a", password="password123")
        url = reverse("ticket_update", kwargs={"ticket_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class TicketListSearchTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code="SRCH", name="Search Branch")
        self.department = Department.objects.create(name="Search Dept")
        self.category = Category.objects.create(
            department=self.department,
            name="VPN Issues",
            default_priority=Ticket.Priority.MEDIUM,
        )
        self.role = Role.objects.create(name="Search Support", can_create_ticket=True)
        self.support = User.objects.create_user(
            username="search_agent",
            email="search@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            department=self.department,
            role=self.role,
        )
        self.creator = User.objects.create_user(
            username="branch_creator",
            email="creator@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch,
        )
        self.by_title = Ticket.objects.create(
            ticket_number="TK-2001",
            title="Cannot reset password",
            description="Login page error",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.creator,
            client_name="Alice Smith",
            client_phone="555-0100",
        )
        self.by_client = Ticket.objects.create(
            ticket_number="TK-2002",
            title="Printer offline",
            description="Hardware issue",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.creator,
            assigned_to=self.support,
            client_name="Bob Jones",
            client_phone="555-0199",
        )
        self.by_category = Ticket.objects.create(
            ticket_number="TK-2003",
            title="Network dropouts",
            description="Intermittent wifi",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.creator,
            client_name="Carol",
            client_phone="555-0111",
        )
        self.client.login(username="search_agent", password="password123")

    def test_search_by_client_name(self):
        response = self.client.get(reverse("tickets_list"), {"q": "Alice"})
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertIn(self.by_title, tickets)
        self.assertNotIn(self.by_client, tickets)

    def test_search_by_phone_digits(self):
        response = self.client.get(reverse("tickets_list"), {"q": "5550199"})
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertIn(self.by_client, tickets)

    def test_search_by_assignee_username(self):
        response = self.client.get(reverse("tickets_list"), {"q": "search_agent"})
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertIn(self.by_client, tickets)
        self.assertNotIn(self.by_title, tickets)

    def test_multi_word_and_search(self):
        response = self.client.get(reverse("tickets_list"), {"q": "reset password"})
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertIn(self.by_title, tickets)
        self.assertNotIn(self.by_client, tickets)

    def test_relevance_ranks_ticket_number_first(self):
        response = self.client.get(reverse("tickets_list"), {"q": "TK-2001"})
        self.assertEqual(response.status_code, 200)
        tickets = list(response.context["tickets"])
        self.assertEqual(tickets[0], self.by_title)

    def test_htmx_partial_updates_load_more(self):
        response = self.client.get(
            reverse("tickets_list"),
            {"q": "Alice"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tickets/list_live_partial.html")
        self.assertTrue(response.context["is_htmx"])
        self.assertContains(response, self.by_title.ticket_number)


from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from core.models import Role
from kb.models import Article
from tickets.access import user_can_view_ticket, user_can_pick_ticket, user_can_reopen_ticket


class SecurityXSSAndUploadTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(code="XSS", name="XSS Branch")
        self.department = Department.objects.create(name="XSS Dept")
        self.category = Category.objects.create(
            department=self.department, name="XSS Cat", default_priority=Ticket.Priority.MEDIUM
        )
        self.role = Role.objects.create(name="XSS Branch Role", can_send_message=True)
        self.user = User.objects.create_user(
            username="xss_branch",
            email="xss@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch,
            role=self.role,
        )
        self.ticket = Ticket.objects.create(
            ticket_number="TK-XSS-1",
            title="XSS ticket",
            description="desc",
            branch=self.branch,
            department=self.department,
            category=self.category,
            created_by=self.user,
            client_name="Client",
            client_phone="123",
        )

    def test_message_html_escaped_in_detail(self):
        TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message='<img src=x onerror=alert(1)>',
        )
        self.client.login(username="xss_branch", password="password123")
        response = self.client.get(reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<img src=x onerror=alert(1)>")
        self.assertContains(response, "&lt;img src=x onerror=alert(1)&gt;")

    def test_reject_html_attachment(self):
        bad = SimpleUploadedFile("evil.html", b"<script>alert(1)</script>", content_type="text/html")
        with self.assertRaises(ValidationError):
            TicketMessage.objects.create(
                ticket=self.ticket,
                sender=self.user,
                message="",
                attachment=bad,
            )

    def test_reject_svg_attachment(self):
        bad = SimpleUploadedFile("evil.svg", b"<svg onload=alert(1)></svg>", content_type="image/svg+xml")
        with self.assertRaises(ValidationError):
            TicketMessage.objects.create(
                ticket=self.ticket,
                sender=self.user,
                message="",
                attachment=bad,
            )

    def test_accept_png_attachment(self):
        # Minimal 1x1 PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        good = SimpleUploadedFile("ok.png", png, content_type="image/png")
        msg = TicketMessage.objects.create(
            ticket=self.ticket,
            sender=self.user,
            message="with image",
            attachment=good,
        )
        self.assertTrue(msg.attachment.name.endswith(".png"))


class SecurityTenancyTests(TestCase):
    def setUp(self):
        self.branch_a = Branch.objects.create(code="BA", name="Branch A")
        self.branch_b = Branch.objects.create(code="BB", name="Branch B")
        self.dept_a = Department.objects.create(name="Dept A")
        self.dept_b = Department.objects.create(name="Dept B")
        self.cat_a = Category.objects.create(
            department=self.dept_a, name="Cat A", default_priority=Ticket.Priority.MEDIUM
        )
        self.role_kb = Role.objects.create(
            name="KB Viewer", can_access_kb=True, can_pick_ticket=True, can_send_message=True
        )
        self.role_no_kb = Role.objects.create(
            name="No KB", can_access_kb=False, can_pick_ticket=True, can_send_message=True
        )
        self.branch_user_b_kb = User.objects.create_user(
            username="branch_b_kb",
            email="bbkb@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_b,
            role=self.role_kb,
        )
        self.branch_user_b_nokk = User.objects.create_user(
            username="branch_b_nokb",
            email="bbnokb@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_b,
            role=self.role_no_kb,
        )
        self.support_a = User.objects.create_user(
            username="support_a_pick",
            email="sa@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_a,
            role=self.role_kb,
        )
        self.support_b = User.objects.create_user(
            username="support_b_pick",
            email="sb@test.com",
            password="password123",
            user_type=User.UserType.SUPPORT,
            department=self.dept_b,
            role=self.role_kb,
        )
        self.creator = User.objects.create_user(
            username="creator_a",
            email="ca@test.com",
            password="password123",
            user_type=User.UserType.BRANCH,
            branch=self.branch_a,
            role=self.role_no_kb,
        )
        self.ticket = Ticket.objects.create(
            ticket_number="TK-TEN-1",
            title="Tenancy ticket",
            description="desc",
            branch=self.branch_a,
            department=self.dept_a,
            category=self.cat_a,
            created_by=self.creator,
            status=Ticket.Status.OPEN,
            client_name="Client",
            client_phone="123",
        )
        self.article = Article.objects.create(
            title="Related article",
            content="<p>help</p>",
            is_published=True,
            related_ticket=self.ticket,
            created_by=self.support_a,
        )

    def test_kb_bypass_requires_can_access_kb(self):
        self.assertTrue(user_can_view_ticket(self.branch_user_b_kb, self.ticket))
        self.assertFalse(user_can_view_ticket(self.branch_user_b_nokk, self.ticket))

    def test_kb_bypass_http_allows_kb_user(self):
        self.client.login(username="branch_b_kb", password="password123")
        response = self.client.get(reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))
        self.assertEqual(response.status_code, 200)

    def test_kb_bypass_http_denies_non_kb_user(self):
        self.client.login(username="branch_b_nokb", password="password123")
        response = self.client.get(reverse("ticket_detail", kwargs={"ticket_id": self.ticket.id}))
        self.assertEqual(response.status_code, 403)

    def test_cross_dept_cannot_pick(self):
        self.assertFalse(user_can_pick_ticket(self.support_b, self.ticket))
        self.client.login(username="support_b_pick", password="password123")
        response = self.client.post(reverse("pick_ticket", kwargs={"ticket_id": self.ticket.id}))
        self.assertEqual(response.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assigned_to_id)

    def test_same_dept_can_pick(self):
        self.assertTrue(user_can_pick_ticket(self.support_a, self.ticket))
        self.client.login(username="support_a_pick", password="password123")
        response = self.client.post(reverse("pick_ticket", kwargs={"ticket_id": self.ticket.id}))
        self.assertIn(response.status_code, (200, 204, 302))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to_id, self.support_a.id)

    def test_cross_dept_cannot_reopen(self):
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.assigned_to = self.support_a
        self.ticket.save()
        self.assertFalse(user_can_reopen_ticket(self.support_b, self.ticket))
        self.client.login(username="support_b_pick", password="password123")
        response = self.client.post(
            reverse("update_status", kwargs={"ticket_id": self.ticket.id}),
            {"status": Ticket.Status.IN_PROGRESS},
        )
        self.assertEqual(response.status_code, 403)

    def test_same_dept_can_reopen(self):
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.assigned_to = self.support_a
        self.ticket.save()
        self.assertTrue(user_can_reopen_ticket(self.support_a, self.ticket))
        self.client.login(username="support_a_pick", password="password123")
        response = self.client.post(
            reverse("update_status", kwargs={"ticket_id": self.ticket.id}),
            {"status": Ticket.Status.IN_PROGRESS},
        )
        self.assertIn(response.status_code, (200, 204, 302))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.IN_PROGRESS)
