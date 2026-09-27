import logging
import time

from django.core.cache import cache
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection

from core.models import EmailSetting

logger = logging.getLogger(__name__)

_EMAIL_SETTING_CACHE_KEY = "active_email_setting"


def clear_email_setting_cache():
    cache.delete(_EMAIL_SETTING_CACHE_KEY)


def _get_active_email_setting():
    cached = cache.get(_EMAIL_SETTING_CACHE_KEY)
    if isinstance(cached, dict) and "setting" in cached:
        setting = cached["setting"]
        if setting is None:
            if not EmailSetting.objects.filter(is_active=True).exists():
                return None
        elif EmailSetting.objects.filter(pk=setting.pk, is_active=True).exists():
            return setting
    setting = EmailSetting.objects.filter(is_active=True).order_by("-updated_at").first()
    cache.set(_EMAIL_SETTING_CACHE_KEY, {"setting": setting}, 60)
    return setting


def is_email_event_enabled(flag_name: str) -> bool:
    setting = _get_active_email_setting()
    if not setting:
        return False
    return bool(getattr(setting, flag_name, True))


def _build_connection(setting: EmailSetting):
    use_tls = setting.encryption == "tls"
    use_ssl = setting.encryption == "ssl"
    return get_connection(
        host=setting.smtp_host,
        port=setting.smtp_port,
        username=setting.smtp_email,
        password=setting.smtp_password,
        use_tls=use_tls,
        use_ssl=use_ssl,
    )


def send_with_retries(
    subject,
    body,
    recipients,
    retries=1,
    delay_seconds=2,
    setting: EmailSetting | None = None,
    html_body: str | None = None,
):
    if not recipients:
        return False

    setting = setting or _get_active_email_setting()
    if not setting:
        logger.warning("No active email setting configured.")
        return False

    connection = _build_connection(setting)
    from_email = f"{setting.from_name} <{setting.from_email}>"
    unique_recipients = list(set(recipients))

    for attempt in range(1, retries + 1):
        try:
            if html_body:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=unique_recipients,
                    connection=connection,
                )
                email.attach_alternative(html_body, "text/html")
            else:
                email = EmailMessage(
                    subject=subject,
                    body=body,
                    from_email=from_email,
                    to=unique_recipients,
                    connection=connection,
                )
            email.send(fail_silently=False)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Email send failed on attempt %s: %s", attempt, exc)
            if attempt < retries:
                time.sleep(delay_seconds)

    return False
