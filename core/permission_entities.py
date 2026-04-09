PERMISSION_ENTITIES = [
    "admin_access",
    "admin_branches_access",
    "admin_branches_edit",
    "admin_departments_access",
    "admin_departments_edit",
    "admin_categories_access",
    "admin_categories_edit",
    "admin_users_access",
    "admin_users_edit",
    "admin_roles_access",
    "admin_roles_edit",
    "admin_email_settings_access",
    "admin_email_settings_edit",
    "dashboard_read",
    "tickets_list",
    "ticket_details",
    "ticket_create",
    "ticket_pick",
    "ticket_status",
    "ticket_update",
    "ticket_delete",
    "ticket_messages_read",
    "ticket_messages_create",
    "ticket_messages_update",
    "ticket_messages_delete",
]


def flags_for_entity(entity: str):
    if entity.endswith("_access"):
        return {"can_create": False, "can_read": True, "can_update": False, "can_delete": False}
    if entity.endswith("_edit"):
        return {"can_create": False, "can_read": False, "can_update": True, "can_delete": False}
    if entity.endswith("_create") or entity == "ticket_create":
        return {"can_create": True, "can_read": False, "can_update": False, "can_delete": False}
    if entity.endswith("_update") or entity in {"ticket_pick", "ticket_status", "ticket_update"}:
        return {"can_create": False, "can_read": False, "can_update": True, "can_delete": False}
    if entity.endswith("_delete") or entity == "ticket_delete":
        return {"can_create": False, "can_read": False, "can_update": False, "can_delete": True}
    return {"can_create": False, "can_read": True, "can_update": False, "can_delete": False}
