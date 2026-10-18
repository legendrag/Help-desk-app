from django.utils.cache import add_never_cache_headers

_PWA_PATHS = frozenset({"/sw.js", "/manifest.webmanifest"})


class NoCacheAfterLogoutMiddleware:
    """
    Prevents the browser from serving cached authenticated pages
    after the user logs out.

    Sets Cache-Control: no-cache, no-store, must-revalidate on every
    response for authenticated users, so the browser's Back/Forward
    buttons always re-validate with the server.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path in _PWA_PATHS:
            return response

        if request.user.is_authenticated:
            add_never_cache_headers(response)

        return response


class HtmxMessagesMiddleware:
    """Show Django messages added during an HTMX request as toasts right away.

    A 204 or a partial swap has nowhere to render ``partials/messages.html``,
    so the message used to wait in the session and pop up on some later page.
    Messages the response already rendered are left alone.
    """

    TRIGGER = "flashMessages"
    RELOAD_TRIGGER = "reloadPage"
    _NAVIGATION_HEADERS = ("HX-Redirect", "HX-Location", "HX-Refresh")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.headers.get("HX-Request"):
            return response
        # A redirect or full navigation shows them on the page it lands on.
        if 300 <= response.status_code < 400 or any(h in response for h in self._NAVIGATION_HEADERS):
            return response
        # The page is about to reload (app-shell.js reloadPage); the reloaded
        # page shows them. A toast now would vanish with the old page.
        if self.RELOAD_TRIGGER in response.get("HX-Trigger", ""):
            return response
        storage = getattr(request, "_messages", None)
        if storage is None or storage.used:
            return response
        items = [
            {"message": str(message), "tags": message.tags, "sticky": message.level >= 40}
            for message in storage
        ]
        if items:
            self._add_trigger(response, items)
        return response

    def _add_trigger(self, response, items):
        import json

        existing = response.get("HX-Trigger", "").strip()
        if existing.startswith("{"):
            try:
                events = json.loads(existing)
            except ValueError:
                events = {}
        else:
            events = {name.strip(): "" for name in existing.split(",") if name.strip()}
        events[self.TRIGGER] = items
        response["HX-Trigger"] = json.dumps(events)
