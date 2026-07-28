"""Helpers to remove django-webpush subscriptions for a user."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def clear_user_webpush_subscriptions(user) -> int:
    """Delete all PushInformation rows for ``user`` and orphaned SubscriptionInfo.

    Returns the number of push-info rows removed. Safe no-op if webpush is absent.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return 0
    if getattr(user, "is_anonymous", False):
        return 0

    try:
        from webpush.models import PushInformation, SubscriptionInfo
    except Exception:
        return 0

    infos = list(
        PushInformation.objects.filter(user=user).select_related("subscription")
    )
    if not infos:
        return 0

    subscription_ids = [
        info.subscription_id for info in infos if info.subscription_id
    ]
    count = len(infos)
    PushInformation.objects.filter(id__in=[info.id for info in infos]).delete()

    for sid in subscription_ids:
        if not PushInformation.objects.filter(subscription_id=sid).exists():
            SubscriptionInfo.objects.filter(id=sid).delete()

    logger.info("Cleared %s web push subscription(s) for user %s", count, user.pk)
    return count
