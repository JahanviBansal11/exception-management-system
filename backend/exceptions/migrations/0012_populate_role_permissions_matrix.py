from django.db import migrations


REQUESTOR = "Requestor"
APPROVER = "Approver"
RISK_OWNER = "RiskOwner"
SECURITY = "Security"


def _perm_codenames(model_name, actions):
    return [f"{action}_{model_name}" for action in actions]


def forwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    role_matrix = {
        REQUESTOR: {
            "exceptions": {
                "exceptionrequest": ["add", "change", "view"],
                "exceptioncheckpoint": ["view"],
                "businessunit": ["view"],
                "exceptiontype": ["view"],
                "riskissue": ["view"],
                "assettype": ["view"],
                "assetpurpose": ["view"],
                "dataclassification": ["view"],
                "datacomponent": ["view"],
                "internetexposure": ["view"],
            },
        },
        APPROVER: {
            "exceptions": {
                "exceptionrequest": ["view", "change"],
                "exceptioncheckpoint": ["view", "change"],
                "auditlog": ["view"],
                "reminderlog": ["view"],
                "businessunit": ["view"],
                "exceptiontype": ["view"],
                "riskissue": ["view"],
                "assettype": ["view"],
                "assetpurpose": ["view"],
                "dataclassification": ["view"],
                "datacomponent": ["view"],
                "internetexposure": ["view"],
            },
        },
        RISK_OWNER: {
            "exceptions": {
                "exceptionrequest": ["view", "change"],
                "exceptioncheckpoint": ["view", "change"],
                "auditlog": ["view"],
                "businessunit": ["view"],
                "exceptiontype": ["view"],
                "riskissue": ["view"],
                "assettype": ["view"],
                "assetpurpose": ["view"],
                "dataclassification": ["view"],
                "datacomponent": ["view"],
                "internetexposure": ["view"],
            },
        },
        SECURITY: {
            "exceptions": {
                "assetpurpose": ["add", "change", "delete", "view"],
                "assettype": ["add", "change", "delete", "view"],
                "auditlog": ["add", "change", "delete", "view"],
                "businessunit": ["add", "change", "delete", "view"],
                "dataclassification": ["add", "change", "delete", "view"],
                "datacomponent": ["add", "change", "delete", "view"],
                "exception": ["add", "change", "delete", "view"],
                "exceptioncheckpoint": ["add", "change", "delete", "view"],
                "exceptionrequest": ["add", "change", "delete", "view"],
                "exceptiontype": ["add", "change", "delete", "view"],
                "internetexposure": ["add", "change", "delete", "view"],
                "reminderlog": ["add", "change", "delete", "view"],
                "riskissue": ["add", "change", "delete", "view"],
            },
            "auth": {
                "user": ["view", "change"],
                "group": ["view", "change"],
            },
        },
    }

    for role_name, app_map in role_matrix.items():
        group, _ = Group.objects.get_or_create(name=role_name)

        permission_ids = []
        for app_label, model_map in app_map.items():
            for model_name, actions in model_map.items():
                codenames = _perm_codenames(model_name, actions)
                permission_ids.extend(
                    Permission.objects.filter(
                        content_type__app_label=app_label,
                        codename__in=codenames,
                    ).values_list("id", flat=True)
                )

        group.permissions.set(sorted(set(permission_ids)))


def backwards(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for role_name in [REQUESTOR, APPROVER, RISK_OWNER, SECURITY]:
        group = Group.objects.filter(name=role_name).first()
        if group:
            group.permissions.clear()


class Migration(migrations.Migration):

    dependencies = [
        ("exceptions", "0011_standardize_risk_owner_role_cleanup"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
