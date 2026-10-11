from django import template
from django.utils.safestring import mark_safe

from shifts.clock import clock_html, clock_range_html, format_clock

register = template.Library()


@register.filter
def shifts_clock(value):
    return mark_safe(clock_html(value))


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
