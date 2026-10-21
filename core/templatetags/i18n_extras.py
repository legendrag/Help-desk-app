from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter(name="gettext")
def gettext_filter(value):
    """Translate a string variable (e.g. model_name kept in English for comparisons)."""
    if value is None or value == "":
        return value
    return _(str(value))


@register.filter(name="day_month_year")
def day_month_year(value):
    """"Oct 17, 2026" in English, "17 أكتوبر، 2026" (Arabic comma) in Arabic."""
    from django.template.defaultfilters import date as date_filter
    from django.utils.translation import get_language

    if not value:
        return ""
    if (get_language() or "").startswith("ar"):
        return date_filter(value, "j F، Y")
    return date_filter(value, "M j, Y")
