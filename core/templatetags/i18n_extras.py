from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter(name="gettext")
def gettext_filter(value):
    """Translate a string variable (e.g. model_name kept in English for comparisons)."""
    if value is None or value == "":
        return value
    return _(str(value))
