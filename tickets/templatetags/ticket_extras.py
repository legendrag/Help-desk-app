import math
from django import template

register = template.Library()


@register.filter
def human_duration(seconds):
    if seconds is None:
        return "N/A"
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return "N/A"

    if seconds < 0:
        seconds = 0

    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"

    hours = math.ceil(minutes / 60)
    if hours < 24:
        return f"{hours} hrs"

    days = math.ceil(hours / 24)
    return f"{days} days"


@register.filter
def is_image(filename):
    if not filename:
        return False
    if hasattr(filename, 'name'):
        filename = filename.name
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
    import os
    _, ext = os.path.splitext(filename.lower())
    return ext in image_extensions
