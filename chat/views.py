from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from chat.models import Conversation, Message
from chat.api.serializers import ConversationSerializer
from rest_framework.authtoken.views import ObtainAuthToken
from django.db.models import Q
from chat.api.serializers import UserSerializer, MessageSerializer
from chat.api.pagination import MessagePagination
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

User = get_user_model()


class UserViewSet(RetrieveModelMixin, ListModelMixin, UpdateModelMixin, GenericViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    lookup_field = "username"

    # commenting this as it is causing the error of only rendering one conversation in activeConversation page.
    # def get_queryset(self, *args, **kwargs):
    #     assert isinstance(self.request.user.id, int)
    #     return self.queryset.filter(id=self.request.user.id)

    @action(detail=False)
    def me(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)

    @action(detail=False)
    def all(self, request):
        users = User.objects.exclude(id=request.user.id)
        serializer = UserSerializer(users, many=True, context={"request": request})
        return Response(status=status.HTTP_200_OK, data=serializer.data)


class CustomObtainAuthTokenView(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class ConversationViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.none()
    lookup_field = "name"

    # ✅ ADD THESE LINES
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        name = self.kwargs.get("name")
        participants = name.split("__")
        normalized = "__".join(sorted(participants))
        return get_object_or_404(Conversation, name=normalized)

    def get_queryset(self):
        username = self.request.user.username
        # Filter conversations to include only those involving the current user
        # and exclude self-conversations (e.g., "root__root").
        queryset = Conversation.objects.filter(
            Q(name__startswith=f"{username}__")
            | Q(name__endswith=f"__{username}")
            # name__contains=self.request.user.username
        )
        queryset = queryset.exclude(
            name=f"{username}__{username}"
            # name__iexact=f"{self.request.user.username}__{self.request.user.username}"
        )
        return queryset

    def list(self, request, *args, **kwargs):
        """Override list to filter out conversations with null other_user"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        # ✅ Filter out conversations where other_user is None
        data = [conv for conv in serializer.data if conv.get("other_user") is not None]

        return Response(data)

    def get_serializer_context(self):
        """
        Pass the request object to the serializer context.
        """
        return {"request": self.request}

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to prevent accessing self-conversations"""
        conversation_name = kwargs.get("name")
        participants = conversation_name.split("__")

        # Block self-conversations
        if len(participants) == 2 and participants[0] == participants[1]:
            return Response(
                {"error": "Self-conversations are not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().retrieve(request, *args, **kwargs)

    # def get_queryset(self):
    #     current_user = self.request.user.username
    #     print(f"DEBUG: Current user is: {current_user}")

    #     queryset = Conversation.objects.filter(name__contains=current_user).distinct()
    #     print(f"DEBUG: Conversations before filtering: {[c.name for c in queryset]}")

    #     # Exclude self-conversations (e.g., "root__root")
    #     self_conversation_name = f"{current_user}__{current_user}"
    #     print(f"DEBUG: Excluding self-conversation: {self_conversation_name}")
    #     queryset = queryset.exclude(name=self_conversation_name)

    #     print(f"DEBUG: Conversations after filtering: {[c.name for c in queryset]}")
    #     return queryset

    # def get_serializer_context(self):
    #     return {"request": self.request , "user": self.request.user}


class MessageViewSet(ListModelMixin, GenericViewSet):
    """
    This viewset handles listing messages for a specific conversation.
    It filters messages based on the conversation name provided in the query parameters
    and ensures that the requesting user is part of that conversation.

    """

    serializer_class = MessageSerializer
    queryset = Message.objects.none()
    pagination_class = MessagePagination

    def get_queryset(self):
        conversation_name = self.request.GET.get("conversation")
        queryset = (
            Message.objects.filter(
                conversation__name__contains=self.request.user.username,
            )
            .filter(conversation__name=conversation_name)
            .order_by("-timestamp")
        )
        return queryset
