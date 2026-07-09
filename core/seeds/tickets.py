from datetime import timedelta

from django.utils import timezone

from tickets.models import Ticket, TicketMessage, TicketStatusHistory


TICKET_SPECS = (
    {
        "key": "printer_main",
        "title": "Printer not responding on 3rd floor",
        "description": "The shared HP printer shows offline since this morning.",
        "branch": "MAIN",
        "department": "IT Support",
        "category": "Hardware",
        "priority": Ticket.Priority.MEDIUM,
        "status": Ticket.Status.OPEN,
        "creator": "branch_main1",
        "assignee": None,
        "client_name": "Reception Desk",
        "client_phone": "+201111111101",
        "messages": (
            ("branch_main1", "Printer display says 'Offline'. We restarted it twice."),
        ),
        "age_hours": 5,
    },
    {
        "key": "vpn_north",
        "title": "VPN disconnects every 10 minutes",
        "description": "Remote staff at North branch cannot stay connected to VPN.",
        "branch": "NORTH",
        "department": "IT Support",
        "category": "Network",
        "priority": Ticket.Priority.HIGH,
        "status": Ticket.Status.IN_PROGRESS,
        "creator": "branch_north1",
        "assignee": "agent1",
        "client_name": "North Sales Team",
        "client_phone": "+201111111102",
        "messages": (
            ("branch_north1", "VPN drops after login. Happens on Wi-Fi and wired."),
            ("agent1", "Checking VPN gateway logs. Can you confirm your client version?"),
            ("branch_north1", "Using version 5.2.1 on Windows 11."),
        ),
        "age_hours": 18,
    },
    {
        "key": "payroll_south",
        "title": "Payslip missing for March",
        "description": "Employee cannot download March payslip from the portal.",
        "branch": "SOUTH",
        "department": "Human Resources",
        "category": "Payroll",
        "priority": Ticket.Priority.MEDIUM,
        "status": Ticket.Status.WAITING_FOR_BRANCH,
        "creator": "branch_south1",
        "assignee": "agent2",
        "client_name": "Finance Team South",
        "client_phone": "+201111111103",
        "messages": (
            ("branch_south1", "March payslip is blank in the employee portal."),
            ("agent2", "Please send the employee ID and a screenshot of the error."),
        ),
        "age_hours": 30,
    },
    {
        "key": "ac_east",
        "title": "AC unit leaking in meeting room B",
        "description": "Water is dripping from the ceiling unit during meetings.",
        "branch": "EAST",
        "department": "Facilities",
        "category": "Maintenance",
        "priority": Ticket.Priority.HIGH,
        "status": Ticket.Status.IN_PROGRESS,
        "creator": "branch_main1",
        "assignee": "agent3",
        "client_name": "East Operations",
        "client_phone": "+201111111104",
        "messages": (
            ("branch_main1", "Leak started yesterday afternoon. Room is unusable."),
            ("agent3", "Facilities vendor scheduled for tomorrow 9 AM."),
        ),
        "age_hours": 26,
    },
    {
        "key": "email_closed",
        "title": "Cannot access shared mailbox",
        "description": "Support mailbox permissions were revoked after migration.",
        "branch": "MAIN",
        "department": "IT Support",
        "category": "Access & Accounts",
        "priority": Ticket.Priority.MEDIUM,
        "status": Ticket.Status.CLOSED,
        "creator": "branch_main1",
        "assignee": "agent1",
        "client_name": "Support Desk",
        "client_phone": "+201111111105",
        "messages": (
            ("branch_main1", "Team lost access to support@company mailbox."),
            ("agent1", "Restored permissions in Exchange admin center."),
            ("agent1", "Please confirm access is working on your side."),
            ("branch_main1", "Confirmed. All good now, thanks."),
        ),
        "age_hours": 72,
    },
    {
        "key": "invoice_closed",
        "title": "Vendor invoice approval stuck",
        "description": "Invoice #INV-4421 pending approval for over a week.",
        "branch": "SOUTH",
        "department": "Finance",
        "category": "Invoices",
        "priority": Ticket.Priority.LOW,
        "status": Ticket.Status.CLOSED,
        "creator": "branch_south1",
        "assignee": "lead1",
        "client_name": "Accounts Payable",
        "client_phone": "+201111111106",
        "messages": (
            ("branch_south1", "Invoice stuck in workflow since last Monday."),
            ("lead1", "Escalated to finance manager. Approval completed."),
            ("branch_south1", "Received confirmation. Closing ticket."),
        ),
        "age_hours": 96,
    },
    {
        "key": "software_main",
        "title": "CRM export fails with timeout",
        "description": "Exporting customer list from CRM times out after 60 seconds.",
        "branch": "MAIN",
        "department": "IT Support",
        "category": "Software",
        "priority": Ticket.Priority.MEDIUM,
        "status": Ticket.Status.OPEN,
        "creator": "branch_main1",
        "assignee": None,
        "client_name": "Sales Operations",
        "client_phone": "+201111111107",
        "messages": (
            ("branch_main1", "Export fails for lists over 500 records."),
        ),
        "age_hours": 8,
    },
    {
        "key": "leave_open",
        "title": "Annual leave balance incorrect",
        "description": "HR portal shows 5 days remaining but policy says 12.",
        "branch": "NORTH",
        "department": "Human Resources",
        "category": "Leave Requests",
        "priority": Ticket.Priority.LOW,
        "status": Ticket.Status.OPEN,
        "creator": "branch_north1",
        "assignee": None,
        "client_name": "HR Self-Service",
        "client_phone": "+201111111108",
        "messages": (
            ("branch_north1", "Balance updated incorrectly after promotion."),
        ),
        "age_hours": 12,
    },
)


def _record_status(ticket, user, status, event_type=TicketStatusHistory.EventType.STATUS_CHANGE, detail=""):
    TicketStatusHistory.objects.create(
        ticket=ticket,
        status=status,
        event_type=event_type,
        detail=detail,
        changed_by=user,
    )


def _seed_one_ticket(spec, organization, users, stdout=None):
    branch = organization["branches"][spec["branch"]]
    department = organization["departments"][spec["department"]]
    category = organization["categories"][(spec["department"], spec["category"])]
    creator = users[spec["creator"]]
    assignee = users.get(spec["assignee"]) if spec.get("assignee") else None
    target_status = spec["status"]
    now = timezone.now()
    created_at = now - timedelta(hours=spec.get("age_hours", 1))

    ticket, created = Ticket.objects.get_or_create(
        title=spec["title"],
        branch=branch,
        created_by=creator,
        defaults={
            "description": spec["description"],
            "department": department,
            "category": category,
            "priority": spec["priority"],
            "status": Ticket.Status.OPEN,
            "client_name": spec.get("client_name", ""),
            "client_phone": spec.get("client_phone", ""),
        },
    )

    if not created:
        ticket.description = spec["description"]
        ticket.department = department
        ticket.category = category
        ticket.priority = spec["priority"]
        ticket.client_name = spec.get("client_name", "")
        ticket.client_phone = spec.get("client_phone", "")
        ticket.status = Ticket.Status.OPEN
        ticket.assigned_to = None
        ticket.picked_at = None
        ticket.closed_at = None
        ticket.save()
        ticket.messages.all().delete()
        ticket.status_history.all().delete()

    Ticket.objects.filter(pk=ticket.pk).update(created_at=created_at, updated_at=created_at)
    ticket.refresh_from_db()

    _record_status(ticket, creator, Ticket.Status.OPEN, detail="Ticket created")

    message_offset = 0
    for username, text in spec.get("messages", ()):
        sender = users[username]
        msg_time = created_at + timedelta(minutes=15 + message_offset)
        message_offset += 20
        message = TicketMessage.objects.create(ticket=ticket, sender=sender, message=text)
        TicketMessage.objects.filter(pk=message.pk).update(created_at=msg_time, updated_at=msg_time)

    if assignee and target_status in {
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.WAITING_FOR_BRANCH,
        Ticket.Status.CLOSED,
    }:
        picked_at = created_at + timedelta(hours=1)
        ticket.assigned_to = assignee
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.picked_at = picked_at
        ticket.last_status_change_at = picked_at
        ticket.save()
        _record_status(
            ticket,
            assignee,
            Ticket.Status.IN_PROGRESS,
            event_type=TicketStatusHistory.EventType.ASSIGNED,
            detail=f"Assigned to {assignee.username}",
        )
        Ticket.objects.filter(pk=ticket.pk).update(picked_at=picked_at, last_status_change_at=picked_at)

    if target_status == Ticket.Status.WAITING_FOR_BRANCH and assignee:
        waiting_at = created_at + timedelta(hours=3)
        ticket.status = Ticket.Status.WAITING_FOR_BRANCH
        ticket.last_status_change_at = waiting_at
        ticket.save()
        _record_status(ticket, assignee, Ticket.Status.WAITING_FOR_BRANCH, detail="Awaiting branch response")
        Ticket.objects.filter(pk=ticket.pk).update(last_status_change_at=waiting_at)

    if target_status == Ticket.Status.CLOSED and assignee:
        closed_at = created_at + timedelta(hours=6)
        ticket.status = Ticket.Status.CLOSED
        ticket.closed_at = closed_at
        ticket.last_status_change_at = closed_at
        ticket.save()
        _record_status(ticket, assignee, Ticket.Status.CLOSED, detail="Issue resolved")
        Ticket.objects.filter(pk=ticket.pk).update(closed_at=closed_at, last_status_change_at=closed_at)

    if stdout:
        label = "created" if created else "updated"
        stdout.write(f"  Ticket {ticket.ticket_number} ({label}) — {ticket.status}")

    return ticket


def seed_tickets(organization, users, stdout=None):
    tickets = {}
    for spec in TICKET_SPECS:
        tickets[spec["key"]] = _seed_one_ticket(spec, organization, users, stdout=stdout)
    return tickets
