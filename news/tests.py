from django.test import TestCase

from accounts.models import User
from news.models import Announcement
from news.views import NewsListView


class NewsListQueryOptimizationTests(TestCase):
    def test_news_list_queryset_selects_related_created_by(self):
        author = User.objects.create_user(
            username="news_author",
            email="news_author@test.com",
            password="password123",
        )
        Announcement.objects.create(title="Query opt news", content="Body", created_by=author)
        announcements = list(NewsListView().get_queryset())
        listed = next(a for a in announcements if a.title == "Query opt news")
        with self.assertNumQueries(0):
            self.assertEqual(listed.created_by.username, "news_author")
