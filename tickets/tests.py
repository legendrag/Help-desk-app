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

