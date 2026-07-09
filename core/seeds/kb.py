from kb.models import Article, Category
from core.seeds import data


def seed_kb(users, tickets=None, stdout=None):
    categories = {}
    for item in data.KB_CATEGORIES:
        category, created = Category.objects.get_or_create(
            name=item["name"],
            defaults={"description": item["description"]},
        )
        if category.description != item["description"]:
            category.description = item["description"]
            category.save(update_fields=["description"])
        categories[item["name"]] = category
        if stdout and created:
            stdout.write(f"  KB category {category.name}")

    author = users.get("kb_editor1") or users.get("admin")
    related_ticket = tickets.get("email_closed") if tickets else None
    articles = {}

    for index, item in enumerate(data.KB_ARTICLES):
        article, created = Article.objects.get_or_create(
            title=item["title"],
            defaults={
                "category": categories[item["category"]],
                "content": item["content"],
                "is_published": True,
                "created_by": author,
            },
        )
        article.category = categories[item["category"]]
        article.content = item["content"]
        article.is_published = True
        article.created_by = author
        if index == 1 and related_ticket:
            article.related_ticket = related_ticket
        article.save()
        articles[item["title"]] = article
        if stdout:
            label = "created" if created else "updated"
            stdout.write(f"  KB article '{article.title}' ({label})")

    return {"categories": categories, "articles": articles}
