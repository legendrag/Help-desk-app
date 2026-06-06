from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from tickets.models import Ticket, TicketMessage, TicketMergeHistory, TicketStatusHistory


@transaction.atomic
def merge_tickets(primary_ticket_id, secondary_ticket_ids, user):
    """
    Merges one or more secondary tickets into a primary ticket.

    Args:
        primary_ticket_id: ID of the primary ticket
        secondary_ticket_ids: List of IDs of the secondary tickets
        user: The user performing the merge

    Returns:
        Ticket: The primary ticket after the merge is completed.

    Raises:
        ValidationError: If the merge is invalid (e.g. duplicate IDs, already merged tickets).
    """
    if primary_ticket_id in secondary_ticket_ids:
        raise ValidationError("Primary ticket cannot be in the list of secondary tickets.")

    try:
        primary_ticket = Ticket.objects.select_for_update().get(id=primary_ticket_id)
    except Ticket.DoesNotExist:
        raise ValidationError("Primary ticket not found.")

    if primary_ticket.status == Ticket.Status.CLOSED:
        raise ValidationError("Cannot merge into a closed ticket.")

    if primary_ticket.merged_into is not None:
        raise ValidationError("Cannot merge into a ticket that is already merged.")

    # Remove duplicates from secondary_ticket_ids just in case
    secondary_ticket_ids = list(set(secondary_ticket_ids))
    secondary_tickets = Ticket.objects.select_for_update().filter(id__in=secondary_ticket_ids)

    if secondary_tickets.count() != len(secondary_ticket_ids):
        raise ValidationError("One or more secondary tickets not found.")

    priority_order = {
        Ticket.Priority.LOW: 1,
        Ticket.Priority.MEDIUM: 2,
        Ticket.Priority.HIGH: 3,
        Ticket.Priority.URGENT: 4,
    }
    highest_priority = primary_ticket.priority

    for st in secondary_tickets:
        if st.merged_into is not None:
            raise ValidationError(f"Secondary ticket {st.ticket_number} is already merged.")

        # Determine if priority needs an upgrade
        if priority_order[st.priority] > priority_order[highest_priority]:
            highest_priority = st.priority

        # Move messages (and associated attachments/comments) to primary ticket
        TicketMessage.objects.filter(ticket=st).update(ticket=primary_ticket)

        # Update secondary ticket status and relation
        st.status = Ticket.Status.MERGED
        st.closed_at = timezone.now()
        st.merged_into = primary_ticket
        st.save()

        # Insert system message in primary ticket
        TicketMessage.objects.create(
            ticket=primary_ticket,
            sender=user,
            message=f"Merged messages from ticket #{st.ticket_number}",
            is_system_message=True,
        )

        # Create status history record for secondary ticket
        TicketStatusHistory.objects.create(
            ticket=st,
            status=Ticket.Status.MERGED,
            changed_by=user,
        )

        # Create audit log record
        TicketMergeHistory.objects.create(
            primary_ticket=primary_ticket,
            secondary_ticket=st,
            merged_by=user,
        )

    # Optional: Update primary ticket priority if it should be upgraded
    if primary_ticket.priority != highest_priority:
        primary_ticket.priority = highest_priority
        primary_ticket.save()

    return primary_ticket
