from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import InAppNotification
try:
    from webpush import send_user_notification
except ImportError:
    send_user_notification = None


@require_GET
@login_required
def notifications_list(request):
    limit = int(request.GET.get("limit", 20))
    qs = (
        InAppNotification.objects.filter(recipient=request.user)
        .order_by("-created_at")
    )
    notifications = [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "link": n.link,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in qs[:limit]
    ]
    unread_count = InAppNotification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({"notifications": notifications, "unread_count": unread_count})


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


@require_POST
@login_required
def test_webpush(request):
    if not send_user_notification:
        return JsonResponse({"status": "error", "message": "django-webpush is not installed"}, status=400)
    
    try:
        from webpush.models import PushInformation
        count = PushInformation.objects.filter(user=request.user).count()
        if count == 0:
            return JsonResponse({"status": "error", "message": "No active webpush subscription in database for this user."}, status=400)
        
        payload = {
            "title": "Test Web Push",
            "body": "This is a test notification!",
            "icon": "/static/images/deskplus-logo.png",
            "data": {"url": "/"}
        }
        send_user_notification(user=request.user, payload=payload, ttl=1000)
        return JsonResponse({"status": "success", "message": f"Push sent successfully to {count} subscriptions."})
    except Exception as e:
        import traceback
        return JsonResponse({"status": "error", "message": str(e), "traceback": traceback.format_exc()}, status=500)
