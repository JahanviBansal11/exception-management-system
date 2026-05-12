"""
WorkflowService — the single authoritative orchestrator for all exception state transitions.

All status changes, checkpoint recording, and notification dispatch flow through here.
Views call this service directly. Models are thin data containers.

Import graph:
    WorkflowService → RiskService (calculate before routing)
    WorkflowService → NotificationService (notify after status change)
    WorkflowService → AuditLog, ExceptionCheckpoint (writes inside atomic block)
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


class WorkflowService:

    # ── PRIMITIVES ───────────────────────────────────────────────────────

    @staticmethod
    def change_status(exception_request, new_status, user, action_type, details=None):
        """
        Atomic status transition + AuditLog creation.
        Validates the transition against APPROVAL_ALLOWED_TRANSITIONS.
        Sets approval_deadline on Submitted, approved_at on Approved.
        """
        allowed = exception_request.APPROVAL_ALLOWED_TRANSITIONS.get(
            exception_request.status, []
        )
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {exception_request.status} → {new_status}"
            )

        from exceptions.models import AuditLog

        previous = exception_request.status

        with transaction.atomic():
            exception_request.status = new_status

            if new_status == "Submitted":
                exception_request.approval_deadline = timezone.now() + timedelta(
                    days=exception_request.exception_type.approval_sla_days
                )
                exception_request.approved_at = None

            elif new_status == "Approved":
                exception_request.approved_at = timezone.now()
                exception_request.reminder_stage = "None"

            exception_request.save(
                update_fields=["status", "updated_at", "approval_deadline", "approved_at", "reminder_stage"]
            )

            AuditLog.objects.create(
                exception_request=exception_request,
                action_type=action_type,
                previous_status=previous,
                new_status=new_status,
                performed_by=user,
                details=details or {},
            )

        logger.info(
            "Exception #%s: %s → %s (by %s)",
            exception_request.id, previous, new_status,
            user.username if user else "system",
        )

    @staticmethod
    def record_checkpoint(exception_request, checkpoint, status="completed", user=None, notes=""):
        """
        Upsert a workflow milestone checkpoint.
        Creates on first call, updates on subsequent calls.
        """
        from exceptions.models import ExceptionCheckpoint

        obj, created = ExceptionCheckpoint.objects.get_or_create(
            exception_request=exception_request,
            checkpoint=checkpoint,
            defaults={
                "status": status,
                "completed_by": user,
                "completed_at": timezone.now() if status == "completed" else None,
                "notes": notes,
            },
        )

        if not created:
            obj.status = status
            obj.completed_by = user
            obj.notes = notes
            if status == "completed" and obj.completed_at is None:
                obj.completed_at = timezone.now()
            obj.save(update_fields=["status", "completed_by", "completed_at", "notes"])

    # ── WORKFLOW ACTIONS (linear forward pass) ───────────────────────────

    @staticmethod
    def submit(exception_request, user):
        """Draft → Submitted. Sets approval deadline. Notifies BU CIO."""
        if exception_request.status != "Draft":
            raise ValueError("Only Draft exceptions can be submitted.")

        with transaction.atomic():
            WorkflowService.change_status(exception_request, "Submitted", user, "SUBMIT")
            exception_request.checkpoints.all().delete()
            WorkflowService.record_checkpoint(
                exception_request, "exception_requested", "completed",
                user=user, notes="Exception submitted by requestor",
            )
            WorkflowService.record_checkpoint(
                exception_request, "bu_approval_notified", "pending",
                notes="Awaiting BU CIO decision",
            )

        from exceptions.services.notification_service import NotificationService
        NotificationService.send_submission_notification(exception_request)
        approver = exception_request.assigned_approver
        if approver:
            NotificationService.notify(
                recipients=[approver],
                exception=exception_request,
                notification_type='exception_submitted',
                severity='info',
                title='New exception submitted',
                message=f'Exception #{exception_request.id} "{exception_request.short_description[:60]}" requires your review.',
            )

    @staticmethod
    def bu_approve(exception_request, user, notes=""):
        """
        Submitted → AwaitingRiskOwner (High/Critical risk)
               OR → Approved (Low/Medium risk).
        Notes are mandatory for High/Critical.
        """
        if exception_request.status != "Submitted":
            raise ValueError("Only Submitted exceptions can receive BU approval.")

        # Ensure risk is calculated before routing decision (outside atomic — has its own)
        if exception_request.risk_score is None or not exception_request.risk_rating:
            from exceptions.services.risk_service import RiskService
            RiskService.recalculate_and_persist(exception_request)
            exception_request.refresh_from_db(fields=["risk_score", "risk_rating"])

        approval_notes = (notes or "").strip()

        from exceptions.services.notification_service import NotificationService

        if exception_request.risk_rating in {"High", "Critical"}:
            if not approval_notes:
                raise ValueError(
                    "Approver notes are required when approving High/Critical exceptions."
                )
            with transaction.atomic():
                WorkflowService.change_status(
                    exception_request, "AwaitingRiskOwner", user, "APPROVE",
                    details={
                        "stage": "bu_approval", "decision": "approved",
                        "risk_rating": exception_request.risk_rating,
                        "approver_notes": approval_notes,
                    },
                )
                WorkflowService.record_checkpoint(
                    exception_request, "bu_approval_notified", "completed",
                    user=user, notes="BU CIO reviewed and approved",
                )
                WorkflowService.record_checkpoint(
                    exception_request, "bu_approval_decision", "completed",
                    user=user,
                    notes=f"BU CIO approved. Notes: {approval_notes}",
                )
                WorkflowService.record_checkpoint(
                    exception_request, "risk_assessment_notified", "pending",
                    notes=f"Awaiting risk owner. BU CIO notes: {approval_notes}",
                )
            NotificationService.send_risk_owner_notification(exception_request)
            risk_owner = exception_request.risk_owner
            if risk_owner:
                NotificationService.notify(
                    recipients=[risk_owner],
                    exception=exception_request,
                    notification_type='exception_submitted',
                    severity='warning',
                    title='Risk assessment required',
                    message=f'Exception #{exception_request.id} has been approved by BU CIO and requires your risk assessment.',
                )
            return

        # Low / Medium — auto-approve
        if not exception_request.exception_end_date:
            raise ValueError("Exception end date must be set before the exception can be approved.")

        with transaction.atomic():
            WorkflowService.change_status(
                exception_request, "Approved", user, "APPROVE",
                details={
                    "stage": "bu_approval", "decision": "approved",
                    "risk_rating": exception_request.risk_rating,
                    "approver_notes": approval_notes,
                },
            )
            WorkflowService.record_checkpoint(
                exception_request, "bu_approval_notified", "completed",
                user=user, notes="BU CIO reviewed and approved",
            )
            WorkflowService.record_checkpoint(
                exception_request, "bu_approval_decision", "completed",
                user=user,
                notes=f"BU CIO approved. Notes: {approval_notes}" if approval_notes
                      else "BU CIO decision: approved",
            )
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_notified", "skipped",
                notes="Risk owner stage skipped for Low/Medium risk",
            )
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_complete", "skipped",
                notes="Risk owner stage skipped for Low/Medium risk",
            )
            WorkflowService.record_checkpoint(
                exception_request, "final_decision", "completed",
                user=user,
                notes=f"Approved by BU CIO (Low/Medium risk). Notes: {approval_notes}" if approval_notes
                      else "Approved by BU CIO (Low/Medium risk)",
            )
        NotificationService.send_exception_approved_notification(exception_request, approved_by_user=user)
        NotificationService.notify(
            recipients=[exception_request.requested_by],
            exception=exception_request,
            notification_type='exception_approved',
            severity='success',
            title='Exception approved',
            message=f'Exception #{exception_request.id} "{exception_request.short_description[:60]}" has been approved.',
        )

    @staticmethod
    def bu_reject(exception_request, user, notes):
        """Submitted → Rejected. Notes are mandatory."""
        if exception_request.status != "Submitted":
            raise ValueError("Only Submitted exceptions can be rejected by BU CIO.")

        feedback = (notes or "").strip()
        if not feedback:
            raise ValueError("Rejection feedback is required.")

        with transaction.atomic():
            WorkflowService.change_status(
                exception_request, "Rejected", user, "REJECT",
                details={"stage": "bu_approval", "decision": "rejected", "feedback": feedback},
            )
            WorkflowService.record_checkpoint(
                exception_request, "bu_approval_notified", "completed",
                user=user, notes="BU CIO reviewed request",
            )
            WorkflowService.record_checkpoint(
                exception_request, "bu_approval_decision", "completed",
                user=user, notes="BU CIO decision: rejected",
            )
            for cp in ("risk_assessment_notified", "risk_assessment_complete"):
                WorkflowService.record_checkpoint(
                    exception_request, cp, "skipped",
                    notes="Skipped — rejected at BU stage",
                )
            WorkflowService.record_checkpoint(
                exception_request, "final_decision", "completed",
                user=user, notes=f"Rejected by BU CIO. Feedback: {feedback}",
            )

        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_rejected_notification(exception_request, feedback)
        NotificationService.notify(
            recipients=[exception_request.requested_by],
            exception=exception_request,
            notification_type='exception_rejected',
            severity='danger',
            title='Exception rejected',
            message=f'Exception #{exception_request.id} was rejected. Feedback: {feedback}',
        )

    @staticmethod
    def risk_approve(exception_request, user, notes=""):
        """AwaitingRiskOwner → Approved."""
        if exception_request.status != "AwaitingRiskOwner":
            raise ValueError("Only AwaitingRiskOwner exceptions can be approved by risk owner.")

        if not exception_request.exception_end_date:
            raise ValueError("Exception end date must be set before the exception can be approved.")

        with transaction.atomic():
            WorkflowService.change_status(exception_request, "Approved", user, "APPROVE")
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_notified", "completed",
                user=user, notes="Risk owner acknowledged task",
            )
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_complete", "completed",
                user=user, notes=notes or "Risk owner approved exception",
            )
            WorkflowService.record_checkpoint(
                exception_request, "final_decision", "completed",
                user=user, notes="Final decision: approved by Risk Owner",
            )

        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_approved_notification(exception_request, approved_by_user=user)
        NotificationService.notify(
            recipients=[exception_request.requested_by],
            exception=exception_request,
            notification_type='exception_approved',
            severity='success',
            title='Exception approved',
            message=f'Exception #{exception_request.id} "{exception_request.short_description[:60]}" has been approved.',
        )

    @staticmethod
    def risk_reject(exception_request, user, notes):
        """AwaitingRiskOwner → Rejected. Notes are mandatory."""
        if exception_request.status != "AwaitingRiskOwner":
            raise ValueError("Only AwaitingRiskOwner exceptions can be rejected by risk owner.")

        feedback = (notes or "").strip()
        if not feedback:
            raise ValueError("Rejection feedback is required.")

        with transaction.atomic():
            WorkflowService.change_status(
                exception_request, "Rejected", user, "REJECT",
                details={"stage": "risk_owner", "decision": "rejected", "feedback": feedback},
            )
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_notified", "completed",
                user=user, notes="Risk owner acknowledged task",
            )
            WorkflowService.record_checkpoint(
                exception_request, "risk_assessment_complete", "completed",
                user=user, notes=notes or "Risk owner rejected exception",
            )
            WorkflowService.record_checkpoint(
                exception_request, "final_decision", "completed",
                user=user, notes=f"Rejected by Risk Owner. Feedback: {feedback}",
            )

        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_rejected_notification(exception_request, feedback)
        NotificationService.notify(
            recipients=[exception_request.requested_by],
            exception=exception_request,
            notification_type='exception_rejected',
            severity='danger',
            title='Exception rejected',
            message=f'Exception #{exception_request.id} was rejected by risk owner. Feedback: {feedback}',
        )

    @staticmethod
    def mark_expired(exception_request, user):
        """Submitted | AwaitingRiskOwner → ApprovalDeadlinePassed. Called by EscalationEngine."""
        if exception_request.status not in {"Submitted", "AwaitingRiskOwner"}:
            raise ValueError("Only pending approvals can have their deadline passed.")

        WorkflowService.change_status(
            exception_request, "ApprovalDeadlinePassed", user, "EXPIRE",
            details={"message": "Approval deadline passed without a decision."},
        )

        from exceptions.services.notification_service import NotificationService
        recipients = [r for r in [exception_request.assigned_approver, exception_request.requested_by] if r]
        NotificationService.notify(
            recipients=recipients,
            exception=exception_request,
            notification_type='approval_deadline_passed',
            severity='danger',
            title='Approval deadline passed',
            message=f'Exception #{exception_request.id} approval deadline has passed without a decision.',
        )

    @staticmethod
    def mark_active_expired(exception_request, user):
        """Approved → Expired. Called by EscalationEngine when exception_end_date passes."""
        if exception_request.status != "Approved":
            raise ValueError("Only Approved exceptions can be marked as Expired.")

        WorkflowService.change_status(
            exception_request, "Expired", user, "EXPIRE",
            details={"message": "Exception end date passed — pending extension or remediation."},
        )

    @staticmethod
    def close(exception_request, user):
        """Approved → Closed."""
        if exception_request.status != "Approved":
            raise ValueError("Only Approved exceptions can be closed.")

        WorkflowService.change_status(exception_request, "Closed", user, "CLOSE")

        from exceptions.services.notification_service import NotificationService
        NotificationService.notify(
            recipients=[exception_request.requested_by],
            exception=exception_request,
            notification_type='exception_closed',
            severity='info',
            title='Exception closed',
            message=f'Exception #{exception_request.id} has been closed.',
        )

    @staticmethod
    def close_rejected(exception_request, user):
        """Rejected → Closed. Requestor gives up — no modification or extension will follow."""
        if exception_request.status != "Rejected":
            raise ValueError("Only Rejected exceptions can be closed this way.")

        WorkflowService.change_status(
            exception_request, "Closed", user, "CLOSE",
            details={"message": "Requestor closed rejected exception without further action."},
        )

    @staticmethod
    def mark_modified(exception_request, user, related_version=None, new_exception_id=None):
        """
        Rejected → Modified. Called when a modification request supersedes this exception.
        new_exception_id: ID of the new Draft created to replace this one (stored in audit log).
        """
        if exception_request.status != "Rejected":
            raise ValueError("Only Rejected exceptions can be marked as Modified.")

        details = {"message": "Superseded by a modification request.", "related_version": related_version}
        if new_exception_id is not None:
            details["new_exception_id"] = new_exception_id

        WorkflowService.change_status(
            exception_request, "Modified", user, "MODIFY",
            details=details,
        )

    @staticmethod
    def remediate(exception_request, user, notes):
        """Expired → Closed. Requestor documents remediation steps and closes the exception."""
        if exception_request.status != "Expired":
            raise ValueError("Only Expired exceptions can be remediated and closed.")

        notes = (notes or "").strip()
        if not notes:
            raise ValueError("Remediation notes are required.")

        WorkflowService.change_status(
            exception_request, "Closed", user, "CLOSE",
            details={
                "message": "Exception closed via remediation.",
                "remediation_notes": notes,
            },
        )

    @staticmethod
    def mark_extended(exception_request, user, related_version=None, new_exception_id=None):
        """
        Approved | Expired → Extended. Called when an extension request supersedes this exception.
        new_exception_id: ID of the new Draft created to replace this one (stored in audit log).
        """
        if exception_request.status not in {"Approved", "Expired"}:
            raise ValueError("Only Approved or Expired exceptions can be marked as Extended.")

        details = {"message": "Superseded by an extension request.", "related_version": related_version}
        if new_exception_id is not None:
            details["new_exception_id"] = new_exception_id

        WorkflowService.change_status(
            exception_request, "Extended", user, "EXTEND",
            details=details,
        )
