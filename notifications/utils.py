from accounts.models import User
from tickets.models import Ticket

def get_branch_users(ticket: Ticket):
    return User.objects.filter(
        user_type=User.UserType.BRANCH,
        branch=ticket.branch,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")

def get_department_users(ticket: Ticket):
    return User.objects.filter(
        user_type=User.UserType.SUPPORT,
        department=ticket.department,
        status=User.Status.ACTIVE,
        is_superuser=False,
    ).exclude(role__name__iexact="admin")

def format_status_label(status):
    if not status:
        return None
    try:
        return Ticket.Status(status).label
    except Exception:
        return str(status).replace("_", " ").title()
