"""Session middleware with a narrow exception for idle ticket-list polls.

``SESSION_SAVE_EVERY_REQUEST`` rewrites the session on every request so the
3-day sliding expiry stays current. Ticket-list HTMX polls do that every 20
seconds even when the response is 304 and the session payload did not change.

Those polls still count as activity. This middleware keeps the sliding window,
but skips the write when all of the following are true:

- the view opted in (ticket-list 304 only)
- the session was not modified and is not empty
- the session uses the default cookie lifetime (no custom expiry)
- the last save is newer than ``TICKET_LIST_304_SESSION_REFRESH_SECONDS``

An open ticket list therefore renews the session at least once a minute.
Login, logout, password changes, and every other request still save as before.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils import timezone

# Polls are every 20s. One minute is long enough to skip most idle writes and
# short enough that an open ticket list cannot drift into an early logout on
# a multi-day session.
TICKET_LIST_304_SESSION_REFRESH_SECONDS = 60


class TicketListPollSessionMiddleware(SessionMiddleware):
    def process_response(self, request, response):
        if not self._should_defer_unmodified_save(request, response):
            return super().process_response(request, response)

        session = request.session
        original_save = session.save

        def save(must_create=False, *args, **kwargs):
            # A modified or brand-new session must still persist. The deferral
            # only drops the forced rewrite from SESSION_SAVE_EVERY_REQUEST.
            if must_create or session.modified:
                return original_save(must_create=must_create, *args, **kwargs)
            return None

        session.save = save
        response = super().process_response(request, response)
        if not session.modified and settings.SESSION_COOKIE_NAME in response.cookies:
            # Parent refreshed the browser cookie without moving expire_date.
            # Drop that Set-Cookie so the browser and the row stay aligned.
            del response.cookies[settings.SESSION_COOKIE_NAME]
        return response

    def _should_defer_unmodified_save(self, request, response):
        if getattr(response, "status_code", None) != 304:
            return False
        if not getattr(request, "ticket_list_304_defer_session_save", False):
            return False
        session = getattr(request, "session", None)
        if session is None:
            return False
        try:
            if session.modified or session.is_empty():
                return False
            # Custom expiry (including browser-close) is left on the normal
            # save path so we do not guess a different lifetime.
            if session.get("_session_expiry") is not None:
                return False
            if session.get_expire_at_browser_close():
                return False
        except AttributeError:
            return False
        return _sliding_expiry_is_fresh(session)


def _sliding_expiry_is_fresh(session):
    expire_at = getattr(session, "loaded_expire_date", None)
    if expire_at is None:
        return False
    if timezone.is_naive(expire_at):
        expire_at = timezone.make_aware(expire_at, timezone.get_current_timezone())
    expiry_age = session.get_expiry_age()
    try:
        expiry_age = int(expiry_age)
    except (TypeError, ValueError):
        return False
    if expiry_age <= 0:
        return False
    refresh_after = min(TICKET_LIST_304_SESSION_REFRESH_SECONDS, expiry_age)
    # The last save set expire_date to save_time + expiry_age.
    last_save_at = expire_at - timedelta(seconds=expiry_age)
    age = timezone.now() - last_save_at
    return age < timedelta(seconds=refresh_after)
