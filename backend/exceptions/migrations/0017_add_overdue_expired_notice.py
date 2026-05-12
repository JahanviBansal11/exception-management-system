from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exceptions', '0016_add_parent_exception_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exceptionrequest',
            name='reminder_stage',
            field=models.CharField(
                choices=[
                    ('None', 'No reminder sent'),
                    ('Reminder_50', '50% of approval window'),
                    ('Reminder_75', '75% of approval window'),
                    ('Reminder_90', '90% of approval window'),
                    ('Expired_Notice', 'Expired notification sent'),
                    ('Overdue_Expired_Notice', 'Overdue expired — 14-day grace window passed'),
                ],
                default='None',
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='reminderlog',
            name='reminder_type',
            field=models.CharField(
                choices=[
                    ('None', 'No reminder sent'),
                    ('Reminder_50', '50% of approval window'),
                    ('Reminder_75', '75% of approval window'),
                    ('Reminder_90', '90% of approval window'),
                    ('Expired_Notice', 'Expired notification sent'),
                    ('Overdue_Expired_Notice', 'Overdue expired — 14-day grace window passed'),
                ],
                max_length=50,
            ),
        ),
    ]
