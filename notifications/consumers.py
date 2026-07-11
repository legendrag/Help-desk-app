from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.group_name = f"user_{user.id}_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        cache.set(f"ws_active_{self.user.id}_path", "online", timeout=3600)

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "user"):
            cache.delete(f"ws_active_{self.user.id}_path")

    async def receive_json(self, content):
        if content.get("type") == "page_view":
            path = content.get("path")
            if path and hasattr(self, "user"):
                cache.set(f"ws_active_{self.user.id}_path", path, timeout=3600)

    async def notification_event(self, event):
        await self.send_json(event["payload"])
