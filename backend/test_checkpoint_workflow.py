"""Comprehensive functional validations for Option B workflow."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grc_backend.settings')
django.setup()

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.utils import timezone
from rest_framework.test import APIClient

if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver']

from exceptions.models import (
    ExceptionRequest,
    BusinessUnit,
    ExceptionType,
    DataClassification,
    AssetType,
    AssetPurpose,
    InternetExposure,
    RiskIssue,
    DataComponent,
)
from exceptions.serializers import ExceptionRequestSerializer
from exceptions.services.reminder_engine import ReminderEngine
from exceptions.services.escalation_engine import EscalationEngine
from exceptions.services.notification_service import NotificationService


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def setup_test_data():
    print("[SETUP] Creating test users and reference data...")

    requestor = User.objects.create_user('test_requestor', 'req@test.com', 'testpass123')
    approver = User.objects.create_user('test_approver', 'app@test.com', 'testpass123')
    risk_owner = User.objects.create_user('test_riskowner', 'risk@test.com', 'testpass123')
    outsider = User.objects.create_user('test_outsider', 'out@test.com', 'testpass123')
    system_user, _ = User.objects.get_or_create(username='system', defaults={'email': 'system@test.com'})

    Group.objects.get_or_create(name='Requestor')
    Group.objects.get_or_create(name='Approver')
    Group.objects.get_or_create(name='Risk Owner')
    Group.objects.get_or_create(name='Security')

    bu, _ = BusinessUnit.objects.get_or_create(
        bu_code='FIN',
        defaults={'name': 'Finance', 'cio': approver}
    )
    exc_type, _ = ExceptionType.objects.get_or_create(
        name='Firewall Exception',
        defaults={'approval_sla_days': 28}
    )
    risk_issue, _ = RiskIssue.objects.get_or_create(
        title='Firewall Rule Deviation',
        defaults={'description': 'Non-standard firewall rule needed', 'inherent_risk_score': 6}
    )

    high_data_class, _ = DataClassification.objects.get_or_create(level='Sensitive', defaults={'weight': 3})
    high_asset_type, _ = AssetType.objects.get_or_create(name='Server', defaults={'weight': 8})
    high_asset_purpose, _ = AssetPurpose.objects.get_or_create(name='Database', defaults={'weight': 7})
    high_data_component, _ = DataComponent.objects.get_or_create(name='Customer DB', defaults={'weight': 9})
    high_internet_exp, _ = InternetExposure.objects.get_or_create(label='Internal Only', defaults={'weight': 2})

    low_data_class, _ = DataClassification.objects.get_or_create(level='Public', defaults={'weight': 1})
    low_asset_type, _ = AssetType.objects.get_or_create(name='Workstation', defaults={'weight': 1})
    low_asset_purpose, _ = AssetPurpose.objects.get_or_create(name='Documentation', defaults={'weight': 1})
    low_data_component, _ = DataComponent.objects.get_or_create(name='User Guide', defaults={'weight': 1})
    low_internet_exp, _ = InternetExposure.objects.get_or_create(label='No Exposure', defaults={'weight': 1})

    return {
        'requestor': requestor,
        'approver': approver,
        'risk_owner': risk_owner,
        'outsider': outsider,
        'system_user': system_user,
        'bu': bu,
        'exc_type': exc_type,
        'risk_issue': risk_issue,
        'high': {
            'data_class': high_data_class,
            'asset_type': high_asset_type,
            'asset_purpose': high_asset_purpose,
            'data_component': high_data_component,
            'internet_exp': high_internet_exp,
        },
        'low': {
            'data_class': low_data_class,
            'asset_type': low_asset_type,
            'asset_purpose': low_asset_purpose,
            'data_component': low_data_component,
            'internet_exp': low_internet_exp,
        },
    }


def create_exception(test_data, profile='high', suffix=''):
    p = test_data[profile]
    exc = ExceptionRequest.objects.create(
        requested_by=test_data['requestor'],
        business_unit=test_data['bu'],
        exception_type=test_data['exc_type'],
        risk_issue=test_data['risk_issue'],
        short_description=f'Test exception {profile} {suffix}'.strip(),
        reason_for_exception='Validation scenario',
        asset_type=p['asset_type'],
        asset_purpose=p['asset_purpose'],
        data_classification=p['data_class'],
        internet_exposure=p['internet_exp'],
        number_of_assets=1,
        exception_end_date=timezone.now() + timezone.timedelta(days=30),
        assigned_approver=test_data['approver'],
        risk_owner=test_data['risk_owner'],
    )
    exc.data_components.add(p['data_component'])
    exc.refresh_from_db()
    return exc


def test_high_branch_with_checkpoints(test_data):
    print("\n[VALIDATION] High/Critical branch end-to-end")
    exc = create_exception(test_data, profile='high', suffix='high-path')

    exc.submit(test_data['requestor'])
    assert_true(exc.status == 'Submitted', 'Expected Submitted after submit')

    exc.bu_approve(test_data['approver'], notes='BU CIO notes for risk owner')
    exc.refresh_from_db()
    assert_true(exc.status == 'AwaitingRiskOwner', 'Expected AwaitingRiskOwner for high/critical after BU approve')

    exc.risk_approve(test_data['risk_owner'], notes='Approved by risk owner')
    exc.refresh_from_db()
    assert_true(exc.status == 'Approved', 'Expected Approved after risk owner approval')

    serializer_data = ExceptionRequestSerializer(exc).data
    assert_true(len(serializer_data['checkpoints']) == 6, 'Expected 6 checkpoints in serializer payload')

    print("  ✓ High branch transitions validated")


def test_low_medium_shortcut_branch(test_data):
    print("\n[VALIDATION] Low/Medium shortcut branch")
    exc = create_exception(test_data, profile='low', suffix='low-path')

    exc.submit(test_data['requestor'])
    exc.bu_approve(test_data['approver'], notes='BU CIO notes for low/medium approval')
    exc.refresh_from_db()

    assert_true(exc.status == 'Approved', 'Expected direct Approved for low/medium after BU approval')

    risk_notified = exc.checkpoints.get(checkpoint='risk_assessment_notified')
    risk_complete = exc.checkpoints.get(checkpoint='risk_assessment_complete')
    final_decision = exc.checkpoints.get(checkpoint='final_decision')

    assert_true(risk_notified.status == 'skipped', 'Expected risk_assessment_notified to be skipped on low/medium path')
    assert_true(risk_complete.status == 'skipped', 'Expected risk_assessment_complete to be skipped on low/medium path')
    assert_true(final_decision.status == 'completed', 'Expected final_decision completed on low/medium path')
    assert_true(final_decision.completed_by_id == test_data['approver'].id, 'Expected BU approver as final decider on low/medium path')

    print("  ✓ Low/Medium shortcut validated")


def test_reject_flows(test_data):
    print("\n[VALIDATION] Reject flows (BU reject and Risk reject)")

    bu_reject_exc = create_exception(test_data, profile='low', suffix='bu-reject')
    bu_reject_exc.submit(test_data['requestor'])
    bu_reject_exc.bu_reject(test_data['approver'], notes='Insufficient justification')
    bu_reject_exc.refresh_from_db()
    assert_true(bu_reject_exc.status == 'Rejected', 'Expected Rejected after BU reject')

    risk_reject_exc = create_exception(test_data, profile='high', suffix='risk-reject')
    risk_reject_exc.submit(test_data['requestor'])
    risk_reject_exc.bu_approve(test_data['approver'], notes='Escalating due to high residual risk')
    risk_reject_exc.risk_reject(test_data['risk_owner'], notes='Rejected by risk owner')
    risk_reject_exc.refresh_from_db()
    assert_true(risk_reject_exc.status == 'Rejected', 'Expected Rejected after risk owner reject')

    print("  ✓ Reject flows validated")


def test_api_permissions(test_data):
    print("\n[VALIDATION] API permission enforcement (403 checks)")
    client = APIClient()

    exc_for_bu = create_exception(test_data, profile='high', suffix='api-bu')
    exc_for_bu.submit(test_data['requestor'])

    client.force_authenticate(user=test_data['outsider'])
    resp = client.post(f'/api/exceptions/{exc_for_bu.id}/bu_approve/')
    assert_true(resp.status_code == 404, f'Expected 404 for outsider BU approve (queryset scoping), got {resp.status_code}')

    exc_for_risk = create_exception(test_data, profile='high', suffix='api-risk')
    exc_for_risk.submit(test_data['requestor'])
    exc_for_risk.bu_approve(test_data['approver'], notes='Needs risk owner assessment')

    client.force_authenticate(user=test_data['outsider'])
    resp = client.post(f'/api/exceptions/{exc_for_risk.id}/risk_assess/', {'notes': 'x'}, format='json')
    assert_true(resp.status_code == 404, f'Expected 404 for outsider risk assess (queryset scoping), got {resp.status_code}')

    client.force_authenticate(user=test_data['risk_owner'])
    resp = client.post(f'/api/exceptions/{exc_for_risk.id}/risk_assess/', {'notes': 'approved'}, format='json')
    assert_true(resp.status_code == 200, f'Expected 200 for risk owner risk assess, got {resp.status_code}')

    print("  ✓ API role permissions validated")


def test_scheduler_behaviour(test_data):
    print("\n[VALIDATION] Scheduler behaviour (reminder, escalation, auto-close)")

    original_reminder_sender = NotificationService.send_approval_reminder
    original_expired_sender = NotificationService.send_approval_expired_notification
    NotificationService.send_approval_reminder = staticmethod(lambda exception_request, reminder_type: True)
    NotificationService.send_approval_expired_notification = staticmethod(lambda exception_request: True)

    try:
        reminder_exc = create_exception(test_data, profile='high', suffix='reminder')
        reminder_exc.submit(test_data['requestor'])
        ExceptionRequest.objects.filter(pk=reminder_exc.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=20),
            approval_deadline=timezone.now() + timezone.timedelta(days=8),
        )
        reminder_exc.refresh_from_db()
        sent_count = ReminderEngine.evaluate_pending_approvals()
        reminder_exc.refresh_from_db()
        assert_true(sent_count >= 1, 'Expected at least one reminder sent')
        assert_true(reminder_exc.reminder_stage in {'Reminder_50', 'Reminder_75', 'Reminder_90'}, 'Expected reminder stage to advance')

        expired_exc = create_exception(test_data, profile='high', suffix='expire')
        expired_exc.submit(test_data['requestor'])
        ExceptionRequest.objects.filter(pk=expired_exc.pk).update(
            approval_deadline=timezone.now() - timezone.timedelta(minutes=5),
            reminder_stage='Reminder_90'
        )
        escalated_count = EscalationEngine.escalate_expired_approvals()
        expired_exc.refresh_from_db()
        assert_true(escalated_count >= 1, 'Expected at least one escalation')
        assert_true(expired_exc.status == 'Expired', 'Expected status Expired after escalation')

        close_exc = create_exception(test_data, profile='low', suffix='auto-close')
        close_exc.submit(test_data['requestor'])
        close_exc.bu_approve(test_data['approver'], notes='BU approval rationale captured')
        ExceptionRequest.objects.filter(pk=close_exc.pk).update(
            exception_end_date=timezone.now() - timezone.timedelta(days=1)
        )
        closed_count = EscalationEngine.close_expired_exceptions()
        close_exc.refresh_from_db()
        assert_true(closed_count >= 1, 'Expected at least one auto-close')
        assert_true(close_exc.status == 'Closed', 'Expected status Closed after auto-close job')

    finally:
        NotificationService.send_approval_reminder = original_reminder_sender
        NotificationService.send_approval_expired_notification = original_expired_sender

    print("  ✓ Scheduler behaviour validated")


if __name__ == '__main__':
    try:
        ExceptionRequest.objects.filter(requested_by__username__startswith='test_').delete()
        User.objects.filter(username__startswith='test_').delete()

        data = setup_test_data()
        test_high_branch_with_checkpoints(data)
        test_low_medium_shortcut_branch(data)
        test_reject_flows(data)
        test_api_permissions(data)
        test_scheduler_behaviour(data)

        print("\n" + "=" * 72)
        print("ALL VALIDATIONS PASSED")
        print("=" * 72)

    except Exception as exc:
        print(f"\nVALIDATION FAILED: {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)
