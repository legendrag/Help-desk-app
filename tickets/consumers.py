from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from tickets.models import Ticket, TicketMessage


class TicketChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.group_name = f"ticket_{self.ticket_id}"

        user = self.scope.get("user")
        print(f"[WS-DEBUG] Attempting connect: User {user} to group {self.group_name}")

        if not user or not user.is_authenticated:
            print("[WS-DEBUG] Connection rejected: Anonymous user")
            await self.close(code=4401)
            return

        # Removed granular ticket_messages_read check because it causes typing indicator issues

        allowed_ticket = await self._user_can_access_ticket(user.id, self.ticket_id)
        if not allowed_ticket:
            print(f"[WS-DEBUG] Connection rejected: User {user.id} cannot access ticket {self.ticket_id}")
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"[WS-DEBUG] Connection accepted: User {user.username} joined {self.group_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Handle typing indicator
        if content.get("type") == "typing":
            user = self.scope.get("user")
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "chat.event",
                    "event": "typing",
                    "payload": {
                        "sender": user.id,
                        "sender_username": user.username,
                    },
                },
            )
            return

        message_text = (content.get("message") or "").strip()
        reply_to_id = content.get("reply_to")
        if not message_text:
            await self.send_json({"error": "Message is required."})
            return

        user = self.scope.get("user")
        allowed = await self._user_can_send_message(user.id)
        if not allowed:
            await self.send_json({"error": "Permission denied."})
            return

        payload = await self._create_message(self.ticket_id, user.id, message_text, reply_to_id)
        if not payload:
            await self.send_json({"error": "Cannot send message on this ticket."})
            return

    async def chat_event(self, event):
        await self.send_json({
            "event": event.get("event"),
            "payload": event.get("payload"),
        })

    @database_sync_to_async
    def _user_can_send_message(self, user_id):
        from accounts.models import User

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return False

        if user.is_superuser:
            return True

        if not user.role_id:
            return False

        return bool(user.role.can_send_message)

    @database_sync_to_async
    def _user_can_access_ticket(self, user_id, ticket_id):
        from accounts.models import User

        try:
            user = User.objects.get(id=user_id)
            ticket = Ticket.objects.get(id=ticket_id)
        except (User.DoesNotExist, Ticket.DoesNotExist):
            return False

        if user.is_superuser:
            return True
        if user.user_type == "branch":
            return bool(user.branch_id) and ticket.branch_id == user.branch_id
        if user.user_type == "support":
            return bool(user.department_id) and ticket.department_id == user.department_id
        return False

    @database_sync_to_async
    def _create_message(self, ticket_id, user_id, message_text, reply_to_id=None):
        from accounts.models import User

        try:
            ticket = Ticket.objects.get(id=ticket_id)
            user = User.objects.get(id=user_id)
        except (Ticket.DoesNotExist, User.DoesNotExist):
            return None

        if user.is_superuser:
            pass
        elif user.user_type == "branch":
            if not user.branch_id or ticket.branch_id != user.branch_id:
                return None
        elif user.user_type == "support":
            if not user.department_id or ticket.department_id != user.department_id:
                return None
            if ticket.assigned_to_id != user.id:
                return None
        else:
            return None

        if ticket.status in [Ticket.Status.CLOSED, Ticket.Status.MERGED]:
            return None

        reply_to = None
        if reply_to_id:
            reply_to = TicketMessage.objects.filter(id=reply_to_id, ticket=ticket).first()
        message = TicketMessage.objects.create(ticket=ticket, sender=user, message=message_text, reply_to=reply_to)
        return {
            "id": message.id,
            "ticket": ticket.id,
            "sender": user.id,
            "sender_username": user.username,
            "message": message.message,
            "is_system_message": message.is_system_message,
            "attachment_url": None,
            "created_at": message.created_at.isoformat(),
            "updated_at": message.updated_at.isoformat(),
            "reply_to": {
                "id": reply_to.id,
                "message": reply_to.message,
                "sender_username": getattr(reply_to.sender, "username", "Unknown"),
                "created_at": reply_to.created_at.isoformat() if reply_to.created_at else None,
            } if reply_to else None,
        }


class TicketListConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        # Permission check removed to match TicketListView's access level.

        if user.is_superuser:
            self.group_name = "ticket_list"
        elif user.user_type == "branch":
            if not user.branch_id:
                await self.close(code=4403)
                return
            self.group_name = f"ticket_list_branch_{user.branch_id}"
        elif user.user_type == "support":
            if not user.department_id:
                await self.close(code=4403)
                return
            self.group_name = f"ticket_list_department_{user.department_id}"
        else:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def ticket_event(self, event):
        await self.send_json({
            "event": event.get("event"),
            "payload": event.get("payload"),
        })
