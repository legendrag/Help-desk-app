"""Static definitions for demo seed data."""

DEMO_PASSWORD = "demo1234"

DEMO_BRANCH_CODES = ("MAIN", "NORTH", "SOUTH", "EAST")
DEMO_USERNAMES = (
    "lead1",
    "agent1",
    "agent2",
    "agent3",
    "branch_main1",
    "branch_north1",
    "branch_south1",
    "kb_editor1",
)
DEMO_ROLE_NAMES = ("Team Lead", "KB Editor")
DEMO_KB_CATEGORY_NAMES = ("Getting Started", "Troubleshooting", "Policies & Procedures")
DEMO_EMAIL_HOST = "demo-smtp.deskplus.local"

BRANCHES = (
    {"code": "MAIN", "name": "Main Office"},
    {"code": "NORTH", "name": "North Branch"},
    {"code": "SOUTH", "name": "South Branch"},
    {"code": "EAST", "name": "East Branch"},
)

DEPARTMENTS = (
    "IT Support",
    "Human Resources",
    "Facilities",
    "Finance",
)

CATEGORIES = {
    "IT Support": (
        ("Hardware", "medium"),
        ("Software", "medium"),
        ("Network", "high"),
        ("Access & Accounts", "high"),
    ),
    "Human Resources": (
        ("Leave Requests", "low"),
        ("Payroll", "medium"),
        ("Onboarding", "medium"),
    ),
    "Facilities": (
        ("Maintenance", "medium"),
        ("Cleaning", "low"),
        ("Office Supplies", "low"),
    ),
    "Finance": (
        ("Invoices", "medium"),
        ("Expenses", "medium"),
        ("Budget Requests", "high"),
    ),
}

SUPPORT_AGENTS = (
    {"username": "agent1", "first_name": "Sarah", "last_name": "Ahmed", "department": "IT Support"},
    {"username": "agent2", "first_name": "Omar", "last_name": "Hassan", "department": "IT Support"},
    {"username": "agent3", "first_name": "Layla", "last_name": "Mahmoud", "department": "Facilities"},
)

BRANCH_USERS = (
    {"username": "branch_main1", "first_name": "Khaled", "last_name": "Ali", "branch": "MAIN", "department": "IT Support"},
    {"username": "branch_north1", "first_name": "Nour", "last_name": "Ibrahim", "branch": "NORTH", "department": "Human Resources"},
    {"username": "branch_south1", "first_name": "Youssef", "last_name": "Farid", "branch": "SOUTH", "department": "Finance"},
)

KB_CATEGORIES = (
    {"name": "Getting Started", "description": "New user guides and onboarding material."},
    {"name": "Troubleshooting", "description": "Common issues and step-by-step fixes."},
    {"name": "Policies & Procedures", "description": "Official company policies and workflows."},
)

KB_ARTICLES = (
    {
        "title": "How to Create a Support Ticket",
        "category": "Getting Started",
        "content": (
            "<p>Follow these steps to open a ticket:</p>"
            "<ol><li>Log in with your branch account.</li>"
            "<li>Click <strong>New Ticket</strong>.</li>"
            "<li>Select department and category.</li>"
            "<li>Describe the issue clearly and submit.</li></ol>"
        ),
    },
    {
        "title": "Reset Your Password",
        "category": "Troubleshooting",
        "content": (
            "<p>If you cannot sign in, contact IT Support to reset your password.</p>"
            "<p>After reset, you will be prompted to choose a new password on first login.</p>"
        ),
    },
    {
        "title": "VPN Connection Issues",
        "category": "Troubleshooting",
        "content": (
            "<p>Try these steps before opening a ticket:</p>"
            "<ul><li>Restart the VPN client.</li>"
            "<li>Check your internet connection.</li>"
            "<li>Verify your credentials are up to date.</li></ul>"
        ),
    },
    {
        "title": "Ticket Priority Guidelines",
        "category": "Policies & Procedures",
        "content": (
            "<p><strong>Urgent:</strong> Production outage or security incident.</p>"
            "<p><strong>High:</strong> Major workflow blocked for multiple users.</p>"
            "<p><strong>Medium:</strong> Single-user issue with workaround available.</p>"
            "<p><strong>Low:</strong> General requests and enhancements.</p>"
        ),
    },
    {
        "title": "Office Maintenance Request Process",
        "category": "Policies & Procedures",
        "content": (
            "<p>Facilities requests should include location, asset tag (if any), "
            "and photos when possible. Non-urgent requests are handled within 2 business days.</p>"
        ),
    },
)

ANNOUNCEMENTS = (
    {
        "title": "Welcome to DeskPlus",
        "content": "The DeskPlus portal is now live. Use your branch account to submit and track tickets.",
        "target_branch": None,
        "target_department": None,
        "is_active": True,
    },
    {
        "title": "Scheduled Maintenance — North Branch",
        "content": "Network maintenance is planned this Friday from 10 PM to 12 AM. Expect brief connectivity drops.",
        "target_branch": "NORTH",
        "target_department": None,
        "is_active": True,
    },
    {
        "title": "HR Policy Update",
        "content": "Updated leave request guidelines are effective immediately. See the knowledge base for details.",
        "target_branch": None,
        "target_department": "Human Resources",
        "is_active": True,
    },
)
