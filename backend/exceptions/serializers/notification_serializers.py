from rest_framework import serializers
from exceptions.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    exception_id = serializers.IntegerField(source='exception_request_id', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'severity', 'title', 'message',
            'action_url', 'is_read', 'read_at', 'exception_id', 'created_at', 'metadata',
        ]
        read_only_fields = fields
