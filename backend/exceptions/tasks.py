"""
Celery Tasks
Async tasks for reminders, escalations, and email delivery.
Triggered by Celery Beat schedule or event signals.
"""

import logging
from celery import shared_task
from django.core.mail import send_mail
from django.core.mail.message import EmailMessage
from django.utils import timezone
from django.contrib.auth.models import User

from exceptions.services import ReminderEngine, EscalationEngine

logger = logging.getLogger(__name__)


# ============================================
# SCHEDULED TASKS (Celery Beat)
# ============================================

@shared_task(bind=True, max_retries=3)
def evaluate_pending_approvals(self):
    """
    Periodic task: Evaluate pending exceptions and send reminders.
    Runs every 5 minutes (configured in celery.py beat schedule).
    """
    try:
        count = ReminderEngine.evaluate_pending_approvals()
        logger.info(f"Evaluated pending approvals. Sent {count} reminders.")
        return {'status': 'success', 'reminders_sent': count}
    
    except Exception as exc:
        logger.error(f"Error in evaluate_pending_approvals: {str(exc)}")
        # Retry after 60 seconds, up to 3 times
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def evaluate_active_exceptions(self):
    """
    Periodic task: Monitor approved exceptions approaching expiry.
    Runs every 10 minutes.
    """
    try:
        count = ReminderEngine.evaluate_active_exceptions()
        logger.info(f"Evaluated active exceptions. Found {count} approaching expiry.")
        return {'status': 'success', 'exceptions_checked': count}
    
    except Exception as exc:
        logger.error(f"Error in evaluate_active_exceptions: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def escalate_expired_approvals(self):
    """
    Periodic task: Auto-escalate exceptions past approval deadline.
    Runs every 1 hour.
    """
    try:
        count = EscalationEngine.escalate_expired_approvals()
        logger.info(f"Escalated {count} expired approvals.")
        return {'status': 'success', 'escalated_count': count}
    
    except Exception as exc:
        logger.error(f"Error in escalate_expired_approvals: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


@shared_task(bind=True, max_retries=3)
def close_expired_exceptions(self):
    """
    Periodic task: Auto-close approved exceptions past validity window.
    Runs every 1 hour.
    """
    try:
        count = EscalationEngine.close_expired_exceptions()
        logger.info(f"Closed {count} expired approved exceptions.")
        return {'status': 'success', 'closed_count': count}
    
    except Exception as exc:
        logger.error(f"Error in close_expired_exceptions: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


# ============================================
# EMAIL DELIVERY TASK
# ============================================

@shared_task(bind=True, max_retries=5)
def send_email_task(self, subject, message, from_email, recipient_list, reminder_log_id=None):
    """
    Send email via SendGrid.
    Retries up to 5 times with exponential backoff.
    
    Args:
        subject: Email subject
        message: Email body (HTML)
        from_email: Sender email address
        recipient_list: List of recipient emails
    """
    try:
        reminder_log = None
        if reminder_log_id:
            from exceptions.models import ReminderLog
            reminder_log = ReminderLog.objects.filter(id=reminder_log_id).first()

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=recipient_list,
        )
        email.content_subtype = 'html'
        
        result = email.send(fail_silently=False)
        
        if result:
            if reminder_log:
                reminder_log.delivery_status = 'sent'
                reminder_log.error_message = ''
                reminder_log.save(update_fields=['delivery_status', 'error_message'])
            logger.info(f"Email sent successfully to {recipient_list}")
            return {'status': 'success', 'recipients': recipient_list}
        else:
            raise Exception("Email send returned 0")
    
    except Exception as exc:
        if reminder_log_id:
            from exceptions.models import ReminderLog
            reminder_log = ReminderLog.objects.filter(id=reminder_log_id).first()
            if reminder_log:
                reminder_log.delivery_status = 'failed'
                reminder_log.error_message = str(exc)
                reminder_log.save(update_fields=['delivery_status', 'error_message'])
        logger.error(f"Error sending email: {str(exc)}")
        # Retry with exponential backoff: 60s, 120s, 240s, 480s, 960s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ============================================
# EVENT-DRIVEN TASKS
# ============================================

@shared_task
def on_exception_submitted(exception_id):
    """
    Triggered when exception status changes to Submitted.
    Sets approval_deadline and logs initial audit.
    """
    try:
        from exceptions.models import ExceptionRequest
        exception = ExceptionRequest.objects.get(pk=exception_id)
        exception._record_checkpoint(
            checkpoint='exception_requested',
            status='completed',
            user=exception.requested_by,
            notes='Exception submitted by requestor'
        )
        exception._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='pending',
            notes='Awaiting BU CIO decision'
        )
        logger.info(f"Exception #{exception_id} submitted. Deadline: {exception.approval_deadline}")
        return {'status': 'success', 'exception_id': exception_id}
    except Exception as exc:
        logger.error(f"Error in on_exception_submitted: {str(exc)}")
        raise


@shared_task
def on_exception_approved(exception_id):
    """
    Triggered when exception is approved.
    Sends notification to requester.
    """
    try:
        from exceptions.models import ExceptionRequest
        from exceptions.services import NotificationService
        
        exception = ExceptionRequest.objects.get(pk=exception_id)
        approver = exception.assigned_approver
        exception._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='completed',
            user=approver,
            notes='BU CIO reviewed and approved'
        )
        exception._record_checkpoint(
            checkpoint='bu_approval_decision',
            status='completed',
            user=approver,
            notes='BU CIO decision received: approved'
        )
        exception._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='pending',
            notes='Awaiting risk owner assessment'
        )
        NotificationService.send_exception_approved_notification(exception)
        logger.info(f"Approval notification sent for exception #{exception_id}")
        return {'status': 'success', 'exception_id': exception_id}
    except Exception as exc:
        logger.error(f"Error in on_exception_approved: {str(exc)}")
        raise


@shared_task
def on_exception_rejected(exception_id, reason=""):
    """
    Triggered when exception is rejected.
    Sends notification to requester.
    """
    try:
        from exceptions.models import ExceptionRequest
        from exceptions.services import NotificationService
        
        exception = ExceptionRequest.objects.get(pk=exception_id)
        decider = exception.assigned_approver
        exception._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=decider,
            notes=f'Final decision: rejected. {reason}'.strip()
        )
        NotificationService.send_exception_rejected_notification(exception, reason)
        logger.info(f"Rejection notification sent for exception #{exception_id}")
        return {'status': 'success', 'exception_id': exception_id}
    except Exception as exc:
        logger.error(f"Error in on_exception_rejected: {str(exc)}")
        raise


@shared_task
def on_risk_assessment_complete(exception_id, assessed_by_id, notes=""):
    """
    Triggered when risk owner completes assessment.
    """
    try:
        from exceptions.models import ExceptionRequest

        exception = ExceptionRequest.objects.get(pk=exception_id)
        assessor = User.objects.get(pk=assessed_by_id)

        exception._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='completed',
            user=assessor,
            notes='Risk owner acknowledged assessment task'
        )
        exception._record_checkpoint(
            checkpoint='risk_assessment_complete',
            status='completed',
            user=assessor,
            notes=notes or 'Risk assessment completed'
        )

        logger.info(f"Risk assessment checkpoint completed for exception #{exception_id}")
        return {'status': 'success', 'exception_id': exception_id}
    except Exception as exc:
        logger.error(f"Error in on_risk_assessment_complete: {str(exc)}")
        raise


@shared_task
def on_final_decision(exception_id, decision, decided_by_id):
    """
    Triggered when final decision is made.
    """
    try:
        from exceptions.models import ExceptionRequest

        exception = ExceptionRequest.objects.get(pk=exception_id)
        decider = User.objects.get(pk=decided_by_id)

        exception._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=decider,
            notes=f'Final decision: {decision}'
        )

        logger.info(f"Final decision checkpoint recorded for exception #{exception_id}")
        return {'status': 'success', 'exception_id': exception_id}
    except Exception as exc:
        logger.error(f"Error in on_final_decision: {str(exc)}")
        raise
