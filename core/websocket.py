"""WebSocket origin check that still works when ALLOWED_HOSTS is "*"."""

from urllib.parse import urlsplit

from channels.security.websocket import WebsocketDenier
from django.conf import settings
from django.http.request import validate_host


def is_allowed_origin(origin: str, host: str) -> bool:
    """A page on this site: Origin names the host the socket was opened on.

    Channels' AllowedHostsOriginValidator lets every origin through when
    ALLOWED_HOSTS is "*" (the default here), so another site could open a
    socket that rides the user's session cookie. Hosts listed explicitly in
    ALLOWED_HOSTS are accepted too (e.g. a second name for the same server).
    """
    if not origin:
        return False  # browsers always send Origin on a WebSocket handshake
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    if host and parts.netloc.lower() == host.lower():
        return True
    explicit = [h for h in settings.ALLOWED_HOSTS if h != "*"]
    return bool(explicit) and validate_host(parts.hostname or "", explicit)


class SameOriginValidator:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        origin = headers.get(b"origin", b"").decode("latin1")
        host = headers.get(b"host", b"").decode("latin1")
        if is_allowed_origin(origin, host):
            return await self.application(scope, receive, send)
        return await WebsocketDenier()(scope, receive, send)
