"""
Add a partial unique constraint to ReminderLog so that two concurrent
Celery Beat workers cannot both claim the same (exception, recipient,
reminder_type) slot.  Only rows with delivery_status='sent' are covered;
failed/bounced rows are intentionally unconstrained so retry attempts can
still be recorded separately.

The RunPython step below deduplicates any existing rows first — for each
(exception, recipient, type) group keep only the most recent 'sent' row
and delete the older ones.  Without this the AddConstraint would fail on
databases that already have duplicates from the old check-then-insert code.
"""

from django.db import migrations, models


def deduplicate_sent_reminder_logs(apps, schema_editor):
    """
    For every (exception_request, sent_to, reminder_type) group that has
    more than one row with delivery_status='sent', keep the newest row
    (highest pk) and delete the rest.
    """
    ReminderLog = apps.get_model('exceptions', 'ReminderLog')

    # Collect all (exception_request_id, sent_to_id, reminder_type) combos
    # that have duplicates so we can resolve them.
    from django.db.models import Count, Max

    dupes = (
        ReminderLog.objects
        .filter(delivery_status='sent')
        .values('exception_request_id', 'sent_to_id', 'reminder_type')
        .annotate(cnt=Count('id'), latest_id=Max('id'))
        .filter(cnt__gt=1)
    )

    for group in dupes:
        ReminderLog.objects.filter(
            exception_request_id=group['exception_request_id'],
            sent_to_id=group['sent_to_id'],
            reminder_type=group['reminder_type'],
            delivery_status='sent',
        ).exclude(pk=group['latest_id']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("exceptions", "0019_notification_db_hardening"),
    ]

    operations = [
        migrations.RunPython(
            deduplicate_sent_reminder_logs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="reminderlog",
            constraint=models.UniqueConstraint(
                fields=["exception_request", "sent_to", "reminder_type"],
                condition=models.Q(delivery_status="sent"),
                name="reminderlog_unique_sent",
            ),
        ),
    ]
