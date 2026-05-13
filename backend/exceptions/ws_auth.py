"""
WebSocket authentication middleware for Django Channels.

Flow:
  1. Frontend calls POST /api/ws-ticket/ (authenticated REST request) and
     receives a short-lived, one-time UUID ticket stored in Redis.
  2. Frontend opens  ws://.../ws/notifications/?ticket=<uuid>
  3. This middleware reads the ticket, looks up the user_id in the cache,
     deletes the ticket (one-time use), and attaches the user to scope.

Why tickets instead of passing the JWT in the query string?
  Query-string tokens appear in plain text in server access logs and browser
  history.  A ticket has a 30-second TTL and is deleted the moment it is
  consumed, so a leaked URL is useless almost immediately.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _user_from_ticket(ticket: str):
    """Exchange a one-time ticket for the matching User, or AnonymousUser."""
    from django.core.cache import cache
    from django.contrib.auth.models import User

    if not ticket:
        return AnonymousUser()

    cache_key = f"ws_ticket_{ticket}"
    user_id = cache.get(cache_key)
    if not user_id:
        return AnonymousUser()

    # Delete immediately — tickets are single-use
    cache.delete(cache_key)

    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        ticket = query.get("ticket", [None])[0]
        scope["user"] = await _user_from_ticket(ticket)
        return await super().__call__(scope, receive, send)
