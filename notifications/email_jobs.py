import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from news.models import Announcement
from notifications.email_content import (
    absolute_url,
    display_name,
    format_datetime,
    render_notification_email,
    ticket_details,
    ticket_url,
    truncate_text,
)
from notifications.email_service import is_email_event_enabled, send_with_retries
from notifications.utils import format_status_label, get_branch_users, get_department_users
from tickets.models import Ticket, TicketMessage

logger = logging.getLogger(__name__)


def _get_branch_recipients(ticket):
    branch_users = get_branch_users(ticket)
    return list(
        branch_users.exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _get_department_recipients(ticket):
    support_users = get_department_users(ticket)
    return list(
        support_users.exclude(email__isnull=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def _ticket_queryset():
    return Ticket.objects.select_related(
        "department", "branch", "category", "created_by", "assigned_to"
    )


def _send_rendered(subject, recipients, **email_kwargs) -> bool:
    if not recipients:
        return False
    text_body, html_body = render_notification_email(**email_kwargs)
    return send_with_retries(subject, text_body, recipients, html_body=html_body)


def send_new_ticket_email(ticket_id: int) -> bool:
    ticket = _ticket_queryset().filter(id=ticket_id).first()
    if not ticket:
        logger.warning("send_new_ticket_email: ticket %s not found", ticket_id)
        return False

    if not is_email_event_enabled("notify_new_ticket"):
        return False

    recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
    if ticket.created_by and ticket.created_by.email:
        # Branch/support recipients only — creator already knows they opened it.
        recipients = [email for email in recipients if email != ticket.created_by.email]
    if not recipients:
        return False

    title = truncate_text(ticket.title, 80)
    subject = f"[mlamehticket] New ticket #{ticket.ticket_number}: {title}"
    return _send_rendered(
        subject,
        recipients,
        headline=f"New ticket #{ticket.ticket_number}",
        intro=(
            f"{display_name(ticket.created_by)} submitted a new request"
            f"{f' for {ticket.department.name}' if ticket.department_id else ''}."
        ),
        details=ticket_details(ticket),
        message_title="Request",
        message_body=truncate_text(ticket.description, 800) or ticket.title,
        cta_url=ticket_url(ticket),
        cta_label="View ticket",
    )


def send_ticket_picked_email(ticket_id: int, actor_id: int) -> bool:
    ticket = _ticket_queryset().filter(id=ticket_id).first()
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
    if actor.email in recipients:
        recipients.remove(actor.email)
    if not recipients:
        return False

    status_label = format_status_label(ticket.status) or ticket.status
    subject = f"[mlamehticket] Ticket #{ticket.ticket_number} picked up"
    return _send_rendered(
        subject,
        recipients,
        headline=f"Ticket #{ticket.ticket_number} was picked up",
        intro=f"{display_name(actor)} is now handling this ticket. Status is {status_label}.",
        details=ticket_details(ticket),
        message_title="Request",
        message_body=truncate_text(ticket.description, 500) or ticket.title,
        cta_url=ticket_url(ticket),
        cta_label="Open ticket",
    )


def send_ticket_update_email(
    ticket_id: int,
    actor_id: int,
    message_id: int | None = None,
    status_changed: bool = False,
    new_status: str | None = None,
) -> bool:
    ticket = _ticket_queryset().filter(id=ticket_id).first()
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
        if (
            not recipient
            or not recipient.email
            or recipient.is_superuser
            or (recipient.role and recipient.role.name.lower() == "admin")
        ):
            return False
        recipients = [recipient.email]
        message = TicketMessage.objects.filter(id=message_id).first()
        message_text = truncate_text(message.message, 1000) if message and message.message else ""
        subject = f"[mlamehticket] New reply on #{ticket.ticket_number}"
        headline = f"New reply on #{ticket.ticket_number}"
        intro = f"{display_name(actor)} replied to the ticket."
        message_title = "Message"
        message_body = message_text

        from .models import InAppNotification

        read_emails = set(
            InAppNotification.objects.filter(
                recipient__email__in=recipients,
                link__in=[f"/tickets/{ticket.id}", f"/tickets/{ticket.id}/"],
                notification_type="message",
                is_read=True,
                created_at__gte=timezone.now() - timedelta(minutes=5),
            ).values_list("recipient__email", flat=True)
        )
        recipients = [r for r in recipients if r not in read_emails]
        if not recipients:
            return False
    elif status_changed and new_status:
        if not is_email_event_enabled("notify_ticket_status"):
            return False
        recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
        if actor.email in recipients:
            recipients.remove(actor.email)
        if not recipients:
            return False
        status_label = format_status_label(new_status) or new_status
        subject = f"[mlamehticket] Status update on #{ticket.ticket_number}: {status_label}"
        headline = f"Status changed on #{ticket.ticket_number}"
        intro = f"{display_name(actor)} updated the status to {status_label}."
        message_title = "Request"
        message_body = truncate_text(ticket.description, 500) or ticket.title
    else:
        if not is_email_event_enabled("notify_ticket_update"):
            return False
        recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
        if actor.email in recipients:
            recipients.remove(actor.email)
        if not recipients:
            return False
        status_label = format_status_label(ticket.status) or ticket.status
        subject = f"[mlamehticket] Update on ticket #{ticket.ticket_number}"
        headline = f"Ticket #{ticket.ticket_number} was updated"
        intro = f"{display_name(actor)} made an update to this ticket."
        message_title = "Request"
        message_body = truncate_text(ticket.description, 500) or ticket.title

    return _send_rendered(
        subject,
        recipients,
        headline=headline,
        intro=intro,
        details=ticket_details(ticket),
        message_title=message_title,
        message_body=message_body,
        cta_url=ticket_url(ticket),
        cta_label="Open ticket",
    )


def send_transfer_event_email(ticket_id: int, actor_id: int, recipient_id: int, event: str) -> bool:
    """Email the transfer counterparty for request / accept / deny events."""
    ticket = _ticket_queryset().filter(id=ticket_id).first()
    if not ticket:
        logger.warning("send_transfer_event_email: ticket %s not found", ticket_id)
        return False

    actor = User.objects.filter(id=actor_id).first()
    recipient_user = User.objects.filter(id=recipient_id).first()
    if not actor or not recipient_user:
        logger.warning("send_transfer_event_email: actor or recipient not found")
        return False

    if not is_email_event_enabled("notify_ticket_update"):
        return False

    if not recipient_user.email:
        return False

    event_copy = {
        "requested": (
            f"[mlamehticket] Transfer requested: #{ticket.ticket_number}",
            f"Transfer requested for #{ticket.ticket_number}",
            f"{display_name(actor)} wants to transfer this ticket to you.",
        ),
        "accepted": (
            f"[mlamehticket] Transfer accepted: #{ticket.ticket_number}",
            f"Transfer accepted for #{ticket.ticket_number}",
            f"{display_name(actor)} accepted the ticket transfer.",
        ),
        "denied": (
            f"[mlamehticket] Transfer declined: #{ticket.ticket_number}",
            f"Transfer declined for #{ticket.ticket_number}",
            f"{display_name(actor)} declined the ticket transfer.",
        ),
    }
    if event not in event_copy:
        logger.warning("send_transfer_event_email: unknown event %s", event)
        return False

    subject, headline, intro = event_copy[event]
    return _send_rendered(
        subject,
        [recipient_user.email],
        headline=headline,
        intro=intro,
        details=ticket_details(ticket),
        message_title="Request",
        message_body=truncate_text(ticket.description, 500) or ticket.title,
        cta_url=ticket_url(ticket),
        cta_label="Open ticket",
    )


def send_announcement_email(announcement_id: int, actor_id: int | None = None) -> bool:
    announcement = (
        Announcement.objects.select_related("target_branch", "created_by")
        .filter(id=announcement_id)
        .first()
    )
    if not announcement:
        logger.warning("send_announcement_email: announcement %s not found", announcement_id)
        return False

    if not announcement.is_active or announcement.is_expired:
        return False

    if not is_email_event_enabled("notify_announcement"):
        return False

    users_qs = User.objects.filter(status=User.Status.ACTIVE).exclude(
        Q(email__isnull=True) | Q(email="")
    )
    if announcement.target_branch_id:
        users_qs = users_qs.filter(
            Q(branch_id=announcement.target_branch_id) | Q(is_superuser=True)
        )
    if actor_id:
        users_qs = users_qs.exclude(id=actor_id)

    recipients = list(users_qs.values_list("email", flat=True).distinct())
    if not recipients:
        return False

    details = []
    if announcement.target_branch_id:
        details.append(("Audience", f"{announcement.target_branch.name} branch"))
    else:
        details.append(("Audience", "All users"))
    if announcement.expires_at:
        details.append(("Expires", format_datetime(announcement.expires_at)))
    if announcement.created_by_id:
        details.append(("Posted by", display_name(announcement.created_by)))
    details.append(("Posted", format_datetime(announcement.created_at)))

    title = truncate_text(announcement.title, 80)
    subject = f"[mlamehticket] Announcement: {title}"
    return _send_rendered(
        subject,
        recipients,
        headline=announcement.title,
        intro="A new announcement has been posted in mlamehticket.",
        details=details,
        message_title="Announcement",
        message_body=truncate_text(announcement.content, 1500) or announcement.title,
        cta_url=absolute_url("/tickets/"),
        cta_label="View announcements",
        footer_note="You’re receiving this because announcement email notifications are enabled.",
    )
