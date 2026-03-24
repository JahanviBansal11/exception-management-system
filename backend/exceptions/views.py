from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from datetime import timedelta
from django.contrib.auth.models import User, Group
from django.utils import timezone

from .models import (
    ExceptionRequest,
    AuditLog,
    ReminderLog,
    BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification,
    DataComponent, InternetExposure,
)
from .serializers import (
    ExceptionRequestSerializer,
    BusinessUnitSerializer, ExceptionTypeSerializer, RiskIssueSerializer,
    AssetTypeSerializer, AssetPurposeSerializer, DataClassificationSerializer,
    DataComponentSerializer, InternetExposureSerializer, UserBriefSerializer,
)
from .permissions import IsAssignedApprover, IsAssignedRequestor, IsSecurity


def resolve_role_view(user):
    if user.groups.filter(name="Security").exists():
        return "security"
    if user.groups.filter(name="Approver").exists():
        return "approver"
    if user.groups.filter(name="RiskOwner").exists():
        return "risk-owner"
    if user.groups.filter(name="Requestor").exists():
        return "requestor"
    return "requestor"


def get_visible_exceptions_for_user(user):
    view = resolve_role_view(user)

    if view == "security":
        return ExceptionRequest.objects.exclude(status="Draft"), view
    if view == "approver":
        return ExceptionRequest.objects.filter(assigned_approver=user).exclude(status="Draft"), view
    if view == "risk-owner":
        return ExceptionRequest.objects.filter(risk_owner=user).exclude(status="Draft"), view
    return ExceptionRequest.objects.filter(requested_by=user), view


def is_security_user(user):
    return user.groups.filter(name="Security").exists() or user.is_superuser or user.is_staff


class ExceptionRequestViewSet(viewsets.ModelViewSet):
    queryset = ExceptionRequest.objects.all()
    serializer_class = ExceptionRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        visible, _ = get_visible_exceptions_for_user(self.request.user)
        return visible

    def perform_create(self, serializer):
        """Set requestor automatically on creation."""
        serializer.save(requested_by=self.request.user)

    def perform_update(self, serializer):
        """Block edits on exceptions that are no longer in an editable state."""
        instance = self.get_object()
        EDITABLE_STATUSES = {'Draft', 'Rejected', 'Expired'}
        if instance.status not in EDITABLE_STATUSES:
            raise PermissionDenied(
                f"An exception in '{instance.status}' status cannot be edited. "
                "Only Draft, Rejected, or Expired exceptions are editable."
            )
        # Only the original requestor or Security team may edit
        is_security = self.request.user.groups.filter(name='Security').exists()
        if instance.requested_by != self.request.user and not is_security:
            raise PermissionDenied(
                "Only the original requestor or Security team can edit this exception."
            )
        changed_fields = sorted(list(serializer.validated_data.keys()))
        instance_before = {
            "status": instance.status,
            "version": instance.version,
        }

        serializer.save()

        AuditLog.objects.create(
            exception_request=instance,
            action_type="UPDATE",
            previous_status=instance_before["status"],
            new_status=instance.status,
            performed_by=self.request.user,
            details={
                "message": "Exception details updated",
                "changed_fields": changed_fields,
                "previous_version": instance_before["version"],
                "new_version": instance.version,
            },
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def submit(self, request, pk=None):
        """Submit exception for review."""
        exception = self.get_object()
        
        # Only requestor can submit their own exception
        if exception.requested_by != request.user:
            raise PermissionDenied(
                "Only the requestor can submit this exception."
            )
        
        try:
            exception.submit(request.user)
            return Response(
                {"message": "Exception submitted successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def bu_approve(self, request, pk=None):
        """BU CIO approval stage."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_assigned_approver = exception.assigned_approver == request.user
        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_assigned_approver or is_security):
            raise PermissionDenied(
                "Only assigned approvers or Security team can perform BU approval."
            )

        try:
            exception.bu_approve(request.user, notes=notes)
            return Response(
                {"message": "BU approval captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def risk_assess(self, request, pk=None):
        """Risk owner approval stage for High/Critical exceptions."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_risk_owner = request.user == exception.risk_owner
        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_risk_owner or is_security):
            raise PermissionDenied(
                "Only risk owner or Security team can complete risk assessment."
            )

        try:
            exception.risk_approve(request.user, notes=notes)
            return Response(
                {"message": "Risk owner approval captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def final_approve(self, request, pk=None):
        """Backward-compatible final approve endpoint (risk owner stage)."""
        exception = self.get_object()

        is_risk_owner = request.user == exception.risk_owner
        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_risk_owner or is_security):
            raise PermissionDenied(
                "Only risk owner or Security team can make final approval at this stage."
            )

        try:
            exception.risk_approve(request.user)
            return Response(
                {"message": "Final approval captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def bu_reject(self, request, pk=None):
        """BU CIO rejection stage."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_assigned_approver = exception.assigned_approver == request.user
        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_assigned_approver or is_security):
            raise PermissionDenied(
                "Only assigned approvers or Security team can reject at BU stage."
            )

        try:
            exception.bu_reject(request.user, notes=notes)
            return Response(
                {"message": "BU rejection captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def risk_reject(self, request, pk=None):
        """Risk owner rejection stage for High/Critical exceptions."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_risk_owner = request.user == exception.risk_owner
        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_risk_owner or is_security):
            raise PermissionDenied(
                "Only risk owner or Security team can reject at risk stage."
            )

        try:
            exception.risk_reject(request.user, notes=notes)
            return Response(
                {"message": "Risk rejection captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def final_reject(self, request, pk=None):
        """Backward-compatible final reject endpoint."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        if exception.status == "Submitted":
            is_allowed = exception.assigned_approver == request.user
            stage_label = "BU stage"
        elif exception.status == "AwaitingRiskOwner":
            is_allowed = request.user == exception.risk_owner
            stage_label = "risk stage"
        else:
            is_allowed = False
            stage_label = "current stage"

        is_security = request.user.groups.filter(name="Security").exists()
        if not (is_allowed or is_security):
            raise PermissionDenied(
                f"Only the assigned decision owner or Security team can reject at {stage_label}."
            )

        try:
            exception.final_reject(request.user, notes=notes)
            return Response(
                {"message": "Final rejection captured successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        """Backward-compatible approve endpoint."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_security = request.user.groups.filter(name="Security").exists()

        try:
            if exception.status == "Submitted":
                is_assigned_approver = exception.assigned_approver == request.user
                if not (is_assigned_approver or is_security):
                    raise PermissionDenied(
                        "Only assigned approvers or Security team can approve at BU stage."
                    )
                exception.bu_approve(request.user, notes=notes)
            elif exception.status == "AwaitingRiskOwner":
                is_risk_owner = request.user == exception.risk_owner
                if not (is_risk_owner or is_security):
                    raise PermissionDenied(
                        "Only risk owner or Security team can approve at risk stage."
                    )
                exception.risk_approve(request.user)
            else:
                raise ValidationError("Approve is only valid from Submitted or AwaitingRiskOwner.")
            return Response(
                {"message": "Exception approved successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def reject(self, request, pk=None):
        """Backward-compatible reject endpoint."""
        exception = self.get_object()
        notes = request.data.get("notes", "")

        is_security = request.user.groups.filter(name="Security").exists()

        try:
            if exception.status == "Submitted":
                is_assigned_approver = exception.assigned_approver == request.user
                if not (is_assigned_approver or is_security):
                    raise PermissionDenied(
                        "Only assigned approvers or Security team can reject at BU stage."
                    )
            elif exception.status == "AwaitingRiskOwner":
                is_risk_owner = request.user == exception.risk_owner
                if not (is_risk_owner or is_security):
                    raise PermissionDenied(
                        "Only risk owner or Security team can reject at risk stage."
                    )
            else:
                raise ValidationError("Reject is only valid from Submitted or AwaitingRiskOwner.")
            exception.final_reject(request.user, notes=notes)
            return Response(
                {"message": "Exception rejected successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def close(self, request, pk=None):
        """Close approved exception."""
        exception = self.get_object()
        
        # Only assigned approver or Security group can close
        is_assigned_approver = exception.assigned_approver == request.user
        is_security = request.user.groups.filter(name="Security").exists()
        
        if not (is_assigned_approver or is_security):
            raise PermissionDenied(
                "Only assigned approvers or Security team can close exceptions."
            )
        
        try:
            exception.close(request.user)
            return Response(
                {"message": "Exception closed successfully"},
                status=status.HTTP_200_OK
            )
        except ValueError as e:
            raise ValidationError(str(e))


class ReferenceDataView(APIView):
    """Single endpoint returning all lookup data needed to populate create/edit forms."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_users = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
        approvers = active_users.filter(groups__name='Approver').distinct()
        risk_owners = active_users.filter(groups__name='RiskOwner').distinct()

        return Response({
            "business_units":      BusinessUnitSerializer(BusinessUnit.objects.select_related('cio').all(), many=True).data,
            "exception_types":     ExceptionTypeSerializer(ExceptionType.objects.all(), many=True).data,
            "risk_issues":         RiskIssueSerializer(RiskIssue.objects.all(), many=True).data,
            "asset_types":         AssetTypeSerializer(AssetType.objects.all(), many=True).data,
            "asset_purposes":      AssetPurposeSerializer(AssetPurpose.objects.all(), many=True).data,
            "data_classifications": DataClassificationSerializer(DataClassification.objects.all(), many=True).data,
            "data_components":     DataComponentSerializer(DataComponent.objects.all(), many=True).data,
            "internet_exposures":  InternetExposureSerializer(InternetExposure.objects.all(), many=True).data,
            "users":               UserBriefSerializer(active_users, many=True).data,
            "approvers":           UserBriefSerializer(approvers, many=True).data,
            "risk_owners":         UserBriefSerializer(risk_owners, many=True).data,
        })


class WorklistSummaryView(APIView):
    """Role-aware queue summary counters for dashboard cards."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        visible, view = get_visible_exceptions_for_user(user)

        my_queue = visible

        overdue_qs = my_queue.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
            approval_deadline__lt=now,
        )

        response = {
            "view": view,
            "total_visible": visible.count(),
            "my_queue_total": my_queue.count(),
            "draft": my_queue.filter(status="Draft").count(),
            "submitted": my_queue.filter(status="Submitted").count(),
            "awaiting_risk_owner": my_queue.filter(status="AwaitingRiskOwner").count(),
            "approved": my_queue.filter(status="Approved").count(),
            "rejected": my_queue.filter(status="Rejected").count(),
            "expired": my_queue.filter(status="Expired").count(),
            "closed": my_queue.filter(status="Closed").count(),
            "overdue_approval": overdue_qs.count(),
            "pending_action": my_queue.filter(status__in=["Submitted", "AwaitingRiskOwner"]).count(),
        }

        return Response(response)


class WorklistNotificationsView(APIView):
    """Role-aware notification center feed for dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        soon_window = now + timedelta(hours=24)

        visible, view = get_visible_exceptions_for_user(user)

        events = []

        overdue_qs = visible.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
            approval_deadline__lt=now,
        ).order_by("approval_deadline")[:10]

        for exception in overdue_qs:
            events.append({
                "event_type": "deadline_overdue",
                "severity": "danger",
                "title": "Approval overdue",
                "message": f"Exception #{exception.id} is overdue for action.",
                "exception_id": exception.id,
                "status": exception.status,
                "timestamp": exception.approval_deadline,
            })

        due_soon_qs = visible.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
            approval_deadline__gte=now,
            approval_deadline__lte=soon_window,
        ).order_by("approval_deadline")[:10]

        for exception in due_soon_qs:
            events.append({
                "event_type": "deadline_due_soon",
                "severity": "warning",
                "title": "Approval due soon",
                "message": f"Exception #{exception.id} is due within 24 hours.",
                "exception_id": exception.id,
                "status": exception.status,
                "timestamp": exception.approval_deadline,
            })

        reminder_logs = ReminderLog.objects.filter(exception_request__in=visible)
        if view in {"approver", "risk-owner"}:
            reminder_logs = reminder_logs.filter(sent_to=user)
        reminder_logs = reminder_logs.select_related("exception_request", "sent_to").order_by("-sent_at")[:20]

        for log in reminder_logs:
            events.append({
                "event_type": "reminder_sent" if log.delivery_status == "sent" else "reminder_failed",
                "severity": "info" if log.delivery_status == "sent" else "danger",
                "title": f"Reminder {log.delivery_status}",
                "message": f"{log.reminder_type} for Exception #{log.exception_request_id}",
                "exception_id": log.exception_request_id,
                "status": log.exception_request.status if log.exception_request else None,
                "timestamp": log.sent_at,
            })

        if view == "requestor":
            requester_updates = AuditLog.objects.filter(
                exception_request__in=visible,
            ).exclude(
                action_type="SUBMIT",
            ).exclude(
                performed_by=user,
            ).select_related("exception_request", "performed_by").order_by("-timestamp")[:40]

            for log in requester_updates:
                details = log.details or {}
                feedback = details.get("feedback")
                actor_name = None
                if log.performed_by:
                    actor_name = log.performed_by.get_full_name() or log.performed_by.username
                actor_label = actor_name or "System"

                event_type = "request_updated"
                severity = "info"
                title = "Request updated"

                if log.action_type == "REJECT":
                    event_type = "request_rejected"
                    severity = "danger"
                    title = "Request rejected"
                elif log.action_type == "APPROVE":
                    event_type = "request_approved"
                    severity = "info"
                    title = "Request approved"
                elif log.action_type == "EXPIRE":
                    event_type = "request_expired"
                    severity = "warning"
                    title = "Request expired"
                elif log.action_type == "CLOSE":
                    event_type = "request_closed"
                    severity = "info"
                    title = "Request closed"

                message = details.get("message")
                if not message:
                    status_text = log.new_status or log.action_type
                    message = f"{actor_label} changed your request to {status_text}."

                if feedback:
                    message = f"{message} Feedback: {feedback}"

                events.append({
                    "event_type": event_type,
                    "severity": severity,
                    "title": title,
                    "message": message,
                    "exception_id": log.exception_request_id,
                    "status": log.new_status,
                    "feedback": feedback,
                    "timestamp": log.timestamp,
                })

        events.sort(key=lambda item: item["timestamp"] or now, reverse=True)

        response_items = []
        for item in events[:25]:
            response_items.append({
                **item,
                "timestamp": item["timestamp"].isoformat() if item["timestamp"] else None,
            })

        return Response({
            "view": view,
            "items": response_items,
        })


class SecurityUsersView(APIView):
    """Security-only endpoint to administer users, roles, and emails."""
    permission_classes = [IsAuthenticated]

    ALLOWED_ROLES = {"Requestor", "Approver", "RiskOwner", "Security"}

    def _ensure_security(self, request):
        if not is_security_user(request.user):
            raise PermissionDenied("Only Security team can administer users.")

    def get(self, request):
        self._ensure_security(request)

        users = User.objects.all().order_by("username")
        items = []
        for user in users:
            groups = list(user.groups.values_list("name", flat=True))
            items.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_active": user.is_active,
                "roles": groups,
            })

        return Response({
            "roles": sorted(self.ALLOWED_ROLES),
            "users": items,
        })

    def post(self, request):
        self._ensure_security(request)

        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        email = (request.data.get("email") or "").strip()
        first_name = (request.data.get("first_name") or "").strip()
        last_name = (request.data.get("last_name") or "").strip()
        roles = request.data.get("roles") or []
        is_active = bool(request.data.get("is_active", True))

        if not username:
            raise ValidationError({"username": "Username is required."})
        if not password:
            raise ValidationError({"password": "Password is required."})
        if User.objects.filter(username=username).exists():
            raise ValidationError({"username": "Username already exists."})

        invalid_roles = [role for role in roles if role not in self.ALLOWED_ROLES]
        if invalid_roles:
            raise ValidationError({"roles": f"Invalid roles: {', '.join(invalid_roles)}"})

        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
        )

        if roles:
            groups = [Group.objects.get_or_create(name=role)[0] for role in roles]
            user.groups.set(groups)

        return Response({
            "message": "User created successfully.",
            "id": user.id,
        }, status=status.HTTP_201_CREATED)


class SecurityUserDetailView(APIView):
    """Security-only endpoint to update existing user role/email/status."""
    permission_classes = [IsAuthenticated]

    ALLOWED_ROLES = {"Requestor", "Approver", "RiskOwner", "Security"}

    def _ensure_security(self, request):
        if not is_security_user(request.user):
            raise PermissionDenied("Only Security team can administer users.")

    def patch(self, request, user_id):
        self._ensure_security(request)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError({"user": "User not found."})

        if "email" in request.data:
            user.email = (request.data.get("email") or "").strip()
        if "first_name" in request.data:
            user.first_name = (request.data.get("first_name") or "").strip()
        if "last_name" in request.data:
            user.last_name = (request.data.get("last_name") or "").strip()
        if "is_active" in request.data:
            user.is_active = bool(request.data.get("is_active"))

        password = request.data.get("password")
        if password:
            user.set_password(password)

        if "roles" in request.data:
            roles = request.data.get("roles") or []
            invalid_roles = [role for role in roles if role not in self.ALLOWED_ROLES]
            if invalid_roles:
                raise ValidationError({"roles": f"Invalid roles: {', '.join(invalid_roles)}"})
            groups = [Group.objects.get_or_create(name=role)[0] for role in roles]
            user.groups.set(groups)

        user.save()

        return Response({"message": "User updated successfully."})
