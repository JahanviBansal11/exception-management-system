"""
Data migration: rename the old "approval deadline passed" status value.

Before this migration, WorkflowService.mark_expired() wrote status='Expired' when
the approval window closed without a decision. After the cleanup, that transition now
writes status='ApprovalDeadlinePassed'. The two meanings of 'Expired' are now split:

    ApprovalDeadlinePassed — approval window closed without a decision
    Expired                — approved exception's exception_end_date has passed
                             (wired by the future remediation branch)

Since the remediation branch has never been deployed, ALL existing rows with
status='Expired' were created by the old mark_expired() path and must be renamed.
AuditLog rows are updated in the same pass so the audit trail stays consistent.
"""

from django.db import migrations


def rename_expired_to_approval_deadline_passed(apps, schema_editor):
    ExceptionRequest = apps.get_model('exceptions', 'ExceptionRequest')
    AuditLog = apps.get_model('exceptions', 'AuditLog')

    updated = ExceptionRequest.objects.filter(status='Expired').update(
        status='ApprovalDeadlinePassed'
    )

    # Keep audit trail consistent: EXPIRE actions that recorded new_status='Expired'
    AuditLog.objects.filter(
        action_type='EXPIRE', new_status='Expired'
    ).update(new_status='ApprovalDeadlinePassed')

    # Also fix previous_status references so history reads correctly
    AuditLog.objects.filter(previous_status='Expired').update(
        previous_status='ApprovalDeadlinePassed'
    )

    if updated:
        print(f"  Renamed {updated} ExceptionRequest row(s): Expired → ApprovalDeadlinePassed")


def reverse_rename(apps, schema_editor):
    ExceptionRequest = apps.get_model('exceptions', 'ExceptionRequest')
    AuditLog = apps.get_model('exceptions', 'AuditLog')

    ExceptionRequest.objects.filter(status='ApprovalDeadlinePassed').update(status='Expired')

    AuditLog.objects.filter(
        action_type='EXPIRE', new_status='ApprovalDeadlinePassed'
    ).update(new_status='Expired')

    AuditLog.objects.filter(previous_status='ApprovalDeadlinePassed').update(
        previous_status='Expired'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('exceptions', '0013_add_risk_owner_to_exceptiontype'),
    ]

    operations = [
        migrations.RunPython(
            rename_expired_to_approval_deadline_passed,
            reverse_code=reverse_rename,
        ),
    ]
