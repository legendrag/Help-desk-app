from django.conf import settings

from accounts.models import User
from core.models import Role, RolePermission
from core.permission_entities import PERMISSION_ENTITIES, flags_for_entity
from core.seeds import data


def _apply_entity_permissions(role, entity_flags):
    for entity, flags in entity_flags.items():
        RolePermission.objects.update_or_create(
            role=role,
            entity=entity,
            defaults={
                "can_create": flags[0],
                "can_read": flags[1],
                "can_update": flags[2],
                "can_delete": flags[3],
            },
        )


def seed_roles(stdout=None):
    admin_role, _ = Role.objects.get_or_create(
        name="Admin",
        defaults={"description": "Full access role"},
    )
    support_role, _ = Role.objects.get_or_create(
        name="Support Agent",
        defaults={"description": "Support operations"},
    )
    branch_role, _ = Role.objects.get_or_create(
        name="Branch User",
        defaults={"description": "Branch ticket requester"},
    )
    team_lead_role, _ = Role.objects.get_or_create(
        name="Team Lead",
        defaults={"description": "Senior support with dashboard and team visibility"},
    )
    kb_editor_role, _ = Role.objects.get_or_create(
        name="KB Editor",
        defaults={"description": "Knowledge base author"},
    )

    seeded_roles = [admin_role, support_role, branch_role, team_lead_role, kb_editor_role]
    RolePermission.objects.filter(role__in=seeded_roles).delete()

    for entity in PERMISSION_ENTITIES:
        RolePermission.objects.create(
            role=admin_role,
            entity=entity,
            **flags_for_entity(entity),
        )

    support_entities = {
        "dashboard_read": (False, True, False, False),
        "tickets_list": (False, True, False, False),
        "ticket_details": (False, True, False, False),
        "ticket_pick": (False, False, True, False),
        "ticket_status": (False, False, True, False),
        "ticket_messages_read": (False, True, False, False),
        "ticket_messages_create": (True, False, False, False),
    }
    _apply_entity_permissions(support_role, support_entities)

    branch_entities = {
        "ticket_create": (True, False, False, False),
        "tickets_list": (False, True, False, False),
        "ticket_details": (False, True, False, False),
        "ticket_messages_read": (False, True, False, False),
        "ticket_messages_create": (True, False, False, False),
    }
    _apply_entity_permissions(branch_role, branch_entities)

    team_lead_entities = {
        "dashboard_read": (False, True, False, False),
        "tickets_list": (False, True, False, False),
        "ticket_details": (False, True, False, False),
        "ticket_create": (True, False, False, False),
        "ticket_pick": (False, False, True, False),
        "ticket_status": (False, False, True, False),
        "ticket_update": (False, False, True, False),
        "ticket_messages_read": (False, True, False, False),
        "ticket_messages_create": (True, False, False, False),
        "ticket_messages_update": (False, False, True, False),
    }
    _apply_entity_permissions(team_lead_role, team_lead_entities)

    kb_entities = {
        "tickets_list": (False, True, False, False),
        "ticket_details": (False, True, False, False),
        "ticket_messages_read": (False, True, False, False),
    }
    _apply_entity_permissions(kb_editor_role, kb_entities)

    support_role.can_create_ticket = False
    support_role.can_update_ticket = False
    support_role.can_pick_ticket = True
    support_role.can_update_status = True
    support_role.can_send_message = True
    support_role.can_access_dashboard = True
    support_role.can_access_kb = True
    support_role.can_manage_kb = True
    support_role.save()

    branch_role.can_create_ticket = True
    branch_role.can_send_message = True
    branch_role.save()

    team_lead_role.can_create_ticket = True
    team_lead_role.can_update_ticket = True
    team_lead_role.can_pick_ticket = True
    team_lead_role.can_update_status = True
    team_lead_role.can_send_message = True
    team_lead_role.can_access_dashboard = True
    team_lead_role.can_view_leaderboard = True
    team_lead_role.can_access_kb = True
    team_lead_role.can_manage_kb = True
    team_lead_role.can_manage_news = True
    team_lead_role.save()

    kb_editor_role.can_access_kb = True
    kb_editor_role.can_manage_kb = True
    kb_editor_role.save()

    username = getattr(settings, "DEFAULT_SUPERADMIN_USERNAME", "admin")
    email = getattr(settings, "DEFAULT_SUPERADMIN_EMAIL", "admin@example.com")
    password = getattr(settings, "DEFAULT_SUPERADMIN_PASSWORD", "admin")

    superadmin, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "user_type": User.UserType.SUPPORT,
            "is_superuser": True,
            "is_staff": True,
            "status": User.Status.ACTIVE,
            "role": admin_role,
        },
    )
    superadmin.role = admin_role
    superadmin.is_superuser = True
    superadmin.is_staff = True
    superadmin.status = User.Status.ACTIVE
    superadmin.set_password(password)
    superadmin.save()

    if stdout:
        action = "created" if created else "updated"
        stdout.write(f"  Superadmin '{username}' {action}")

    return {
        "admin_role": admin_role,
        "support_role": support_role,
        "branch_role": branch_role,
        "team_lead_role": team_lead_role,
        "kb_editor_role": kb_editor_role,
        "superadmin": superadmin,
    }
