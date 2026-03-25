from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from .models import (
    ExceptionRequest, ExceptionCheckpoint, AuditLog,
    BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification,
    DataComponent, InternetExposure,
)


class CheckpointSerializer(serializers.ModelSerializer):
    checkpoint_display = serializers.CharField(source='get_checkpoint_display', read_only=True)
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExceptionCheckpoint
        fields = [
            'checkpoint',
            'checkpoint_display',
            'status',
            'completed_at',
            'completed_by',
            'completed_by_name',
            'notes',
        ]

    def get_completed_by_name(self, obj):
        if obj.completed_by:
            return obj.completed_by.get_full_name() or obj.completed_by.username
        return None


class ExceptionRequestSerializer(serializers.ModelSerializer):
    checkpoints = CheckpointSerializer(many=True, read_only=True)
    submitted_at = serializers.SerializerMethodField()
    rejection_feedback = serializers.SerializerMethodField()
    end_date_change_history = serializers.SerializerMethodField()

    class Meta:
        model = ExceptionRequest
        fields = "__all__"
        read_only_fields = (
            "requested_by",
            "risk_score",
            "risk_rating",
            "status",
            "created_at",
            "updated_at",
            "version",
            "id",
            "checkpoints",
            "submitted_at",
            "rejection_feedback",
            "end_date_change_history",
        )

    def get_submitted_at(self, obj):
        submit_log = AuditLog.objects.filter(
            exception_request=obj,
            action_type="SUBMIT",
        ).order_by("timestamp").first()
        if submit_log:
            return submit_log.timestamp

        if obj.status in {"Submitted", "AwaitingRiskOwner", "Approved", "Rejected", "Expired", "Closed"}:
            return obj.updated_at
        return None

    def get_rejection_feedback(self, obj):
        if obj.status != "Rejected":
            return ""

        final_decision = obj.checkpoints.filter(checkpoint="final_decision").first()
        if final_decision and final_decision.notes:
            marker = "Feedback:"
            if marker in final_decision.notes:
                return final_decision.notes.split(marker, 1)[1].strip()
            return final_decision.notes

        reject_log = AuditLog.objects.filter(
            exception_request=obj,
            action_type="REJECT",
        ).order_by("-timestamp").first()
        if reject_log:
            return (reject_log.details or {}).get("feedback", "")

        return ""

    def get_end_date_change_history(self, obj):
        updates = AuditLog.objects.filter(
            exception_request=obj,
            action_type="UPDATE",
            details__end_date_change=True,
        ).select_related("performed_by").order_by("-timestamp")[:20]

        result = []
        for entry in updates:
            actor = entry.performed_by
            actor_name = actor.get_full_name() if actor else ""
            actor_name = actor_name or (actor.username if actor else "System")
            details = entry.details or {}
            result.append({
                "timestamp": entry.timestamp,
                "performed_by": actor_name,
                "previous_end_date": details.get("previous_end_date"),
                "new_end_date": details.get("new_end_date"),
                "notes": details.get("notes", ""),
            })
        return result

    def validate_exception_end_date(self, value):
        """Ensure exception validity period is in the future."""
        if not value:
            raise serializers.ValidationError("This field is required.")
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Exception end date must be in the future."
            )
        return value

    def validate_number_of_assets(self, value):
        if value < 1:
            raise serializers.ValidationError("Must be at least 1.")
        return value

    def validate_short_description(self, value):
        if len((value or '').strip()) < 10:
            raise serializers.ValidationError("Minimum 10 characters.")
        return value

    def validate_risk_owner(self, value):
        if value is None:
            raise serializers.ValidationError("This field is required.")

        if not value.is_active:
            raise serializers.ValidationError("Selected risk owner is inactive.")

        if not value.groups.filter(name__in=['RiskOwner', 'Risk Owner']).exists():
            raise serializers.ValidationError(
                "Selected user must belong to the RiskOwner group."
            )

        return value

    def validate_reason_for_exception(self, value):
        if len((value or '').strip()) < 20:
            raise serializers.ValidationError("Minimum 20 characters.")
        return value

    def validate(self, data):
        """Cross-field validation."""
        # Ensure at least one data component is selected
        if self.instance:
            components = self.instance.data_components.all()
        else:
            components = data.get('data_components', [])
        
        if not components:
            raise serializers.ValidationError(
                {"data_components": "At least one data component must be selected."}
            )

        # Validate that assigned_approver matches business_unit's CIO
        if not self.instance:  # Only validate on creation, not update
            business_unit = data.get('business_unit')
            assigned_approver = data.get('assigned_approver')

            if business_unit and assigned_approver:
                if business_unit.cio_id != assigned_approver.id:
                    raise serializers.ValidationError(
                        {
                            "assigned_approver": (
                                f"Assigned approver must be the CIO of the selected business unit. "
                                f"The CIO for {business_unit.name} is {business_unit.cio.get_full_name() or business_unit.cio.username}."
                            )
                        }
                    )

        if self.instance and 'risk_owner' in data:
            self.validate_risk_owner(data.get('risk_owner'))
        
        return data


# ============================================
# REFERENCE / LOOKUP DATA SERIALIZERS
# ============================================

class BusinessUnitSerializer(serializers.ModelSerializer):
    cio_name = serializers.SerializerMethodField()

    class Meta:
        model = BusinessUnit
        fields = ['id', 'name', 'bu_code', 'cio', 'cio_name']

    def get_cio_name(self, obj):
        if obj.cio:
            return obj.cio.get_full_name() or obj.cio.username
        return None


class ExceptionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExceptionType
        fields = ['id', 'name', 'description', 'approval_sla_days']


class RiskIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskIssue
        fields = ['id', 'title', 'description', 'inherent_risk_score']


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ['id', 'name', 'weight']


class AssetPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPurpose
        fields = ['id', 'name', 'weight']


class DataClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataClassification
        fields = ['id', 'level', 'weight']


class DataComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataComponent
        fields = ['id', 'name', 'weight']


class InternetExposureSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetExposure
        fields = ['id', 'label', 'weight']


class UserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
