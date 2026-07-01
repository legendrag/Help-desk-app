from django.urls import path
from .views import (
    ArticleListView, 
    ArticleDetailView, 
    ArticleCreateView, 
    ArticleUpdateView, 
    ArticleDeleteView,
    kb_ticket_search
)

urlpatterns = [
    path("", ArticleListView.as_view(), name="kb_list"),
    path("create/", ArticleCreateView.as_view(), name="kb_create"),
    path("<int:pk>/", ArticleDetailView.as_view(), name="kb_detail"),
    path("<int:pk>/edit/", ArticleUpdateView.as_view(), name="kb_update"),
    path("<int:pk>/delete/", ArticleDeleteView.as_view(), name="kb_delete"),
    path("ticket-search/", kb_ticket_search, name="kb_ticket_search"),
]
