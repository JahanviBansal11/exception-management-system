from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from exceptions.models import ExceptionRequest, AuditLog
from exceptions.models import BusinessUnit, ExceptionType
from exceptions.serializers import ExceptionRequestSerializer, ExceptionRequestListSerializer
from exceptions.services.workflow_service import WorkflowService
from exceptions.permissions import IsSecurity, RISK_OWNER_GROUP_NAMES, SECURITY_GROUP_NAME
from .helpers import get_visible_exceptions


def _apply_time_based_transitions(queryset):
    """
    Run expiry transitions synchronously against the given queryset.
    Called on every list/retrieve so statuses stay accurate without Celery.
    Celery Beat duplicates this proactively in production but is not required.
    """
    from exceptions.services.escalation_engine import EscalationEngine
    now = timezone.now()

    has_expired = queryset.filter(
        status="Approved", exception_end_date__lt=now
    ).exists()
    has_deadline_passed = queryset.filter(
        status__in=["Submitted", "AwaitingRiskOwner"],
        approval_deadline__isnull=False,
        approval_deadline__lt=now,
    ).exists()

    if has_expired:
        EscalationEngine.expire_active_exceptions()
    if has_deadline_passed:
        EscalationEngine.escalate_expired_approvals()


class ExceptionRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ExceptionRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return ExceptionRequestListSerializer
        return ExceptionRequestSerializer

    def get_queryset(self):
        qs, _ = get_visible_exceptions(self.request.user)

        # FK traversals: select_related does a single JOIN instead of separate queries
        qs = qs.select_related(
            "business_unit__cio", "exception_type",
            "requested_by", "assigned_approver", "risk_owner",
        )

        if self.action == "retrieve":
            qs = qs.select_related(
                "business_unit__cio", "exception_type", "risk_issue",
                "asset_type", "asset_purpose", "data_classification", "internet_exposure",
                "requested_by", "assigned_approver", "risk_owner",
                # parent snapshot FK traversals
                "parent_exception__exception_type", "parent_exception__risk_issue",
                "parent_exception__asset_type", "parent_exception__asset_purpose",
                "parent_exception__data_classification", "parent_exception__internet_exposure",
                "parent_exception__assigned_approver", "parent_exception__risk_owner",
            )
            # audit_logs need performed_by for end_date_change_history and rejection_feedback
            audit_prefetch = Prefetch(
                "audit_logs",
                queryset=AuditLog.objects.select_related("performed_by").order_by("-timestamp"),
            )
            qs = qs.prefetch_related(
                audit_prefetch,
                "checkpoints__completed_by",
                "reminder_logs",
                "data_components",
                "parent_exception__data_components",
                "parent_exception__checkpoints",
            )

        return qs

    def list(self, request, *args, **kwargs):
        qs, _ = get_visible_exceptions(request.user)
        _apply_time_based_transitions(qs)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        _apply_time_based_transitions(ExceptionRequest.objects.filter(pk=instance.pk))
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status not in {"Draft", "Rejected", "ApprovalDeadlinePassed"}:
            raise PermissionDenied(
                f"Exceptions in '{instance.status}' status cannot be edited."
            )
        if instance.requested_by != self.request.user and not self.request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can edit this exception.")

        changed_fields = sorted(serializer.validated_data.keys())
        prev_version = instance.version
        serializer.save()

        AuditLog.objects.create(
            exception_request=instance,
            action_type="UPDATE",
            previous_status=instance.status,
            new_status=instance.status,
            performed_by=self.request.user,
            details={
                "message": "Exception details updated",
                "changed_fields": changed_fields,
                "previous_version": prev_version,
                "new_version": instance.version,
            },
        )

    # ── Workflow actions ─────────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Draft → Submitted."""
        exception = self.get_object()
        if exception.requested_by != request.user:
            raise PermissionDenied("Only the requestor can submit this exception.")
        try:
            WorkflowService.submit(exception, request.user)
            return Response({"message": "Exception submitted successfully."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def bu_approve(self, request, pk=None):
        """Submitted → Approved or AwaitingRiskOwner (BU CIO stage)."""
        exception = self.get_object()
        if not (exception.assigned_approver == request.user or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the assigned approver or Security team can perform BU approval.")
        try:
            WorkflowService.bu_approve(exception, request.user, notes=request.data.get("notes", ""))
            return Response({"message": "BU approval recorded."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def bu_reject(self, request, pk=None):
        """Submitted → Rejected (BU CIO stage)."""
        exception = self.get_object()
        if not (exception.assigned_approver == request.user or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the assigned approver or Security team can reject at BU stage.")
        try:
            WorkflowService.bu_reject(exception, request.user, notes=request.data.get("notes", ""))
            return Response({"message": "BU rejection recorded."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def risk_assess(self, request, pk=None):
        """AwaitingRiskOwner → Approved (Risk Owner approval)."""
        exception = self.get_object()
        if not (request.user == exception.risk_owner or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the risk owner or Security team can complete risk assessment.")
        try:
            WorkflowService.risk_approve(exception, request.user, notes=request.data.get("notes", ""))
            return Response({"message": "Risk owner approval recorded."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def risk_reject(self, request, pk=None):
        """AwaitingRiskOwner → Rejected (Risk Owner stage)."""
        exception = self.get_object()
        if not (request.user == exception.risk_owner or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the risk owner or Security team can reject at risk stage.")
        try:
            WorkflowService.risk_reject(exception, request.user, notes=request.data.get("notes", ""))
            return Response({"message": "Risk rejection recorded."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        """Approved → Closed."""
        exception = self.get_object()
        if not (exception.assigned_approver == request.user or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the assigned approver or Security team can close exceptions.")
        try:
            WorkflowService.close(exception, request.user)
            return Response({"message": "Exception closed."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def resubmit(self, request, pk=None):
        """ApprovalDeadlinePassed → new Draft (resubmission). Parent status unchanged."""
        old = self.get_object()
        if old.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can resubmit.")
        if old.status != "ApprovalDeadlinePassed":
            raise ValidationError({"detail": "Resubmit is only available for exceptions where the approval deadline has passed."})
        try:
            with transaction.atomic():
                new_exc = self._copy_exception(old)
                WorkflowService.resubmit(old, request.user, new_exception_id=new_exc.id)
            return Response({
                "message": "Resubmission draft created. Edit and submit the new draft.",
                "new_exception_id": new_exc.id,
            })
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def modify(self, request, pk=None):
        """Rejected → Modified + create new fully-editable Draft (modification)."""
        old = self.get_object()
        if old.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can request a modification.")
        try:
            with transaction.atomic():
                new_exc = self._copy_exception(old)
                WorkflowService.mark_modified(
                    old, request.user,
                    related_version=new_exc.version,
                    new_exception_id=new_exc.id,
                )
            return Response({
                "message": "Modification created. Edit and submit the new draft.",
                "new_exception_id": new_exc.id,
            })
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def extend(self, request, pk=None):
        """Approved | Expired → Extended + create new fully-editable Draft (extension).
        Available from 50% of the approved period through 2 weeks after end date."""
        old = self.get_object()
        if old.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can request an extension.")

        if old.status not in {"Approved", "Expired"}:
            raise ValidationError({"detail": "Extension is only available for Approved or Expired exceptions."})

        now = timezone.now()
        approved_at = old.approved_at
        end_date = old.exception_end_date

        if approved_at and end_date:
            midpoint = approved_at + (end_date - approved_at) / 2
            grace_deadline = end_date + timedelta(days=14)
            if now < midpoint:
                raise ValidationError({
                    "detail": f"Extension is not yet available. It opens at the halfway point of the approved period ({midpoint.strftime('%d/%m/%Y %H:%M')} UTC)."
                })
            if now > grace_deadline:
                raise ValidationError({
                    "detail": "Extension window has closed. Extensions must be requested within 14 days of the end date."
                })

        try:
            with transaction.atomic():
                new_exc = self._copy_exception(old)
                WorkflowService.mark_extended(
                    old, request.user,
                    related_version=new_exc.version,
                    new_exception_id=new_exc.id,
                )
            return Response({
                "message": "Extension created. Edit and submit the new draft.",
                "new_exception_id": new_exc.id,
            })
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def remediate(self, request, pk=None):
        """Expired → Closed. Requestor documents remediation and closes the exception."""
        exception = self.get_object()
        if exception.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can remediate an exception.")
        notes = (request.data.get("notes") or "").strip()
        if not notes:
            raise ValidationError({"notes": "Remediation notes are required."})
        try:
            WorkflowService.remediate(exception, request.user, notes)
            return Response({"message": "Exception remediated and closed."})
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"])
    def close_rejected(self, request, pk=None):
        """Rejected → Closed by requestor. Permanently closes without further action."""
        exception = self.get_object()
        if exception.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can close a rejected exception.")
        try:
            WorkflowService.close_rejected(exception, request.user)
            return Response({"message": "Exception permanently closed."})
        except ValueError as e:
            raise ValidationError(str(e))

    def destroy(self, request, *args, **kwargs):
        """Delete a Draft exception. Only the requestor or Security can delete drafts."""
        instance = self.get_object()
        if instance.status != "Draft":
            raise ValidationError({"detail": "Only Draft exceptions can be deleted."})
        if instance.requested_by != request.user and not request.user.groups.filter(name=SECURITY_GROUP_NAME).exists():
            raise PermissionDenied("Only the original requestor or Security team can delete this draft.")
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _copy_exception(old):
        """Create a new Draft copying all fields from old and set parent_exception."""
        new_exc = ExceptionRequest.objects.create(
            business_unit=old.business_unit,
            exception_type=old.exception_type,
            risk_issue=old.risk_issue,
            asset_type=old.asset_type,
            asset_purpose=old.asset_purpose,
            data_classification=old.data_classification,
            internet_exposure=old.internet_exposure,
            number_of_assets=old.number_of_assets,
            short_description=old.short_description,
            reason_for_exception=old.reason_for_exception,
            compensatory_controls=old.compensatory_controls,
            requested_by=old.requested_by,
            assigned_approver=old.assigned_approver,
            risk_owner=old.risk_owner,
            exception_end_date=old.exception_end_date,
            parent_exception=old,
        )
        new_exc.data_components.set(old.data_components.all())
        return new_exc

    @action(detail=True, methods=["post"])
    def update_end_date(self, request, pk=None):
        """Update exception_end_date with mandatory notes."""
        exception = self.get_object()
        if not (exception.assigned_approver == request.user or
                request.user == exception.risk_owner or
                request.user.groups.filter(name=SECURITY_GROUP_NAME).exists()):
            raise PermissionDenied("Only the approver, risk owner, or Security team can update end date.")

        if exception.status in {"Closed", "ApprovalDeadlinePassed", "Modified", "Extended", "Expired"}:
            raise ValidationError("End date cannot be changed for exceptions in a terminal or post-approval state.")

        end_date_raw = request.data.get("exception_end_date")
        if not end_date_raw:
            raise ValidationError({"exception_end_date": "This field is required."})
        new_end_date = parse_datetime(str(end_date_raw))
        if new_end_date is None:
            raise ValidationError({"exception_end_date": "Invalid datetime format."})
        if timezone.is_naive(new_end_date):
            new_end_date = timezone.make_aware(new_end_date, timezone.get_current_timezone())
        if new_end_date <= timezone.now():
            raise ValidationError({"exception_end_date": "End date must be in the future."})

        notes = (request.data.get("notes") or "").strip()
        if not notes:
            raise ValidationError({"notes": "Notes are required when updating end date."})

        previous = exception.exception_end_date
        exception.exception_end_date = new_end_date
        exception.save(update_fields=["exception_end_date", "updated_at"])

        AuditLog.objects.create(
            exception_request=exception,
            action_type="UPDATE",
            previous_status=exception.status,
            new_status=exception.status,
            performed_by=request.user,
            details={
                "end_date_change": True,
                "previous_end_date": previous.isoformat() if previous else None,
                "new_end_date": new_end_date.isoformat(),
                "notes": notes,
            },
        )
        return Response({"message": "End date updated.", "new_end_date": new_end_date.isoformat()})

    @action(detail=False, methods=["get"])
    def get_assignment_defaults(self, request):
        """Return the BU CIO and ExceptionType risk owner for given IDs."""
        bu_id = request.query_params.get("business_unit_id")
        et_id = request.query_params.get("exception_type_id")
        
        if not bu_id and not et_id:
            raise ValidationError({"error": "At least one parameter is required."})

        response_data = {}
        
        if bu_id:
            try:
                bu = BusinessUnit.objects.get(id=bu_id)
                if bu.cio:
                    response_data.update({
                        "assigned_approver_id": bu.cio.id,
                        "assigned_approver_name": bu.cio.get_full_name() or bu.cio.username,
                        "assigned_approver_email": bu.cio.email,
                    })
            except BusinessUnit.DoesNotExist:
                pass
                
        if et_id:
            try:
                et = ExceptionType.objects.get(id=et_id)
                if et.risk_owner:
                    response_data.update({
                        "risk_owner_id": et.risk_owner.id,
                        "risk_owner_name": et.risk_owner.get_full_name() or et.risk_owner.username,
                        "risk_owner_email": et.risk_owner.email,
                    })
            except ExceptionType.DoesNotExist:
                pass

        return Response(response_data)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated, IsSecurity])
    def audit_logs(self, request, pk=None):
        """Return the audit trail for a single exception (Security only)."""
        exception = self.get_object()
        raw_limit = request.query_params.get("limit", "50")
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            raise ValidationError({"limit": "Must be an integer."})
        if not (1 <= limit <= 200):
            raise ValidationError({"limit": "Must be between 1 and 200."})

        logs = (
            AuditLog.objects.filter(exception_request=exception)
            .select_related("performed_by")
            .order_by("-timestamp")[:limit]
        )
        results = [
            {
                "id": log.id,
                "action_type": log.action_type,
                "previous_status": log.previous_status,
                "new_status": log.new_status,
                "performed_by": log.performed_by.username if log.performed_by else None,
                "performed_by_name": (log.performed_by.get_full_name() or log.performed_by.username)
                                     if log.performed_by else None,
                "timestamp": log.timestamp.isoformat(),
                "details": log.details or {},
            }
            for log in logs
        ]
        return Response({"exception_id": exception.id, "count": len(results), "results": results})
