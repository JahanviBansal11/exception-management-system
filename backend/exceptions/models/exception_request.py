from django.db import models
from django.contrib.auth.models import User

from .reference import (
    BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification,
    DataComponent, InternetExposure,
)


class ExceptionRequest(models.Model):
    """
    Core exception request aggregate.

    Lifecycle (managed exclusively by WorkflowService):
        Draft → Submitted → Approved → Closed | Extended
        Draft → Submitted → AwaitingRiskOwner → Approved → Closed | Extended
        Any pending stage → Rejected | ApprovalDeadlinePassed
        Rejected → Modified   (modification/extension branch: MODIFY audit action)
        Rejected → Closed     (requestor gives up — no further action)
        Approved → Expired    (remediation branch: exception_end_date passed)
    """

    # ── Status Constants ────────────────────────────────────────────────
    APPROVAL_STATUS_CHOICES = [
        ('Draft', 'Draft - Not Yet Submitted'),
        ('Submitted', 'Submitted - Pending BU CIO Approval'),
        ('AwaitingRiskOwner', 'BU CIO Approved - Awaiting Risk Owner Assessment'),
        ('Approved', 'Approved - Active Exception'),
        ('Rejected', 'Rejected - Pending Decision'),
        ('ApprovalDeadlinePassed', 'Approval Deadline Passed Without Decision'),
        ('Expired', 'Expired - Exception End Date Passed'),
        ('Modified', 'Modified - Superseded by Approved Modification'),
        ('Extended', 'Extended - Superseded by Approved Extension'),
        ('Closed', 'Closed - Exception No Longer Valid'),
    ]

    APPROVAL_ALLOWED_TRANSITIONS = {
        "Draft": ["Submitted"],
        "Submitted": ["AwaitingRiskOwner", "Approved", "Rejected", "ApprovalDeadlinePassed"],
        "AwaitingRiskOwner": ["Approved", "Rejected", "ApprovalDeadlinePassed"],
        "Approved": ["Closed", "Extended"],       # "Expired" added by remediation branch
        "Rejected": ["Draft", "Closed", "Modified"],
        "ApprovalDeadlinePassed": ["Draft"],
        "Expired": [],                             # outgoing transitions added by remediation branch
        "Modified": [],
        "Extended": [],
        "Closed": [],
    }

    REMINDER_STAGE_CHOICES = [
        ('None', 'No reminder sent'),
        ('Reminder_50', '50% of approval window'),
        ('Reminder_75', '75% of approval window'),
        ('Reminder_90', '90% of approval window'),
        ('Expired_Notice', 'Expired notification sent'),
    ]

    RISK_RATING_CHOICES = [
        ('Low', 'Low Risk'),
        ('Medium', 'Medium Risk'),
        ('High', 'High Risk'),
        ('Critical', 'Critical Risk'),
    ]

    # ── Core Business Fields ─────────────────────────────────────────────
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    exception_type = models.ForeignKey(ExceptionType, on_delete=models.PROTECT)
    risk_issue = models.ForeignKey(RiskIssue, on_delete=models.PROTECT)

    # ── Risk Assessment Fields ───────────────────────────────────────────
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT)
    asset_purpose = models.ForeignKey(AssetPurpose, on_delete=models.PROTECT)
    data_classification = models.ForeignKey(DataClassification, on_delete=models.PROTECT)
    data_components = models.ManyToManyField(DataComponent)
    internet_exposure = models.ForeignKey(InternetExposure, on_delete=models.PROTECT)
    number_of_assets = models.IntegerField(help_text="Number of assets affected (minimum 1)")

    # ── Description Fields ───────────────────────────────────────────────
    short_description = models.TextField()
    reason_for_exception = models.TextField()
    compensatory_controls = models.TextField(blank=True)

    # ── Calculated Risk Fields ───────────────────────────────────────────
    risk_score = models.IntegerField(blank=True, null=True)
    risk_rating = models.CharField(max_length=20, choices=RISK_RATING_CHOICES, blank=True)

    # ── Lifecycle Timing ─────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    approval_deadline = models.DateTimeField(null=True, blank=True, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    exception_end_date = models.DateTimeField(null=True, blank=True, db_index=True)

    # ── Reminder Tracking ────────────────────────────────────────────────
    last_reminder_sent = models.DateTimeField(null=True, blank=True)
    reminder_stage = models.CharField(
        max_length=50, choices=REMINDER_STAGE_CHOICES, default='None',
    )

    # ── Status & Assignment ──────────────────────────────────────────────
    status = models.CharField(
        max_length=30, choices=APPROVAL_STATUS_CHOICES, default='Draft', db_index=True,
    )
    requested_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="requested_exceptions",
    )
    assigned_approver = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="approvals_pending",
    )
    risk_owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="risk_owned_exceptions",
    )

    # ── Optimistic Locking ───────────────────────────────────────────────
    version = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['approval_deadline']),
            models.Index(fields=['exception_end_date']),
            models.Index(fields=['requested_by', 'status']),
            models.Index(fields=['assigned_approver', 'status']),
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['status', 'approval_deadline'], name='exception_status_deadline_idx'),
            models.Index(fields=['status', 'exception_end_date'], name='exception_status_enddate_idx'),
            models.Index(fields=['reminder_stage', 'approval_deadline'], name='exc_reminder_deadln_idx'),
            models.Index(fields=['business_unit', 'status'], name='exception_bu_status_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(number_of_assets__gte=1),
                name='exception_number_of_assets_gte_1',
            ),
            models.CheckConstraint(
                check=models.Q(risk_score__gte=0) | models.Q(risk_score__isnull=True),
                name='exception_risk_score_gte_0_or_null',
            ),
        ]
        verbose_name = "Exception Request"
        verbose_name_plural = "Exception Requests"

    def save(self, *args, **kwargs):
        """
        Increment version on every save.
        Status transitions are guarded — must go through WorkflowService.
        """
        if self.pk:
            old = ExceptionRequest.objects.get(pk=self.pk)
            update_fields = kwargs.get("update_fields")

            if update_fields and "status" not in update_fields:
                if old.status != self.status:
                    raise ValueError(
                        "Direct status modification is not allowed. "
                        "Use WorkflowService for all state transitions."
                    )
            elif not update_fields and old.status != self.status:
                raise ValueError(
                    "Direct status modification is not allowed. "
                    "Use WorkflowService for all state transitions."
                )

            # Skip version bump for risk-only updates (RiskService uses .update() anyway)
            if not (update_fields and set(update_fields) <= {"risk_score", "risk_rating"}):
                self.version = old.version + 1
                # Ensure version is written to DB when update_fields is used
                if update_fields is not None and "version" not in update_fields:
                    kwargs["update_fields"] = list(update_fields) + ["version"]

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Exception #{self.id} - {self.short_description[:50]} ({self.status})"
