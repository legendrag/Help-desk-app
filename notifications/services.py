import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from django.utils import timezone, translation
from django.utils.translation import gettext_noop

from accounts.models import User
from tickets.models import Ticket, TicketMessage
from .utils import get_branch_users, get_department_users
from .models import InAppNotification
from .rendering import interpolate
try:
    import webpush
except ImportError:
    webpush = None
from .email_jobs import (
    send_announcement_email,
    send_new_ticket_email,
    send_ticket_picked_email,
    send_ticket_update_email,
    send_transfer_event_email,
)
from .email_queue import enqueue_email

logger = logging.getLogger(__name__)


def _broadcast_notification(notification: InAppNotification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer configured; skipping notification broadcast.")
        return
    group_name = f"user_{notification.recipient.id}_notifications"
    # The msgid travels with the payload so the consumer can render it in the
    # recipient's language on delivery; title/message are the English fallback.
    payload = {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "title_key": notification.title_key,
        "message_key": notification.message_key,
        "params": notification.params,
        "link": notification.link,
        "notification_type": notification.notification_type,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notification.event",
                "payload": payload,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to broadcast notification %s to user %s: %s",
            notification.id,
            notification.recipient_id,
            exc,
        )





def _get_admin_users():
    return User.objects.filter(
        status=User.Status.ACTIVE,
    ).filter(Q(is_superuser=True) | Q(role__name__iexact="admin"))


def _unique_users(*querysets, extra_users=None):
    users = []
    seen = set()
    for qs in querysets:
        for user in qs:
            if user.id in seen:
                continue
            seen.add(user.id)
            users.append(user)
    if extra_users:
        for user in extra_users:
            if not user or user.id in seen:
                continue
            seen.add(user.id)
            users.append(user)
    return users


def _notify_users(
    users,
    link,
    title_key,
    message_key="",
    message_text="",
    params=None,
    notification_type="general",
    exclude_user=None,
):
    """Create and broadcast in-app notifications with deduplication.

    `title_key` and `message_key` are msgids rendered per reader. Pass
    `message_text` instead for author-written content such as an announcement
    body, which is data and must never go through the catalog.
    """
    params = params or {}
    # Deduplication and web push both need a concrete string, and neither has a
    # reader locale available, so store an English rendering beside the msgid.
    with translation.override("en"):
        title = interpolate(title_key, params)
        message = message_text or interpolate(message_key, params)

    dedup_window = timezone.now() - timedelta(seconds=60)
    exclude_id = getattr(exclude_user, "id", None) if exclude_user is not None else None
    for user in users:
        if exclude_id is not None and user.id == exclude_id:
            continue
        # Deduplication: skip if an identical notification was created in the last 60s
        if notification_type != "message" and InAppNotification.objects.filter(
            recipient=user,
            title=title,
            link=link,
            created_at__gte=dedup_window,
        ).exists():
            continue
        notification = InAppNotification.objects.create(
            recipient=user,
            title=title,
            message=message,
            title_key=title_key,
            message_key=message_key,
            params=params,
            link=link,
            notification_type=notification_type,
        )
        _broadcast_notification(notification)
        
        if webpush and getattr(webpush, "send_user_notification", None):
            try:
                import json
                payload = {
                    "title": title,
                    "head": title,
                    "body": message,
                    "message": message,
                    "icon": "/static/images/mlameh-icon-fg.png",
                    "data": {"url": link}
                }
                webpush.send_user_notification(user=user, payload=json.dumps(payload), ttl=1000)
            except Exception as e:
                logger.warning(f"Web push failed for user {user.id}: {e}")





def _enqueue(func, *args, **kwargs):
    try:
        enqueue_email(func, *args, max_attempts=1, retry_delay=2, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to enqueue email job: %s", exc)


def notify_new_ticket(ticket: Ticket):
    branch_users = get_branch_users(ticket)
    dept_users = get_department_users(ticket)
    admin_users = _get_admin_users()
    users = _unique_users(branch_users, dept_users, extra_users=admin_users)

    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=gettext_noop("New Ticket #%(number)s"),
        message_key=gettext_noop("A new ticket has been created for %(department)s: %(title)s"),
        params={
            "number": ticket.ticket_number,
            "department": ticket.department.name,
            "title": ticket.title,
        },
        notification_type="new_ticket",
        exclude_user=ticket.created_by,
    )

    # Email (async background queue)
    _enqueue(send_new_ticket_email, ticket.id)


def notify_ticket_picked(ticket: Ticket, actor: User):
    branch_users = get_branch_users(ticket)
    dept_users = get_department_users(ticket)
    admin_users = _get_admin_users()
    users = _unique_users(branch_users, dept_users, extra_users=admin_users)

    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=gettext_noop("Ticket Picked: #%(number)s"),
        message_key=gettext_noop("%(actor)s picked this ticket. Status is now %(status)s."),
        # The raw status key is stored so its label resolves per reader.
        params={
            "number": ticket.ticket_number,
            "actor": actor.username,
            "status": ticket.status,
        },
        notification_type="ticket_picked",
        exclude_user=actor,
    )

    # Email (async background queue)
    _enqueue(send_ticket_picked_email, ticket.id, actor.id)


def notify_ticket_update(
    ticket: Ticket,
    actor: User,
    message: TicketMessage | None = None,
    status_changed: bool = False,
    new_status: str | None = None,
):
    if message:
        # Guarantee fresh User instances for django-webpush related managers
        from accounts.models import User
        assigned_user = User.objects.filter(id=ticket.assigned_to_id).first() if ticket.assigned_to_id else None
        creator_user = User.objects.filter(id=ticket.created_by_id).first() if ticket.created_by_id else None
        
        if assigned_user:
            extra = [u for u in [creator_user, assigned_user] if u]
            users = _unique_users(_get_admin_users(), extra_users=extra)
        else:
            if ticket.messages.count() <= 1:
                branch_users = get_branch_users(ticket)
                dept_users = get_department_users(ticket)
                extra = [creator_user] if creator_user else []
                users = _unique_users(branch_users, dept_users, _get_admin_users(), extra_users=extra)
            else:
                extra = [creator_user] if creator_user else []
                users = _unique_users(_get_admin_users(), extra_users=extra)
        title_key = gettext_noop("New Reply: #%(number)s")
        message_key = gettext_noop("%(actor)s replied to the ticket.")
        params = {"number": ticket.ticket_number, "actor": actor.username}
        n_type = "message"
    elif status_changed and new_status:
        branch_users = get_branch_users(ticket)
        dept_users = get_department_users(ticket)
        admin_users = _get_admin_users()
        users = _unique_users(branch_users, dept_users, extra_users=admin_users)
        title_key = gettext_noop("Status Changed: #%(number)s")
        message_key = gettext_noop("%(actor)s updated the status to %(status)s.")
        params = {
            "number": ticket.ticket_number,
            "actor": actor.username,
            "status": new_status,
        }
        n_type = "status_change"
    else:
        branch_users = get_branch_users(ticket)
        dept_users = get_department_users(ticket)
        admin_users = _get_admin_users()
        users = _unique_users(branch_users, dept_users, extra_users=admin_users)
        title_key = gettext_noop("Ticket Updated: #%(number)s")
        message_key = gettext_noop("%(actor)s updated the ticket.")
        params = {"number": ticket.ticket_number, "actor": actor.username}
        n_type = "general"

    if not users:
        return

    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=title_key,
        message_key=message_key,
        params=params,
        notification_type=n_type,
        exclude_user=actor,
    )

    _enqueue(
        send_ticket_update_email,
        ticket.id,
        actor.id,
        message.id if message else None,
        status_changed,
        new_status,
        delay_seconds=120 if message else 0,
    )


def notify_transfer_requested(ticket: Ticket, actor: User, new_assignee: User):
    users = _unique_users([new_assignee])
    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=gettext_noop("Transfer Requested: #%(number)s"),
        message_key=gettext_noop("%(actor)s has requested to transfer this ticket to you."),
        params={"number": ticket.ticket_number, "actor": actor.username},
        notification_type="transfer",
        exclude_user=actor,
    )
    _enqueue(send_transfer_event_email, ticket.id, actor.id, new_assignee.id, "requested")


def notify_transfer_accepted(ticket: Ticket, actor: User, requester: User):
    users = _unique_users([requester])
    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=gettext_noop("Transfer Accepted: #%(number)s"),
        message_key=gettext_noop("%(actor)s accepted the ticket transfer."),
        params={"number": ticket.ticket_number, "actor": actor.username},
        notification_type="transfer",
        exclude_user=actor,
    )
    _enqueue(send_transfer_event_email, ticket.id, actor.id, requester.id, "accepted")


def notify_transfer_denied(ticket: Ticket, actor: User, requester: User):
    users = _unique_users([requester])
    _notify_users(
        users,
        link=f"/tickets/{ticket.id}/",
        title_key=gettext_noop("Transfer Denied: #%(number)s"),
        message_key=gettext_noop("%(actor)s denied the ticket transfer."),
        params={"number": ticket.ticket_number, "actor": actor.username},
        notification_type="transfer",
        exclude_user=actor,
    )
    _enqueue(send_transfer_event_email, ticket.id, actor.id, requester.id, "denied")


def notify_announcement_created(announcement, actor=None):
    """Push an in-app notification to users who can see this announcement."""
    if not announcement.is_active or announcement.is_expired:
        return

    actor = actor or announcement.created_by
    users_qs = User.objects.filter(status=User.Status.ACTIVE)

    # Mirror ticket-list banner visibility:
    # - no target branch → everyone active
    # - target branch → that branch's users + superusers (support agents do not see it)
    if announcement.target_branch_id:
        users_qs = users_qs.filter(
            Q(branch_id=announcement.target_branch_id) | Q(is_superuser=True)
        )

    content = (announcement.content or "").strip()
    if len(content) > 160:
        content = f"{content[:157]}..."

    _notify_users(
        list(users_qs),
        link="/tickets/",
        title_key=gettext_noop("Announcement: %(title)s"),
        # The body is author-written content, so it is stored verbatim; only the
        # stand-in for an empty announcement is translatable.
        message_text=content,
        message_key="" if content else gettext_noop("A new announcement has been posted."),
        params={"title": announcement.title},
        notification_type="announcement",
        exclude_user=actor,
    )

    _enqueue(
        send_announcement_email,
        announcement.id,
        actor.id if actor else None,
    )
