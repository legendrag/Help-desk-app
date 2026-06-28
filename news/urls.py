from django.urls import path
from .views import NewsListView, NewsCreateView, NewsUpdateView, NewsDeleteView

urlpatterns = [
    path("", NewsListView.as_view(), name="news_list"),
    path("create/", NewsCreateView.as_view(), name="news_create"),
    path("<int:pk>/edit/", NewsUpdateView.as_view(), name="news_update"),
    path("<int:pk>/delete/", NewsDeleteView.as_view(), name="news_delete"),
]
