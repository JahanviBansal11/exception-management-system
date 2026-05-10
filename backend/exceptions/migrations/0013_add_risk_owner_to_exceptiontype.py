from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds risk_owner FK to ExceptionType.

    Uses SeparateDatabaseAndState with an IF NOT EXISTS guard so that:
    - Fresh test databases: the column is created correctly by the DDL.
    - Production DB: column already exists, IF NOT EXISTS makes it a no-op.
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('exceptions', '0012_populate_role_permissions_matrix'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='exceptiontype',
                    name='risk_owner',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE exceptions_exceptiontype
                        ADD COLUMN IF NOT EXISTS risk_owner_id BIGINT
                        REFERENCES auth_user(id) ON DELETE SET NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE exceptions_exceptiontype
                        DROP COLUMN IF EXISTS risk_owner_id;
                    """,
                ),
            ],
        ),
    ]
