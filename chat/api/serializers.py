from rest_framework import serializers
from chat.models import Conversation, Message
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username",)


class MessageSerializer(serializers.ModelSerializer):
    from_user = UserSerializer(read_only=True)
    to_user = UserSerializer(read_only=True)
    conversation = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "from_user",
            "to_user",
            "content",
            "timestamp",
            "read",
        )

    def get_conversation(self, obj):
        return str(obj.conversation.id)


class ConversationSerializer(serializers.ModelSerializer):
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "name", "other_user", "last_message")

    def get_other_user(self, obj):
        # ✅ CRITICAL: Get request from context
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        current_user = request.user
        usernames = obj.name.split("__")

        # ✅ Filter out current user from participants
        other_usernames = [name for name in usernames if name != current_user.username]

        # ✅ If no other user found, it's a self-conversation
        if not other_usernames:
            return None

        other_username = other_usernames[0]

        try:
            other_user = User.objects.get(username=other_username)
            return UserSerializer(other_user).data
        except User.DoesNotExist:
            return None

    def get_last_message(self, obj):
        last = getattr(obj, "last_message", None)
        if last is not None:
            return MessageSerializer(last).data
        # Fallback to querying if field doesn't exist
        last_msg = obj.messages.order_by("-timestamp").first()
        return MessageSerializer(last_msg).data if last_msg else None


# from rest_framework import serializers
# from django.contrib.auth import get_user_model
# from chat.models import Message

# User = get_user_model()


# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ["username"]


# class MessageSerializer(serializers.ModelSerializer):
#     from_user = serializers.SerializerMethodField()
#     to_user = serializers.SerializerMethodField()
#     conversation = serializers.SerializerMethodField()

#     class Meta:
#         model = Message
#         fields = (
#             "id",
#             "conversation",
#             "from_user",
#             "to_user",
#             "content",
#             "timestamp",
#             "read",
#         )

#     def get_conversation(self, obj):
#         return str(obj.conversation.id)

#     def get_from_user(self, obj):
#         return UserSerializer(obj.from_user).data

#     def get_to_user(self, obj):
#         return UserSerializer(obj.to_user).data


# from django.contrib.auth import get_user_model
# from chat.models import Conversation


# User = get_user_model()


# class ConversationSerializer(serializers.ModelSerializer):
#     other_user = serializers.SerializerMethodField()
#     last_message = serializers.SerializerMethodField()

#     class Meta:
#         model = Conversation
#         fields = ("id", "name", "other_user", "last_message")

#     def get_last_message(self, obj):
#         messages = obj.messages.all().order_by("-timestamp")
#         if not messages.exists():
#             return None
#         message = messages[0]
#         return MessageSerializer(message).data

#     def get_other_user(self, obj):
#         current_user = self.context["request"].user
#         usernames = obj.name.split("__")

#         print(f"\n=== SERIALIZER DEBUG ===")
#         print(f"Conversation: {obj.name}")
#         print(f"Current user: {current_user.username}")
#         print(f"Participants: {usernames}")
#         other_username = [name for name in usernames if name != current_user.username]

#         if other_username:
#             other_username = other_username[0]
#             print(f"Selected other_username: {other_username}")

#             try:
#                 other_user = User.objects.get(username=other_username)
#                 print(f"Found other_user: {other_user.username}")

#                 return UserSerializer(other_user).data
#             except User.DoesNotExist:
#                 return None  # Should not happen if data is clean

#         # This is a self-conversation (e.g., "root__root").
#         # Return the user's own data so the frontend can filter it.
#         print("WARNING: No other user found (self-conversation)")
#         return None
#         # else:
#         #     return UserSerializer(current_user).data

#         # if not other_username:
#         #     other_username = usernames[0]  # Fallback to the first username if none found

#         # if other_username:
#         #     try:
#         #         other_user = User.objects.get(username=other_username)
#         #         return UserSerializer(other_user).data
#         #     except User.DoesNotExist:
#         #         return None
#         # return None

#     # def get_other_user(self, obj):
#     #     current_user = self.context["request"].user
#     #     usernames = obj.name.split("__")

#     #     for username in usernames:
#     #         if username != current_user.username:
#     #             # This is the other participant
#     #             try:
#     #                 other_user = User.objects.get(username=username)
#     #                 return UserSerializer(other_user).data
#     #             except User.DoesNotExist:
#     #                 return None
#     #     return None
