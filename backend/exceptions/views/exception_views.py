from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from exceptions.models import ExceptionRequest, AuditLog
from exceptions.models import BusinessUnit, ExceptionType
from exceptions.serializers import ExceptionRequestSerializer, ExceptionRequestListSerializer
from exceptions.services.workflow_service import WorkflowService
from exceptions.permissions import IsSecurity, RISK_OWNER_GROUP_NAMES, SECURITY_GROUP_NAME
from .helpers import get_visible_exceptions


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
            )

        return qs

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
