"""Build English + Arabic notification copy at creation time.

English title/message remain the source of truth for dedupe, web push, and
fallback. Arabic is a parallel finished string — never rendered in the
WebSocket consumer or required for the panel to work.
"""

from django.utils import translation
from django.utils.translation import gettext

from .utils import format_status_label


def _format(msgid, params):
    if not msgid:
        return ""
    params = params or {}
    for candidate in (gettext(msgid), msgid):
        try:
            return candidate % params
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return msgid


def bilingual(
    title_msgid,
    title_params,
    message_msgid="",
    message_params=None,
    *,
    message_plain=None,
    status=None,
):
    """Return (title, message, title_ar, message_ar).

    `message_plain` is author-written content (e.g. announcement body) and is
    stored identically in both languages. When `status` is set, it is resolved
    to a translated label inside each language override.
    """
    title_params = dict(title_params or {})
    message_params = dict(message_params if message_params is not None else title_params)

    def _params(base):
        out = dict(base)
        if status is not None:
            out["status"] = format_status_label(status) or status
        return out

    with translation.override("en"):
        title = _format(title_msgid, _params(title_params))
        if message_plain is not None:
            message = message_plain
        else:
            message = _format(message_msgid, _params(message_params))

    with translation.override("ar"):
        title_ar = _format(title_msgid, _params(title_params))
        if message_plain is not None:
            message_ar = message_plain
        else:
            message_ar = _format(message_msgid, _params(message_params))

    # If Arabic rendering somehow fails empty, leave blank so callers fall back
    # to English rather than showing a broken string.
    if not title_ar:
        title_ar = ""
    if not message_ar and message_plain is None:
        message_ar = ""

    return title, message, title_ar, message_ar
