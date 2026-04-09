from django.urls import re_path

from tickets.consumers import TicketChatConsumer, TicketListConsumer

websocket_urlpatterns = [
    re_path(r"ws/tickets/$", TicketListConsumer.as_asgi()),
    re_path(r"ws/tickets/(?P<ticket_id>\d+)/$", TicketChatConsumer.as_asgi()),
]
