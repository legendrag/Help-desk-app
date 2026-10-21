from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import InAppNotification
try:
    from webpush import send_user_notification
except ImportError:
    send_user_notification = None


MAX_NOTIFICATIONS_LIMIT = 100


def _parse_limit(raw, default=20):
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, MAX_NOTIFICATIONS_LIMIT))


@require_GET
@login_required
def notifications_list(request):
    limit = _parse_limit(request.GET.get("limit"))
    qs = (
        InAppNotification.objects.filter(recipient=request.user)
        .order_by("-created_at", "-id")
    )
    # ?before=<id> pages back through older notifications.
    before = request.GET.get("before")
    if before and before.isdigit():
        qs = qs.filter(id__lt=int(before))
    notifications = [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "title_ar": n.arabic_title(),
            "message_ar": n.arabic_message(),
            "link": n.link,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in qs[: limit + 1]
    ]
    has_more = len(notifications) > limit
    notifications = notifications[:limit]
    unread_count = InAppNotification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse(
        {"notifications": notifications, "unread_count": unread_count, "has_more": has_more}
    )


@require_POST
@login_required
def mark_notifications_read(request):
    InAppNotification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


@require_POST
@login_required
def mark_notification_read(request, notification_id):
    InAppNotification.objects.filter(id=notification_id, recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"ok": True})


@require_POST
@login_required
def delete_notification(request, notification_id):
    """Delete a single notification."""
    InAppNotification.objects.filter(id=notification_id, recipient=request.user).delete()
    unread_count = InAppNotification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread_count": unread_count})


@require_POST
@login_required
def clear_read_notifications(request):
    """Delete all read notifications for the current user."""
    InAppNotification.objects.filter(recipient=request.user, is_read=True).delete()
    unread_count = InAppNotification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({"ok": True, "unread_count": unread_count})

