"""
DB hardening for the notification system:
  1. ReminderLog.channel — strip unused sms/in_app choices (were in 0003, never used)
  2. ReminderLog — add covering index for the _already_sent() idempotency query
  3. Notification.exception_request — CASCADE → SET_NULL (preserve history on exception delete)
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("exceptions", "0018_add_notification_model"),
    ]

    operations = [
        # Fix 1: align channel choices with model (removes sms, in_app that were never used)
        migrations.AlterField(
            model_name="reminderlog",
            name="channel",
            field=models.CharField(
                max_length=20,
                choices=[("email", "Email"), ("system", "System Log")],
                default="email",
            ),
        ),

        # Fix 2: covering index for the per-recipient, per-stage deduplication query
        migrations.AddIndex(
            model_name="reminderlog",
            index=models.Index(
                fields=["exception_request", "sent_to", "reminder_type", "delivery_status"],
                name="reminderlog_dedup_idx",
            ),
        ),

        # Fix 3: notification history survives exception deletion
        migrations.AlterField(
            model_name="notification",
            name="exception_request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notifications",
                to="exceptions.exceptionrequest",
            ),
        ),
    ]
