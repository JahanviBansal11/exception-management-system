"""
Reminder Engine
Evaluates approval windows and sends reminders at 50%, 75%, and 90% progress.
Called periodically by Celery Beat schedule.
"""

import logging
from django.utils import timezone

from exceptions.models import ExceptionRequest, ReminderLog
from .notification_service import NotificationService

logger = logging.getLogger(__name__)


class ReminderEngine:
    """
    Evaluates pending exceptions and sends reminders based on approval progress.
    
    Formula:
    elapsed_percentage = (now - created_at) / (approval_deadline - created_at)
    
    Sends reminders at:
    - 50% progress
    - 75% progress
    - 90% progress
    """
    
    REMINDER_THRESHOLDS = {
        'Reminder_50': 0.50,
        'Reminder_75': 0.75,
        'Reminder_90': 0.90,
    }

    ACTIVE_EXPIRY_THRESHOLDS = {
        'Reminder_50': 0.50,
        'Reminder_75': 0.75,
        'Reminder_90': 0.90,
    }
    
    @staticmethod
    def evaluate_pending_approvals():
        """
        Find all submitted exceptions within approval window.
        Send reminders based on deadline progress.
        """
        logger.info("Starting evaluation of pending approvals...")
        
        now = timezone.now()
        
        # Find all exceptions pending approval workflow
        pending = ExceptionRequest.objects.filter(
            status__in=['Submitted', 'AwaitingRiskOwner'],
            approval_deadline__isnull=False
        )
        
        reminders_sent = 0
        
        for exception in pending:
            try:
                # Calculate progress
                elapsed = (now - exception.created_at).total_seconds()
                total = (exception.approval_deadline - exception.created_at).total_seconds()
                
                if total <= 0:
                    # Deadline already passed, will be handled by escalation engine
                    continue
                
                progress = elapsed / total
                
                # Determine which reminder to send
                reminder_type = ReminderEngine._get_reminder_type(progress, exception.reminder_stage)
                
                if reminder_type:
                    # Send reminder
                    success = NotificationService.send_approval_reminder(
                        exception, 
                        reminder_type
                    )
                    
                    if success:
                        # Update reminder stage
                        exception.reminder_stage = reminder_type
                        exception.last_reminder_sent = now
                        exception.save(update_fields=['reminder_stage', 'last_reminder_sent'])
                        reminders_sent += 1
                        
                        logger.info(
                            f"Sent {reminder_type} reminder for exception #{exception.id} "
                            f"({progress*100:.1f}% progress)"
                        )
            
            except Exception as e:
                logger.error(
                    f"Error evaluating exception #{exception.id}: {str(e)}"
                )
        
        logger.info(f"Completed evaluation. Sent {reminders_sent} reminders.")
        return reminders_sent
    
    @staticmethod
    def _get_reminder_type(progress: float, current_stage: str) -> str:
        """
        Determine if a reminder should be sent based on progress.
        
        Args:
            progress: Percentage of approval window elapsed (0.0 to 1.0)
            current_stage: Current reminder stage
        
        Returns:
            Reminder type to send, or None if no reminder needed
        """
        # Don't resend if already at this stage
        sent_reminders = {
            'Reminder_50', 'Reminder_75', 'Reminder_90', 'Expired_Notice'
        }
        
        if progress >= 0.90 and current_stage != 'Reminder_90':
            return 'Reminder_90'
        elif progress >= 0.75 and current_stage not in {'Reminder_75', 'Reminder_90'}:
            return 'Reminder_75'
        elif progress >= 0.50 and current_stage not in {'Reminder_50', 'Reminder_75', 'Reminder_90'}:
            return 'Reminder_50'
        
        return None
    
    @staticmethod
    def evaluate_active_exceptions():
        """
        Find all approved exceptions approaching end date.
        Send reminders to requestor about upcoming closure.
        """
        logger.info("Starting evaluation of active exceptions...")
        
        now = timezone.now()
        reminders_sent = 0
        
        # Find approved exceptions with validity window
        active = ExceptionRequest.objects.filter(
            status='Approved',
            exception_end_date__isnull=False
        )
        
        for exception in active:
            try:
                active_start = exception.approved_at or exception.created_at
                total_seconds = (exception.exception_end_date - active_start).total_seconds()
                if total_seconds <= 0:
                    continue

                elapsed_seconds = (now - active_start).total_seconds()
                progress = elapsed_seconds / total_seconds

                reminder_stage = ReminderEngine._get_active_expiry_reminder_stage(exception, progress)
                if reminder_stage is None:
                    continue

                success = NotificationService.send_active_exception_expiry_reminder(
                    exception,
                    reminder_stage,
                    progress,
                )
                if success:
                    reminders_sent += 1
                    logger.info(
                        f"Sent active expiry reminder ({reminder_stage}) for exception #{exception.id}"
                    )
            
            except Exception as e:
                logger.error(
                    f"Error evaluating active exception #{exception.id}: {str(e)}"
                )
        
        logger.info(f"Completed evaluation. Found {reminders_sent} exceptions approaching expiry.")
        return reminders_sent

    @staticmethod
    def _get_active_expiry_reminder_stage(exception: ExceptionRequest, progress: float):
        """Return active reminder stage (Reminder_50/75/90) if pending and not already sent."""
        if progress >= 0.90:
            stage = 'Reminder_90'
        elif progress >= 0.75:
            stage = 'Reminder_75'
        elif progress >= 0.50:
            stage = 'Reminder_50'
        else:
            return None

        marker = f"ACTIVE_EXPIRY:{stage}"
        already_sent = ReminderLog.objects.filter(
            exception_request=exception,
            reminder_type='Expired_Notice',
            delivery_status='sent',
            message_content__contains=marker,
        ).exists()

        if already_sent:
            return None
        return stage
