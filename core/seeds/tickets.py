import random
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


BULK_TICKET_TEMPLATES = (
    ("Network connectivity issues in {location}", "Unable to connect to {resource}. Error: {error_type}.", "IT Support", "Network"),
    ("Password reset request for {user_type}", "User cannot access {system} and needs password reset.", "IT Support", "Access & Accounts"),
    ("Printer {issue_type} in {location}", "Printer {issue_detail}.", "IT Support", "Hardware"),
    ("Software installation request: {software}", "Need {software} installed for {purpose}.", "IT Support", "Software"),
    ("Leave request for {leave_type}", "Requesting {days} days off starting {date_ref}.", "Human Resources", "Leave Requests"),
    ("Payslip inquiry for {period}", "Cannot access payslip for {period}.", "Human Resources", "Payroll"),
    ("New hire setup for {name}", "Onboarding checklist for {name} joining {date_ref}.", "Human Resources", "Onboarding"),
    ("Maintenance needed: {issue}", "{issue} reported in {location}.", "Facilities", "Maintenance"),
    ("Office supplies request", "Need {supplies} for {location}.", "Facilities", "Office Supplies"),
    ("Cleaning service issue in {location}", "Cleaning {issue_detail} in {location}.", "Facilities", "Cleaning"),
    ("Invoice approval for {vendor}", "Invoice {invoice_number} pending approval.", "Finance", "Invoices"),
    ("Expense reimbursement request", "Reimbursement for {expense_type} totaling {amount}.", "Finance", "Expenses"),
    ("Budget request for {project}", "Need budget approval for {project}.", "Finance", "Budget Requests"),
)

TEMPLATE_VARS = {
    "location": ("meeting room A", "3rd floor", "2nd floor lobby", "main office", "north wing", "parking lot"),
    "resource": ("internal network", "Wi-Fi", "VPN", "file server", "email server"),
    "error_type": ("timeout", "connection refused", "DNS error", "authentication failed"),
    "user_type": ("new employee", "contractor", "department head", "team member"),
    "system": ("email", "CRM", "payroll portal", "intranet", "file share"),
    "issue_type": ("jam", "offline", "error", "maintenance"),
    "issue_detail": ("shows error code E-401", "not responding", "displays offline status", "has paper jam"),
    "software": ("Adobe Acrobat", "MS Project", "AutoCAD", "Zoom", "Slack"),
    "purpose": ("project work", "client presentations", "design tasks", "team collaboration"),
    "leave_type": ("annual leave", "sick leave", "personal day", "training"),
    "days": ("3", "5", "2", "1", "7"),
    "date_ref": ("next week", "next month", "this Friday", "mid-month"),
    "period": ("last month", "March", "Q1", "this quarter"),
    "name": ("Ahmed", "Fatima", "Ali", "Nour", "Hassan", "Layla"),
    "issue": ("HVAC malfunction", "door lock broken", "light fixture out", "water leak"),
    "supplies": ("printer paper", "toner cartridges", "pens and notebooks", "whiteboard markers"),
    "vendor": ("TechCorp", "OfficeMax", "CleanPro", "FacilityCo"),
    "invoice_number": ("INV-5501", "INV-5502", "INV-5503", "INV-5504"),
    "expense_type": ("travel", "training course", "client lunch", "office equipment"),
    "amount": ("$250", "$500", "$125", "$750"),
    "project": ("Q2 marketing campaign", "office renovation", "new software rollout", "team offsite"),
}


def _generate_bulk_ticket_spec(index, branches, departments_list):
    template = random.choice(BULK_TICKET_TEMPLATES)
    title_template, desc_template, department_name, category_name = template
    
    title = title_template
    description = desc_template
    for var_name, var_values in TEMPLATE_VARS.items():
        if "{" + var_name + "}" in title:
            title = title.replace("{" + var_name + "}", random.choice(var_values))
        if "{" + var_name + "}" in description:
            description = description.replace("{" + var_name + "}", random.choice(var_values))
    
    branch_code = random.choice(branches)
    status_choice = random.choices(
        [Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS, Ticket.Status.WAITING_FOR_BRANCH, Ticket.Status.CLOSED],
        weights=[40, 30, 15, 15],
        k=1
    )[0]
    
    priority_choice = random.choices(
        [Ticket.Priority.LOW, Ticket.Priority.MEDIUM, Ticket.Priority.HIGH, Ticket.Priority.URGENT],
        weights=[20, 50, 25, 5],
        k=1
    )[0]
    
    creator_choice = random.choice([
        "branch_main1", "branch_north1", "branch_south1"
    ])
    
    assignee_choice = None
    if status_choice in [Ticket.Status.IN_PROGRESS, Ticket.Status.WAITING_FOR_BRANCH, Ticket.Status.CLOSED]:
        assignee_choice = random.choice(["agent1", "agent2", "agent3", "lead1"])
    
    age_hours = random.randint(1, 240)
    
    has_messages = random.random() < 0.4
    messages = []
    if has_messages:
        messages.append((creator_choice, f"Additional detail for ticket #{index}."))
        if assignee_choice and random.random() < 0.6:
            messages.append((assignee_choice, random.choice([
                "Working on this now.",
                "Investigating the issue.",
                "Can you provide more details?",
                "This has been escalated.",
            ])))
    
    return {
        "key": f"bulk_{index}",
        "title": title,
        "description": description,
        "branch": branch_code,
        "department": department_name,
        "category": category_name,
        "priority": priority_choice,
        "status": status_choice,
        "creator": creator_choice,
        "assignee": assignee_choice,
        "client_name": random.choice(["Operations Team", "Staff", "Department Head", "Admin", "Support", "Client"]),
        "client_phone": f"+20111111{random.randint(1000, 9999)}",
        "messages": tuple(messages),
        "age_hours": age_hours,
    }


def seed_tickets(organization, users, ticket_count=None, stdout=None):
    tickets = {}
    
    for spec in TICKET_SPECS:
        tickets[spec["key"]] = _seed_one_ticket(spec, organization, users, stdout=stdout)
    
    if ticket_count and ticket_count > 0:
        if stdout:
            stdout.write(f"  Generating {ticket_count} additional tickets for performance testing...")
        
        branches = list(organization["branches"].keys())
        departments_list = list(organization["departments"].keys())
        
        for i in range(ticket_count):
            spec = _generate_bulk_ticket_spec(i, branches, departments_list)
            
            branch = organization["branches"][spec["branch"]]
            department = organization["departments"][spec["department"]]
            category = organization["categories"][(spec["department"], spec["category"])]
            creator = users[spec["creator"]]
            assignee = users.get(spec["assignee"]) if spec.get("assignee") else None
            
            now = timezone.now()
            created_at = now - timedelta(hours=spec.get("age_hours", 1))
            
            ticket = Ticket.objects.create(
                title=spec["title"],
                description=spec["description"],
                branch=branch,
                department=department,
                category=category,
                priority=spec["priority"],
                status=Ticket.Status.OPEN,
                created_by=creator,
                client_name=spec.get("client_name", ""),
                client_phone=spec.get("client_phone", ""),
            )
            
            Ticket.objects.filter(pk=ticket.pk).update(created_at=created_at, updated_at=created_at)
            ticket.refresh_from_db()
            
            _record_status(ticket, ticket.created_by, Ticket.Status.OPEN, detail="Ticket created")
            
            for username, text in spec.get("messages", ()):
                sender = users[username]
                message = TicketMessage.objects.create(ticket=ticket, sender=sender, message=text)
                msg_time = created_at + timedelta(minutes=15)
                TicketMessage.objects.filter(pk=message.pk).update(created_at=msg_time, updated_at=msg_time)
            
            target_status = spec["status"]
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
            stdout.write(f"  Created {ticket_count} bulk tickets.")
    
    return tickets
