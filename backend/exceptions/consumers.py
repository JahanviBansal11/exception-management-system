import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Per-user WebSocket channel. On connect, joins the user's private group.
    NotificationService.notify() pushes events to that group via the channel layer.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return
        self.group_name = f'notifications_user_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive push from NotificationService via channel layer
    async def notification_push(self, event):
        await self.send(text_data=json.dumps(event['data']))
