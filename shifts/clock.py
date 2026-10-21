from datetime import datetime

from django.utils import timezone
from django.utils.dateformat import time_format
from django.utils.html import format_html
from django.utils.translation import get_language


def format_clock(value):
    """12-hour clock, localized AM/PM (ص/م in Arabic).

    Aware datetimes are stored in UTC. Convert those to the active time zone
    before reading the hour. Plain ``datetime.time`` values (shift start/end
    and overrides) are already a wall clock and stay as they are.
    """
    if not value:
        return ""
    if isinstance(value, datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    return time_format(value, "g:i A")


def _arabic():
    return (get_language() or "").startswith("ar")


def clock_html(value):
    """One clock, isolated so the suffix stays with its number."""
    text = format_clock(value)
    if not text:
        return ""
    if _arabic():
        return format_html('<bdi dir="auto">{}</bdi>', text)
    return format_html('<bdi class="shifts-ltr" dir="ltr">{}</bdi>', text)


def clock_range_html(start, end):
    """English keeps one left-to-right range. Arabic isolates each time."""
    start_text = format_clock(start)
    end_text = format_clock(end)
    if _arabic():
        return format_html(
            '<bdi dir="auto">{}</bdi> – <bdi dir="auto">{}</bdi>',
            start_text,
            end_text,
        )
    return format_html(
        '<bdi class="shifts-ltr" dir="ltr">{}–{}</bdi>',
        start_text,
        end_text,
    )
