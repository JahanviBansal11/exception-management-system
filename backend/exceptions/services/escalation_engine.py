"""
Escalation Engine
Automatically escalates exceptions when approval deadline passes.
Called periodically by Celery Beat schedule.
"""

import logging
from django.utils import timezone
from django.contrib.auth.models import User

from exceptions.models import ExceptionRequest
from .notification_service import NotificationService

logger = logging.getLogger(__name__)


class EscalationEngine:
    """
    Monitors approval windows and automatically escalates expired exceptions.
    Marks as "Expired" when approval_deadline passes.
    """
    
    @staticmethod
    def escalate_expired_approvals():
        """
        Find all submitted exceptions past approval deadline.
        Auto-escalate to Expired status.
        Notify approver immediately.
        """
        logger.info("Starting escalation of expired approvals...")
        
        now = timezone.now()
        escalated_count = 0
        
        # Find all exceptions pending approval that are past deadline
        expired = ExceptionRequest.objects.filter(
            status__in=['Submitted', 'AwaitingRiskOwner'],
            approval_deadline__lt=now,
            reminder_stage__in=['Reminder_90', 'Expired_Notice']  # Only if reminders were sent
        )
        
        # Get system user for escalation action
        try:
            system_user = User.objects.get(username='system') or User.objects.first()
        except:
            system_user = User.objects.first()
        
        for exception in expired:
            try:
                # Mark as expired
                exception.mark_expired(system_user)
                
                # Send immediate notification to approver
                NotificationService.send_approval_expired_notification(exception)
                
                escalated_count += 1
                
                logger.warning(
                    f"Escalated exception #{exception.id} to EXPIRED status. "
                    f"Approval deadline was {exception.approval_deadline}"
                )
            
            except Exception as e:
                logger.error(
                    f"Error escalating exception #{exception.id}: {str(e)}"
                )
        
        logger.info(f"Completed escalation. Escalated {escalated_count} exceptions.")
        return escalated_count
    
    @staticmethod
    def close_expired_exceptions():
        """
        Find all approved exceptions past validity end date.
        Auto-close them.
        """
        logger.info("Starting closure of expired approved exceptions...")
        
        now = timezone.now()
        closed_count = 0
        
        # Find approved exceptions past validity window
        expired_approvals = ExceptionRequest.objects.filter(
            status='Approved',
            exception_end_date__lt=now
        )
        
        try:
            system_user = User.objects.get(username='system') or User.objects.first()
        except:
            system_user = User.objects.first()
        
        for exception in expired_approvals:
            try:
                # Close the exception
                exception.close(system_user)
                closed_count += 1
                
                logger.info(
                    f"Auto-closed exception #{exception.id}. "
                    f"Validity window ended {exception.exception_end_date}"
                )
            
            except Exception as e:
                logger.error(
                    f"Error closing exception #{exception.id}: {str(e)}"
                )
        
        logger.info(f"Completed closure. Closed {closed_count} exceptions.")
        return closed_count
    
    @staticmethod
    def notify_critical_exceptions():
        """
        Find exceptions with Critical risk rating.
        Ensure they're being tracked and escalated appropriately.
        """
        logger.info("Checking for critical exceptions...")
        
        critical = ExceptionRequest.objects.filter(
            status__in=['Submitted', 'AwaitingRiskOwner'],
            risk_rating='Critical'
        )
        
        for exception in critical:
            # TODO: Send alert to security team
            logger.warning(
                f"CRITICAL risk exception #{exception.id} pending approval: "
                f"{exception.short_description}"
            )
        
        logger.info(f"Found {critical.count()} critical exceptions.")
        return critical.count()
