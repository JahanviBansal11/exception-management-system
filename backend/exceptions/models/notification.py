from django.contrib.auth.models import User
from django.db import models

from .exception_request import ExceptionRequest


class Notification(models.Model):
    TYPE_CHOICES = [
        # Action-triggered
        ('exception_submitted',       'Exception submitted'),
        ('exception_approved',        'Exception approved'),
        ('exception_rejected',        'Exception rejected'),
        ('exception_closed',          'Exception closed'),
        ('exception_modified',        'Modification created'),
        ('exception_extended',        'Extension requested'),
        ('exception_expired',         'Exception expired'),
        ('approval_deadline_passed',  'Approval deadline passed'),
        # Time-based
        ('approval_reminder_50',      'Approval window 50% elapsed'),
        ('approval_reminder_75',      'Approval window 75% elapsed'),
        ('approval_reminder_90',      'Approval window 90% elapsed'),
        ('expiry_reminder',           'Active exception expiry reminder'),
        ('overdue_expired_notice',    'Overdue expired — 14-day grace passed'),
    ]
    SEVERITY_CHOICES = [
        ('info',    'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger',  'Danger'),
    ]

    recipient         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    exception_request = models.ForeignKey(ExceptionRequest, on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=60, choices=TYPE_CHOICES)
    severity          = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    title             = models.CharField(max_length=200)
    message           = models.TextField()
    action_url        = models.CharField(max_length=500, blank=True)
    is_read           = models.BooleanField(default=False)
    read_at           = models.DateTimeField(null=True, blank=True)
    # True when an email was dispatched to the Celery queue alongside this
    # in-app notification.  Does NOT confirm delivery — the async task may
    # still fail.  False = in-app only (e.g. close/expire system events).
    email_queued      = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)
    metadata          = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.title} → {self.recipient}"
