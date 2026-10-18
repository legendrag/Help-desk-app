from django.contrib import admin

from .models import EmailOutbox


@admin.register(EmailOutbox)
class EmailOutboxAdmin(admin.ModelAdmin):
    list_display = ("func", "status", "attempts", "max_attempts", "next_attempt_at", "created_at")
    list_filter = ("status",)
    readonly_fields = ("created_at",)
    actions = ["retry_now"]

    @admin.action(description="Retry now")
    def retry_now(self, request, queryset):
        from django.utils import timezone

        queryset.update(status=EmailOutbox.Status.PENDING, attempts=0, next_attempt_at=timezone.now())
