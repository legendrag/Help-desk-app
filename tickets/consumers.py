from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from tickets.access import user_in_ticket_org
from tickets.models import Ticket, TicketMessage


class TicketChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.group_name = f"ticket_{self.ticket_id}"

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        # Strict org scope for live chat — no KB bypass (view-only cross-org via HTTP).
        allowed_ticket = await self._user_can_access_ticket(user.id, self.ticket_id)
        if not allowed_ticket:
            await self.close(code=4403)
            return

        await self._cache_sender(user.id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

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
        payload = await self._create_message(self.ticket_id, user.id, message_text, reply_to_id)
        if payload == "denied":
            await self.send_json({"error": "Permission denied."})
            return
        if not payload:
            await self.send_json({"error": "Cannot send message on this ticket."})
            return

    async def chat_event(self, event):
        await self.send_json({
            "event": event.get("event"),
            "payload": event.get("payload"),
        })

    @database_sync_to_async
    def _cache_sender(self, user_id):
        self._cache_sender_sync(user_id)

    def _permission_changed(self, role_id, is_superuser):
        return role_id != getattr(self, "sender_role_id", None) or bool(is_superuser) != bool(getattr(self, "sender_is_superuser", False))

    def _cache_sender_sync(self, user_id):
        from accounts.models import User

        user = User.objects.select_related("role").filter(pk=user_id).first()
        if not user:
            self.sender_role_id = None
            self.sender_is_superuser = False
            self.sender_can_send = False
            self.sender_user_type = ""
            self.sender_branch_id = None
            self.sender_department_id = None
            self.sender_username = ""
            return
        self.sender_role_id = user.role_id
        self.sender_is_superuser = user.is_superuser
        self.sender_can_send = bool(user.is_superuser or (user.role_id and user.role.can_send_message))
        self.sender_user_type = user.user_type
        self.sender_branch_id = user.branch_id
        self.sender_department_id = user.department_id
        self.sender_username = user.username

    def _cached_in_org(self, ticket):
        if self.sender_is_superuser:
            return True
        if self.sender_user_type == "branch":
            return bool(self.sender_branch_id) and ticket.branch_id == self.sender_branch_id
        if self.sender_user_type == "support":
            return bool(self.sender_department_id) and ticket.department_id == self.sender_department_id
        return False

    @database_sync_to_async
    def _user_can_access_ticket(self, user_id, ticket_id):
        from accounts.models import User

        try:
            user = User.objects.get(id=user_id)
            ticket = Ticket.objects.get(id=ticket_id)
        except (User.DoesNotExist, Ticket.DoesNotExist):
            return False

        return user_in_ticket_org(user, ticket)

    @database_sync_to_async
    def _create_message(self, ticket_id, user_id, message_text, reply_to_id=None):
        from accounts.models import User

        current = User.objects.filter(pk=user_id).values_list("role_id", "is_superuser").first()
        if current is None:
            return "denied"
        role_id, is_superuser = current
        if self._permission_changed(role_id, is_superuser):
            self._cache_sender_sync(user_id)
        if not self.sender_can_send:
            return "denied"

        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            return None

        if not self._cached_in_org(ticket):
            return None
        if self.sender_user_type == "support" and not self.sender_is_superuser and ticket.assigned_to_id != user_id:
            return None

        if ticket.status in [Ticket.Status.CLOSED, Ticket.Status.MERGED]:
            return None

        reply_to = None
        if reply_to_id:
            reply_to = TicketMessage.objects.filter(id=reply_to_id, ticket=ticket).first()
        message = TicketMessage.objects.create(
            ticket=ticket,
            sender_id=user_id,
            message=message_text,
            reply_to=reply_to,
        )
        return {
            "id": message.id,
            "ticket": ticket.id,
            "sender": user_id,
            "sender_username": self.sender_username,
            "message": message.message,
            "message_ar": getattr(message, "message_ar", "") or "",
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
