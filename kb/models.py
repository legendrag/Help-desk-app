from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel

from .sanitize import sanitize_article_html

def kb_attachment_path(instance, filename):
    from django.utils.text import get_valid_filename
    import os
    name = get_valid_filename(os.path.basename(filename or "attachment"))
    return f"kb/{instance.article_id}/{name}"

ICON_CHOICES = [
    ("document", "Document (Default)"),
    ("book", "Book"),
    ("wrench", "Wrench"),
    ("shield", "Shield"),
    ("star", "Star"),
    ("info", "Info"),
    ("users", "Users"),
    ("help", "Help"),
    ("globe", "Globe"),
]

class Category(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        choices=ICON_CHOICES,
        default="document",
        help_text="Icon to display for this category"
    )

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Article(TimeStampedModel):
    class Visibility(models.TextChoices):
        ONLY_ME = "only_me", _("Only me")
        DEPARTMENT = "department", _("My department")
        ALL_SUPPORT = "all_support", _("All support")

    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    content = models.TextField(help_text="HTML content from TinyMCE")
    is_published = models.BooleanField(default=True)
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.ALL_SUPPORT,
        help_text=_("Who can read this article after it is published."),
    )
    visibility_department = models.ForeignKey(
        "core.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visibility_kb_articles",
        help_text=_("Author's department at the time this article was published to that department."),
    )
    
    related_ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kb_articles",
        help_text="Ticket that inspired or is resolved by this article"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_kb_articles"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_published", "-updated_at"], name="kb_pub_updated_idx"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "content" in set(update_fields):
            self.content = sanitize_article_html(self.content or "")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"content"}
        super().save(*args, **kwargs)

class ArticleAttachment(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=kb_attachment_path)
    
    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Attachment {self.id} for Article {self.article_id}"
