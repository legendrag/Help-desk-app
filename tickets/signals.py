from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from tickets.models import Ticket, TicketMessage, TicketStatusHistory
from tickets.realtime import broadcast_ticket_message, broadcast_ticket_list_event
from notifications.services import notify_new_ticket, notify_ticket_update

logger = logging.getLogger(__name__)


def _mark_followup_message(ticket, message):
    """Set has_followup_message once a second message exists. Matches messages.count() > 1."""
    if ticket.has_followup_message:
        return
    prior = (
        TicketMessage.objects.filter(ticket_id=ticket.pk)
        .exclude(pk=message.pk)
        .exists()
    )
    if not prior:
        return
    Ticket.objects.filter(pk=ticket.pk, has_followup_message=False).update(has_followup_message=True)
    ticket.has_followup_message = True


def _maybe_unpicked_notice(instance):
    ticket = instance.ticket
    if instance.sender.user_type != "branch":
        return
    if ticket.assigned_to_id or ticket.unpicked_notice_sent:
        return
    if ticket.status in (Ticket.Status.CLOSED, Ticket.Status.MERGED):
        return
    prior_branch = (
        TicketMessage.objects.filter(
            ticket_id=ticket.pk,
            sender__user_type="branch",
            is_system_message=False,
        )
        .exclude(pk=instance.pk)
        .exists()
    )
    if not prior_branch:
        return
    message_text = getattr(
        settings,
        "TICKET_UNPICKED_SYSTEM_MESSAGE",
        "Someone will help you soon.",
    )
    updated = Ticket.objects.filter(pk=ticket.pk, unpicked_notice_sent=False).update(
        unpicked_notice_sent=True
    )
    if not updated:
        ticket.unpicked_notice_sent = True
        return
    ticket.unpicked_notice_sent = True
    from tickets.system_text import create_system_message

    try:
        create_system_message(ticket, ticket.created_by, message_text)
    except Exception:
        Ticket.objects.filter(pk=ticket.pk).update(unpicked_notice_sent=False)
        ticket.unpicked_notice_sent = False
        raise


@receiver(post_save, sender=TicketMessage)
def broadcast_new_message(sender, instance, created, **kwargs):
    if created:
        try:
            reply_to = instance.reply_to
            ticket = instance.ticket
            _mark_followup_message(ticket, instance)

            sender_username = getattr(instance.sender, "username", "Unknown")
            if instance.sender.user_type == "branch" and instance.sender.branch_id == ticket.branch_id and ticket.client_name:
                sender_username = f"{sender_username} - {ticket.client_name}"

            payload = {
                "id": instance.id,
                "ticket": instance.ticket_id,
                "sender": instance.sender_id,
                "sender_username": sender_username,
                "message": instance.message,
                "message_ar": getattr(instance, "message_ar", "") or "",
                "is_system_message": getattr(instance, "is_system_message", False),
                "attachment_url": instance.attachment.url if instance.attachment else None,
                "attachment_name": __import__("os").path.basename(instance.attachment.name) if instance.attachment else None,
                "created_at": instance.created_at.isoformat() if instance.created_at else None,
                "reply_to": {
                    "id": reply_to.id,
                    "message": reply_to.message,
                    "sender_username": getattr(reply_to.sender, "username", "Unknown"),
                    "created_at": reply_to.created_at.isoformat() if reply_to.created_at else None,
                } if reply_to else None,
            }
            broadcast_ticket_message(instance.ticket_id, payload)
            if not getattr(instance, "is_system_message", False):
                message_id = instance.id

                def _notify_after_commit():
                    try:
                        message = TicketMessage.objects.select_related("ticket", "sender").get(pk=message_id)
                    except TicketMessage.DoesNotExist:
                        return
                    notify_ticket_update(message.ticket, message.sender, message=message)

                transaction.on_commit(_notify_after_commit)
                _maybe_unpicked_notice(instance)
        except Exception:
            logger.exception("Error broadcasting message / notifying for TicketMessage %s", getattr(instance, "id", None))


@receiver(post_save, sender=Ticket)
def broadcast_ticket_change(sender, instance, created, **kwargs):
    try:
        event_type = "ticket_created" if created else "ticket_updated"
        payload = {
            "id": instance.id,
            "ticket_number": instance.ticket_number,
            "title": instance.title,
            "status": instance.status,
            "priority": instance.priority,
            "branch_name": getattr(instance.branch, "name", None) if instance.branch_id else None,
            "department_name": getattr(instance.department, "name", None) if instance.department_id else None,
            "category_name": getattr(instance.category, "name", None) if instance.category_id else None,
            "assigned_to": instance.assigned_to_id,
            "assigned_to_username": getattr(instance.assigned_to, "username", None) if instance.assigned_to_id else None,
            "created_at": instance.created_at.isoformat() if instance.created_at else None,
            "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
        }
        broadcast_ticket_list_event(event_type, payload, branch_id=instance.branch_id, department_id=instance.department_id)
        
        if created:
            notify_new_ticket(instance)
    except Exception:
        logger.exception("Error broadcasting ticket change / notifying for Ticket %s", getattr(instance, "id", None))


@receiver(post_delete, sender=Ticket)
def broadcast_ticket_deletion(sender, instance, **kwargs):
    try:
        payload = {"id": instance.id}
        broadcast_ticket_list_event("ticket_deleted", payload, branch_id=instance.branch_id, department_id=instance.department_id)
    except Exception:
        logger.exception("Error broadcasting ticket deletion for Ticket %s", getattr(instance, "id", None))


@receiver(post_save, sender=TicketStatusHistory)
def create_status_system_message(sender, instance, created, **kwargs):
    if created:
        try:
            from tickets.system_text import create_system_message

            ticket = instance.ticket
            user = instance.changed_by

            if instance.status == Ticket.Status.CLOSED:
                create_system_message(
                    ticket,
                    user,
                    "Ticket closed by %(username)s",
                    {"username": user.username},
                )
            elif instance.event_type == TicketStatusHistory.EventType.REOPENED:
                create_system_message(
                    ticket,
                    user,
                    "Ticket reopened by %(username)s",
                    {"username": user.username},
                )
        except Exception:
            logger.exception("Error creating status system message for history %s", getattr(instance, "id", None))


