"""Build English + Arabic system chat messages at creation time.

English `message` stays the source of truth (tests, dedupe, WS status sniffing).
`message_ar` is optional display text — empty means fall back to English.
"""

from django.utils import translation
from django.utils.translation import gettext, gettext_noop

from tickets.models import TicketMessage

# Mark defaults for extraction. Runtime may use settings for the unpicked text.
gettext_noop("Someone will help you soon.")
gettext_noop("Ticket closed by %(username)s")
gettext_noop("Ticket reopened by %(username)s")
gettext_noop("Merged messages from ticket #%(number)s")
gettext_noop("Requested transfer to %(username)s")
gettext_noop("Accepted ticket transfer")
gettext_noop("Denied ticket transfer")
gettext_noop("Canceled ticket transfer to %(username)s")


def _format(msgid, params=None):
    params = params or {}
    if not msgid:
        return ""
    for candidate in (gettext(msgid), msgid):
        try:
            return candidate % params if params else candidate
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return msgid


def bilingual_system(msgid, params=None):
    """Return (english, arabic) for a system message msgid."""
    params = params or {}
    try:
        with translation.override("en"):
            english = _format(msgid, params)
        with translation.override("ar"):
            arabic = _format(msgid, params)
        return english, arabic or ""
    except Exception:
        try:
            english = msgid % params if params else msgid
        except Exception:
            english = str(msgid)
        return english, ""


def create_system_message(ticket, sender, msgid, params=None):
    """Create a system TicketMessage with English + Arabic copy."""
    english, arabic = bilingual_system(msgid, params)
    return TicketMessage.objects.create(
        ticket=ticket,
        sender=sender,
        message=english,
        message_ar=arabic,
        is_system_message=True,
    )
