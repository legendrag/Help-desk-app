import logging
import smtplib

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives, get_connection

from core.models import EmailSetting

logger = logging.getLogger(__name__)

_EMAIL_SETTING_CACHE_KEY = "active_email_setting"


def clear_email_setting_cache():
    cache.delete(_EMAIL_SETTING_CACHE_KEY)


def _get_active_email_setting():
    # Read fresh every time: a cached copy kept the on/off switches stale for up
    # to a minute in other processes, and it saved no queries anyway (each read
    # re-checked the row).
    return EmailSetting.objects.filter(is_active=True).order_by("-updated_at").first()


def is_email_event_enabled(flag_name: str) -> bool:
    setting = _get_active_email_setting()
    if not setting:
        return False
    return bool(getattr(setting, flag_name, True))


# A mail server that accepts the connection and then stalls must not hold the
# email lane forever.
SMTP_TIMEOUT_SECONDS = 20
# Waits before resending to recipients that failed with a temporary error.
RETRY_DELAYS_SECONDS = (60, 300, 1800, 7200)


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
        timeout=SMTP_TIMEOUT_SECONDS,
    )


def _clean_subject(subject) -> str:
    # A CR/LF (e.g. from a ticket title) makes Django refuse the whole message.
    return " ".join(str(subject).split())


def _is_temporary(exc: Exception) -> bool:
    """Whether resending later could succeed (4xx replies, network trouble)."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return all(400 <= code < 500 for code, _msg in exc.recipients.values())
    if isinstance(exc, smtplib.SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return True
    if isinstance(exc, smtplib.SMTPException):
        return False
    return isinstance(exc, OSError)  # refused connection, DNS, timeout


def _send_each(subject, body, recipients, setting, html_body):
    """Send one message per recipient over one connection.

    Separate messages keep recipients from seeing each other's addresses, and
    one bad address can't sink the rest. Returns {recipient: exception}.
    """
    from_email = f"{setting.from_name} <{setting.from_email}>"
    connection = _build_connection(setting)
    try:
        connection.open()
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not connect to the mail server %s: %s", setting.smtp_host, exc)
        return {recipient: exc for recipient in recipients}

    failed = {}
    try:
        for recipient in recipients:
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[recipient],
                connection=connection,
            )
            if html_body:
                email.attach_alternative(html_body, "text/html")
            try:
                email.send(fail_silently=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Email to %s failed: %s", recipient, exc)
                failed[recipient] = exc
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
    return failed


def send_with_retries(
    subject,
    body,
    recipients,
    setting: EmailSetting | None = None,
    html_body: str | None = None,
    retry_later: bool = False,
    attempt: int = 0,
):
    """Send now. Returns True if every recipient got it.

    With ``retry_later``, recipients that failed with a temporary error are
    queued again with growing delays (the setting is re-read each time, so a
    fixed SMTP config is picked up).
    """
    recipients = sorted({r for r in (recipients or []) if r})
    if not recipients:
        return False

    setting = setting or _get_active_email_setting()
    if not setting:
        logger.warning("No active email setting configured.")
        return False

    subject = _clean_subject(subject)
    failed = _send_each(subject, body, recipients, setting, html_body)
    if not failed:
        return True

    temporary = [r for r, exc in failed.items() if _is_temporary(exc)]
    permanent = [r for r in failed if r not in temporary]
    if permanent:
        logger.error("Email %r not delivered to %s (permanent error).", subject, ", ".join(permanent))
    if temporary:
        if retry_later and attempt < len(RETRY_DELAYS_SECONDS) and not getattr(
            settings, "EMAIL_QUEUE_SYNC", False
        ):
            from notifications.email_queue import enqueue_email

            delay = RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "Email %r to %s failed temporarily; retrying in %ss (retry %s/%s).",
                subject, ", ".join(temporary), delay, attempt + 1, len(RETRY_DELAYS_SECONDS),
            )
            enqueue_email(
                send_with_retries,
                subject,
                body,
                temporary,
                html_body=html_body,
                retry_later=True,
                attempt=attempt + 1,
                delay_seconds=delay,
                max_attempts=1,
            )
        else:
            logger.error("Email %r not delivered to %s; giving up.", subject, ", ".join(temporary))
    return False
