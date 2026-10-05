"""Shared ticket authorization helpers."""


def user_in_ticket_org(user, ticket) -> bool:
    """Strict branch/department match (no KB bypass). Used for mutations."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    if user.user_type == "branch":
        return bool(user.branch_id) and ticket.branch_id == user.branch_id
    if user.user_type == "support":
        return bool(user.department_id) and ticket.department_id == user.department_id
    return False


def user_can_view_ticket(user, ticket) -> bool:
    """View access is same-org only. A published KB article does not widen it."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    return user_in_ticket_org(user, ticket)


def user_can_pick_ticket(user, ticket) -> bool:
    if not user_in_ticket_org(user, ticket):
        return False
    if ticket.assigned_to_id:
        return False
    if ticket.status == ticket.Status.MERGED:
        return False
    if user.is_superuser:
        return True
    return bool(user.role_id and user.role.can_pick_ticket)


def user_can_reopen_ticket(user, ticket) -> bool:
    """Same-org support (or explicit role) may reopen; no cross-org."""
    if not user_in_ticket_org(user, ticket):
        return False
    if user.is_superuser:
        return True
    if user.user_type == "support":
        return True
    return bool(user.role_id and user.role.can_update_closed_ticket)
