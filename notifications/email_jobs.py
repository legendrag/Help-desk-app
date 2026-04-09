import logging

from django.utils import timezone

from accounts.models import User
from notifications.email_service import is_email_event_enabled, send_with_retries
from tickets.models import Ticket, TicketMessage

logger = logging.getLogger(__name__)


def _format_status_label(status):
    if not status:
        return None
    try:
        return Ticket.Status(status).label
    except Exception:
        return str(status).replace("_", " " ).title()




def _get_branch_recipients(ticket):
    branch_users = User.objects.filter(
        user_type=User.UserType.BRANCH,
        branch=ticket.branch,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")
    return list(
        branch_users.exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )

def _get_department_recipients(ticket):
    support_users = User.objects.filter(
        user_type=User.UserType.SUPPORT,
        department=ticket.department,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")
    return list(
        support_users.exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _add_owner_email(ticket, recipients):
    if ticket.created_by and ticket.created_by.email:
        recipients.append(ticket.created_by.email)
    return list(set(recipients))


def _format_ticket_summary(ticket):
    return (
        "Summary\n"
        "-------\n"
        f"Title: {ticket.title}\n"
        f"Description: {ticket.description}\n"
    )


def _format_ticket_details(ticket):
    requester = ticket.created_by
    requester_name = requester.get_full_name().strip() if requester else ""
    if not requester_name:
        requester_name = requester.username if requester else "N/A"
    requester_phone = requester.phone if requester and requester.phone else "N/A"
    branch_name = ticket.branch.name if ticket.branch_id else "N/A"
    department_name = ticket.department.name if ticket.department_id else "N/A"
    created_at = (
        timezone.localtime(ticket.created_at).strftime("%Y-%m-%d %H:%M")
        if ticket.created_at
        else "N/A"
    )
    return (
        "Ticket Details\n"
        "--------------\n"
        f"Ticket: {ticket.ticket_number}\n"
        f"Created At: {created_at}\n"
        f"Priority: {ticket.priority}\n"
        f"Department: {department_name}\n"
        f"Branch: {branch_name}\n"
        f"Requester: {requester_name}\n"
        f"Requester Phone: {requester_phone}\n"
    )


def send_new_ticket_email(ticket_id: int) -> bool:
    ticket = (
        Ticket.objects.select_related("department", "branch", "created_by")
        .filter(id=ticket_id)
        .first()
    )
    if not ticket:
        logger.warning("send_new_ticket_email: ticket %s not found", ticket_id)
        return False

    if not is_email_event_enabled("notify_new_ticket"):
        return False

    recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
    if not recipients:
        return False

    subject = f"[HelpDesk] New Ticket {ticket.ticket_number}"
    body = (
        "A new ticket has been created.\n\n"
        f"{_format_ticket_summary(ticket)}\n"
        f"{_format_ticket_details(ticket)}"
    )
    return send_with_retries(subject, body, recipients)


def send_ticket_picked_email(ticket_id: int, actor_id: int) -> bool:
    ticket = Ticket.objects.select_related("created_by", "department").filter(id=ticket_id).first()
    if not ticket:
        logger.warning("send_ticket_picked_email: ticket %s not found", ticket_id)
        return False

    actor = User.objects.filter(id=actor_id).first()
    if not actor:
        logger.warning("send_ticket_picked_email: actor %s not found", actor_id)
        return False

    if not is_email_event_enabled("notify_ticket_picked"):
        return False

    recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
    if not recipients:
        return False

    status_label = _format_status_label(ticket.status) or ticket.status
    subject = f"[HelpDesk] Ticket Picked {ticket.ticket_number}"
    body = (
        "Ticket pickup update.\n\n"
        f"Picked By: {actor.username}\n"
        f"Status: {status_label}\n\n"
        f"{_format_ticket_summary(ticket)}\n"
        f"{_format_ticket_details(ticket)}"
    )
    return send_with_retries(subject, body, recipients)


def send_ticket_update_email(
    ticket_id: int,
    actor_id: int,
    message_id: int | None = None,
    status_changed: bool = False,
    new_status: str | None = None,
) -> bool:
    ticket = (
        Ticket.objects.select_related("created_by", "assigned_to", "department", "branch")
        .filter(id=ticket_id)
        .first()
    )
    if not ticket:
        logger.warning("send_ticket_update_email: ticket %s not found", ticket_id)
        return False

    actor = User.objects.filter(id=actor_id).first()
    if not actor:
        logger.warning("send_ticket_update_email: actor %s not found", actor_id)
        return False

    if message_id:
        if not is_email_event_enabled("notify_ticket_message"):
            return False
        recipient = ticket.assigned_to if actor == ticket.created_by else ticket.created_by
        if not recipient or not recipient.email or recipient.is_superuser or (recipient.role and recipient.role.name.lower() == "admin"):
            return False
        recipients = [recipient.email]
    elif status_changed and new_status:
        if not is_email_event_enabled("notify_ticket_status"):
            return False
        recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
        if not recipients:
            return False
    else:
        if not is_email_event_enabled("notify_ticket_update"):
            return False
        recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
        if not recipients:
            return False

    if status_changed and new_status:
        status_label = _format_status_label(new_status) or new_status
    else:
        status_label = _format_status_label(ticket.status) or ticket.status

    subject = f"[HelpDesk] Update on Ticket {ticket.ticket_number}"
    if message_id:
        body_header = "New message on ticket.\n\n"
        actor_line = f"Message By: {actor.username}\n"
    elif status_changed and new_status:
        body_header = "Ticket status has been updated.\n\n"
        actor_line = f"Updated By: {actor.username}\n"
    else:
        body_header = "Ticket has been updated.\n\n"
        actor_line = f"Updated By: {actor.username}\n"

    body = (
        body_header
        + actor_line
        + f"Status: {status_label}\n\n"
        + f"{_format_ticket_summary(ticket)}\n"
        + f"{_format_ticket_details(ticket)}"
    )

    if message_id:
        message = TicketMessage.objects.filter(id=message_id).first()
        if message and message.message:
            body += (
                "\nMessage\n"
                "-------\n"
                f"{message.message[:200]}\n"
            )

    return send_with_retries(subject, body, recipients)
