"""Who may read or manage knowledge-base articles, and which rows they see."""

from django.db.models import Q

from accounts.models import User

from .models import Article


def user_can_read_kb(user) -> bool:
    """Support users with can_access_kb, plus superusers. Branch users never qualify."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if getattr(user, "user_type", None) != User.UserType.SUPPORT:
        return False
    role = getattr(user, "role", None)
    return bool(role and getattr(role, "can_access_kb", False))


def user_can_manage_kb(user) -> bool:
    """Support users with can_manage_kb, plus superusers. Branch users never qualify."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if getattr(user, "user_type", None) != User.UserType.SUPPORT:
        return False
    role = getattr(user, "role", None)
    return bool(role and getattr(role, "can_manage_kb", False))


def published_visibility_q(user, prefix=""):
    """
    Published articles this user may see.

    prefix is "" on Article querysets and "articles__" when annotating Category.
    """

    def field(name):
        return f"{prefix}{name}"

    published = Q(**{field("is_published"): True})
    if user.is_superuser:
        return published

    audience = Q(**{field("visibility"): Article.Visibility.ALL_SUPPORT})
    audience |= Q(
        **{
            field("visibility"): Article.Visibility.ONLY_ME,
            field("created_by"): user.pk,
        }
    )
    department_id = getattr(user, "department_id", None)
    if department_id:
        audience |= Q(
            **{
                field("visibility"): Article.Visibility.DEPARTMENT,
                field("created_by__department_id"): department_id,
            }
        )
    return published & audience


def articles_for_user(user, *, include_drafts=False):
    """
    One visibility rule for list, detail, search, related, counts, and recent.

    Drafts are included only for managers and superusers, and only when the
    caller asks for them (article detail and the draft list). Reader surfaces
    pass include_drafts=False so drafts stay out of search, counts, recent,
    and related articles.
    """
    if not user_can_read_kb(user):
        return Article.objects.none()
    if user.is_superuser:
        queryset = Article.objects.all()
        if not include_drafts:
            queryset = queryset.filter(is_published=True)
        return queryset

    visible = published_visibility_q(user)
    if include_drafts and user_can_manage_kb(user):
        return Article.objects.filter(visible | Q(is_published=False))
    return Article.objects.filter(visible)
