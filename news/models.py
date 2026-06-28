from django.db import models
from django.conf import settings
from core.models import TimeStampedModel, Branch, Department

class Announcement(TimeStampedModel):
    title = models.CharField(max_length=150)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional. The announcement will automatically hide after this date and time.")
    
    target_branch = models.ForeignKey(Branch, on_delete=models.CASCADE, null=True, blank=True, related_name="announcements", help_text="Leave blank to show to all branches.")
    target_department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, related_name="announcements", help_text="Leave blank to show to all departments.")
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="announcements")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
