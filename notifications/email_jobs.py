import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from news.models import Announcement
from notifications.email_content import render_notification_email, ticket_url
from notifications.email_service import is_email_event_enabled, send_with_retries
from notifications.email_templates import (
    announcement_merge_context,
    resolve_template,
    ticket_merge_context,
)
from notifications.utils import get_branch_users, get_department_users
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


def _send_template(
    event_type: str,
    recipients,
    context: dict,
    *,
    cta_url: str = "",
    footer_note: str | None = None,
) -> bool:
    if not recipients:
        return False
    subject, body, cta_label = resolve_template(event_type, context)
    kwargs = {
        "body": body,
        "cta_url": cta_url,
        "cta_label": cta_label,
        "brand_name": context.get("brand_name") or "mlamehticket",
    }
    if footer_note is not None:
        kwargs["footer_note"] = footer_note
    text_body, html_body = render_notification_email(**kwargs)
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
        recipients = [email for email in recipients if email != ticket.created_by.email]
    if not recipients:
        return False

    context = ticket_merge_context(ticket)
    return _send_template(
        "new_ticket",
        recipients,
        context,
        cta_url=ticket_url(ticket),
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

    context = ticket_merge_context(ticket, actor=actor)
    return _send_template(
        "ticket_picked",
        recipients,
        context,
        cta_url=ticket_url(ticket),
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
        message_text = message.message if message and message.message else ""

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

        context = ticket_merge_context(ticket, actor=actor, message=message_text)
        return _send_template(
            "ticket_message",
            recipients,
            context,
            cta_url=ticket_url(ticket),
        )

    if status_changed and new_status:
        if not is_email_event_enabled("notify_ticket_status"):
            return False
        recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
        if actor.email in recipients:
            recipients.remove(actor.email)
        if not recipients:
            return False
        context = ticket_merge_context(ticket, actor=actor, status=new_status)
        return _send_template(
            "ticket_status",
            recipients,
            context,
            cta_url=ticket_url(ticket),
        )

    if not is_email_event_enabled("notify_ticket_update"):
        return False
    recipients = list(set(_get_branch_recipients(ticket) + _get_department_recipients(ticket)))
    if actor.email in recipients:
        recipients.remove(actor.email)
    if not recipients:
        return False
    context = ticket_merge_context(ticket, actor=actor)
    return _send_template(
        "ticket_update",
        recipients,
        context,
        cta_url=ticket_url(ticket),
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

    event_map = {
        "requested": "transfer_requested",
        "accepted": "transfer_accepted",
        "denied": "transfer_denied",
    }
    event_type = event_map.get(event)
    if not event_type:
        logger.warning("send_transfer_event_email: unknown event %s", event)
        return False

    context = ticket_merge_context(ticket, actor=actor)
    return _send_template(
        event_type,
        [recipient_user.email],
        context,
        cta_url=ticket_url(ticket),
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

    context = announcement_merge_context(announcement)
    return _send_template(
        "announcement",
        recipients,
        context,
        cta_url=context.get("announcement_url") or "",
        footer_note="You’re receiving this because announcement email notifications are enabled.",
    )
