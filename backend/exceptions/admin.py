from django.contrib import admin
from .models import (
    BusinessUnit,
    ExceptionType,
    RiskIssue,
    AssetType,
    AssetPurpose,
    DataClassification,
    DataComponent,
    InternetExposure,
    ExceptionRequest,
    ExceptionCheckpoint,
    AuditLog,
    ReminderLog
)


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "bu_code", "cio")
    search_fields = ("name", "bu_code")


@admin.register(ExceptionType)
class ExceptionTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(RiskIssue)
class RiskIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "inherent_risk_score")
    search_fields = ("title",)


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(AssetPurpose)
class AssetPurposeAdmin(admin.ModelAdmin):
    list_display = ("name", "weight")
    search_fields = ("name",)


@admin.register(DataClassification)
class DataClassificationAdmin(admin.ModelAdmin):
    list_display = ("level", "weight")


@admin.register(DataComponent)
class DataComponentAdmin(admin.ModelAdmin):
    list_display = ("name", "weight")
    search_fields = ("name",)


@admin.register(InternetExposure)
class InternetExposureAdmin(admin.ModelAdmin):
    list_display = ("label", "weight")
    search_fields = ("label",)


@admin.register(ExceptionRequest)
class ExceptionRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "exception_type",
        "business_unit",
        "risk_owner",
        "status",
        "risk_score",
        "created_at"
    )

    list_filter = ("status", "business_unit", "exception_type")
    search_fields = ("short_description",)
    readonly_fields = (
        "status",
        "risk_score",
        "created_at",
        "updated_at"
    )

    ordering = ("-created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "exception_request",
        "action_type",
        "previous_status",
        "new_status",
        "performed_by",
        "timestamp"
    )
    readonly_fields = (
        "exception_request",
        "action_type",
        "previous_status",
        "new_status",
        "performed_by",
        "timestamp"
    )


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = (
        "exception_request",
        "sent_to",
        "reminder_type",
        "delivery_status",
        "sent_at"
    )
    readonly_fields = (
        "exception_request",
        "sent_to",
        "reminder_type",
        "sent_at",
        "delivery_status"
    )
    list_filter = ("delivery_status", "reminder_type", "sent_at")
    ordering = ("-sent_at",)


@admin.register(ExceptionCheckpoint)
class ExceptionCheckpointAdmin(admin.ModelAdmin):
    list_display = (
        "exception_request",
        "checkpoint",
        "status",
        "completed_by",
        "completed_at",
    )
    list_filter = ("checkpoint", "status", "completed_at")
    search_fields = ("exception_request__id", "notes")
    readonly_fields = ("completed_at",)
