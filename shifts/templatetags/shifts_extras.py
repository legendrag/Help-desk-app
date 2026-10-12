from django import template
from django.utils.dateformat import format as date_format
from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from shifts.clock import clock_html, clock_range_html, format_clock

register = template.Library()


@register.filter
def shifts_clock(value):
    return mark_safe(clock_html(value))


def _arabic():
    return (get_language() or "").startswith("ar")


# Django's short Arabic weekday names are spelled differently from the full ones
# (إثنين vs الاثنين), so Arabic always uses the full names; English keeps "Mon".

@register.filter
def shifts_weekday(value):
    """Mon / الاثنين"""
    if not value:
        return ""
    return date_format(value, "l" if _arabic() else "D")


@register.filter
def shifts_day(value):
    """Mon 12 Oct / الاثنين 12 أكتوبر"""
    if not value:
        return ""
    return date_format(value, "l j F" if _arabic() else "D j M")


@register.filter
def shifts_day_year(value):
    """Mon 12 Oct 2026 / الاثنين 12 أكتوبر 2026"""
    if not value:
        return ""
    return date_format(value, "l j F Y" if _arabic() else "D j M Y")


@register.filter
def shifts_long_date(value):
    """Monday, 12 October 2026 / الاثنين، 12 أكتوبر 2026 (Arabic comma)."""
    if not value:
        return ""
    comma = "، " if _arabic() else ", "
    return f"{date_format(value, 'l')}{comma}{date_format(value, 'j F Y')}"


@register.filter
def shifts_clock_text(value):
    """Plain 12-hour clock for attributes such as title, where markup would show as text."""
    return format_clock(value)


@register.simple_tag
def shifts_time_range(start, end):
    return mark_safe(clock_range_html(start, end))


@register.filter
def chip_ink(colour):
    """Pick ink that stays readable on a shift-type colour chip."""
    raw = (colour or "").strip().lstrip("#")
    if len(raw) != 6:
        return "shifts-chip--on-dark"
    try:
        red, green, blue = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return "shifts-chip--on-dark"
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    if luminance > 0.62:
        return "shifts-chip--on-light"
    return "shifts-chip--on-dark"
