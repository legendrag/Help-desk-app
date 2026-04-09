from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_ticket_message(ticket_id, payload):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    group_name = f"ticket_{ticket_id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "chat.event",
            "event": "message_created",
            "payload": payload,
        },
    )


def broadcast_ticket_list_event(event_type, payload, branch_id=None, department_id=None):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    group_names = {"ticket_list"}
    if branch_id:
        group_names.add(f"ticket_list_branch_{branch_id}")
    if department_id:
        group_names.add(f"ticket_list_department_{department_id}")

    for group_name in group_names:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "ticket.event",
                "event": event_type,
                "payload": payload,
            },
        )
