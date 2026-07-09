from django.urls import path
from .views import (
    ArticleListView,
    ArticleDetailView,
    ArticleCreateView,
    ArticleUpdateView,
    ArticleDeleteView,
    kb_ticket_search,
    kb_search_suggest,
    KBCategoryListView,
    KBCategoryCreateView,
    KBCategoryUpdateView,
    KBCategoryDeleteView,
)

urlpatterns = [
    path("", ArticleListView.as_view(), name="kb_list"),
    path("create/", ArticleCreateView.as_view(), name="kb_create"),
    path("<int:pk>/", ArticleDetailView.as_view(), name="kb_detail"),
    path("<int:pk>/edit/", ArticleUpdateView.as_view(), name="kb_update"),
    path("<int:pk>/delete/", ArticleDeleteView.as_view(), name="kb_delete"),
    path("search-suggest/", kb_search_suggest, name="kb_search_suggest"),
    path("ticket-search/", kb_ticket_search, name="kb_ticket_search"),
    
    # KB Category Management
    path("categories/", KBCategoryListView.as_view(), name="kb_category_list"),
    path("categories/add/", KBCategoryCreateView.as_view(), name="kb_category_create"),
    path("categories/<int:pk>/edit/", KBCategoryUpdateView.as_view(), name="kb_category_update"),
    path("categories/<int:pk>/delete/", KBCategoryDeleteView.as_view(), name="kb_category_delete"),
]
