from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exceptions', '0012_populate_role_permissions_matrix'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationDismissal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_key', models.CharField(max_length=255)),
                ('dismissed_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='dismissed_notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-dismissed_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='notificationdismissal',
            constraint=models.UniqueConstraint(fields=('user', 'event_key'), name='unique_user_notification_dismissal'),
        ),
        migrations.AddIndex(
            model_name='notificationdismissal',
            index=models.Index(fields=['user', 'dismissed_at'], name='notif_dismiss_user_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationdismissal',
            index=models.Index(fields=['user', 'event_key'], name='notif_dismiss_user_key_idx'),
        ),
    ]
