"""
JWT authentication middleware for Django Channels WebSocket connections.
Reads ?token=<access_token> from the query string and authenticates the user.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def get_user_from_token(token_key):
    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import TokenError
    from django.contrib.auth.models import User
    try:
        token = AccessToken(token_key)
        return User.objects.get(id=token['user_id'])
    except (TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get('query_string', b'').decode())
        token_key = query.get('token', [None])[0]
        scope['user'] = await get_user_from_token(token_key) if token_key else AnonymousUser()
        return await super().__call__(scope, receive, send)
