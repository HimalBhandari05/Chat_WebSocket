from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()
from urllib.parse import parse_qs
from channels.db import database_sync_to_async


class TokenAuthentication:
    """
    Simple token based authentication.

    Clients should authenticate by passing the token key in the query parameters.
    For example:

        ?token=401f7ac837da42b97f613d789819ff93537bee6a
    """

    model = None  # if there is any custom token model then here we can use it.

    def get_model(self):
        if self.model is None:
            from rest_framework.authtoken.models import Token

            return Token
        return self.model

    """
    A custom token model may be used, but must have the following properties.

    * key -- The string identifying the token
    * user -- The user to which the token belongs
    """

    def authenticate_credentials(self, key):  # key vaneko token sent by client.
        """
        Token model ma : key , user , expires_at. yo kura haru hunxa.. while fetching the token also fetch the user related to it
        """
        model = self.get_model()
        try:
            token = model.objects.select_related("user").get(key=key)
        except model.DoesNotExist:
            raise AuthenticationFailed(_("Invalid Tokens"))

        if not token.user.is_active:
            raise AuthenticationFailed(_("User inactive or deleted."))

        print("Token User is ", token.user)
        return token.user


@database_sync_to_async
def get_user(scope):
    """
    Scope: dictionary which contains the information of websocket connections
    This returns a user model associated with that scope. else return an anynomous user.
    """

    from django.contrib.auth.models import AnonymousUser

    if "token" not in scope:
        raise ValueError(
            "Cannot find token in scope. You should wrap your consumer in "
            "TokenAuthMiddleware."
        )
    token = scope["token"]
    user = None
    try:
        auth = TokenAuthentication()
        user = auth.authenticate_credentials(token)
    except AuthenticationFailed:
        pass

    return user or AnonymousUser()


class TokenAuthMiddleware:
    """
    Custom middleware that takes a token from the query string and authenticates via
    Django Rest Framework authtoken.
    """

    def __init__(self, app):
        # Store the ASGI application we were passed
        self.app = app

    async def __call__(self, scope, receive, send):
        # Look up user from query string (you should also do things like
        # checking if it is a valid user ID, or if scope["user"] is already
        # populated).
        query_params = parse_qs(scope["query_string"].decode())
        token = query_params["token"][0]
        scope["token"] = token
        scope["user"] = await get_user(scope)
        return await self.app(scope, receive, send)
