import logging
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from tickets.models import Ticket, TicketMessage
from .models import InAppNotification
from .text import bilingual as _bilingual
from django.utils.translation import gettext_noop
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


def bilingual(*args, **kwargs):
    """Never let translation failures block notification delivery."""
    try:
        return _bilingual(*args, **kwargs)
    except Exception:
        logger.exception("bilingual() failed; falling back to English-only copy")
        title_msgid = args[0] if args else kwargs.get("title_msgid", "")
        title_params = args[1] if len(args) > 1 else kwargs.get("title_params") or {}
        message_msgid = args[2] if len(args) > 2 else kwargs.get("message_msgid", "")
        message_params = args[3] if len(args) > 3 else kwargs.get("message_params")
        message_plain = kwargs.get("message_plain")
        status = kwargs.get("status")
        params = dict(title_params or {})
        if status is not None:
            from .utils import format_status_label
            params["status"] = format_status_label(status) or status
        try:
            title = title_msgid % params if title_msgid else ""
        except Exception:
            title = str(title_msgid)
        if message_plain is not None:
            message = message_plain
        else:
            mp = dict(message_params if message_params is not None else params)
            if status is not None and "status" not in mp:
                from .utils import format_status_label
                mp["status"] = format_status_label(status) or status
            try:
                message = message_msgid % mp if message_msgid else ""
            except Exception:
                message = str(message_msgid)
        return title, message, "", ""


def _broadcast_notification(notification: InAppNotification):
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer configured; skipping notification broadcast.")
        return
    group_name = f"user_{notification.recipient.id}_notifications"
    payload = {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "title_ar": notification.arabic_title(),
        "message_ar": notification.arabic_message(),
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





_NOTIFY_CHUNK = 500


def _admin_q():
    return Q(status=User.Status.ACTIVE) & (
        Q(is_superuser=True) | Q(role__name__iexact="admin")
    )


def _audience_users(ticket, *, include_org, extras=None):
    """Active admins, plus branch and department users when include_org is set. One query."""
    q = _admin_q()
    if include_org and ticket.branch_id:
        q = q | Q(
            user_type=User.UserType.BRANCH,
            branch_id=ticket.branch_id,
            status=User.Status.ACTIVE,
            is_superuser=False,
        )
    if include_org and ticket.department_id:
        q = q | Q(
            user_type=User.UserType.SUPPORT,
            department_id=ticket.department_id,
            status=User.Status.ACTIVE,
            is_superuser=False,
        )
    users = list(User.objects.filter(q).distinct())
    return _unique_users(extra_users=list(extras or []) + users)


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


def _enqueue_web_push(user, title, message, link):
    if not webpush or not getattr(webpush, "send_user_notification", None):
        return
    try:
        import json
        payload = {
            "title": title,
            "head": title,
            "body": message,
            "message": message,
            "icon": "/static/images/mlameh-icon-fg.png",
            "data": {"url": link},
        }
        _enqueue(
            webpush.send_user_notification,
            user=user,
            payload=json.dumps(payload),
            ttl=1000,
        )
    except Exception as exc:
        logger.warning("Web push failed for user %s: %s", getattr(user, "id", None), exc)


def _deliver_notification(notification):
    if not notification.pk:
        return
    _broadcast_notification(notification)
    _enqueue_web_push(
        notification.recipient,
        notification.title,
        notification.message,
        notification.link,
    )


def _notification_row(user, title, message, link, notification_type, title_ar, message_ar):
    now = timezone.now()
    return InAppNotification(
        recipient=user,
        title=title,
        message=message,
        title_ar=title_ar or "",
        message_ar=message_ar or "",
        params={
            "title_ar": title_ar or "",
            "message_ar": message_ar or "",
        },
        link=link,
        notification_type=notification_type,
        created_at=now,
    )


def _create_notification_rows(rows):
    """Insert rows in chunks. If a chunk fails, insert that chunk one row at a time."""
    created = []
    for start in range(0, len(rows), _NOTIFY_CHUNK):
        chunk = rows[start:start + _NOTIFY_CHUNK]
        try:
            with transaction.atomic():
                created.extend(InAppNotification.objects.bulk_create(chunk))
        except Exception:
            logger.exception("Bulk notification insert failed; falling back to per-user creates")
            for row in chunk:
                try:
                    with transaction.atomic():
                        created.append(
                            InAppNotification.objects.create(
                                recipient=row.recipient,
                                title=row.title,
                                message=row.message,
                                title_ar=row.title_ar,
                                message_ar=row.message_ar,
                                params=row.params,
                                link=row.link,
                                notification_type=row.notification_type,
                                created_at=row.created_at,
                            )
                        )
                except Exception:
                    logger.exception(
                        "Failed to create in-app notification for user %s (title=%r)",
                        getattr(row.recipient, "id", None),
                        row.title,
                    )
    return created


def _notify_users(
    users,
    title,
    message,
    link,
    notification_type="general",
    exclude_user=None,
    title_ar="",
    message_ar="",
):
    """Create and broadcast in-app notifications with deduplication.

    `title`/`message` are English and required for dedupe, web push, and fallback.
    `title_ar`/`message_ar` are optional; the panel falls back to English if empty.
    """
    dedup_window = timezone.now() - timedelta(seconds=60)
    exclude_id = getattr(exclude_user, "id", None) if exclude_user is not None else None
    recipients = []
    seen = set()
    for user in users:
        if not user or user.id in seen:
            continue
        if exclude_id is not None and user.id == exclude_id:
            continue
        seen.add(user.id)
        recipients.append(user)
    if not recipients:
        return

    skip = set()
    if notification_type != "message":
        skip = set(
            InAppNotification.objects.filter(
                recipient_id__in=[user.id for user in recipients],
                title=title,
                link=link,
                created_at__gte=dedup_window,
            ).values_list("recipient_id", flat=True)
        )

    rows = [
        _notification_row(user, title, message, link, notification_type, title_ar, message_ar)
        for user in recipients
        if user.id not in skip
    ]
    for notification in _create_notification_rows(rows):
        _deliver_notification(notification)





def _enqueue(func, *args, **kwargs):
    try:
        enqueue_email(func, *args, max_attempts=1, retry_delay=2, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to enqueue email job: %s", exc)


def notify_new_ticket(ticket: Ticket):
    users = _audience_users(ticket, include_org=True)

    params = {
        "number": ticket.ticket_number,
        "department": ticket.department.name,
        "title": ticket.title,
    }
    title, message, title_ar, message_ar = bilingual(
        gettext_noop("New Ticket #%(number)s"),
        params,
        gettext_noop("A new ticket has been created for %(department)s: %(title)s"),
        params,
    )
    _notify_users(
        users,
        title,
        message,
        f"/tickets/{ticket.id}/",
        notification_type="new_ticket",
        exclude_user=ticket.created_by,
        title_ar=title_ar,
        message_ar=message_ar,
    )

    # Email (async background queue)
    _enqueue(send_new_ticket_email, ticket.id)


def notify_ticket_picked(ticket: Ticket, actor: User):
    users = _audience_users(ticket, include_org=True)

    params = {
        "number": ticket.ticket_number,
        "actor": actor.username,
    }
    title, message, title_ar, message_ar = bilingual(
        gettext_noop("Ticket Picked: #%(number)s"),
        params,
        gettext_noop("%(actor)s picked this ticket. Status is now %(status)s."),
        params,
        status=ticket.status,
    )
    _notify_users(
        users,
        title,
        message,
        f"/tickets/{ticket.id}/",
        notification_type="ticket_picked",
        exclude_user=actor,
        title_ar=title_ar,
        message_ar=message_ar,
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
        extras = [user for user in (creator_user, assigned_user) if user]

        if assigned_user or ticket.has_followup_message:
            users = _audience_users(ticket, include_org=False, extras=extras)
        else:
            users = _audience_users(ticket, include_org=True, extras=extras)
        params = {"number": ticket.ticket_number, "actor": actor.username}
        title, message_text, title_ar, message_ar = bilingual(
            gettext_noop("New Reply: #%(number)s"),
            params,
            gettext_noop("%(actor)s replied to the ticket."),
            params,
        )
        n_type = "message"
    elif status_changed and new_status:
        users = _audience_users(ticket, include_org=True)
        params = {"number": ticket.ticket_number, "actor": actor.username}
        title, message_text, title_ar, message_ar = bilingual(
            gettext_noop("Status Changed: #%(number)s"),
            params,
            gettext_noop("%(actor)s updated the status to %(status)s."),
            params,
            status=new_status,
        )
        n_type = "status_change"
    else:
        users = _audience_users(ticket, include_org=True)
        params = {"number": ticket.ticket_number, "actor": actor.username}
        title, message_text, title_ar, message_ar = bilingual(
            gettext_noop("Ticket Updated: #%(number)s"),
            params,
            gettext_noop("%(actor)s updated the ticket."),
            params,
        )
        n_type = "general"

    if not users:
        return

    _notify_users(
        users,
        title,
        message_text,
        f"/tickets/{ticket.id}/",
        notification_type=n_type,
        exclude_user=actor,
        title_ar=title_ar,
        message_ar=message_ar,
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
    params = {"number": ticket.ticket_number, "actor": actor.username}
    title, message, title_ar, message_ar = bilingual(
        gettext_noop("Transfer Requested: #%(number)s"),
        params,
        gettext_noop("%(actor)s has requested to transfer this ticket to you."),
        params,
    )
    _notify_users(
        users,
        title,
        message,
        f"/tickets/{ticket.id}/",
        notification_type="transfer",
        exclude_user=actor,
        title_ar=title_ar,
        message_ar=message_ar,
    )
    _enqueue(send_transfer_event_email, ticket.id, actor.id, new_assignee.id, "requested")


def notify_transfer_accepted(ticket: Ticket, actor: User, requester: User):
    users = _unique_users([requester])
    params = {"number": ticket.ticket_number, "actor": actor.username}
    title, message, title_ar, message_ar = bilingual(
        gettext_noop("Transfer Accepted: #%(number)s"),
        params,
        gettext_noop("%(actor)s accepted the ticket transfer."),
        params,
    )
    _notify_users(
        users,
        title,
        message,
        f"/tickets/{ticket.id}/",
        notification_type="transfer",
        exclude_user=actor,
        title_ar=title_ar,
        message_ar=message_ar,
    )
    _enqueue(send_transfer_event_email, ticket.id, actor.id, requester.id, "accepted")


def notify_transfer_denied(ticket: Ticket, actor: User, requester: User):
    users = _unique_users([requester])
    params = {"number": ticket.ticket_number, "actor": actor.username}
    title, message, title_ar, message_ar = bilingual(
        gettext_noop("Transfer Denied: #%(number)s"),
        params,
        gettext_noop("%(actor)s denied the ticket transfer."),
        params,
    )
    _notify_users(
        users,
        title,
        message,
        f"/tickets/{ticket.id}/",
        notification_type="transfer",
        exclude_user=actor,
        title_ar=title_ar,
        message_ar=message_ar,
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

    title_params = {"title": announcement.title}
    if content:
        title, message, title_ar, message_ar = bilingual(
            gettext_noop("Announcement: %(title)s"),
            title_params,
            message_plain=content,
        )
    else:
        title, message, title_ar, message_ar = bilingual(
            gettext_noop("Announcement: %(title)s"),
            title_params,
            gettext_noop("A new announcement has been posted."),
            {},
        )

    chunk = []
    for user in users_qs.iterator(chunk_size=_NOTIFY_CHUNK):
        chunk.append(user)
        if len(chunk) >= _NOTIFY_CHUNK:
            _notify_users(
                chunk,
                title,
                message,
                "/tickets/",
                notification_type="announcement",
                exclude_user=actor,
                title_ar=title_ar,
                message_ar=message_ar,
            )
            chunk = []
    if chunk:
        _notify_users(
            chunk,
            title,
            message,
            "/tickets/",
            notification_type="announcement",
            exclude_user=actor,
            title_ar=title_ar,
            message_ar=message_ar,
        )

    _enqueue(
        send_announcement_email,
        announcement.id,
        actor.id if actor else None,
    )
