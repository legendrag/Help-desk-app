from channels.generic.websocket import AsyncJsonWebsocketConsumer

ROTA_GROUP = "shifts_rota"  # notifications.services.ROTA_GROUP


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        session = self.scope.get("session")
        self.session_key = getattr(session, "session_key", None)
        self.group_name = f"user_{user.id}_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        # Staff pages with a rota grid reload it when a department changes.
        self.rota_group = ROTA_GROUP if getattr(user, "user_type", "") != "branch" else None
        if self.rota_group:
            await self.channel_layer.group_add(self.rota_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if getattr(self, "rota_group", None):
            await self.channel_layer.group_discard(self.rota_group, self.channel_name)

    async def rota_changed(self, event):
        await self.send_json({"kind": "rota_changed", "departments": event["departments"]})

    async def notification_event(self, event):
        await self.send_json(event["payload"])

    async def session_ended(self, event):
        # Sent on logout. Only the logged-out session's sockets close; the
        # user's other devices stay connected.
        if event.get("session_key") and event["session_key"] == self.session_key:
            await self.close(code=4401)
