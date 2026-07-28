from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache
from django.utils import translation
from django.utils.translation import get_supported_language_variant

from .rendering import render_payload

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f"user_{user.id}_notifications"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    def _reader_language(self):
        """The language of the user on the other end of this connection.

        A notification is broadcast from the actor's request, so the sender's
        language says nothing about the reader's. This connection belongs to the
        recipient, which makes their language cookie the authoritative source.
        """
        requested = (self.scope.get("cookies") or {}).get(settings.LANGUAGE_COOKIE_NAME)
        if requested:
            try:
                return get_supported_language_variant(requested)
            except LookupError:
                pass
        return settings.LANGUAGE_CODE

    async def notification_event(self, event):
        with translation.override(self._reader_language()):
            payload = render_payload(event["payload"])
        await self.send_json(payload)
