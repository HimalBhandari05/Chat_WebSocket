from channels.generic.websocket import AsyncWebsocketConsumer, JsonWebsocketConsumer
from asgiref.sync import async_to_sync
from chat.models import Conversation, Message
from django.contrib.auth import get_user_model
from chat.middleware import get_user
from chat.api.serializers import MessageSerializer

"""
    Group add , group_send is a async function so if we want to use it for jsonwebsconsumer we have to use asynctosync (wraps the function you want to call).
"""

User = get_user_model()

import json
from uuid import UUID


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)


class chatConsumer(JsonWebsocketConsumer):

    def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            self.close()
            return

        conversation_name = self.scope["url_route"]["kwargs"]["conversation_name"]
        participants = conversation_name.split("__")
        normalized_name = "__".join(sorted(participants))

        if len(participants) != 2 or participants[0] == participants[1]:
            print(
                f"Connection rejected: Invalid conversation name '{conversation_name}'."
            )
            self.close()
            return

        # ✅ MUST set BEFORE using
        conversation, created = Conversation.objects.get_or_create(name=normalized_name)
        self.conversation = conversation
        self.conversation_name = normalized_name
        self.user = user

        self.accept()

        # Add user to the conversation's channel group
        async_to_sync(self.channel_layer.group_add)(
            normalized_name,
            self.channel_name,
        )

        self.send_json(
            {
                "type": "online_user_list",
                "users": [u.username for u in self.conversation.online.all()],
            }
        )

        async_to_sync(self.channel_layer.group_send)(
            normalized_name,
            {
                "type": "user_join",
                "user": user.username,
            },
        )

        self.conversation.online.add(user)
        print(f"Connected to conversation: {normalized_name}")

        # Send connection confirmation
        self.send_json({"type": "welcome_message", "message": "You are connected."})

        # Send message history
        messages = self.conversation.messages.all().order_by("-timestamp")[0:50]
        message_count = self.conversation.messages.count()
        self.send_json(
            {
                "type": "last_50_messages",
                "messages": MessageSerializer(messages, many=True).data,
                "has_more": message_count > 50,
            }
        )

    # def disconnect(self, code):
    #     """
    #     Handles WebSocket disconnections.
    #     """
    #     conversation_name = self.scope["url_route"]["kwargs"]["conversation_name"]
    #     # Remove user from the channel group
    #     async_to_sync(self.channel_layer.group_discard)(
    #         conversation_name,
    #         self.channel_name,
    #     )
    #     print(f"Disconnected from {conversation_name}")

    def disconnect(self, code):
        # This method is called automatically when the websocket closes
        if hasattr(self, "user") and self.user.is_authenticated:
            # Notify other users in the conversation
            async_to_sync(self.channel_layer.group_send)(
                self.conversation_name,
                {
                    "type": "user_leave",
                    "user": self.user.username,
                },
            )

            # Remove user from online users list (ManyToManyField)
            if hasattr(self, "conversation"):
                self.conversation.online.remove(self.user)

        # Always discard from group
        async_to_sync(self.channel_layer.group_discard)(
            self.conversation_name,
            self.channel_name,
        )

    def receive_json(self, content, **kwargs):
        """
        Handles incoming JSON messages from the client.
        """
        message_type = content.get("type")
        user = self.scope["user"]
        conversation_name = self.scope["url_route"]["kwargs"]["conversation_name"]

        if message_type == "typing":
            async_to_sync(self.channel_layer.group_send)(
                self.conversation_name,
                {
                    "type": "typing",
                    "user": self.user.username,
                    "typing": content["typing"],
                },
            )

        if message_type == "chat_message":
            conversation, created = Conversation.objects.get_or_create(
                name=conversation_name
            )

            # Find the receiver
            usernames = conversation_name.split("__")
            receiver_username = next(
                (name for name in usernames if name != user.username), user.username
            )
            receiver = User.objects.get(username=receiver_username)

            # Create the message
            message = Message.objects.create(
                from_user=user,
                to_user=receiver,
                content=content["message"],
                conversation=conversation,
            )
            conversation.last_message = message
            conversation.save()
            # Broadcast the new message to the channel group
            async_to_sync(self.channel_layer.group_send)(
                conversation_name,
                {
                    "type": "chat_message_echo",
                    "name": user.username,
                    "message": MessageSerializer(message).data,
                },
            )
            print(f"Broadcasting message to conversation: {conversation_name}")

            # Send notification to receiver
            notification_group_name = receiver.username + "__notifications"
            async_to_sync(self.channel_layer.group_send)(
                notification_group_name,
                {
                    "type": "new_message_notification",
                    "name": user.username,
                    "message": MessageSerializer(message).data,
                },
            )

        if message_type == "read_messages":
            messages_to_me = self.conversation.messages.filter(to_user=self.user)
            messages_to_me.update(read=True)

            # Update the unread message count
            unread_count = Message.objects.filter(to_user=self.user, read=False).count()
            async_to_sync(self.channel_layer.group_send)(
                self.user.username + "__notifications",
                {
                    "type": "unread_count",
                    "unread_count": unread_count,
                },
            )

    def chat_message_echo(self, event):
        """
        Handler for messages broadcast to the group. Sends the message to the client.
        """
        self.send_json(event)

    @classmethod
    def encode_json(cls, content):
        return json.dumps(content, cls=UUIDEncoder)

    def user_join(self, event):
        """
        Triggered when someone joins the conversation
        """
        self.send_json(
            {
                "type": "user_join",
                "user": event["user"],
            }
        )

    def user_leave(self, event):
        """
        Triggered when someone leaves the conversation
        """
        self.send_json(
            {
                "type": "user_leave",
                "user": event["user"],
            }
        )

    def typing(self, event):
        self.send_json(event)


class NotificationConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.user = None
        self.notification_group_name = None

    def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            return

        self.accept()

        # Private notification group
        self.notification_group_name = self.user.username + "__notifications"
        async_to_sync(self.channel_layer.group_add)(
            self.notification_group_name,
            self.channel_name,
        )

        # Send count of unread messages
        unread_count = Message.objects.filter(to_user=self.user, read=False).count()
        self.send_json(
            {
                "type": "unread_count",
                "unread_count": unread_count,
            }
        )

    def disconnect(self, code):
        async_to_sync(self.channel_layer.group_discard)(
            self.notification_group_name,
            self.channel_name,
        )
        return super().disconnect(code)

    def new_message_notification(self, event):
        self.send_json(event)

    def unread_count(self, event):
        self.send_json(event)
