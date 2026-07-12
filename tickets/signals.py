from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from tickets.models import Ticket, TicketMessage, TicketStatusHistory
from tickets.realtime import broadcast_ticket_message, broadcast_ticket_list_event
from notifications.services import notify_new_ticket, notify_ticket_update
@receiver(post_save, sender=TicketMessage)
def broadcast_new_message(sender, instance, created, **kwargs):
    if created:
        try:
            reply_to = instance.reply_to
            
            sender_username = getattr(instance.sender, "username", "Unknown")
            if instance.sender.user_type == "branch" and instance.sender.branch_id == instance.ticket.branch_id and instance.ticket.client_name:
                sender_username = f"{sender_username} - {instance.ticket.client_name}"
                
            payload = {
                "id": instance.id,
                "ticket": instance.ticket_id,
                "sender": instance.sender_id,
                "sender_username": sender_username,
                "message": instance.message,
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
            # Notify owner/assignee about the reply (exclude system messages)
            if not getattr(instance, "is_system_message", False):
                notify_ticket_update(instance.ticket, instance.sender, message=instance)

                # Check if the branch user sends more than one message on an unpicked ticket
                if instance.sender.user_type == "branch":
                    ticket = instance.ticket
                    if not ticket.assigned_to and ticket.status not in [Ticket.Status.CLOSED, Ticket.Status.MERGED]:
                        branch_msgs_count = TicketMessage.objects.filter(
                            ticket=ticket,
                            sender__user_type="branch",
                            is_system_message=False
                        ).count()

                        if branch_msgs_count > 1:
                            from django.conf import settings
                            message_text = getattr(settings, "TICKET_UNPICKED_SYSTEM_MESSAGE", "Someone will help you soon.")

                            already_sent = TicketMessage.objects.filter(
                                ticket=ticket,
                                is_system_message=True,
                                message=message_text
                            ).exists()

                            if not already_sent:
                                TicketMessage.objects.create(
                                    ticket=ticket,
                                    sender=ticket.created_by,
                                    message=message_text,
                                    is_system_message=True
                                )
        except Exception as e:
            print(f"[WS-DEBUG] Error broadcasting message: {e}")


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
    except Exception as e:
        print(f"[WS-DEBUG] Error broadcasting ticket change: {e}")


@receiver(post_delete, sender=Ticket)
def broadcast_ticket_deletion(sender, instance, **kwargs):
    try:
        payload = {"id": instance.id}
        broadcast_ticket_list_event("ticket_deleted", payload, branch_id=instance.branch_id, department_id=instance.department_id)
    except Exception as e:
        print(f"[WS-DEBUG] Error broadcasting ticket deletion: {e}")


@receiver(post_save, sender=TicketStatusHistory)
def create_status_system_message(sender, instance, created, **kwargs):
    if created:
        try:
            ticket = instance.ticket
            user = instance.changed_by

            if instance.status == Ticket.Status.CLOSED:
                message_text = f"Ticket closed by {user.username}"
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    message=message_text,
                    is_system_message=True
                )
            elif instance.event_type == TicketStatusHistory.EventType.REOPENED:
                message_text = f"Ticket reopened by {user.username}"
                TicketMessage.objects.create(
                    ticket=ticket,
                    sender=user,
                    message=message_text,
                    is_system_message=True
                )
        except Exception as e:
            print(f"[WS-DEBUG] Error creating status system message: {e}")


