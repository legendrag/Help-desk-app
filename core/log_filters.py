import logging

from django.core.exceptions import PermissionDenied


class PermissionDeniedOneLine(logging.Filter):
    """Drop the traceback from "Forbidden (Permission denied)" records.

    Views raise PermissionDenied so Django renders the styled 403 page; that is
    an expected refusal, not an error, so one log line is enough.
    """

    def filter(self, record):
        exc = record.exc_info[1] if record.exc_info else None
        if isinstance(exc, PermissionDenied):
            record.exc_info = None
            record.exc_text = None
        return True
