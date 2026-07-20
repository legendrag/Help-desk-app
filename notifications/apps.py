import sys
from types import ModuleType
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
        # 1. Patch webpush.models.SubscriptionInfo to exclude user_agent field
        try:
            from webpush.models import SubscriptionInfo
            SubscriptionInfo._meta.local_fields = [
                f for f in SubscriptionInfo._meta.local_fields if f.name != 'user_agent'
            ]
            keys_to_clear = [
                'fields', '_field_cache', 'concrete_fields', 
                'local_concrete_fields'
            ]
            for key in keys_to_clear:
                SubscriptionInfo._meta.__dict__.pop(key, None)
            if hasattr(SubscriptionInfo._meta, '_get_fields_cache') and SubscriptionInfo._meta._get_fields_cache is not None:
                SubscriptionInfo._meta._get_fields_cache.clear()
        except (ImportError, RuntimeError):
            pass

        # 2. Inject patched webpush.forms module into sys.modules
        try:
            from django import forms
            from webpush.models import Group, PushInformation, SubscriptionInfo

            forms_mod = ModuleType('webpush.forms')

            class WebPushForm(forms.Form):
                group = forms.CharField(max_length=255, required=False)
                status_type = forms.ChoiceField(choices=[
                    ('subscribe', 'subscribe'),
                    ('unsubscribe', 'unsubscribe')
                ])

                def save_or_delete(self, subscription, user, status_type, group_name):
                    data = {"user": None, "group": None}
                    if user.is_authenticated:
                        data["user"] = user
                    if group_name:
                        group, created = Group.objects.get_or_create(name=group_name)
                        data["group"] = group
                    data["subscription"] = subscription
                    try:
                        push_info, created = PushInformation.objects.get_or_create(**data)
                    except PushInformation.MultipleObjectsReturned:
                        push_infos = PushInformation.objects.filter(**data)
                        push_info = push_infos.first()
                        push_infos.exclude(id=push_info.id).delete()
                        created = False

                    if status_type == "unsubscribe":
                        if created:
                            push_info.delete()
                        else:
                            PushInformation.objects.filter(**data).delete()
                        subscription.delete()
                        return

                    # Keep a single active push subscription per user so stale FCM
                    # endpoints cannot produce duplicate OS toasts.
                    if user.is_authenticated:
                        stale = (
                            PushInformation.objects.filter(user=user)
                            .exclude(id=push_info.id)
                            .select_related("subscription")
                        )
                        for old in stale:
                            old_sub = old.subscription
                            old.delete()
                            if old_sub and not PushInformation.objects.filter(subscription=old_sub).exists():
                                old_sub.delete()

            class SubscriptionForm(forms.ModelForm):
                class Meta:
                    model = SubscriptionInfo
                    fields = ('endpoint', 'auth', 'p256dh', 'browser')

                def get_or_save(self):
                    try:
                        subscription, created = SubscriptionInfo.objects.get_or_create(**self.cleaned_data)
                    except SubscriptionInfo.MultipleObjectsReturned:
                        subscriptions = SubscriptionInfo.objects.filter(**self.cleaned_data)
                        subscription = subscriptions.first()
                        subscriptions.exclude(id=subscription.id).delete()
                    return subscription

            forms_mod.WebPushForm = WebPushForm
            forms_mod.SubscriptionForm = SubscriptionForm
            
            sys.modules['webpush.forms'] = forms_mod
        except (ImportError, RuntimeError):
            pass

        # 3. Patch webpush sending functions to be resilient and not crash the whole loop
        try:
            import logging
            logger = logging.getLogger(__name__)

            import webpush.utils
            import webpush
            from pywebpush import WebPushException

            def resilient_send_notification_to_user(user, payload, ttl=0):
                from webpush.utils import _send_notification
                push_infos = user.webpush_info.select_related("subscription")
                seen_endpoints = set()
                for push_info in push_infos:
                    subscription = push_info.subscription
                    endpoint = getattr(subscription, "endpoint", None) or ""
                    if endpoint in seen_endpoints:
                        continue
                    if endpoint:
                        seen_endpoints.add(endpoint)
                    try:
                        _send_notification(subscription, payload, ttl)
                    except WebPushException as e:
                        status_code = e.response.status_code if e.response is not None else None
                        logger.warning(
                            f"WebPush failed for user {user.id} subscription {subscription.id}: {e}"
                        )
                        if status_code in [403, 404, 410]:
                            try:
                                subscription.delete()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(
                            f"WebPush unexpected error for user {user.id} subscription {subscription.id}: {e}"
                        )

            def resilient_send_notification_to_group(group_name, payload, ttl=0, exclude_user_id=None):
                from webpush.models import Group
                from webpush.utils import _send_notification
                try:
                    group = Group.objects.get(name=group_name)
                except Group.DoesNotExist:
                    return

                push_infos = group.webpush_info.select_related("subscription")
                if exclude_user_id is not None:
                    push_infos = push_infos.exclude(user__id=exclude_user_id)

                seen_endpoints = set()
                for push_info in push_infos:
                    subscription = push_info.subscription
                    endpoint = getattr(subscription, "endpoint", None) or ""
                    if endpoint in seen_endpoints:
                        continue
                    if endpoint:
                        seen_endpoints.add(endpoint)
                    try:
                        _send_notification(subscription, payload, ttl)
                    except WebPushException as e:
                        status_code = e.response.status_code if e.response is not None else None
                        logger.warning(
                            f"WebPush group notify failed for subscription {subscription.id}: {e}"
                        )
                        if status_code in [403, 404, 410]:
                            try:
                                subscription.delete()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(
                            f"WebPush unexpected error for subscription {subscription.id}: {e}"
                        )

            # Apply the patches to utils module
            webpush.utils.send_notification_to_user = resilient_send_notification_to_user
            webpush.utils.send_notification_to_group = resilient_send_notification_to_group

            # Apply the patches to the main webpush package namespaces
            webpush.send_user_notification = resilient_send_notification_to_user
            webpush.send_group_notification = resilient_send_notification_to_group

        except (ImportError, RuntimeError):
            pass




