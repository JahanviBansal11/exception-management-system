from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from exceptions.models import (
    AssetPurpose,
    AssetType,
    BusinessUnit,
    DataClassification,
    DataComponent,
    ExceptionRequest,
    ExceptionType,
    InternetExposure,
    RiskIssue,
)
from exceptions.services.escalation_engine import EscalationEngine
from exceptions.services.reminder_engine import ReminderEngine


class OptionBWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.requestor = User.objects.create_user('test_requestor', 'req@test.com', 'pass123')
        cls.approver = User.objects.create_user('test_approver', 'app@test.com', 'pass123')
        cls.risk_owner = User.objects.create_user('test_riskowner', 'risk@test.com', 'pass123')
        cls.outsider = User.objects.create_user('test_outsider', 'out@test.com', 'pass123')
        User.objects.get_or_create(username='system', defaults={'email': 'system@test.com'})

        requestor_group, _ = Group.objects.get_or_create(name='Requestor')
        approver_group, _ = Group.objects.get_or_create(name='Approver')
        risk_owner_group, _ = Group.objects.get_or_create(name='Risk Owner')
        Group.objects.get_or_create(name='Security')

        cls.requestor.groups.add(requestor_group)
        cls.approver.groups.add(approver_group)
        cls.risk_owner.groups.add(risk_owner_group)

        cls.bu, _ = BusinessUnit.objects.get_or_create(
            bu_code='FIN',
            defaults={'name': 'Finance', 'cio': cls.approver},
        )
        cls.exc_type, _ = ExceptionType.objects.get_or_create(
            name='Firewall Exception',
            defaults={'approval_sla_days': 28},
        )
        cls.risk_issue, _ = RiskIssue.objects.get_or_create(
            title='Firewall Rule Deviation',
            defaults={
                'description': 'Non-standard firewall rule needed',
                'inherent_risk_score': 6,
            },
        )

        cls.high_data_class, _ = DataClassification.objects.get_or_create(level='Sensitive', defaults={'weight': 3})
        cls.high_asset_type, _ = AssetType.objects.get_or_create(name='Server', defaults={'weight': 8})
        cls.high_asset_purpose, _ = AssetPurpose.objects.get_or_create(name='Database', defaults={'weight': 7})
        cls.high_data_component, _ = DataComponent.objects.get_or_create(name='Customer DB', defaults={'weight': 9})
        cls.high_internet_exp, _ = InternetExposure.objects.get_or_create(label='Internal Only', defaults={'weight': 2})

        cls.low_data_class, _ = DataClassification.objects.get_or_create(level='Public', defaults={'weight': 1})
        cls.low_asset_type, _ = AssetType.objects.get_or_create(name='Workstation', defaults={'weight': 1})
        cls.low_asset_purpose, _ = AssetPurpose.objects.get_or_create(name='Documentation', defaults={'weight': 1})
        cls.low_data_component, _ = DataComponent.objects.get_or_create(name='User Guide', defaults={'weight': 1})
        cls.low_internet_exp, _ = InternetExposure.objects.get_or_create(label='No Exposure', defaults={'weight': 1})

    def create_exception(self, profile='high', suffix=''):
        if profile == 'high':
            data_class = self.high_data_class
            asset_type = self.high_asset_type
            asset_purpose = self.high_asset_purpose
            data_component = self.high_data_component
            internet_exp = self.high_internet_exp
        else:
            data_class = self.low_data_class
            asset_type = self.low_asset_type
            asset_purpose = self.low_asset_purpose
            data_component = self.low_data_component
            internet_exp = self.low_internet_exp

        exc = ExceptionRequest.objects.create(
            requested_by=self.requestor,
            business_unit=self.bu,
            exception_type=self.exc_type,
            risk_issue=self.risk_issue,
            short_description=f'Test exception {profile} {suffix}'.strip(),
            reason_for_exception='Validation scenario',
            asset_type=asset_type,
            asset_purpose=asset_purpose,
            data_classification=data_class,
            internet_exposure=internet_exp,
            number_of_assets=1,
            exception_end_date=timezone.now() + timezone.timedelta(days=30),
            assigned_approver=self.approver,
            risk_owner=self.risk_owner,
        )
        exc.data_components.add(data_component)
        exc.refresh_from_db()
        return exc

    def test_high_branch_transitions_to_risk_owner_then_approved(self):
        exc = self.create_exception(profile='high', suffix='high-path')

        exc.submit(self.requestor)
        self.assertEqual(exc.status, 'Submitted')

        exc.bu_approve(self.approver, notes='BU CIO rationale for risk owner review')
        exc.refresh_from_db()
        self.assertEqual(exc.status, 'AwaitingRiskOwner')

        exc.risk_approve(self.risk_owner, notes='Approved by risk owner')
        exc.refresh_from_db()
        self.assertEqual(exc.status, 'Approved')

        self.assertEqual(exc.checkpoints.count(), 6)
        final_decision = exc.checkpoints.get(checkpoint='final_decision')
        self.assertEqual(final_decision.status, 'completed')
        self.assertEqual(final_decision.completed_by_id, self.risk_owner.id)

    def test_low_medium_shortcut_approved_and_risk_checkpoints_skipped(self):
        exc = self.create_exception(profile='low', suffix='low-path')

        exc.submit(self.requestor)
        exc.bu_approve(self.approver)
        exc.refresh_from_db()

        self.assertEqual(exc.status, 'Approved')

        risk_notified = exc.checkpoints.get(checkpoint='risk_assessment_notified')
        risk_complete = exc.checkpoints.get(checkpoint='risk_assessment_complete')
        final_decision = exc.checkpoints.get(checkpoint='final_decision')

        self.assertEqual(risk_notified.status, 'skipped')
        self.assertEqual(risk_complete.status, 'skipped')
        self.assertEqual(final_decision.status, 'completed')
        self.assertEqual(final_decision.completed_by_id, self.approver.id)

    def test_reject_flows_bu_and_risk_owner(self):
        bu_reject_exc = self.create_exception(profile='low', suffix='bu-reject')
        bu_reject_exc.submit(self.requestor)
        bu_reject_exc.bu_reject(self.approver, notes='Missing compensating controls')
        bu_reject_exc.refresh_from_db()
        self.assertEqual(bu_reject_exc.status, 'Rejected')

        risk_reject_exc = self.create_exception(profile='high', suffix='risk-reject')
        risk_reject_exc.submit(self.requestor)
        risk_reject_exc.bu_approve(self.approver, notes='Escalating to risk owner due to high risk')
        risk_reject_exc.risk_reject(self.risk_owner, notes='Rejected by risk owner')
        risk_reject_exc.refresh_from_db()
        self.assertEqual(risk_reject_exc.status, 'Rejected')

    def test_api_permissions_queryset_scoping_and_risk_owner_access(self):
        client = APIClient()

        exc_for_bu = self.create_exception(profile='high', suffix='api-bu')
        exc_for_bu.submit(self.requestor)

        client.force_authenticate(user=self.outsider)
        response = client.post(f'/api/exceptions/{exc_for_bu.id}/bu_approve/')
        self.assertEqual(response.status_code, 404)

        exc_for_risk = self.create_exception(profile='high', suffix='api-risk')
        exc_for_risk.submit(self.requestor)
        exc_for_risk.bu_approve(self.approver, notes='Needs explicit risk owner decision')

        client.force_authenticate(user=self.outsider)
        response = client.post(f'/api/exceptions/{exc_for_risk.id}/risk_assess/', {'notes': 'x'}, format='json')
        self.assertEqual(response.status_code, 404)

        client.force_authenticate(user=self.risk_owner)
        response = client.post(f'/api/exceptions/{exc_for_risk.id}/risk_assess/', {'notes': 'approved'}, format='json')
        self.assertEqual(response.status_code, 200)

    @patch('exceptions.services.notification_service.NotificationService.send_approval_expired_notification', return_value=True)
    @patch('exceptions.services.notification_service.NotificationService.send_approval_reminder', return_value=True)
    def test_scheduler_reminder_escalation_and_auto_close(self, _mock_reminder, _mock_expired):
        reminder_exc = self.create_exception(profile='high', suffix='reminder')
        reminder_exc.submit(self.requestor)
        ExceptionRequest.objects.filter(pk=reminder_exc.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=20),
            approval_deadline=timezone.now() + timezone.timedelta(days=8),
        )
        reminder_exc.refresh_from_db()

        sent_count = ReminderEngine.evaluate_pending_approvals()
        reminder_exc.refresh_from_db()
        self.assertGreaterEqual(sent_count, 1)
        self.assertIn(reminder_exc.reminder_stage, {'Reminder_50', 'Reminder_75', 'Reminder_90'})

        expired_exc = self.create_exception(profile='high', suffix='expire')
        expired_exc.submit(self.requestor)
        ExceptionRequest.objects.filter(pk=expired_exc.pk).update(
            approval_deadline=timezone.now() - timezone.timedelta(minutes=5),
            reminder_stage='Reminder_90',
        )

        escalated_count = EscalationEngine.escalate_expired_approvals()
        expired_exc.refresh_from_db()
        self.assertGreaterEqual(escalated_count, 1)
        self.assertEqual(expired_exc.status, 'Expired')

        close_exc = self.create_exception(profile='low', suffix='auto-close')
        close_exc.submit(self.requestor)
        close_exc.bu_approve(self.approver, notes='BU approved low-risk exception')
        ExceptionRequest.objects.filter(pk=close_exc.pk).update(
            exception_end_date=timezone.now() - timezone.timedelta(days=1)
        )

        closed_count = EscalationEngine.close_expired_exceptions()
        close_exc.refresh_from_db()
        self.assertGreaterEqual(closed_count, 1)
        self.assertEqual(close_exc.status, 'Closed')

    def test_jwt_token_obtain_and_current_user_endpoint(self):
        client = APIClient()
        response = client.post(
            '/api/auth/token/',
            {'username': 'test_requestor', 'password': 'pass123'},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        access_token = response.data['access']
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        me_response = client.get('/api/auth/me/')
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data['username'], 'test_requestor')
