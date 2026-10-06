def is_shift_manager(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    role = getattr(user, "role", None)
    return bool(role and role.can_manage_shifts)
