import sys
from types import ModuleType
from django.apps import AppConfig
import ipaddress
import logging
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# A push service that never answers must not hold up the delivery queue.
PUSH_TIMEOUT_SECONDS = 10
# Drop a subscription after this many failures in a row with no success.
PUSH_MAX_CONSECUTIVE_FAILURES = 20


def _is_public_push_endpoint(endpoint):
    """Push endpoints are HTTPS URLs on a public push service, never an internal address."""
    try:
        parts = urlsplit(endpoint)
        host = (parts.hostname or "").lower()
    except ValueError:
        return False
    if parts.scheme != "https" or not host or host == "localhost":
        return False
    if host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return "." in host  # a public DNS name
    return False  # browsers' push services are never bare IP addresses


def _send_push(subscription, payload, ttl):
    from django.conf import settings
    from pywebpush import webpush as pywebpush_send
    from webpush.utils import _process_subscription_info

    webpush_settings = getattr(settings, "WEBPUSH_SETTINGS", {})
    vapid = {}
    if webpush_settings.get("VAPID_PRIVATE_KEY"):
        vapid = {
            "vapid_private_key": webpush_settings["VAPID_PRIVATE_KEY"],
            "vapid_claims": {"sub": "mailto:{}".format(webpush_settings.get("VAPID_ADMIN_EMAIL"))},
        }
    return pywebpush_send(
        subscription_info=_process_subscription_info(subscription),
        data=payload,
        ttl=ttl,
        timeout=PUSH_TIMEOUT_SECONDS,
        **vapid,
    )


def _push_failure_key(subscription):
    return f"webpush_failures_{subscription.pk}"


def _delete_subscription(subscription):
    try:
        subscription.delete()
    except Exception:
        pass


def _record_push_failure(subscription, detail):
    from django.core.cache import cache

    key = _push_failure_key(subscription)
    try:
        count = cache.get(key, 0) + 1
        cache.set(key, count, 7 * 24 * 3600)
    except Exception:
        count = 1
    if count >= PUSH_MAX_CONSECUTIVE_FAILURES:
        logger.warning(
            "WebPush subscription %s removed after %s failures in a row (%s)", subscription.pk, count, detail
        )
        _delete_subscription(subscription)
        cache.delete(key)
    elif count == 1 or count % 5 == 0:
        # The first failure, then every fifth, so a dead endpoint can't flood the log.
        logger.warning(
            "WebPush failed for subscription %s (failure %s in a row): %s", subscription.pk, count, detail
        )


def _clear_push_failures(subscription):
    from django.core.cache import cache

    try:
        cache.delete(_push_failure_key(subscription))
    except Exception:
        pass




def _close_session_sockets(sender, request, user, **kwargs):
    """Stop an open page from receiving notifications after its session logs out."""
    session_key = getattr(getattr(request, "session", None), "session_key", None)
    if user is None or not session_key:
        return
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            f"user_{user.pk}_notifications",
            {"type": "session.ended", "session_key": session_key},
        )
    except Exception:
        pass


class NotificationsConfig(AppConfig):
    name = 'notifications'

    def ready(self):
        from django.contrib.auth.signals import user_logged_out

        user_logged_out.connect(_close_session_sockets, dispatch_uid="notifications.close_session_sockets")

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

        # After migrate / on first request, drop a leftover user_agent column
        # that would 500 on /webpush/save_information.
        try:
            from django.core.signals import request_started
            from django.db.models.signals import post_migrate
            from notifications.webpush_schema import (
                drop_subscriptioninfo_user_agent_if_exists,
                ensure_subscriptioninfo_schema,
            )

            def _ensure_webpush_schema(sender, app_config, **kwargs):
                if app_config.label not in ("notifications", "webpush"):
                    return
                try:
                    drop_subscriptioninfo_user_agent_if_exists()
                except Exception:
                    pass

            post_migrate.connect(_ensure_webpush_schema, dispatch_uid="notifications.drop_webpush_user_agent")
            request_started.connect(
                lambda **kwargs: ensure_subscriptioninfo_schema(),
                dispatch_uid="notifications.ensure_webpush_schema_on_request",
            )
        except Exception:
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
                    # The app only pushes to users. Anonymous "group" sign-ups
                    # would let anyone register endpoints the server then calls.
                    if not user.is_authenticated:
                        if not PushInformation.objects.filter(subscription=subscription).exists():
                            subscription.delete()
                        return
                    data = {"user": user, "group": None, "subscription": subscription}
                    try:
                        push_info, created = PushInformation.objects.get_or_create(**data)
                    except PushInformation.MultipleObjectsReturned:
                        push_infos = PushInformation.objects.filter(**data)
                        push_info = push_infos.first()
                        push_infos.exclude(id=push_info.id).delete()
                        created = False

                    if status_type == "unsubscribe":
                        # Only drop the caller's own rows; the subscription goes
                        # once nobody else holds it.
                        PushInformation.objects.filter(**data).delete()
                        if not PushInformation.objects.filter(subscription=subscription).exists():
                            subscription.delete()
                        return

                    # A browser subscription belongs to whoever registered it last
                    # (e.g. another user logged in on the same browser), so pushes
                    # never reach a previous user's device.
                    PushInformation.objects.filter(subscription=subscription).exclude(user=user).delete()

                    # Allow multiple devices (browser + PWA + phone). Only remove
                    # other PushInformation rows that share this exact endpoint.
                    if user.is_authenticated:
                        endpoint = getattr(subscription, "endpoint", None)
                        if endpoint:
                            stale = (
                                PushInformation.objects.filter(
                                    user=user,
                                    subscription__endpoint=endpoint,
                                )
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

                def clean_endpoint(self):
                    endpoint = self.cleaned_data.get("endpoint") or ""
                    if not _is_public_push_endpoint(endpoint):
                        raise forms.ValidationError("Invalid push endpoint.")
                    return endpoint

                def get_or_save(self):
                    from django.db.utils import OperationalError
                    from notifications.webpush_schema import drop_subscriptioninfo_user_agent_if_exists

                    def _create():
                        try:
                            subscription, _created = SubscriptionInfo.objects.get_or_create(
                                **self.cleaned_data
                            )
                        except SubscriptionInfo.MultipleObjectsReturned:
                            subscriptions = SubscriptionInfo.objects.filter(**self.cleaned_data)
                            subscription = subscriptions.first()
                            subscriptions.exclude(id=subscription.id).delete()
                        return subscription

                    try:
                        return _create()
                    except OperationalError as exc:
                        # MySQL 1364 when user_agent is NOT NULL and omitted by our patch.
                        if "user_agent" not in str(exc).lower():
                            raise
                        drop_subscriptioninfo_user_agent_if_exists()
                        return _create()

            forms_mod.WebPushForm = WebPushForm
            forms_mod.SubscriptionForm = SubscriptionForm
            
            sys.modules['webpush.forms'] = forms_mod
            # views may already hold references from `from webpush.forms import ...`
            try:
                import webpush.views as webpush_views
                webpush_views.WebPushForm = WebPushForm
                webpush_views.SubscriptionForm = SubscriptionForm
            except Exception:
                pass
        except (ImportError, RuntimeError):
            pass

        # 3. Patch webpush sending functions to be resilient and not crash the whole loop
        try:
            import webpush.utils
            import webpush
            from pywebpush import WebPushException

            def _push_one(subscription, payload, ttl, label):
                try:
                    _send_push(subscription, payload, ttl)
                except WebPushException as e:
                    status_code = e.response.status_code if e.response is not None else None
                    # 404/410: the browser dropped the subscription. Anything
                    # else (403 after a VAPID key change, 429, 5xx) may recover.
                    if status_code in (404, 410):
                        _delete_subscription(subscription)
                        return
                    _record_push_failure(subscription, f"{label}: {e}")
                except Exception as e:
                    _record_push_failure(subscription, f"{label}: unexpected error {e}")
                else:
                    _clear_push_failures(subscription)

            def resilient_send_notification_to_user(user, payload, ttl=0):
                push_infos = user.webpush_info.select_related("subscription")
                seen_endpoints = set()
                for push_info in push_infos:
                    subscription = push_info.subscription
                    endpoint = getattr(subscription, "endpoint", None) or ""
                    if endpoint in seen_endpoints:
                        continue
                    if endpoint:
                        seen_endpoints.add(endpoint)
                    _push_one(subscription, payload, ttl, f"user {user.id}")

            def resilient_send_notification_to_group(group_name, payload, ttl=0, exclude_user_id=None):
                from webpush.models import Group
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
                    _push_one(subscription, payload, ttl, f"group {group_name}")

            # Apply the patches to utils module
            webpush.utils.send_notification_to_user = resilient_send_notification_to_user
            webpush.utils.send_notification_to_group = resilient_send_notification_to_group

            # Apply the patches to the main webpush package namespaces
            webpush.send_user_notification = resilient_send_notification_to_user
            webpush.send_group_notification = resilient_send_notification_to_group

        except (ImportError, RuntimeError):
            pass




