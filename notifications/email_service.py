import logging
import time

from django.core.mail import EmailMessage, get_connection

from core.models import EmailSetting

logger = logging.getLogger(__name__)


def _get_active_email_setting():
    return EmailSetting.objects.filter(is_active=True).order_by("-updated_at").first()


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


def send_with_retries(subject, body, recipients, retries=3, delay_seconds=2, setting: EmailSetting | None = None):
    if not recipients:
        return False

    setting = setting or _get_active_email_setting()
    if not setting:
        logger.warning("No active email setting configured.")
        return False

    connection = _build_connection(setting)

    from_email = f"{setting.from_name} <{setting.from_email}>"

    for attempt in range(1, retries + 1):
        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=list(set(recipients)),
                connection=connection,
            )
            email.send(fail_silently=False)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Email send failed on attempt %s: %s", attempt, exc)
            if attempt < retries:
                time.sleep(delay_seconds)

    return False
