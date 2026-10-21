from django.apps import AppConfig


class ShiftsConfig(AppConfig):
    name = "shifts"

    def ready(self):
        # Start the shift reminder thread with the first web request, so
        # migrate and other management commands never spawn it.
        from django.core.signals import request_started

        from shifts.reminders import ensure_reminder_thread

        request_started.connect(ensure_reminder_thread, dispatch_uid="shifts-reminder-thread")
