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
    def close_expired_exceptions() -> int:
        """
        Find all Approved exceptions past their exception_end_date.
        Transition each to Closed via WorkflowService.
        """
        from exceptions.models import ExceptionRequest
        from exceptions.services.workflow_service import WorkflowService

        now = timezone.now()
        closeable_qs = ExceptionRequest.objects.filter(
            status="Approved",
            exception_end_date__lt=now,
        )

        user = _system_user()
        count = 0

        for exception in closeable_qs:
            try:
                WorkflowService.close(exception, user)
                count += 1
                logger.info(
                    "Auto-closed exception #%s (end date was %s)",
                    exception.id, exception.exception_end_date,
                )
            except Exception as exc:
                logger.error("Error closing exception #%s: %s", exception.id, exc)

        logger.info("EscalationEngine: closed %s exceptions.", count)
        return count
