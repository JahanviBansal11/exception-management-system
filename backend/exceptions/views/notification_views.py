import uuid

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exceptions.models import Notification
from exceptions.serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        if request.query_params.get('unread') == 'true':
            qs = qs.filter(is_read=False)
        notifications = qs[:50]
        return Response(NotificationSerializer(notifications, many=True).data)


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count})


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, recipient=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        if not notif.is_read:
            notif.is_read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=['is_read', 'read_at'])
        return Response(NotificationSerializer(notif).data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'marked_read': updated})


class WsTicketView(APIView):
    """
    Issue a short-lived, one-time WebSocket connection ticket.

    The frontend calls this endpoint (authenticated via the normal JWT Bearer
    header) and receives a UUID ticket.  It then opens the WebSocket with
    ?ticket=<uuid> instead of passing the long-lived JWT in the URL.

    Why: JWT tokens in query strings appear in plain-text server logs and
    browser history.  A ticket has a 30-second TTL and is deleted the moment
    the WebSocket handshake consumes it, so a leaked URL becomes useless
    almost immediately.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ticket = str(uuid.uuid4())
        ttl = getattr(settings, 'WS_TICKET_TTL', 30)
        cache.set(f'ws_ticket_{ticket}', request.user.id, timeout=ttl)
        return Response({'ticket': ticket})
