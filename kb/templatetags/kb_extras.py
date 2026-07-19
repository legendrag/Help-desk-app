import html
import math
import re

from django import template
from django.utils.html import escape, strip_tags
from django.utils.safestring import mark_safe

register = template.Library()

CATEGORY_ICONS = {
    "Getting Started": "book",
    "Troubleshooting": "wrench",
    "Policies & Procedures": "shield",
}


@register.filter
def read_time(content):
    # Decode entities and normalize non-breaking spaces
    cleaned = html.unescape(str(content or "")).replace('\xa0', ' ')
    text = strip_tags(cleaned)
    words = len(text.split())
    if not words:
        return "1 min read"
    minutes = max(1, math.ceil(words / 200))
    return f"{minutes} min read"


@register.filter
def highlight(text, search):
    if not text:
        return ""
    # Decode entities and normalize non-breaking spaces
    cleaned = html.unescape(str(text)).replace('\xa0', ' ')
    safe_text = escape(strip_tags(cleaned))
    if not search:
        return mark_safe(safe_text)

    terms = [t for t in search.split() if t.strip()]
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        safe_text = pattern.sub(
            lambda m: f'<mark class="kb-highlight">{m.group(0)}</mark>',
            safe_text,
        )
    return mark_safe(safe_text)


@register.inclusion_tag("kb/partials/category_icon.html")
def kb_category_icon(category):
    if not category:
        return {"icon": "document"}

    if hasattr(category, "icon") and category.icon and category.icon != "document":
        icon_name = category.icon
    elif hasattr(category, "name") and category.name in CATEGORY_ICONS:
        icon_name = CATEGORY_ICONS[category.name]
    elif hasattr(category, "icon"):
        icon_name = category.icon
    else:
        # Fallback if passed a string or unknown object
        icon_name = CATEGORY_ICONS.get(category, "document") if isinstance(category, str) else "document"

    return {
        "icon": icon_name,
    }
