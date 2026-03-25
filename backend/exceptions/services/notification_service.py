"""
Notification Service
Handles all communication channels (email, in-app, SMS).
Production-ready with logging, retries, and delivery tracking.
"""

import logging
from urllib.parse import quote
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

from exceptions.models import ExceptionRequest, ReminderLog, AuditLog

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Centralized notification service for sending reminders and alerts.
    Supports multiple channels and tracks delivery status.
    """

    @staticmethod
    def _build_portal_link(role: str, exception_id: int) -> str:
        next_path = f"/dashboard/{role}?exception={exception_id}"
        return f"{settings.FRONTEND_BASE_URL}/login?next={quote(next_path, safe='')}"
    
    @staticmethod
    def send_submission_notification(exception_request: ExceptionRequest) -> bool:
        """
        Send notification to assigned approver when exception is submitted.
        
        Args:
            exception_request: The submitted exception
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            approver = exception_request.assigned_approver
            if not approver or not approver.email:
                logger.warning(
                    f"No approver assigned for exception #{exception_request.id}"
                )
                return False
            
            context = {
                'exception': exception_request,
                'approver': approver,
                'requester': exception_request.requested_by,
                'approval_deadline': exception_request.approval_deadline,
                'risk_rating': exception_request.risk_rating,
                'review_link': NotificationService._build_portal_link('approver', exception_request.id),
            }
            
            html_message = NotificationService._render_submission_template(context)
            
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"[ACTION REQUIRED] New Exception Submission: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approver.email],
            )
            
            logger.info(
                f"Submission notification sent to {approver.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send submission notification for exception #{exception_request.id}: {str(e)}"
            )
            return False
    
    @staticmethod
    def send_risk_owner_notification(exception_request: ExceptionRequest) -> bool:
        """
        Send notification to risk owner when BU approves High/Critical exception.
        
        Args:
            exception_request: The exception awaiting risk owner approval
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            risk_owner = exception_request.risk_owner
            if not risk_owner or not risk_owner.email:
                logger.warning(
                    f"No risk owner assigned for exception #{exception_request.id}"
                )
                return False
            
            context = {
                'exception': exception_request,
                'risk_owner': risk_owner,
                'requester': exception_request.requested_by,
                'approval_deadline': exception_request.approval_deadline,
                'risk_rating': exception_request.risk_rating,
                'business_unit': exception_request.business_unit,
                'approver_notes': '',
                'review_link': NotificationService._build_portal_link('risk-owner', exception_request.id),
            }

            approval_log = AuditLog.objects.filter(
                exception_request=exception_request,
                action_type='APPROVE',
                new_status='AwaitingRiskOwner',
            ).order_by('-timestamp').first()
            if approval_log:
                context['approver_notes'] = (approval_log.details or {}).get('approver_notes', '')
            
            html_message = NotificationService._render_risk_owner_template(context)
            
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"[ACTION REQUIRED] Risk Assessment Needed: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[risk_owner.email],
            )
            
            logger.info(
                f"Risk owner notification sent to {risk_owner.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send risk owner notification for exception #{exception_request.id}: {str(e)}"
            )
            return False

    @staticmethod
    def send_approval_reminder(exception_request: ExceptionRequest, reminder_type: str) -> bool:
        """
        Send reminder email to approver.
        
        Args:
            exception_request: The exception to remind about
            reminder_type: Type of reminder (Reminder_50, Reminder_75, Reminder_90, Expired_Notice)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            approver = exception_request.assigned_approver
            
            # Prepare email content
            context = {
                'exception': exception_request,
                'approver': approver,
                'reminder_type': reminder_type,
                'approval_deadline': exception_request.approval_deadline,
            }
            
            # Render template
            html_message = NotificationService._render_approval_reminder_template(context)
            
            # Create email
            email = EmailMessage(
                subject=f"[ACTION REQUIRED] Exception Approval: {exception_request.short_description[:50]}",
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[approver.email],
                reply_to=['support@grc-system.com'],
            )
            email.content_subtype = 'html'
            
            # Send via Celery task
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=email.subject,
                message=html_message,
                from_email=email.from_email,
                recipient_list=email.to,
            )
            
            # Log reminder
            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=approver,
                channel='email',
                reminder_type=reminder_type,
                delivery_status='sent',
                message_content=html_message[:500],  # Preview
            )
            
            logger.info(
                f"Approval reminder sent to {approver.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send approval reminder for exception #{exception_request.id}: {str(e)}"
            )
            
            # Log failure
            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=exception_request.assigned_approver,
                channel='email',
                reminder_type=reminder_type,
                delivery_status='failed',
                error_message=str(e),
            )
            return False
    
    @staticmethod
    def send_exception_approved_notification(exception_request: ExceptionRequest) -> bool:
        """
        Notify requester that their exception was approved.
        
        Args:
            exception_request: The approved exception
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            requester = exception_request.requested_by
            
            context = {
                'exception': exception_request,
                'requester': requester,
                'approved_at': exception_request.approved_at,
                'validity_end': exception_request.exception_end_date,
            }
            
            html_message = NotificationService._render_approval_notification_template(context)
            
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"Exception Approved: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester.email],
            )
            
            logger.info(
                f"Approval notification sent to {requester.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send approval notification for exception #{exception_request.id}: {str(e)}"
            )
            return False
    
    @staticmethod
    def send_exception_rejected_notification(exception_request: ExceptionRequest, reason: str = "") -> bool:
        """
        Notify requester that their exception was rejected.
        """
        try:
            requester = exception_request.requested_by
            
            context = {
                'exception': exception_request,
                'requester': requester,
                'reason': reason,
                'review_link': NotificationService._build_portal_link('requestor', exception_request.id),
            }
            
            html_message = NotificationService._render_rejection_notification_template(context)
            
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"Exception Rejected: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester.email],
            )
            
            logger.info(
                f"Rejection notification sent to {requester.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send rejection notification for exception #{exception_request.id}: {str(e)}"
            )
            return False
    
    @staticmethod
    def send_approval_expired_notification(exception_request: ExceptionRequest) -> bool:
        """
        Notify approver that approval deadline has passed.
        """
        try:
            approver = exception_request.assigned_approver
            requester = exception_request.requested_by
            
            context = {
                'exception': exception_request,
                'approver': approver,
                'requester': requester,
            }
            
            html_message = NotificationService._render_expired_notification_template(context)
            
            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"[ESCALATED] Exception Approval Expired: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[approver.email],
            )
            
            logger.info(
                f"Expiry notification sent to {approver.email} for exception #{exception_request.id}"
            )
            return True
        
        except Exception as e:
            logger.error(
                f"Failed to send expiry notification for exception #{exception_request.id}: {str(e)}"
            )
            return False

    @staticmethod
    def send_active_exception_expiry_reminder(exception_request: ExceptionRequest, reminder_stage: str, progress: float) -> bool:
        """
        Notify requester that an approved exception is approaching expiry.
        """
        try:
            requester = exception_request.requested_by
            if not requester or not requester.email:
                logger.warning(
                    f"No requester email for active expiry reminder on exception #{exception_request.id}"
                )
                return False

            marker = f"ACTIVE_EXPIRY:{reminder_stage}"

            context = {
                'exception': exception_request,
                'requester': requester,
                'reminder_stage': reminder_stage,
                'progress_percent': int(progress * 100),
                'review_link': NotificationService._build_portal_link('requestor', exception_request.id),
            }

            html_message = NotificationService._render_active_expiry_reminder_template(context)
            body_with_marker = f"{marker}\n{html_message}"

            from exceptions.tasks import send_email_task
            send_email_task.delay(
                subject=f"[REMINDER] Active Exception Progress {reminder_stage}: {exception_request.short_description[:50]}",
                message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester.email],
            )

            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=requester,
                channel='email',
                reminder_type='Expired_Notice',
                delivery_status='sent',
                message_content=body_with_marker[:1000],
            )

            logger.info(
                f"Active expiry reminder ({reminder_stage}) sent to {requester.email} for exception #{exception_request.id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send active expiry reminder for exception #{exception_request.id}: {str(e)}"
            )

            requester = getattr(exception_request, 'requested_by', None)
            ReminderLog.objects.create(
                exception_request=exception_request,
                sent_to=requester,
                channel='email',
                reminder_type='Expired_Notice',
                delivery_status='failed',
                error_message=str(e),
                message_content=f"ACTIVE_EXPIRY:{reminder_stage}",
            )
            return False
    
    @staticmethod
    def _render_approval_reminder_template(context):
        """Render approval reminder email template."""
        template = """
        <h2>Approval Reminder</h2>
        <p>Hello {{ approver.first_name }},</p>
        <p>This is a reminder to review and approve the following exception:</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Requested By:</strong> {{ exception.requested_by.get_full_name }}</p>
            <p><strong>Deadline:</strong> {{ approval_deadline|date:"M d, Y H:i" }}</p>
        </div>
        
        <p>Please review and approve or reject this exception before the deadline.</p>
        <p><a href="{{ review_link }}">Review Exception</a></p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
    
    @staticmethod
    def _render_approval_notification_template(context):
        """Render approval notification email template."""
        template = """
        <h2>Exception Approved</h2>
        <p>Hello {{ requester.first_name }},</p>
        <p>Your exception has been approved!</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Approved At:</strong> {{ approved_at|date:"M d, Y H:i" }}</p>
            <p><strong>Valid Until:</strong> {{ validity_end|date:"M d, Y" }}</p>
        </div>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
    
    @staticmethod
    def _render_rejection_notification_template(context):
        """Render rejection notification email template."""
        template = """
        <h2>Exception Rejected</h2>
        <p>Hello {{ requester.first_name }},</p>
        <p>Your exception has been rejected.</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            {% if reason %}<p><strong>Reason:</strong> {{ reason }}</p>{% endif %}
        </div>
        
        <p>You can resubmit this exception with modifications.</p>
        <p><a href="{{ review_link }}" style="display: inline-block; padding: 10px 20px; background-color: #6b7280; color: white; text-decoration: none; border-radius: 4px;">Open Exception</a></p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
    
    @staticmethod
    def _render_expired_notification_template(context):
        """Render expiry notification email template."""
        template = """
        <h2>Approval Deadline Expired</h2>
        <p>Hello {{ approver.first_name }},</p>
        <p>The approval deadline for the following exception has passed:</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0; background-color: #fff3cd;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
            <p><strong>Status:</strong> <span style="color: red;">EXPIRED</span></p>
        </div>
        
        <p>Please take action immediately to review and approve/reject this exception.</p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
    
    @staticmethod
    def _render_submission_template(context):
        """Render submission notification email template for approver."""
        template = """
        <h2>New Exception Submission - Action Required</h2>
        <p>Hello {{ approver.first_name }},</p>
        <p>A new exception has been submitted and requires your approval.</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
            <p><strong>Business Unit:</strong> {{ exception.business_unit.name }}</p>
            <p><strong>Risk Rating:</strong> <span style="font-weight: bold; color: {% if risk_rating == 'Critical' %}red{% elif risk_rating == 'High' %}orange{% elif risk_rating == 'Medium' %}#f0ad4e{% else %}green{% endif %};">{{ risk_rating }}</span></p>
            <p><strong>Deadline:</strong> {{ approval_deadline|date:"M d, Y H:i" }}</p>
        </div>
        
        <p>Please review the details and approve or reject this exception before the deadline.</p>
        <p><a href="{{ review_link }}" style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px;">Review Exception</a></p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
    
    @staticmethod
    def _render_risk_owner_template(context):
        """Render risk owner notification email template."""
        template = """
        <h2>Risk Assessment Required - Action Required</h2>
        <p>Hello {{ risk_owner.first_name }},</p>
        <p>An exception has been approved by the BU CIO and now requires your risk assessment.</p>
        
        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0; background-color: #ffe0e0;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Requested By:</strong> {{ requester.get_full_name }}</p>
            <p><strong>Business Unit:</strong> {{ business_unit.name }}</p>
            <p><strong>Risk Rating:</strong> <span style="font-weight: bold; color: red;">{{ risk_rating }} (REQUIRES ASSESSMENT)</span></p>
            {% if approver_notes %}<p><strong>BU CIO Notes:</strong> {{ approver_notes }}</p>{% endif %}
            <p><strong>Deadline:</strong> {{ approval_deadline|date:"M d, Y H:i" }}</p>
        </div>
        
        <p>Please review the exception details and provide your risk assessment before the deadline.</p>
        <p><a href="{{ review_link }}" style="display: inline-block; padding: 10px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 4px;">Assess Risk</a></p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))

    @staticmethod
    def _render_active_expiry_reminder_template(context):
        """Render active exception expiry reminder email template."""
        template = """
        <h2>Active Exception Reminder</h2>
        <p>Hello {{ requester.first_name }},</p>
        <p>Your approved exception has reached {{ reminder_stage }} of its allowed active time window.</p>

        <div style="border: 1px solid #ddd; padding: 15px; margin: 20px 0; background-color: #fff7ed;">
            <p><strong>Exception ID:</strong> #{{ exception.id }}</p>
            <p><strong>Description:</strong> {{ exception.short_description }}</p>
            <p><strong>Current Status:</strong> {{ exception.status }}</p>
            <p><strong>Elapsed Window:</strong> {{ progress_percent }}%</p>
            <p><strong>Reminder Stage:</strong> {{ reminder_stage }}</p>
            <p><strong>End Date:</strong> {{ exception.exception_end_date|date:"M d, Y H:i" }}</p>
        </div>

        <p>Please plan remediation or extension actions before expiry.</p>
        <p><a href="{{ review_link }}" style="display: inline-block; padding: 10px 20px; background-color: #f97316; color: white; text-decoration: none; border-radius: 4px;">Open Exception</a></p>
        """
        from django.template import Template, Context
        t = Template(template)
        return t.render(Context(context))
