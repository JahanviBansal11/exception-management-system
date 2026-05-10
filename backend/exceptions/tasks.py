"""
Celery tasks — thin wrappers only.

Scheduled tasks call ReminderEngine / EscalationEngine.
send_email_task handles async email delivery with retries.
No business logic lives here.
"""

import logging

from celery import shared_task
from django.core.mail.message import EmailMessage

logger = logging.getLogger(__name__)


# ── Scheduled Tasks (Celery Beat) ───────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def evaluate_pending_approvals(self):
    """Every 5 min: check approval window progress and send 50/75/90% reminders."""
    try:
        from exceptions.services.reminder_engine import ReminderEngine
        count = ReminderEngine.evaluate_pending_approvals()
        logger.info("evaluate_pending_approvals: %s reminders sent.", count)
        return {"status": "success", "reminders_sent": count}
    except Exception as exc:
        logger.error("evaluate_pending_approvals failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def evaluate_active_exceptions(self):
    """Every 10 min: check active exceptions approaching end date."""
    try:
        from exceptions.services.reminder_engine import ReminderEngine
        count = ReminderEngine.evaluate_active_exceptions()
        logger.info("evaluate_active_exceptions: %s expiry reminders sent.", count)
        return {"status": "success", "reminders_sent": count}
    except Exception as exc:
        logger.error("evaluate_active_exceptions failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def escalate_expired_approvals(self):
    """Every hour: auto-expire exceptions past approval deadline."""
    try:
        from exceptions.services.escalation_engine import EscalationEngine
        count = EscalationEngine.escalate_expired_approvals()
        logger.info("escalate_expired_approvals: %s exceptions expired.", count)
        return {"status": "success", "escalated_count": count}
    except Exception as exc:
        logger.error("escalate_expired_approvals failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def close_expired_exceptions(self):
    """Every hour: auto-close approved exceptions past their end date."""
    try:
        from exceptions.services.escalation_engine import EscalationEngine
        count = EscalationEngine.close_expired_exceptions()
        logger.info("close_expired_exceptions: %s exceptions closed.", count)
        return {"status": "success", "closed_count": count}
    except Exception as exc:
        logger.error("close_expired_exceptions failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


# ── Email Delivery Task ──────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=5)
def send_email_task(self, subject, message, from_email, recipient_list):
    """
    Send an HTML email. Retries up to 5 times with exponential backoff.
    Called by NotificationService — do not call directly from business logic.
    """
    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=recipient_list,
        )
        email.content_subtype = "html"
        result = email.send(fail_silently=False)
        if not result:
            raise RuntimeError("email.send() returned 0")
        logger.info("Email sent to %s", recipient_list)
        return {"status": "success", "recipients": recipient_list}
    except Exception as exc:
        logger.error("Email send failed to %s: %s", recipient_list, exc)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
