import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Branch, Department, Category, Role
from tickets.models import Ticket, TicketMessage, TicketMergeHistory
from tickets.services import merge_tickets
import uuid

User = get_user_model()

def run_test():
    # Setup basic data
    try:
        user = User.objects.first()
        if not user:
            print("No users found. Creating one.")
            # For testing, we might need a role if custom user model requires it.
            # Assuming standard user for now, or just get any user.
            user = User.objects.create(email="test_merge@example.com", username="test_merge", password="password")
    except Exception as e:
        print("Failed to get/create user:", e)
        return

    branch = Branch.objects.first()
    department = Department.objects.first()
    category = Category.objects.filter(department=department).first() if department else None

    if not all([branch, department, category]):
        print("Required core data (Branch, Department, Category) missing. Please ensure DB is seeded.")
        return

    print("Creating tickets...")
    t1 = Ticket.objects.create(
        title="Primary Ticket",
        description="This is the primary ticket.",
        branch=branch,
        department=department,
        category=category,
        created_by=user,
        priority=Ticket.Priority.MEDIUM
    )
    t1_msg = TicketMessage.objects.create(ticket=t1, sender=user, message="Initial msg on primary.")

    t2 = Ticket.objects.create(
        title="Secondary Ticket 1",
        description="First secondary ticket.",
        branch=branch,
        department=department,
        category=category,
        created_by=user,
        priority=Ticket.Priority.HIGH
    )
    t2_msg = TicketMessage.objects.create(ticket=t2, sender=user, message="Msg on secondary 1.")

    t3 = Ticket.objects.create(
        title="Secondary Ticket 2",
        description="Second secondary ticket.",
        branch=branch,
        department=department,
        category=category,
        created_by=user,
        priority=Ticket.Priority.LOW
    )
    t3_msg = TicketMessage.objects.create(ticket=t3, sender=user, message="Msg on secondary 2.")

    print(f"Created: {t1.ticket_number}, {t2.ticket_number}, {t3.ticket_number}")

    print("Testing merge...")
    try:
        merged_ticket = merge_tickets(t1.id, [t2.id, t3.id], user)
        print("Merge successful!")
        
        # Verify status and priority
        t2.refresh_from_db()
        t3.refresh_from_db()
        print(f"T2 status: {t2.status}, Merged into: {t2.merged_into.id if t2.merged_into else None}")
        print(f"T3 status: {t3.status}, Merged into: {t3.merged_into.id if t3.merged_into else None}")
        print(f"Primary priority: {merged_ticket.priority} (Expected: HIGH)")
        
        # Verify messages
        msgs = merged_ticket.messages.all()
        print(f"Primary ticket messages count: {msgs.count()} (Expected: 5)") # 1 initial + 2 merged + 2 system msgs
        for m in msgs:
            print(f"- {m.message} (system={m.is_system_message})")
            
        # Verify history
        histories = TicketMergeHistory.objects.filter(primary_ticket=merged_ticket)
        print(f"Merge histories count: {histories.count()} (Expected: 2)")
        
    except Exception as e:
        print("Merge failed:", e)

if __name__ == '__main__':
    run_test()
