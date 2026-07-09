from django.contrib.auth import get_user_model

from accounts.models import User
from core.models import Branch, EmailSetting, Role
from core.seeds import data
from core.seeds.email import seed_email
from core.seeds.kb import seed_kb
from core.seeds.news import seed_news
from core.seeds.notifications import seed_notifications
from core.seeds.organization import seed_organization
from core.seeds.roles import seed_roles
from core.seeds.tickets import seed_tickets
from core.seeds.users import seed_users
from kb.models import Article, Category as KBCategory
from news.models import Announcement
from notifications.models import InAppNotification
from tickets.models import Ticket, TicketMessage, TicketStatusHistory


def clear_seed(stdout=None):
    User = get_user_model()

    demo_users = User.objects.filter(username__in=data.DEMO_USERNAMES)
    demo_user_ids = list(demo_users.values_list("id", flat=True))

    if demo_user_ids:
        InAppNotification.objects.filter(recipient_id__in=demo_user_ids).delete()

    demo_tickets = Ticket.objects.filter(created_by_id__in=demo_user_ids)
    ticket_ids = list(demo_tickets.values_list("id", flat=True))
    if ticket_ids:
        TicketMessage.objects.filter(ticket_id__in=ticket_ids).delete()
        TicketStatusHistory.objects.filter(ticket_id__in=ticket_ids).delete()
        Article.objects.filter(related_ticket_id__in=ticket_ids).update(related_ticket=None)
        demo_tickets.delete()

    Article.objects.filter(title__in=[item["title"] for item in data.KB_ARTICLES]).delete()
    KBCategory.objects.filter(name__in=data.DEMO_KB_CATEGORY_NAMES).delete()
    Announcement.objects.filter(title__in=[item["title"] for item in data.ANNOUNCEMENTS]).delete()
    EmailSetting.objects.filter(smtp_host=data.DEMO_EMAIL_HOST).delete()

    demo_users.delete()
    Role.objects.filter(name__in=data.DEMO_ROLE_NAMES).delete()

    for branch_code in data.DEMO_BRANCH_CODES:
        branch = Branch.objects.filter(code=branch_code).first()
        if not branch:
            continue
        if branch.tickets.exists() or branch.users.exists():
            if stdout:
                stdout.write(f"  Skipped branch {branch_code} (still referenced)")
            continue
        branch.delete()

    for department_name in data.DEPARTMENTS:
        from core.models import Category, Department

        department = Department.objects.filter(name=department_name).first()
        if not department:
            continue
        if department.tickets.exists() or department.users.exists():
            if stdout:
                stdout.write(f"  Skipped department {department_name} (still referenced)")
            continue
        Category.objects.filter(department=department).delete()
        department.delete()

    if stdout:
        stdout.write("Demo seed data cleared.")


def run_seed(
    *,
    password=None,
    skip_tickets=False,
    skip_notifications=False,
    stdout=None,
    style=None,
):
    password = password or data.DEMO_PASSWORD

    def write(section):
        if stdout:
            stdout.write(section)

    def success(message):
        if stdout and style:
            stdout.write(style.SUCCESS(message))

    write("Seeding roles and admin...")
    roles = seed_roles(stdout=stdout)

    write("Seeding organization (branches, departments, categories)...")
    organization = seed_organization(stdout=stdout)

    write("Seeding users...")
    users = seed_users(roles, organization, password, stdout=stdout)

    tickets = {}
    if not skip_tickets:
        write("Seeding tickets...")
        tickets = seed_tickets(organization, users, stdout=stdout)

    write("Seeding knowledge base...")
    seed_kb(users, tickets=tickets, stdout=stdout)

    write("Seeding announcements...")
    seed_news(organization, users, stdout=stdout)

    write("Seeding email settings...")
    seed_email(stdout=stdout)

    if not skip_notifications and tickets:
        write("Seeding notifications...")
        seed_notifications(users, tickets, stdout=stdout)

    success("")
    success("System seed completed successfully.")
    success(f"Demo users password: {password}")
    success("Accounts: admin / admin  |  lead1, agent1-3, branch_* , kb_editor1")
