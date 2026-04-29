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
            "version", "submitted_at",
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


class ExceptionRequestSerializer(serializers.ModelSerializer):
    checkpoints = CheckpointSerializer(many=True, read_only=True)
    submitted_at = serializers.SerializerMethodField()
    rejection_feedback = serializers.SerializerMethodField()
    end_date_change_history = serializers.SerializerMethodField()
    requested_by_username = serializers.SerializerMethodField()
    assigned_approver_username = serializers.SerializerMethodField()
    risk_owner_username = serializers.SerializerMethodField()
    business_unit_code = serializers.CharField(source='business_unit.bu_code', read_only=True)
    business_unit_name = serializers.CharField(source='business_unit.name', read_only=True)

    class Meta:
        model = ExceptionRequest
        fields = (
            "id", "business_unit", "business_unit_code", "business_unit_name",
            "exception_type", "risk_issue",
            "asset_type", "asset_purpose", "data_classification",
            "data_components", "internet_exposure", "number_of_assets",
            "short_description", "reason_for_exception", "compensatory_controls",
            "risk_score", "risk_rating",
            "created_at", "updated_at", "approval_deadline", "approved_at",
            "exception_end_date", "last_reminder_sent", "reminder_stage",
            "status",
            "requested_by", "requested_by_username",
            "assigned_approver", "assigned_approver_username",
            "risk_owner", "risk_owner_username",
            "version", "checkpoints",
            "submitted_at", "rejection_feedback", "end_date_change_history",
        )
        read_only_fields = (
            "id", "requested_by", "risk_score", "risk_rating", "status",
            "created_at", "updated_at", "version",
            "checkpoints", "submitted_at", "rejection_feedback", "end_date_change_history",
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

    def get_requested_by_username(self, obj):
        return obj.requested_by.username if obj.requested_by else None

    def get_assigned_approver_username(self, obj):
        return obj.assigned_approver.username if obj.assigned_approver else None

    def get_risk_owner_username(self, obj):
        return obj.risk_owner.username if obj.risk_owner else None

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
