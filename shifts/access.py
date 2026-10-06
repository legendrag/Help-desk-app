def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)


def home_target(user) -> str:
    if is_shift_manager(user):
        return "shifts_rota"
    if getattr(user, "user_type", "") == "support":
        return "shifts_mine"
    if getattr(user, "user_type", "") == "branch":
        return "shifts_available"
    return ""


def display_name(user) -> str:
    full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full or user.username
