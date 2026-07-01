from django.contrib import admin
from .models import Article, Category, ArticleAttachment

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

class ArticleAttachmentInline(admin.TabularInline):
    model = ArticleAttachment
    extra = 1

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'created_by', 'created_at')
    list_filter = ('is_published', 'category', 'created_at')
    search_fields = ('title', 'content')
    inlines = [ArticleAttachmentInline]
