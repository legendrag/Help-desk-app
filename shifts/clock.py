from django.utils.dateformat import time_format
from django.utils.html import format_html
from django.utils.translation import get_language


def format_clock(value):
    """12-hour clock, localized AM/PM (ص/م in Arabic)."""
    if not value:
        return ""
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
