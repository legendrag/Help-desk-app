from django.urls import reverse

from notifications.models import InAppNotification
from core.seeds import data


def seed_notifications(users, tickets, stdout=None):
    agent1 = users["agent1"]
    branch_main = users["branch_main1"]
    notifications = []

    samples = (
        {
            "recipient": agent1,
            "title": "New ticket assigned",
            "message": "VPN disconnects every 10 minutes — assigned to you.",
            "link": reverse("ticket_detail", kwargs={"ticket_id": tickets["vpn_north"].pk}),
            "notification_type": InAppNotification.NotificationType.TICKET_PICKED,
            "is_read": False,
        },
        {
            "recipient": agent1,
            "title": "New message on ticket",
            "message": "branch_north1 replied on VPN ticket.",
            "link": reverse("ticket_detail", kwargs={"ticket_id": tickets["vpn_north"].pk}),
            "notification_type": InAppNotification.NotificationType.MESSAGE,
            "is_read": True,
        },
        {
            "recipient": branch_main,
            "title": "Ticket update",
            "message": "Your printer ticket is still open and queued.",
            "link": reverse("ticket_detail", kwargs={"ticket_id": tickets["printer_main"].pk}),
            "notification_type": InAppNotification.NotificationType.STATUS_CHANGE,
            "is_read": False,
        },
        {
            "recipient": users["lead1"],
            "title": "Dashboard snapshot",
            "message": "3 tickets are waiting for agent pickup across branches.",
            "link": reverse("dashboard"),
            "notification_type": InAppNotification.NotificationType.GENERAL,
            "is_read": False,
        },
    )

    for sample in samples:
        notification, created = InAppNotification.objects.get_or_create(
            recipient=sample["recipient"],
            title=sample["title"],
            defaults={
                "message": sample["message"],
                "link": sample["link"],
                "notification_type": sample["notification_type"],
                "is_read": sample["is_read"],
            },
        )
        notification.message = sample["message"]
        notification.link = sample["link"]
        notification.notification_type = sample["notification_type"]
        notification.is_read = sample["is_read"]
        notification.save()
        notifications.append(notification)
        if stdout and created:
            stdout.write(f"  Notification for {notification.recipient.username}")

    return notifications
