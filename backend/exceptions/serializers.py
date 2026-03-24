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
