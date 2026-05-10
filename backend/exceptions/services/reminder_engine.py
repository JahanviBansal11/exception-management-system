"""
ReminderEngine — scheduled evaluation of approval window progress.

Sends reminders at 50%, 75%, and 90% of the approval window.
Also monitors approved exceptions approaching their end date.
"""

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

_THRESHOLDS = [
    ("Reminder_90", 0.90),
    ("Reminder_75", 0.75),
    ("Reminder_50", 0.50),
]


class ReminderEngine:

    @staticmethod
    def evaluate_pending_approvals() -> int:
        """
        Evaluate all Submitted/AwaitingRiskOwner exceptions.
        Send reminder at the next applicable threshold (50/75/90%).
        Returns count of reminders sent.
        """
        from exceptions.models import ExceptionRequest
        from exceptions.services.notification_service import NotificationService

        now = timezone.now()
        pending = ExceptionRequest.objects.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
        )

        sent = 0
        for exception in pending:
            try:
                total = (exception.approval_deadline - exception.created_at).total_seconds()
                if total <= 0:
                    continue
                progress = (now - exception.created_at).total_seconds() / total
                reminder_type = ReminderEngine._next_reminder(progress, exception.reminder_stage)
                if not reminder_type:
                    continue

                success = NotificationService.send_approval_reminder(exception, reminder_type)
                if success:
                    exception.reminder_stage = reminder_type
                    exception.last_reminder_sent = now
                    exception.save(update_fields=["reminder_stage", "last_reminder_sent", "updated_at"])
                    sent += 1
            except Exception as exc:
                logger.error("Error evaluating reminder for exception #%s: %s", exception.id, exc)

        logger.info("ReminderEngine (pending): sent %s reminders.", sent)
        return sent

    @staticmethod
    def evaluate_active_exceptions() -> int:
        """
        Evaluate all Approved exceptions with an exception_end_date.
        Send expiry reminder at 50/75/90% of the active window.
        Returns count of reminders sent.
        """
        from exceptions.models import ExceptionRequest
        from exceptions.services.notification_service import NotificationService

        now = timezone.now()
        active = ExceptionRequest.objects.filter(
            status="Approved",
            exception_end_date__isnull=False,
        )

        sent = 0
        for exception in active:
            try:
                start = exception.approved_at or exception.created_at
                total = (exception.exception_end_date - start).total_seconds()
                if total <= 0:
                    continue
                progress = (now - start).total_seconds() / total
                stage = ReminderEngine._next_active_stage(exception, progress)
                if not stage:
                    continue

                success = NotificationService.send_active_exception_expiry_reminder(
                    exception, stage, progress
                )
                if success:
                    sent += 1
            except Exception as exc:
                logger.error("Error evaluating active exception #%s: %s", exception.id, exc)

        logger.info("ReminderEngine (active): sent %s expiry reminders.", sent)
        return sent

    @staticmethod
    def _next_reminder(progress: float, current_stage: str):
        """Return the next reminder type to send, or None if not yet due."""
        for reminder_type, threshold in _THRESHOLDS:
            if progress >= threshold and current_stage != reminder_type:
                # Only send if we haven't already sent this or a later stage
                current_idx = _stage_index(current_stage)
                new_idx = _stage_index(reminder_type)
                if new_idx > current_idx:
                    return reminder_type
        return None

    @staticmethod
    def _next_active_stage(exception, progress: float):
        """Return the active expiry stage to remind about, or None if already sent."""
        from exceptions.models import ReminderLog
        for reminder_type, threshold in _THRESHOLDS:
            if progress >= threshold:
                marker = f"ACTIVE_EXPIRY:{reminder_type}"
                already = ReminderLog.objects.filter(
                    exception_request=exception,
                    reminder_type="Expired_Notice",
                    delivery_status="sent",
                    message_content__contains=marker,
                ).exists()
                if not already:
                    return reminder_type
        return None


def _stage_index(stage: str) -> int:
    order = {"None": 0, "Reminder_50": 1, "Reminder_75": 2, "Reminder_90": 3, "Expired_Notice": 4}
    return order.get(stage, 0)
