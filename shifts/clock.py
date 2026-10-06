from django.utils.dateformat import time_format


def format_clock(value):
    """12-hour clock, localized AM/PM (ص/م in Arabic)."""
    if not value:
        return ""
    return time_format(value, "g:i A")
