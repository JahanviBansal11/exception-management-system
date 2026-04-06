from django.db import migrations


CANONICAL_RISK_OWNER_GROUP = "RiskOwner"
LEGACY_RISK_OWNER_GROUP = "Risk Owner"
FALLBACK_USERNAME = "system"
FALLBACK_EMAIL = "system@local.invalid"


def forwards(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    ExceptionRequest = apps.get_model("exceptions", "ExceptionRequest")

    fallback_user, _ = User.objects.get_or_create(
        username=FALLBACK_USERNAME,
        defaults={
            "email": FALLBACK_EMAIL,
            "is_active": True,
        },
    )

    risk_owner_user_ids = list(
        User.objects.filter(groups__name__in=[CANONICAL_RISK_OWNER_GROUP, LEGACY_RISK_OWNER_GROUP])
        .exclude(id=fallback_user.id)
        .values_list("id", flat=True)
        .distinct()
    )

    if risk_owner_user_ids:
        ExceptionRequest.objects.filter(risk_owner_id__in=risk_owner_user_ids).update(risk_owner_id=fallback_user.id)
        ExceptionRequest.objects.filter(assigned_approver_id__in=risk_owner_user_ids).update(assigned_approver_id=fallback_user.id)
        ExceptionRequest.objects.filter(requested_by_id__in=risk_owner_user_ids).update(requested_by_id=fallback_user.id)
        User.objects.filter(id__in=risk_owner_user_ids).delete()

    Group.objects.filter(name__in=[CANONICAL_RISK_OWNER_GROUP, LEGACY_RISK_OWNER_GROUP]).delete()
    Group.objects.get_or_create(name=CANONICAL_RISK_OWNER_GROUP)


def backwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=CANONICAL_RISK_OWNER_GROUP)


class Migration(migrations.Migration):

    dependencies = [
        ("exceptions", "0010_rename_exceptions__excepti_086844_idx_auditlog_exc_ts_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
