import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("exceptions", "0015_alter_auditlog_action_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="exceptionrequest",
            name="parent_exception",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="derived_requests",
                to="exceptions.exceptionrequest",
            ),
        ),
    ]
