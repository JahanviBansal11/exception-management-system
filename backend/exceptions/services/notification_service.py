"""
NotificationService — email construction, template rendering, and send_email_task dispatch.

Delivery is tracked in ReminderLog where applicable.
Import flow: one-way — NotificationService does NOT import WorkflowService.
"""

import logging
from urllib.parse import quote

from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

logger = logging.getLogger(__name__)


def _portal_link(role: str, exception_id: int) -> str:
    next_path = f"/dashboard/{role}?exception={exception_id}"
    return f"{settings.FRONTEND_BASE_URL}/login?next={quote(next_path, safe='')}"


def _send(subject: str, html: str, recipients: list) -> None:
    """Dispatch email via Celery task."""
    from exceptions.tasks import send_email_task
    send_email_task.delay(
        subject=subject,
        message=html,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
    )


def _render(template_str: str, context: dict) -> str:
    return Template(template_str).render(Context(context))


class NotificationService:

    # ── Workflow event notifications ─────────────────────────────────────

    @staticmethod
    def send_submission_notification(exception_request) -> bool:
        """Notify BU CIO that a new exception requires their review."""
        try:
            approver = exception_request.assigned_approver
            if not approver or not approver.email:
                logger.warning("No approver email for exception #%s", exception_request.id)
                return False

            html = _render(_TEMPLATE_SUBMISSION, {
                "exception": exception_request,
                "approver": approver,
                "requester": exception_request.requested_by,
                "approval_deadline": exception_request.approval_deadline,
                "risk_rating": exception_request.risk_rating,
                "review_link": _portal_link("approver", exception_request.id),
            })
            _send(
                f"[ACTION REQUIRED] New Exception Submission: "
                f"{exception_request.short_description[:50]}",
                html, [approver.email],
            )
            logger.info("Submission notification → %s (exception #%s)", approver.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed submission notification for #%s: %s", exception_request.id, exc)
            return False

    @staticmethod
    def send_risk_owner_notification(exception_request) -> bool:
        """Notify Risk Owner that a High/Critical exception needs their assessment."""
        try:
            risk_owner = exception_request.risk_owner
            if not risk_owner or not risk_owner.email:
                logger.warning("No risk owner email for exception #%s", exception_request.id)
                return False

            # Pull BU CIO notes from the latest APPROVE audit log
            from exceptions.models import AuditLog
            approver_notes = ""
            log = AuditLog.objects.filter(
                exception_request=exception_request,
                action_type="APPROVE",
                new_status="AwaitingRiskOwner",
            ).order_by("-timestamp").first()
            if log:
                approver_notes = (log.details or {}).get("approver_notes", "")

            html = _render(_TEMPLATE_RISK_OWNER, {
                "exception": exception_request,
                "risk_owner": risk_owner,
                "requester": exception_request.requested_by,
                "approval_deadline": exception_request.approval_deadline,
                "risk_rating": exception_request.risk_rating,
                "business_unit": exception_request.business_unit,
                "approver_notes": approver_notes,
                "review_link": _portal_link("risk-owner", exception_request.id),
            })
            _send(
                f"[ACTION REQUIRED] Risk Assessment Needed: "
                f"{exception_request.short_description[:50]}",
                html, [risk_owner.email],
            )
            logger.info("Risk owner notification → %s (exception #%s)", risk_owner.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed risk owner notification for #%s: %s", exception_request.id, exc)
            return False

    @staticmethod
    def send_exception_approved_notification(exception_request, approved_by_user=None) -> bool:
        """Notify requester their exception was approved."""
        try:
            requester = exception_request.requested_by
            if not requester or not requester.email:
                logger.warning("No requester email for exception #%s", exception_request.id)
                return False

            if approved_by_user is None:
                from exceptions.models import AuditLog
                log = AuditLog.objects.filter(
                    exception_request=exception_request, action_type="APPROVE"
                ).select_related("performed_by").order_by("-timestamp").first()
                if log:
                    approved_by_user = log.performed_by

            approver_name = None
            approver_role = "System"
            if approved_by_user:
                approver_name = approved_by_user.get_full_name() or approved_by_user.username
                if approved_by_user.id == exception_request.assigned_approver_id:
                    approver_role = "BU CIO"
                elif approved_by_user.id == exception_request.risk_owner_id:
                    approver_role = "Risk Owner"

            html = _render(_TEMPLATE_APPROVED, {
                "exception": exception_request,
                "requester": requester,
                "approved_at": exception_request.approved_at,
                "validity_end": exception_request.exception_end_date,
                "approver_name": approver_name,
                "approver_role": approver_role,
            })
            _send(
                f"Exception Approved: {exception_request.short_description[:50]}",
                html, [requester.email],
            )
            logger.info("Approval notification → %s (exception #%s)", requester.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed approval notification for #%s: %s", exception_request.id, exc)
            return False

    @staticmethod
    def send_exception_rejected_notification(exception_request, reason: str = "") -> bool:
        """Notify requester their exception was rejected."""
        try:
            requester = exception_request.requested_by
            if not requester or not requester.email:
                logger.warning("No requester email for exception #%s", exception_request.id)
                return False

            html = _render(_TEMPLATE_REJECTED, {
                "exception": exception_request,
                "requester": requester,
                "reason": reason,
                "review_link": _portal_link("requestor", exception_request.id),
            })
            _send(
                f"Exception Rejected: {exception_request.short_description[:50]}",
                html, [requester.email],
            )
            logger.info("Rejection notification → %s (exception #%s)", requester.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed rejection notification for #%s: %s", exception_request.id, exc)
            return False

    @staticmethod
    def send_approval_expired_notification(exception_request) -> bool:
        """Notify approver that the approval deadline has passed."""
        try:
            approver = exception_request.assigned_approver
            requester = exception_request.requested_by
            if not approver or not approver.email:
                logger.warning("No approver email for exception #%s", exception_request.id)
                return False

            html = _render(_TEMPLATE_EXPIRED, {
                "exception": exception_request,
                "approver": approver,
                "requester": requester,
            })
            _send(
                f"[ESCALATED] Exception Approval Expired: {exception_request.short_description[:50]}",
                html, [approver.email],
            )
            logger.info("Expiry notification → %s (exception #%s)", approver.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed expiry notification for #%s: %s", exception_request.id, exc)
            return False

    @staticmethod
    def send_active_exception_expiry_reminder(exception_request, reminder_stage: str, progress: float) -> bool:
        """Notify requester that an approved exception is approaching its end date."""
        try:
            requester = exception_request.requested_by
            if not requester or not requester.email:
                logger.warning("No requester email for expiry reminder on #%s", exception_request.id)
                return False

            marker = f"ACTIVE_EXPIRY:{reminder_stage}"

            html = _render(_TEMPLATE_ACTIVE_EXPIRY, {
                "exception": exception_request,
                "requester": requester,
                "reminder_stage": reminder_stage,
                "progress_percent": int(progress * 100),
                "review_link": _portal_link("requestor", exception_request.id),
            })

            _send(
                f"[REMINDER] Active Exception {reminder_stage}: {exception_request.short_description[:50]}",
                html, [requester.email],
            )

            from exceptions.models import ReminderLog
            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=requester,
                channel="email",
                reminder_type="Expired_Notice",
                delivery_status="sent",
                message_content=f"{marker}\n{html}"[:1000],
            )
            logger.info("Active expiry reminder (%s) → %s (exception #%s)", reminder_stage, requester.email, exception_request.id)
            return True
        except Exception as exc:
            logger.error("Failed active expiry reminder for #%s: %s", exception_request.id, exc)
            from exceptions.models import ReminderLog
            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=getattr(exception_request, "requested_by", None),
                channel="email",
                reminder_type="Expired_Notice",
                delivery_status="failed",
                error_message=str(exc),
                message_content=f"ACTIVE_EXPIRY:{reminder_stage}",
            )
            return False

    @staticmethod
    def send_approval_reminder(exception_request, reminder_type: str) -> bool:
        """
        Approval window reminder (50/75/90%) — not yet implemented.
        Stubbed so ReminderEngine does not crash. Implement in a feature branch.
        """
        logger.warning(
            "send_approval_reminder called for exception #%s (%s) — not yet implemented.",
            exception_request.id, reminder_type,
        )
        return False


# ── Email Templates ──────────────────────────────────────────────────────────

_TEMPLATE_SUBMISSION = """
<h2>New Exception Submission — Action Required</h2>
<p>Hello {{ approver.first_name }},</p>
<p>A new exception has been submitted and requires your approval.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
  <p><strong>Business Unit:</strong> {{ exception.business_unit.name }}</p>
  <p><strong>Deadline:</strong> {{ approval_deadline|date:"M d, Y H:i" }}</p>
</div>
<p><a href="{{ review_link }}" style="padding:10px 20px;background:#007bff;color:#fff;text-decoration:none;border-radius:4px;">Review Exception</a></p>
"""

_TEMPLATE_RISK_OWNER = """
<h2>Risk Assessment Required — Action Required</h2>
<p>Hello {{ risk_owner.first_name }},</p>
<p>An exception has been approved by the BU CIO and now requires your risk assessment.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;background:#fff0f0;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
  <p><strong>Business Unit:</strong> {{ business_unit.name }}</p>
  <p><strong>Risk Rating:</strong> {{ risk_rating }} (requires assessment)</p>
  {% if approver_notes %}<p><strong>BU CIO Notes:</strong> {{ approver_notes }}</p>{% endif %}
  <p><strong>Deadline:</strong> {{ approval_deadline|date:"M d, Y H:i" }}</p>
</div>
<p><a href="{{ review_link }}" style="padding:10px 20px;background:#dc3545;color:#fff;text-decoration:none;border-radius:4px;">Assess Risk</a></p>
"""

_TEMPLATE_APPROVED = """
<h2>Exception Approved</h2>
<p>Hello {{ requester.first_name }},</p>
<p>Your exception has been approved by {{ approver_role }}{% if approver_name %} ({{ approver_name }}){% endif %}.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  <p><strong>Approved At:</strong> {{ approved_at|date:"M d, Y H:i" }}</p>
  <p><strong>Valid Until:</strong> {{ validity_end|date:"M d, Y" }}</p>
</div>
"""

_TEMPLATE_REJECTED = """
<h2>Exception Rejected</h2>
<p>Hello {{ requester.first_name }},</p>
<p>Your exception has been rejected.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  {% if reason %}<p><strong>Reason:</strong> {{ reason }}</p>{% endif %}
</div>
<p>You may resubmit this exception with modifications.</p>
<p><a href="{{ review_link }}" style="padding:10px 20px;background:#6b7280;color:#fff;text-decoration:none;border-radius:4px;">Open Exception</a></p>
"""

_TEMPLATE_EXPIRED = """
<h2>Approval Deadline Expired</h2>
<p>Hello {{ approver.first_name }},</p>
<p>The approval deadline for the following exception has passed without a decision.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;background:#fff3cd;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
  <p><strong>Status:</strong> <span style="color:red;">EXPIRED</span></p>
</div>
"""

_TEMPLATE_ACTIVE_EXPIRY = """
<h2>Active Exception Reminder</h2>
<p>Hello {{ requester.first_name }},</p>
<p>Your approved exception has used {{ progress_percent }}% of its allowed active time.</p>
<div style="border:1px solid #ddd;padding:15px;margin:20px 0;background:#fff7ed;">
  <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
  <p><strong>Description:</strong> {{ exception.short_description }}</p>
  <p><strong>Elapsed:</strong> {{ progress_percent }}%</p>
  <p><strong>End Date:</strong> {{ exception.exception_end_date|date:"M d, Y H:i" }}</p>
</div>
<p>Please plan remediation or extension actions before expiry.</p>
<p><a href="{{ review_link }}" style="padding:10px 20px;background:#f97316;color:#fff;text-decoration:none;border-radius:4px;">Open Exception</a></p>
"""
