from core.version import get_app_version


def app_version(request):
    return {"app_version": get_app_version()}


def attachment_limits(request):
    """Lets the chat form reject oversized files before uploading them."""
    from django.conf import settings

    return {"max_attachment_size": getattr(settings, "MAX_ATTACHMENT_SIZE", 0)}
