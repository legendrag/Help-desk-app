"""Render stored notifications into the language of whoever is reading them.

A notification is created inside the actor's request but read inside the
recipient's, and language is held in the reader's cookie rather than on the
user record. Translating at creation time would therefore stamp every
recipient with the actor's language, so notifications persist a msgid plus
its parameters and are turned into prose here, at read time.
"""

from django.utils.translation import gettext

from .utils import format_status_label

# Parameter values that are enum keys rather than free text, and so have to be
# looked up in the catalog instead of interpolated verbatim. Everything else
# (usernames, ticket titles, department names) is user data and passes through.
_ENUM_PARAMS = {"status"}

_INTERNAL_KEYS = ("title_key", "message_key", "params")


def _resolve_params(params):
    resolved = {}
    for key, value in (params or {}).items():
        if key in _ENUM_PARAMS and value:
            resolved[key] = format_status_label(value)
        else:
            resolved[key] = value
    return resolved


def interpolate(msgid, params):
    """Translate `msgid` and fill in `params`.

    Falls back to the untranslated source if a translation's placeholders have
    drifted from it, so a bad catalog entry degrades one line of text instead
    of breaking the whole notification feed.
    """
    # gettext("") returns the catalog's metadata header, so never let an empty
    # msgid reach it.
    if not msgid:
        return ""
    resolved = _resolve_params(params)
    for candidate in (gettext(msgid), msgid):
        try:
            return candidate % resolved
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return msgid


def _render(title_key, message_key, title, message, params):
    return (
        interpolate(title_key, params) if title_key else title,
        interpolate(message_key, params) if message_key else message,
    )


def render_notification(notification):
    """Return `(title, message)` for a stored notification, in the active language."""
    return _render(
        notification.title_key,
        notification.message_key,
        notification.title,
        notification.message,
        notification.params,
    )


def render_payload(payload):
    """Return a copy of a broadcast payload with its text in the active language.

    The msgid and parameters are dropped on the way out so the browser only
    ever receives finished text.
    """
    title, message = _render(
        payload.get("title_key", ""),
        payload.get("message_key", ""),
        payload.get("title", ""),
        payload.get("message", ""),
        payload.get("params"),
    )
    localized = {k: v for k, v in payload.items() if k not in _INTERNAL_KEYS}
    localized["title"] = title
    localized["message"] = message
    return localized
