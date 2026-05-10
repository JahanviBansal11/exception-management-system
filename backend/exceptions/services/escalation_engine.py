"""
EscalationEngine — scheduled auto-expiry and auto-close of exceptions.

Called by Celery Beat tasks. Delegates state changes to WorkflowService.
"""

import logging

from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)


def _system_user():
    try:
        return User.objects.get(username="system")
    except User.DoesNotExist:
        return User.objects.filter(is_superuser=True).first()


class EscalationEngine:

    @staticmethod
    def escalate_expired_approvals() -> int:
        """
        Find all Submitted/AwaitingRiskOwner exceptions past their approval_deadline.
        Transition each to ApprovalDeadlinePassed via WorkflowService.
        """
        from exceptions.models import ExceptionRequest
        from exceptions.services.workflow_service import WorkflowService
        from exceptions.services.notification_service import NotificationService

        now = timezone.now()
        expired_qs = ExceptionRequest.objects.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__lt=now,
        )

        user = _system_user()
        count = 0

        for exception in expired_qs:
            try:
                WorkflowService.mark_expired(exception, user)
                NotificationService.send_approval_expired_notification(exception)
                count += 1
                logger.warning(
                    "Approval deadline passed for exception #%s (deadline was %s)",
                    exception.id, exception.approval_deadline,
                )
            except Exception as exc:
                logger.error("Error processing deadline for exception #%s: %s", exception.id, exc)

        logger.info("EscalationEngine: marked %s exceptions as ApprovalDeadlinePassed.", count)
        return count

    @staticmethod
    def expire_active_exceptions() -> int:
        """
        Find all Approved exceptions past their exception_end_date.
        Transition each to Expired and notify requestor + Security.
        Does NOT auto-close — requestor must extend or remediate.
        """
        from exceptions.models import ExceptionRequest
        from exceptions.services.workflow_service import WorkflowService
        from exceptions.services.notification_service import NotificationService

        now = timezone.now()
        expirable_qs = ExceptionRequest.objects.filter(
            status="Approved",
            exception_end_date__lt=now,
        ).select_related("requested_by", "assigned_approver", "risk_owner", "exception_type", "business_unit")

        user = _system_user()
        count = 0

        for exception in expirable_qs:
            try:
                WorkflowService.mark_active_expired(exception, user)
                NotificationService.send_exception_expired_notification(exception)
                count += 1
                logger.warning(
                    "Exception #%s expired (end date was %s)",
                    exception.id, exception.exception_end_date,
                )
            except Exception as exc:
                logger.error("Error expiring exception #%s: %s", exception.id, exc)

        logger.info("EscalationEngine: marked %s exceptions as Expired.", count)
        return count

    @staticmethod
    def notify_unresolved_expired_exceptions() -> int:
        """
        Find Expired exceptions whose 14-day grace window has closed with no action.
        Notify risk owner once — deduped via ReminderLog so hourly runs don't re-notify.
        Urgent email for High/Critical; standard email for Low/Medium.
        """
        from datetime import timedelta
        from exceptions.models import ExceptionRequest, ReminderLog
        from exceptions.services.notification_service import NotificationService

        now = timezone.now()
        grace_cutoff = now - timedelta(days=14)

        overdue_qs = ExceptionRequest.objects.filter(
            status="Expired",
            exception_end_date__lt=grace_cutoff,
        ).select_related("requested_by", "risk_owner", "exception_type", "business_unit")

        count = 0
        for exception in overdue_qs:
            already_notified = ReminderLog.objects.filter(
                exception_request=exception,
                reminder_type="Overdue_Expired_Notice",
                delivery_status="sent",
            ).exists()
            if already_notified:
                continue

            try:
                sent = NotificationService.send_overdue_expired_notification(exception)
                ReminderLog.objects.create(
                    exception_request=exception,
                    sent_to=exception.risk_owner,
                    channel="email",
                    reminder_type="Overdue_Expired_Notice",
                    delivery_status="sent" if sent else "failed",
                    message_content=f"Overdue expired notification for exception #{exception.id}",
                )
                if sent:
                    count += 1
                    logger.warning(
                        "Overdue expiry notification sent for exception #%s (grace passed %s)",
                        exception.id, grace_cutoff,
                    )
            except Exception as exc:
                logger.error("Error notifying overdue exception #%s: %s", exception.id, exc)

        logger.info("EscalationEngine: sent %s overdue expired notifications.", count)
        return count
