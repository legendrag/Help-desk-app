from django.utils import timezone

from news.models import Announcement
from core.seeds import data


def seed_news(organization, users, stdout=None):
    branches = organization["branches"]
    departments = organization["departments"]
    author = users.get("lead1") or users.get("admin")
    announcements = {}

    for item in data.ANNOUNCEMENTS:
        target_branch = branches.get(item["target_branch"]) if item.get("target_branch") else None
        target_department = departments.get(item["target_department"]) if item.get("target_department") else None

        announcement, created = Announcement.objects.get_or_create(
            title=item["title"],
            defaults={
                "content": item["content"],
                "is_active": item["is_active"],
                "target_branch": target_branch,
                "target_department": target_department,
                "created_by": author,
            },
        )
        announcement.content = item["content"]
        announcement.is_active = item["is_active"]
        announcement.target_branch = target_branch
        announcement.target_department = target_department
        announcement.created_by = author
        announcement.save()
        announcements[item["title"]] = announcement
        if stdout:
            label = "created" if created else "updated"
            stdout.write(f"  Announcement '{announcement.title}' ({label})")

    return announcements
