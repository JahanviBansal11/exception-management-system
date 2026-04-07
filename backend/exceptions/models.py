from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


# ============================================
# 1. REFERENCE/MASTER DATA MODELS
# ============================================

class BusinessUnit(models.Model):
    name = models.CharField(max_length=255, unique=True)
    bu_code = models.CharField(max_length=50, unique=True)
    cio = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.bu_code} - {self.name}"


class ExceptionType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    approval_sla_days = models.IntegerField(
        default=28,
        help_text="Days allowed for approval before escalation"
    )
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RiskIssue(models.Model):
    title = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    inherent_risk_score = models.IntegerField()
    
    class Meta:
        db_table = 'risk_issue'
        ordering = ['title']
        verbose_name_plural = "Risk Issues"
        constraints = [
            models.CheckConstraint(
                check=models.Q(inherent_risk_score__gte=0),
                name='risk_issue_inherent_score_gte_0',
            )
        ]

    def __str__(self):
        return self.title


class AssetType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    weight = models.IntegerField()
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AssetPurpose(models.Model):
    name = models.CharField(max_length=255, unique=True)
    weight = models.IntegerField()
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Asset Purposes"

    def __str__(self):
        return self.name


class DataClassification(models.Model):
    level = models.CharField(max_length=100, unique=True)
    weight = models.IntegerField()
    
    class Meta:
        ordering = ['weight']

    def __str__(self):
        return self.level


class DataComponent(models.Model):
    name = models.CharField(max_length=255, unique=True)
    weight = models.IntegerField()
    
    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class InternetExposure(models.Model):
    label = models.CharField(max_length=100, unique=True)
    weight = models.IntegerField()
    
    class Meta:
        ordering = ['weight']
        verbose_name_plural = "Internet Exposures"

    def __str__(self):
        return self.label
    



# ============================================
# 2. CORE BUSINESS MODELS
# ============================================

class ExceptionRequest(models.Model):
    """
    Core Exception Management Model.
    
    Lifecycle:
    Draft → Submitted (approval window opens)
          → Approved (if approved before deadline)
          → Closed (when exception validity expires)
    
    OR
    
    Submitted → Expired (if approval deadline passes)
             → Rejected (if explicitly rejected)
             → Draft (can be resubmitted from rejected)
    """
    
    # ===== Status Choices =====
    APPROVAL_STATUS_CHOICES = [
        ('Draft', 'Draft - Not Yet Submitted'),
        ('Submitted', 'Submitted - Pending BU CIO Approval'),
        ('AwaitingRiskOwner', 'BU CIO Approved - Awaiting Risk Owner Assessment'),
        ('Approved', 'Approved - Active Exception'),
        ('Rejected', 'Rejected - Awaiting Resubmission'),
        ('Expired', 'Expired - Approval Deadline Passed'),
        ('Closed', 'Closed - Exception No Longer Valid'),
    ]
    
    APPROVAL_ALLOWED_TRANSITIONS = {
        "Draft": ["Submitted"],
        "Submitted": ["AwaitingRiskOwner", "Approved", "Rejected", "Expired"],
        "AwaitingRiskOwner": ["Approved", "Rejected", "Expired"],
        "Approved": ["Closed", "Submitted"],
        "Rejected": ["Draft"],
        "Expired": ["Draft"],
        "Closed": [],
    }
    
    REMINDER_STAGE_CHOICES = [
        ('None', 'No reminder sent'),
        ('Reminder_50', '50% of approval window'),
        ('Reminder_75', '75% of approval window'),
        ('Reminder_90', '90% of approval window'),
        ('Expired_Notice', 'Expired notification sent'),
    ]
    
    # ===== CORE BUSINESS FIELDS =====
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    exception_type = models.ForeignKey(ExceptionType, on_delete=models.PROTECT)
    risk_issue = models.ForeignKey(RiskIssue, on_delete=models.PROTECT)
    
    # ===== RISK ASSESSMENT FIELDS =====
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT)
    asset_purpose = models.ForeignKey(AssetPurpose, on_delete=models.PROTECT)
    data_classification = models.ForeignKey(DataClassification, on_delete=models.PROTECT)
    data_components = models.ManyToManyField(DataComponent)
    internet_exposure = models.ForeignKey(InternetExposure, on_delete=models.PROTECT)
    number_of_assets = models.IntegerField(help_text="Number of assets affected (minimum 1)")
    
    # ===== DESCRIPTION FIELDS =====
    short_description = models.TextField()
    reason_for_exception = models.TextField()
    compensatory_controls = models.TextField(blank=True)
    
    # ===== CALCULATED RISK FIELDS =====
    RISK_RATING_CHOICES = [
        ('Low', 'Low Risk'),
        ('Medium', 'Medium Risk'),
        ('High', 'High Risk'),
        ('Critical', 'Critical Risk'),
    ]
    
    risk_score = models.IntegerField(blank=True, null=True, help_text="Calculated risk score (0+)")
    risk_rating = models.CharField(
        max_length=20,
        choices=RISK_RATING_CHOICES,
        blank=True,
        help_text="Risk rating category derived from risk score"
    )
    
    # ===== LIFECYCLE TIMING FIELDS (CRITICAL FOR AUTOMATION) =====
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    approval_deadline = models.DateTimeField(
        null=True, 
        blank=True,
        db_index=True,
        help_text="Deadline for approval (created_at + exception_type.approval_sla_days)"
    )
    
    approved_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the exception was approved"
    )
    
    exception_end_date = models.DateTimeField(
        null=True, 
        blank=True,
        db_index=True,
        help_text="When the approved exception validity expires"
    )
    
    # ===== REMINDER TRACKING (CRITICAL FOR AUTOMATION) =====
    last_reminder_sent = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Last time a reminder was sent to approver"
    )
    
    reminder_stage = models.CharField(
        max_length=50,
        choices=REMINDER_STAGE_CHOICES,
        default='None',
        help_text="Track which reminder stage has been sent"
    )
    
    # ===== STATUS & ASSIGNMENT =====
    status = models.CharField(
        max_length=30,
        choices=APPROVAL_STATUS_CHOICES,
        default='Draft',
        db_index=True
    )
    
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="requested_exceptions"
    )
    
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approvals_pending"
    )
    
    risk_owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="risk_owned_exceptions"
    )
    
    # ===== OPTIMISTIC LOCKING & VERSIONING =====
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
            # Scheduler query optimization
            models.Index(fields=['status', 'approval_deadline'], name='exception_status_deadline_idx'),
            models.Index(fields=['status', 'exception_end_date'], name='exception_status_enddate_idx'),
            models.Index(fields=['reminder_stage', 'approval_deadline'], name='exc_reminder_deadln_idx'),
            # Business unit queries
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
    
    # ===== BUSINESS LOGIC METHODS =====
    
    def calculate_risk_score(self):
        """Calculate risk score based on weighted factors."""
        data_component_total = sum(
            component.weight for component in self.data_components.all()
        )

        if data_component_total == 0:
            return 0

        return (
            self.asset_type.weight *
            self.asset_purpose.weight *
            self.data_classification.weight *
            self.internet_exposure.weight *
            data_component_total
        )

    def determine_risk_rating(self, score):
        """Determine risk rating category from score."""
        if score < 36:
            return "Low"
        elif score < 432:
            return "Medium"
        elif score < 1200:
            return "High"
        else:
            return "Critical"

    def recalculate_risk(self):
        """
        Atomic risk recalculation with proper locking.
        Prevents race conditions from concurrent M2M updates.
        """
        with transaction.atomic():
            instance = ExceptionRequest.objects.select_for_update().get(pk=self.pk)
            
            score = instance.calculate_risk_score()
            rating = instance.determine_risk_rating(score)
            
            ExceptionRequest.objects.filter(pk=self.pk).update(
                risk_score=score,
                risk_rating=rating
            )
    
    def _change_status(self, new_status, user, action_type, details=None):
        """
        Atomic status transition with proper audit trail.
        
        Args:
            new_status: Target status
            user: User performing the action
            action_type: Audit action type
        """
        # Validate transition
        if new_status not in self.APPROVAL_ALLOWED_TRANSITIONS.get(self.status, []):
            raise ValueError(
                f"Invalid transition from {self.status} to {new_status}"
            )

        previous = self.status
        
        with transaction.atomic():
            self.status = new_status
            
            # Set timestamps based on transition
            if new_status == "Submitted":
                self.approval_deadline = timezone.now() + timedelta(
                    days=self.exception_type.approval_sla_days
                )
                self.approved_at = None
                self.reminder_stage = "None"
                self.last_reminder_sent = None
            elif new_status == "Approved":
                self.approved_at = timezone.now()
            
            self.save(update_fields=[
                "status",
                "updated_at",
                "approval_deadline",
                "approved_at",
                "reminder_stage",
                "last_reminder_sent",
            ])

            # Create immutable audit log
            AuditLog.objects.create(
                exception_request=self,
                action_type=action_type,
                previous_status=previous,
                new_status=new_status,
                performed_by=user,
                details=details or {},
            )
    
    def submit(self, user):
        """Submit exception for approval."""
        if self.status != "Draft":
            raise ValueError("Only Draft exceptions can be submitted.")
        self._change_status("Submitted", user, "SUBMIT")
        self.checkpoints.all().delete()
        self._record_checkpoint(
            checkpoint='exception_requested',
            status='completed',
            user=user,
            notes='Exception submitted by requestor'
        )
        self._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='pending',
            notes='Awaiting BU CIO decision'
        )
        
        # Send notification to assigned approver
        from exceptions.services.notification_service import NotificationService
        NotificationService.send_submission_notification(self)

    def submit_renewal(self, user, new_end_date, notes=''):
        """Submit approved exception back into approval workflow as a renewal request."""
        if self.status != "Approved":
            raise ValueError("Only Approved exceptions can be renewed.")

        renewal_notes = (notes or '').strip()
        if not renewal_notes:
            raise ValueError("Notes are required when renewing an exception.")

        previous_end_date = self.exception_end_date
        self.exception_end_date = new_end_date

        self._change_status(
            "Submitted",
            user,
            "SUBMIT",
            details={
                "message": "Renewal submitted for approval.",
                "renewal": True,
                "end_date_change": True,
                "previous_end_date": previous_end_date.isoformat() if previous_end_date else None,
                "new_end_date": new_end_date.isoformat() if new_end_date else None,
                "notes": renewal_notes,
            },
        )

        self.checkpoints.all().delete()
        self._record_checkpoint(
            checkpoint='exception_requested',
            status='completed',
            user=user,
            notes='Renewal submitted by requestor'
        )
        self._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='pending',
            notes='Awaiting BU CIO decision for renewal'
        )

        from exceptions.services.notification_service import NotificationService
        NotificationService.send_submission_notification(self)

    def bu_approve(self, user, notes=''):
        """BU CIO approves; Low/Medium auto-approve, High/Critical go to risk owner."""
        if self.status != "Submitted":
            raise ValueError("Only Submitted exceptions can receive BU approval.")

        if self.risk_score is None or not self.risk_rating:
            self.recalculate_risk()
            self.refresh_from_db(fields=["risk_score", "risk_rating"])

        approval_notes = (notes or '').strip()

        self._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='completed',
            user=user,
            notes='BU CIO reviewed and approved'
        )
        self._record_checkpoint(
            checkpoint='bu_approval_decision',
            status='completed',
            user=user,
            notes=f"BU CIO decision received: approved. Notes: {approval_notes}" if approval_notes else 'BU CIO decision received: approved'
        )

        if self.risk_rating in {"High", "Critical"}:
            if not approval_notes:
                raise ValueError("Approver notes are mandatory when approving High/Critical exceptions.")

            self._change_status(
                "AwaitingRiskOwner",
                user,
                "APPROVE",
                details={
                    "stage": "bu_approval",
                    "decision": "approved",
                    "risk_rating": self.risk_rating,
                    "approver_notes": approval_notes,
                },
            )
            self._record_checkpoint(
                checkpoint='risk_assessment_notified',
                status='pending',
                notes=f"Awaiting risk owner decision. BU CIO notes: {approval_notes}"
            )
            # Send notification to risk owner
            from exceptions.services.notification_service import NotificationService
            NotificationService.send_risk_owner_notification(self)
            return

        self._change_status(
            "Approved",
            user,
            "APPROVE",
            details={
                "stage": "bu_approval",
                "decision": "approved",
                "risk_rating": self.risk_rating,
                "approver_notes": approval_notes,
            },
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='skipped',
            notes='Risk owner stage skipped for Low/Medium risk'
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_complete',
            status='skipped',
            notes='Risk owner stage skipped for Low/Medium risk'
        )
        self._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=user,
            notes=f"Final decision: approved by BU CIO (Low/Medium risk). Notes: {approval_notes}" if approval_notes else 'Final decision: approved by BU CIO (Low/Medium risk)'
        )
        
        # Send approval notification to requester (auto-approved for Low/Medium risk)
        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_approved_notification(self, approved_by_user=user)

    def risk_approve(self, user, notes=''):
        """Risk owner approves a High/Critical exception."""
        if self.status != "AwaitingRiskOwner":
            raise ValueError("Only AwaitingRiskOwner exceptions can be approved by risk owner.")
        self._change_status("Approved", user, "APPROVE")
        self._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='completed',
            user=user,
            notes='Risk owner acknowledged decision task'
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_complete',
            status='completed',
            user=user,
            notes=notes or 'Risk owner approved exception'
        )
        self._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=user,
            notes='Final decision: approved by Risk Owner'
        )
        
        # Send approval notification to requester
        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_approved_notification(self, approved_by_user=user)

    def risk_assess_complete(self, user, notes=''):
        """Backward-compatible alias for risk owner approval."""
        self.risk_approve(user, notes=notes)

    def bu_reject(self, user, notes=''):
        """BU CIO rejects during Submitted stage."""
        if self.status != "Submitted":
            raise ValueError("Only Submitted exceptions can be rejected by BU CIO.")

        rejection_feedback = (notes or '').strip()
        if not rejection_feedback:
            raise ValueError("Rejection feedback is required.")

        self._change_status(
            "Rejected",
            user,
            "REJECT",
            details={
                "stage": "bu_approval",
                "decision": "rejected",
                "feedback": rejection_feedback,
            },
        )
        self._record_checkpoint(
            checkpoint='bu_approval_notified',
            status='completed',
            user=user,
            notes='BU CIO reviewed request'
        )
        self._record_checkpoint(
            checkpoint='bu_approval_decision',
            status='completed',
            user=user,
            notes='BU CIO decision received: rejected'
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='skipped',
            notes='Risk owner stage skipped due to BU rejection'
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_complete',
            status='skipped',
            notes='Risk owner stage skipped due to BU rejection'
        )
        self._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=user,
            notes=f"Final decision: rejected by BU CIO. Feedback: {rejection_feedback}"
        )
        
        # Send rejection notification to requester
        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_rejected_notification(self, rejection_feedback)

    def risk_reject(self, user, notes=''):
        """Risk owner rejects during AwaitingRiskOwner stage."""
        if self.status != "AwaitingRiskOwner":
            raise ValueError("Only AwaitingRiskOwner exceptions can be rejected by risk owner.")

        rejection_feedback = (notes or '').strip()
        if not rejection_feedback:
            raise ValueError("Rejection feedback is required.")

        self._change_status(
            "Rejected",
            user,
            "REJECT",
            details={
                "stage": "risk_owner",
                "decision": "rejected",
                "feedback": rejection_feedback,
            },
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_notified',
            status='completed',
            user=user,
            notes='Risk owner acknowledged decision task'
        )
        self._record_checkpoint(
            checkpoint='risk_assessment_complete',
            status='completed',
            user=user,
            notes=notes or 'Risk owner rejected exception'
        )
        self._record_checkpoint(
            checkpoint='final_decision',
            status='completed',
            user=user,
            notes=f"Final decision: rejected by Risk Owner. Feedback: {rejection_feedback}"
        )
        
        # Send rejection notification to requester
        from exceptions.services.notification_service import NotificationService
        NotificationService.send_exception_rejected_notification(self, rejection_feedback)

    def final_approve(self, user):
        """Backward-compatible alias for final approval."""
        if self.status == "AwaitingRiskOwner":
            self.risk_approve(user)
            return
        raise ValueError("Final approval is only valid from AwaitingRiskOwner in this workflow.")

    def approve(self, user, notes=''):
        """Backward-compatible approve alias by current stage."""
        if self.status == "Submitted":
            self.bu_approve(user, notes=notes)
            return
        if self.status == "AwaitingRiskOwner":
            self.risk_approve(user)
            return
        raise ValueError("Approve is only valid from Submitted or AwaitingRiskOwner.")

    def final_reject(self, user, notes=''):
        """Backward-compatible reject alias by current stage."""
        if self.status == "Submitted":
            self.bu_reject(user, notes=notes)
            return
        if self.status == "AwaitingRiskOwner":
            self.risk_reject(user, notes=notes)
            return
        raise ValueError("Reject is only valid from Submitted or AwaitingRiskOwner.")

    def reject(self, user, notes=''):
        """Backward-compatible reject alias for final rejection."""
        self.final_reject(user, notes=notes)

    def mark_expired(self, user):
        """Mark as expired when deadline passes."""
        if self.status not in {"Submitted", "AwaitingRiskOwner"}:
            raise ValueError("Only pending approvals can expire.")
        self._change_status("Expired", user, "EXPIRE")

    def close(self, user):
        """Close approved exception."""
        if self.status != "Approved":
            raise ValueError("Only Approved exceptions can be closed.")
        self._change_status("Closed", user, "CLOSE")

    def _record_checkpoint(self, checkpoint, status='completed', user=None, notes=''):
        checkpoint_obj, created = ExceptionCheckpoint.objects.get_or_create(
            exception_request=self,
            checkpoint=checkpoint,
            defaults={
                'status': status,
                'completed_by': user,
                'completed_at': timezone.now() if status == 'completed' else None,
                'notes': notes,
            }
        )

        if not created:
            checkpoint_obj.status = status
            checkpoint_obj.completed_by = user
            checkpoint_obj.notes = notes
            if status == 'completed' and checkpoint_obj.completed_at is None:
                checkpoint_obj.completed_at = timezone.now()
            checkpoint_obj.save(update_fields=['status', 'completed_by', 'completed_at', 'notes'])

    def save(self, *args, **kwargs):
        """Prevent direct status modification and handle optimistic locking."""
        if self.pk:
            old = ExceptionRequest.objects.get(pk=self.pk)
            
            update_fields = kwargs.get("update_fields")
            if update_fields and "status" not in update_fields:
                if old.status != self.status:
                    raise ValueError("Direct status modification not allowed")
            elif not update_fields and old.status != self.status:
                raise ValueError(
                    "Use submit/approve/reject/close methods for status changes"
                )
            
            # Increment version on non-risk updates
            if not (update_fields and 
                    set(update_fields) <= {"risk_score", "risk_rating"}):
                self.version = old.version + 1
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Exception #{self.id} - {self.short_description[:50]} ({self.status})"


# ============================================
# 3. AUDIT & TRACKING MODELS
# ============================================

class AuditLog(models.Model):
    """Immutable audit trail for compliance."""
    
    ACTION_CHOICES = [
        ("SUBMIT", "Submitted for Approval"),
        ("APPROVE", "Approved"),
        ("REJECT", "Rejected"),
        ("CLOSE", "Closed"),
        ("EXPIRE", "Expired"),
        ("REMIND", "Reminder Sent"),
        ("ESCALATE", "Escalated"),
        ("UPDATE", "Updated"),
    ]

    exception_request = models.ForeignKey(
        ExceptionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs"
    )
    
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=30, null=True, blank=True)
    new_status = models.CharField(max_length=30, null=True, blank=True)
    
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_actions"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['exception_request', '-timestamp'], name='auditlog_exc_ts_idx'),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        exception_id = self.exception_request_id or "NA"
        return f"{exception_id} - {self.action_type} @ {self.timestamp}"


class ExceptionCheckpoint(models.Model):
    """Track checkpoint completion through the approval workflow."""

    CHECKPOINT_CHOICES = [
        ('exception_requested', 'Exception Requested'),
        ('bu_approval_notified', 'BU CIO Notified'),
        ('bu_approval_decision', 'BU CIO Decision Received'),
        ('risk_assessment_notified', 'Risk Owner Notified'),
        ('risk_assessment_complete', 'Risk Assessment Complete'),
        ('final_decision', 'Final Decision Made'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('escalated', 'Escalated'),
    ]

    exception_request = models.ForeignKey(
        ExceptionRequest,
        on_delete=models.CASCADE,
        related_name='checkpoints'
    )
    checkpoint = models.CharField(max_length=40, choices=CHECKPOINT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checkpoints'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['exception_request', 'checkpoint'],
                name='unique_exception_checkpoint'
            )
        ]

    def __str__(self):
        return f"{self.exception_request_id} - {self.checkpoint} ({self.status})"


class ReminderLog(models.Model):
    """Track all reminder communications."""
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('in_app', 'In-App Notification'),
        ('system', 'System Log'),
    ]
    
    exception_request = models.ForeignKey(
        ExceptionRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reminder_logs"
    )
    
    sent_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    reminder_type = models.CharField(
        max_length=50,
        choices=ExceptionRequest.REMINDER_STAGE_CHOICES
    )
    
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=[('queued', 'Queued'), ('sent', 'Sent'), ('failed', 'Failed'), ('bounced', 'Bounced')],
        default='sent'
    )
    
    message_content = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['exception_request', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.exception_request.id} - {self.reminder_type} ({self.delivery_status})"


class NotificationDismissal(models.Model):
    """Store notification dismissals per user for cross-device persistence."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dismissed_notifications',
    )
    event_key = models.CharField(max_length=255)
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-dismissed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'event_key'],
                name='unique_user_notification_dismissal',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'dismissed_at'], name='notif_dismiss_user_ts_idx'),
            models.Index(fields=['user', 'event_key'], name='notif_dismiss_user_key_idx'),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.event_key}"
