def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)


def can_check_in(user) -> bool:
    """Day-shift check-in. Managers do not inherit this from can_manage_shifts.

    Only rostered people check in (see ``has_own_shifts``). A support-type
    superuser checks in like any agent, without needing the role flag.
    """
    if not has_own_shifts(user):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_check_in)


def has_own_shifts(user) -> bool:
    """Whether the user can be put on the rota, and so has a My shifts page.

    Every support-type account is rostered, superusers included.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "user_type", "") == "support"


def home_target(user) -> str:
    if is_shift_manager(user):
        return "shifts_rota"
    if has_own_shifts(user):
        return "shifts_mine"
    if getattr(user, "user_type", "") == "branch":
        return "shifts_available"
    return ""


def display_name(user) -> str:
    full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full or user.username
