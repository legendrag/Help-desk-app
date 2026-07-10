from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

def kb_attachment_path(instance, filename):
    return f"kb/{instance.article_id}/{filename}"

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
    title = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="articles")
    content = models.TextField(help_text="HTML content from TinyMCE")
    is_published = models.BooleanField(default=True)
    
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

    def __str__(self):
        return self.title

class ArticleAttachment(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=kb_attachment_path)
    
    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Attachment {self.id} for Article {self.article_id}"
