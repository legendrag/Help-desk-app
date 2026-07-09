from accounts.models import User
from core.seeds import data


def _upsert_user(username, password, role, user_type, branch=None, department=None, **profile):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@deskplus.local",
            "user_type": user_type,
            "status": User.Status.ACTIVE,
            "role": role,
            "branch": branch,
            "department": department,
            **profile,
        },
    )
    user.role = role
    user.user_type = user_type
    user.status = User.Status.ACTIVE
    user.branch = branch
    user.department = department
    for field, value in profile.items():
        setattr(user, field, value)
    user.set_password(password)
    user.save()
    return user, created


def seed_users(roles, organization, password, stdout=None):
    departments = organization["departments"]
    branches = organization["branches"]
    users = {}

    lead, created = _upsert_user(
        "lead1",
        password,
        roles["team_lead_role"],
        User.UserType.SUPPORT,
        department=departments["IT Support"],
        first_name="Mona",
        last_name="Salem",
        phone="+201000000001",
    )
    users["lead1"] = lead
    if stdout and created:
        stdout.write("  User lead1 (Team Lead)")

    for agent in data.SUPPORT_AGENTS:
        user, created = _upsert_user(
            agent["username"],
            password,
            roles["support_role"],
            User.UserType.SUPPORT,
            department=departments[agent["department"]],
            first_name=agent["first_name"],
            last_name=agent["last_name"],
            phone="+201000000010",
        )
        users[agent["username"]] = user
        if stdout and created:
            stdout.write(f"  User {agent['username']} (Support Agent)")

    for branch_user in data.BRANCH_USERS:
        user, created = _upsert_user(
            branch_user["username"],
            password,
            roles["branch_role"],
            User.UserType.BRANCH,
            branch=branches[branch_user["branch"]],
            department=departments[branch_user["department"]],
            first_name=branch_user["first_name"],
            last_name=branch_user["last_name"],
            phone="+201000000020",
        )
        users[branch_user["username"]] = user
        if stdout and created:
            stdout.write(f"  User {branch_user['username']} (Branch User)")

    kb_editor, created = _upsert_user(
        "kb_editor1",
        password,
        roles["kb_editor_role"],
        User.UserType.SUPPORT,
        department=departments["IT Support"],
        first_name="Hana",
        last_name="Nabil",
    )
    users["kb_editor1"] = kb_editor
    if stdout and created:
        stdout.write("  User kb_editor1 (KB Editor)")

    users["admin"] = roles["superadmin"]
    return users
