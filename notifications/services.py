import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q

from accounts.models import User
from tickets.models import Ticket, TicketMessage
from .models import InAppNotification
from .email_jobs import (
    send_new_ticket_email,
    send_ticket_picked_email,
    send_ticket_update_email,
    send_ticket_transferred_email,
)
from .email_queue import enqueue_email

logger = logging.getLogger(__name__)
def _broadcast_notification(notification: InAppNotification):
    channel_layer = get_channel_layer()
    group_name = f"user_{notification.recipient.id}_notifications"
    payload = {
        "id": notification.id,
        "title": notification.title,
        "message": notification.message,
        "link": notification.link,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "notification.event",
            "payload": payload,
        }
    )




def _get_branch_users(ticket: Ticket):
    return User.objects.filter(
        user_type=User.UserType.BRANCH,
        branch=ticket.branch,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")


def _get_department_users(ticket: Ticket):
    return User.objects.filter(
        user_type=User.UserType.SUPPORT,
        department=ticket.department,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")


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


def _notify_users(users, title, message, link, exclude_user=None):
    for user in users:
        if exclude_user and user.id == exclude_user.id:
            continue
        notification = InAppNotification.objects.create(
            recipient=user,
            title=title,
            message=message,
            link=link,
        )
        _broadcast_notification(notification)

def _format_status_label(status):
    if not status:
        return None
    try:
        return Ticket.Status(status).label
    except Exception:
        return str(status).replace("_", " ").title()


def _enqueue(func, *args):
    try:
        enqueue_email(func, *args, max_attempts=1, retry_delay=2)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to enqueue email job: %s", exc)


def notify_new_ticket(ticket: Ticket):
    branch_users = _get_branch_users(ticket)
    dept_users = _get_department_users(ticket)
    admin_users = _get_admin_users()
    users = _unique_users(branch_users, dept_users, extra_users=admin_users)

    title = f"New Ticket #{ticket.ticket_number}"
    message = f"A new ticket has been created for {ticket.department.name}: {ticket.title}"
    _notify_users(users, title, message, f"/tickets/{ticket.id}")

    # Email (async background queue)
    _enqueue(send_new_ticket_email, ticket.id)


def notify_ticket_picked(ticket: Ticket, actor: User):
    branch_users = _get_branch_users(ticket)
    dept_users = _get_department_users(ticket)
    admin_users = _get_admin_users()
    users = _unique_users(branch_users, dept_users, extra_users=admin_users)

    status_label = _format_status_label(ticket.status) or ticket.status
    title = f"Ticket Picked: #{ticket.ticket_number}"
    message = f"{actor.username} picked this ticket. Status is now {status_label}."
    _notify_users(users, title, message, f"/tickets/{ticket.id}", exclude_user=actor)

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
        recipient = ticket.assigned_to if actor == ticket.created_by else ticket.created_by
        users = _unique_users(_get_admin_users(), extra_users=[recipient] if recipient else [])
        title = f"Ticket Updated: #{ticket.ticket_number}"
        message_text = f"{actor.username} replied to the ticket."
    elif status_changed and new_status:
        branch_users = _get_branch_users(ticket)
        dept_users = _get_department_users(ticket)
        admin_users = _get_admin_users()
        users = _unique_users(branch_users, dept_users, extra_users=admin_users)
        status_label = _format_status_label(new_status) or new_status
        title = f"Ticket Status Updated: #{ticket.ticket_number}"
        message_text = f"{actor.username} updated the status to {status_label}."
    else:
        branch_users = _get_branch_users(ticket)
        dept_users = _get_department_users(ticket)
        admin_users = _get_admin_users()
        users = _unique_users(branch_users, dept_users, extra_users=admin_users)
        title = f"Ticket Updated: #{ticket.ticket_number}"
        message_text = f"{actor.username} updated the ticket."

    if not users:
        return

    _notify_users(users, title, message_text, f"/tickets/{ticket.id}", exclude_user=actor)

    # Email (async background queue)
    _enqueue(
        send_ticket_update_email,
        ticket.id,
        actor.id,
        message.id if message else None,
        status_changed,
        new_status,
    )


def notify_ticket_transferred(ticket: Ticket, actor: User, new_assignee: User):
    branch_users = _get_branch_users(ticket)
    dept_users = _get_department_users(ticket)
    admin_users = list(_get_admin_users())
    users = _unique_users(branch_users, dept_users, extra_users=admin_users + [new_assignee])

    title = f"Ticket Transferred: #{ticket.ticket_number}"
    message = f"{actor.username} transferred this ticket to {new_assignee.username}."
    _notify_users(users, title, message, f"/tickets/{ticket.id}", exclude_user=actor)

    # Email (async background queue)
    _enqueue(send_ticket_transferred_email, ticket.id, actor.id, new_assignee.id)


