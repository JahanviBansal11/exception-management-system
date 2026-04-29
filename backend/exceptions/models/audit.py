from django.db import models
from django.contrib.auth.models import User

from .exception_request import ExceptionRequest


class AuditLog(models.Model):
    """Immutable audit trail for every state change."""

    ACTION_CHOICES = [
        ("SUBMIT", "Submitted for Approval"),
        ("APPROVE", "Approved"),
        ("REJECT", "Rejected"),
        ("CLOSE", "Closed"),
        ("EXPIRE", "Expired"),
        ("MODIFY", "Superseded by Modification"),
        ("EXTEND", "Superseded by Extension"),
        ("REMIND", "Reminder Sent"),
        ("ESCALATE", "Escalated"),
        ("UPDATE", "Updated"),
    ]

    exception_request = models.ForeignKey(
        ExceptionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=30, null=True, blank=True)
    new_status = models.CharField(max_length=30, null=True, blank=True)
    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions",
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['exception_request', '-timestamp'], name='auditlog_exc_ts_idx'),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        exc_id = self.exception_request_id or "NA"
        return f"{exc_id} - {self.action_type} @ {self.timestamp}"


class ExceptionCheckpoint(models.Model):
    """Workflow milestone tracking through the approval pipeline."""

    CHECKPOINT_CHOICES = [
        ('exception_requested', 'Exception Requested'),
        ('bu_approval_notified', 'BU CIO Notified'),
        ('bu_approval_decision', 'BU CIO Decision Received'),
        ('risk_assessment_notified', 'Risk Owner Notified'),
        ('risk_assessment_complete', 'Risk Assessment Complete'),
        ('final_decision', 'Final Decision Made'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('escalated', 'Escalated'),
    ]

    exception_request = models.ForeignKey(
        ExceptionRequest, on_delete=models.CASCADE, related_name='checkpoints',
    )
    checkpoint = models.CharField(max_length=40, choices=CHECKPOINT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_checkpoints',
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['exception_request', 'checkpoint'],
                name='unique_exception_checkpoint',
            )
        ]

    def __str__(self):
        return f"{self.exception_request_id} - {self.checkpoint} ({self.status})"


class ReminderLog(models.Model):
    """Delivery tracking for all reminder and notification emails."""

    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('system', 'System Log'),
    ]

    REMINDER_TYPE_CHOICES = ExceptionRequest.REMINDER_STAGE_CHOICES

    exception_request = models.ForeignKey(
        ExceptionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminder_logs",
    )
    sent_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='email')
    reminder_type = models.CharField(max_length=50, choices=REMINDER_TYPE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=[('sent', 'Sent'), ('failed', 'Failed'), ('bounced', 'Bounced')],
        default='sent',
    )
    message_content = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['exception_request', 'sent_at']),
        ]

    def __str__(self):
        exc_id = self.exception_request_id or "NA"
        return f"{exc_id} - {self.reminder_type} ({self.delivery_status})"
