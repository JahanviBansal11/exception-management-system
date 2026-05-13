"""
Rename Notification.email_sent → email_queued.

The old name implied confirmed delivery; the real semantic is "an email was
dispatched to the Celery queue alongside this in-app notification."  The new
name is honest about what we actually know.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("exceptions", "0020_reminderlog_unique_sent"),
    ]

    operations = [
        migrations.RenameField(
            model_name="notification",
            old_name="email_sent",
            new_name="email_queued",
        ),
    ]
