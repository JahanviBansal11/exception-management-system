from rest_framework import serializers
from django.utils import timezone

from exceptions.models import (
    ExceptionRequest, ExceptionCheckpoint, AuditLog,
)
from exceptions.permissions import RISK_OWNER_GROUP_NAMES


class CheckpointSerializer(serializers.ModelSerializer):
    checkpoint_display = serializers.CharField(source='get_checkpoint_display', read_only=True)
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExceptionCheckpoint
        fields = [
            'checkpoint', 'checkpoint_display', 'status',
            'completed_at', 'completed_by', 'completed_by_name', 'notes',
        ]

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.username
        return None

class ExceptionRequestListSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.SerializerMethodField()
    assigned_approver_username = serializers.SerializerMethodField()
    risk_owner_username = serializers.SerializerMethodField()
    business_unit_code = serializers.CharField(source='business_unit.bu_code', read_only=True)
    business_unit_name = serializers.CharField(source='business_unit.name', read_only=True)
    submitted_at = serializers.SerializerMethodField()

    class Meta:
        model = ExceptionRequest
        fields = (
            "id", "business_unit", "business_unit_code", "business_unit_name",
            "exception_type", "risk_issue",
            "asset_type", "asset_purpose", "data_classification",
            "internet_exposure", "number_of_assets",
            "short_description", "risk_score", "risk_rating",
            "created_at", "updated_at", "approval_deadline", "approved_at",
            "exception_end_date", "status",
            "requested_by", "requested_by_username",
            "assigned_approver", "assigned_approver_username",
            "risk_owner", "risk_owner_username",
            "version", "parent_exception", "submitted_at",
        )
        read_only_fields = fields

    def get_requested_by_username(self, obj):
        return obj.requested_by.username if obj.requested_by else None

    def get_assigned_approver_username(self, obj):
        return obj.assigned_approver.username if obj.assigned_approver else None

    def get_risk_owner_username(self, obj):
        return obj.risk_owner.username if obj.risk_owner else None

    def get_submitted_at(self, obj):
        log = AuditLog.objects.filter(
            exception_request=obj, action_type="SUBMIT",
        ).order_by("timestamp").first()
        if log:
            return log.timestamp
        if obj.status not in {"Draft"}:
            return obj.updated_at
        return None


def _build_snapshot(obj):
    """Return a flat human-readable dict of comparable fields for an ExceptionRequest instance.

    Includes parent_status and parent_reached_risk_owner so the frontend can determine
    whether the viewing user had prior visibility into this parent exception.
    Uses prefetched checkpoints (parent_exception__checkpoints) to avoid extra queries.
    """
    checkpoints = list(obj.checkpoints.all())
    parent_reached_risk_owner = any(
        cp.checkpoint == "risk_assessment_notified" and cp.status in ("pending", "completed", "escalated")
        for cp in checkpoints
    )
    return {
        "short_description": obj.short_description or "",
        "reason_for_exception": obj.reason_for_exception or "",
        "compensatory_controls": obj.compensatory_controls or "",
        "exception_end_date": obj.exception_end_date.isoformat() if obj.exception_end_date else None,
        "number_of_assets": obj.number_of_assets,
        "exception_type_name": obj.exception_type.name if obj.exception_type else None,
        "risk_issue_name": obj.risk_issue.title if obj.risk_issue else None,
        "asset_type_name": obj.asset_type.name if obj.asset_type else None,
        "asset_purpose_name": obj.asset_purpose.name if obj.asset_purpose else None,
        "data_classification_name": obj.data_classification.level if obj.data_classification else None,
        "internet_exposure_name": obj.internet_exposure.label if obj.internet_exposure else None,
        "risk_owner_name": (obj.risk_owner.get_full_name() or obj.risk_owner.username) if obj.risk_owner else None,
        "assigned_approver_name": (obj.assigned_approver.get_full_name() or obj.assigned_approver.username) if obj.assigned_approver else None,
        "data_component_names": sorted(obj.data_components.values_list('name', flat=True)),
        # Access-control metadata for the frontend
        "parent_status": obj.status,
        "parent_reached_risk_owner": parent_reached_risk_owner,
    }


class ExceptionRequestSerializer(serializers.ModelSerializer):
    checkpoints = CheckpointSerializer(many=True, read_only=True)
    submitted_at = serializers.SerializerMethodField()
    rejection_feedback = serializers.SerializerMethodField()
    end_date_change_history = serializers.SerializerMethodField()
    derived_request_ids = serializers.SerializerMethodField()
    requested_by_username = serializers.SerializerMethodField()
    assigned_approver_username = serializers.SerializerMethodField()
    risk_owner_username = serializers.SerializerMethodField()
    business_unit_code = serializers.CharField(source='business_unit.bu_code', read_only=True)
    business_unit_name = serializers.CharField(source='business_unit.name', read_only=True)
    # Human-readable FK name fields for the current exception
    exception_type_name = serializers.SerializerMethodField()
    risk_issue_name = serializers.SerializerMethodField()
    asset_type_name = serializers.SerializerMethodField()
    asset_purpose_name = serializers.SerializerMethodField()
    data_classification_name = serializers.SerializerMethodField()
    internet_exposure_name = serializers.SerializerMethodField()
    risk_owner_name = serializers.SerializerMethodField()
    assigned_approver_name = serializers.SerializerMethodField()
    data_component_names = serializers.SerializerMethodField()
    # Snapshot of parent fields for diff display (None when no parent)
    parent_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = ExceptionRequest
        fields = (
            "id", "business_unit", "business_unit_code", "business_unit_name",
            "exception_type", "exception_type_name",
            "risk_issue", "risk_issue_name",
            "asset_type", "asset_type_name",
            "asset_purpose", "asset_purpose_name",
            "data_classification", "data_classification_name",
            "data_components", "data_component_names",
            "internet_exposure", "internet_exposure_name",
            "number_of_assets",
            "short_description", "reason_for_exception", "compensatory_controls",
            "risk_score", "risk_rating",
            "created_at", "updated_at", "approval_deadline", "approved_at",
            "exception_end_date", "last_reminder_sent", "reminder_stage",
            "status",
            "requested_by", "requested_by_username",
            "assigned_approver", "assigned_approver_username", "assigned_approver_name",
            "risk_owner", "risk_owner_username", "risk_owner_name",
            "version", "parent_exception", "derived_request_ids", "parent_snapshot",
            "checkpoints", "submitted_at", "rejection_feedback", "end_date_change_history",
        )
        read_only_fields = (
            "id", "requested_by", "risk_score", "risk_rating", "status",
            "created_at", "updated_at", "version",
            "checkpoints", "submitted_at", "rejection_feedback", "end_date_change_history",
            "exception_type_name", "risk_issue_name", "asset_type_name", "asset_purpose_name",
            "data_classification_name", "internet_exposure_name", "risk_owner_name",
            "assigned_approver_name", "data_component_names", "parent_snapshot",
        )

    def get_submitted_at(self, obj):
        log = AuditLog.objects.filter(
            exception_request=obj, action_type="SUBMIT",
        ).order_by("timestamp").first()
        if log:
            return log.timestamp
        if obj.status not in {"Draft"}:
            return obj.updated_at
        return None

    def get_rejection_feedback(self, obj):
        if obj.status != "Rejected":
            return ""
        cp = obj.checkpoints.filter(checkpoint="final_decision").first()
        if cp and cp.notes:
            marker = "Feedback:"
            return cp.notes.split(marker, 1)[1].strip() if marker in cp.notes else cp.notes
        log = AuditLog.objects.filter(
            exception_request=obj, action_type="REJECT",
        ).order_by("-timestamp").first()
        if log:
            return (log.details or {}).get("feedback", "")
        return ""

    def get_end_date_change_history(self, obj):
        updates = AuditLog.objects.filter(
            exception_request=obj, action_type="UPDATE", details__end_date_change=True,
        ).select_related("performed_by").order_by("-timestamp")[:20]
        return [
            {
                "timestamp": e.timestamp,
                "performed_by": (e.performed_by.get_full_name() or e.performed_by.username)
                                if e.performed_by else "System",
                "previous_end_date": (e.details or {}).get("previous_end_date"),
                "new_end_date": (e.details or {}).get("new_end_date"),
                "notes": (e.details or {}).get("notes", ""),
            }
            for e in updates
        ]

    def get_derived_request_ids(self, obj):
        return list(obj.derived_requests.values_list('id', flat=True))

    def get_requested_by_username(self, obj):
        return obj.requested_by.username if obj.requested_by else None

    def get_assigned_approver_username(self, obj):
        return obj.assigned_approver.username if obj.assigned_approver else None

    def get_risk_owner_username(self, obj):
        return obj.risk_owner.username if obj.risk_owner else None

    def get_exception_type_name(self, obj):
        return obj.exception_type.name if obj.exception_type else None

    def get_risk_issue_name(self, obj):
        return obj.risk_issue.title if obj.risk_issue else None

    def get_asset_type_name(self, obj):
        return obj.asset_type.name if obj.asset_type else None

    def get_asset_purpose_name(self, obj):
        return obj.asset_purpose.name if obj.asset_purpose else None

    def get_data_classification_name(self, obj):
        return obj.data_classification.level if obj.data_classification else None

    def get_internet_exposure_name(self, obj):
        return obj.internet_exposure.label if obj.internet_exposure else None

    def get_risk_owner_name(self, obj):
        if obj.risk_owner:
            return obj.risk_owner.get_full_name() or obj.risk_owner.username
        return None

    def get_assigned_approver_name(self, obj):
        if obj.assigned_approver:
            return obj.assigned_approver.get_full_name() or obj.assigned_approver.username
        return None

    def get_data_component_names(self, obj):
        return sorted(obj.data_components.values_list('name', flat=True))

    def get_parent_snapshot(self, obj):
        if not obj.parent_exception:
            return None
        return _build_snapshot(obj.parent_exception)

    # ── Field validation ─────────────────────────────────────────────────

    def validate_exception_end_date(self, value):
        if not value:
            raise serializers.ValidationError("This field is required.")
        if value <= timezone.now():
            raise serializers.ValidationError("Exception end date must be in the future.")
        return value

    def validate_number_of_assets(self, value):
        if value < 1:
            raise serializers.ValidationError("Must be at least 1.")
        return value

    def validate_short_description(self, value):
        if len((value or "").strip()) < 10:
            raise serializers.ValidationError("Minimum 10 characters.")
        return value

    def validate_reason_for_exception(self, value):
        if len((value or "").strip()) < 20:
            raise serializers.ValidationError("Minimum 20 characters.")
        return value

    def validate_risk_owner(self, value):
        if value is None:
            raise serializers.ValidationError("This field is required.")
        if not value.is_active:
            raise serializers.ValidationError("Selected risk owner is inactive.")
        if not value.groups.filter(name__in=RISK_OWNER_GROUP_NAMES).exists():
            raise serializers.ValidationError("Selected user must belong to the RiskOwner group.")
        return value

    def validate(self, data):
        # At least one data component required
        components = (
            self.instance.data_components.all() if self.instance
            else data.get("data_components", [])
        )
        if not components:
            raise serializers.ValidationError(
                {"data_components": "At least one data component must be selected."}
            )

        # assigned_approver must be the BU's CIO (creation only)
        if not self.instance:
            bu = data.get("business_unit")
            approver = data.get("assigned_approver")
            if bu and approver and bu.cio_id != approver.id:
                raise serializers.ValidationError({
                    "assigned_approver": (
                        f"Assigned approver must be the CIO of {bu.name}. "
                        f"The CIO is {bu.cio.get_full_name() or bu.cio.username}."
                    )
                })

        if self.instance and "risk_owner" in data:
            self.validate_risk_owner(data["risk_owner"])

        return data
