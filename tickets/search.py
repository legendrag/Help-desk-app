from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Replace

_PHONE_STRIP_CHARS = ("-", " ", "(", ")", ".", "+")


def _phone_digits_expr():
    expr = F("client_phone")
    for char in _PHONE_STRIP_CHARS:
        expr = Replace(expr, Value(char), Value(""))
    return expr


def _token_q(token, *, phone_digits_field=None):
    """Match a single search token across useful ticket fields."""
    q = (
        Q(ticket_number__icontains=token)
        | Q(title__icontains=token)
        | Q(description__icontains=token)
        | Q(client_name__icontains=token)
        | Q(client_phone__icontains=token)
        | Q(branch__name__icontains=token)
        | Q(department__name__icontains=token)
        | Q(category__name__icontains=token)
        | Q(assigned_to__username__icontains=token)
        | Q(created_by__username__icontains=token)
    )
    digits = "".join(ch for ch in token if ch.isdigit())
    if phone_digits_field and len(digits) >= 3:
        q |= Q(**{f"{phone_digits_field}__icontains": digits})
    return q


def apply_ticket_search(queryset, search_query, *, rank=True):
    """
    Filter tickets by a free-text query.

    - Splits into words; every word must match (AND).
    - Searches ID, title, description, client, org names, and usernames.
    - Phone matches ignore common separators (5550199 ≈ 555-0199).
    - Optionally ranks exact/ID/title matches above description hits.
    """
    query = (search_query or "").strip()
    if not query:
        return queryset

    tokens = [token for token in query.split() if token]
    if not tokens:
        return queryset

    needs_phone_digits = any(
        len("".join(ch for ch in token if ch.isdigit())) >= 3 for token in tokens
    )
    phone_digits_field = None
    if needs_phone_digits:
        phone_digits_field = "_phone_digits"
        queryset = queryset.annotate(**{phone_digits_field: _phone_digits_expr()})

    for token in tokens:
        queryset = queryset.filter(
            _token_q(token, phone_digits_field=phone_digits_field)
        )

    if not rank:
        return queryset

    return queryset.annotate(
        search_rank=Case(
            When(ticket_number__iexact=query, then=Value(100)),
            When(ticket_number__icontains=query, then=Value(80)),
            When(title__icontains=query, then=Value(60)),
            When(client_name__icontains=query, then=Value(50)),
            When(client_phone__icontains=query, then=Value(45)),
            When(assigned_to__username__icontains=query, then=Value(35)),
            When(created_by__username__icontains=query, then=Value(30)),
            When(category__name__icontains=query, then=Value(25)),
            When(branch__name__icontains=query, then=Value(20)),
            When(department__name__icontains=query, then=Value(20)),
            When(description__icontains=query, then=Value(10)),
            default=Value(5),
            output_field=IntegerField(),
        )
    ).order_by("-search_rank", "-created_at")
