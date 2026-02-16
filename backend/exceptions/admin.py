from django.contrib import admin
from .models import (
    BusinessUnit,
    ExceptionType,
    RiskIssue,
    AssetType,
    DataClassification,
    Exception,
    AuditLog
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


@admin.register(DataClassification)
class DataClassificationAdmin(admin.ModelAdmin):
    list_display = ("level", "weight")


@admin.register(Exception)
class ExceptionAdmin(admin.ModelAdmin):
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
        "exception",
        "action_type",
        "previous_status",
        "new_status",
        "performed_by",
        "timestamp"
    )
    readonly_fields = (
        "exception",
        "action_type",
        "previous_status",
        "new_status",
        "performed_by",
        "timestamp"
    )
