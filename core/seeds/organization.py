from core.models import Branch, Category, Department
from core.seeds import data


def seed_organization(stdout=None):
    branches = {}
    for item in data.BRANCHES:
        branch, created = Branch.objects.get_or_create(
            code=item["code"],
            defaults={"name": item["name"]},
        )
        if branch.name != item["name"]:
            branch.name = item["name"]
            branch.save(update_fields=["name"])
        branches[item["code"]] = branch
        if stdout and created:
            stdout.write(f"  Branch {branch.code}")

    departments = {}
    for name in data.DEPARTMENTS:
        department, created = Department.objects.get_or_create(name=name)
        departments[name] = department
        if stdout and created:
            stdout.write(f"  Department {department.name}")

    categories = {}
    for department_name, category_rows in data.CATEGORIES.items():
        department = departments[department_name]
        for category_name, default_priority in category_rows:
            category, created = Category.objects.get_or_create(
                department=department,
                name=category_name,
                defaults={"default_priority": default_priority},
            )
            if category.default_priority != default_priority:
                category.default_priority = default_priority
                category.save(update_fields=["default_priority"])
            categories[(department_name, category_name)] = category
            if stdout and created:
                stdout.write(f"  Category {department.name} / {category.name}")

    return {
        "branches": branches,
        "departments": departments,
        "categories": categories,
    }
