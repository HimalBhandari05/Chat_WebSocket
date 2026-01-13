from django.urls import path
from chat.consumers import chatConsumer, NotificationConsumer

websocket_urlpatterns = [
    path("chats/<conversation_name>/", chatConsumer.as_asgi()),
    path("notifications/", NotificationConsumer.as_asgi()),
]