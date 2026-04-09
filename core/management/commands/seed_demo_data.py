from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Role, RolePermission
from core.permission_entities import PERMISSION_ENTITIES, flags_for_entity


class Command(BaseCommand):
    help = "Seed initial required data (Admin user and Roles)"

    ENTITIES = PERMISSION_ENTITIES

    def handle(self, *args, **options):
        User = get_user_model()

        # 1. Create Essential Roles
        admin_role, _ = Role.objects.get_or_create(name="Admin", defaults={"description": "Full access role"})
        support_role, _ = Role.objects.get_or_create(name="Support Agent", defaults={"description": "Support operations"})
        branch_role, _ = Role.objects.get_or_create(name="Branch User", defaults={"description": "Branch ticket requester"})

        # Clear existing permissions for seeded roles to keep rules in sync
        RolePermission.objects.filter(role__in=[admin_role, support_role, branch_role]).delete()

        # 2. Set Permissions for Admin Role
        for entity in self.ENTITIES:
            RolePermission.objects.get_or_create(
                role=admin_role,
                entity=entity,
                defaults=flags_for_entity(entity),
            )

        # 3. Set Permissions for Support Role
        support_entities = {
            "dashboard_read": (False, True, False, False),
            "tickets_list": (False, True, False, False),
            "ticket_details": (False, True, False, False),
            "ticket_pick": (False, False, True, False),
            "ticket_status": (False, False, True, False),
            "ticket_messages_read": (False, True, False, False),
            "ticket_messages_create": (True, False, False, False),
        }
        for entity, flags in support_entities.items():
            RolePermission.objects.get_or_create(
                role=support_role,
                entity=entity,
                defaults={
                    "can_create": flags[0],
                    "can_read": flags[1],
                    "can_update": flags[2],
                    "can_delete": flags[3],
                },
            )

        # 4. Set Permissions for Branch Role
        branch_entities = {
            "ticket_create": (True, False, False, False),
            "tickets_list": (False, True, False, False),
            "ticket_details": (False, True, False, False),
            "ticket_messages_read": (False, True, False, False),
            "ticket_messages_create": (True, False, False, False),
        }
        for entity, flags in branch_entities.items():
            RolePermission.objects.get_or_create(
                role=branch_role,
                entity=entity,
                defaults={
                    "can_create": flags[0],
                    "can_read": flags[1],
                    "can_update": flags[2],
                    "can_delete": flags[3],
                },
            )

        # 5. Create Default Super Admin
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
        if created or superadmin:
            superadmin.set_password(password)
            superadmin.save(update_fields=["password"])
            if created:
                self.stdout.write(self.style.SUCCESS(f"Superadmin '{username}' created successfully."))
            else:
                self.stdout.write(self.style.SUCCESS(f"Superadmin '{username}' password updated."))

        self.stdout.write(self.style.SUCCESS("Initial roles and permissions seeded successfully."))
