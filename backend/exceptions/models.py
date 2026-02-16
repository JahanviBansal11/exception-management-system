from django.db import models
from django.contrib.auth.models import User


class BusinessUnit(models.Model):
    name = models.CharField(max_length=255)
    bu_code = models.CharField(max_length=50, unique=True)
    cio = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name


class ExceptionType(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RiskIssue(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    inherent_risk_score = models.IntegerField()

    def __str__(self):
        return self.title


class AssetType(models.Model):
    name = models.CharField(max_length=255)
    weight = models.IntegerField()

    def __str__(self):
        return self.name
    
class AssetPurpose(models.Model):
    name = models.CharField(max_length=255)
    weight = models.IntegerField()

    def __str__(self):
        return self.name


class DataClassification(models.Model):
    level = models.CharField(max_length=100)
    weight = models.IntegerField()

    def __str__(self):
        return self.level
    
class DataComponent(models.Model):
    name = models.CharField(max_length=255)
    weight = models.IntegerField()

    def __str__(self):
        return self.name
    

class InternetExposure(models.Model):
    label = models.CharField(max_length=100)
    weight = models.IntegerField()

    def __str__(self):
        return self.label
    




class Exception(models.Model):

    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Closed', 'Closed'),
    ]

    ALLOWED_TRANSITIONS = {
        "Draft": ["Submitted"],
        "Submitted": ["UnderReview"],
        "UnderReview": ["Approved", "Rejected"],
        "Approved": ["Closed"],
        "Rejected": [],
        "Closed": [],
    }


    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.PROTECT)
    exception_type = models.ForeignKey(ExceptionType, on_delete=models.PROTECT)
    risk_issue = models.ForeignKey(RiskIssue, on_delete=models.PROTECT)
    risk_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="owned_exceptions")


    requestor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT)
    asset_purpose = models.ForeignKey(AssetPurpose, on_delete=models.PROTECT)
    data_classification = models.ForeignKey(DataClassification, on_delete=models.PROTECT)
    data_components = models.ManyToManyField(DataComponent)
    internet_exposure = models.ForeignKey(InternetExposure, on_delete=models.PROTECT)

    number_of_assets = models.IntegerField()

    short_description = models.TextField()
    reason_for_exception = models.TextField()
    compensatory_controls = models.TextField(blank=True)

    exception_till = models.DateField()

    risk_score = models.IntegerField(blank=True, null=True)
    risk_rating = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    assigned_risk_owner = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    related_name="risk_owner_exceptions"
    )

    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approver_exceptions"
    )

    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="submitted_exceptions"
    )


    # -----------------------------
    # Risk Engine Methods
    # -----------------------------

    def calculate_risk_score(self):
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
        if score < 36:
            return "Low"
        elif score < 432:
            return "Medium"
        elif score < 1200:
            return "High"
        else:
            return "Critical"

    def recalculate_risk(self):
        score = self.calculate_risk_score()
        rating = self.determine_risk_rating(score)

        self.risk_score = score
        self.risk_rating = rating

        # Save only risk fields
        super().save(update_fields=["risk_score", "risk_rating"])

    def __str__(self):
        return f"Exception {self.id} - {self.risk_rating}"
    

    def _change_status(self, new_status, user, action_type):
        previous = self.status
        self.status = new_status
        self.save(update_fields=["status"])

        from .models import AuditLog  # avoid circular import

        AuditLog.objects.create(
            exception=self,
            action_type=action_type,
            previous_status=previous,
            new_status=new_status,
            performed_by=user
        )
    

    def submit(self, user):
        if self.status != "Draft":
            raise ValueError("Only Draft exceptions can be submitted.")
        self._change_status("Submitted", user, "STATUS_CHANGE")


    def approve(self, user):
        if self.status != "Submitted":
            raise ValueError("Only Submitted exceptions can be approved.")
        self._change_status("Approved", user, "APPROVE")


    def reject(self, user):
        if self.status != "Submitted":
            raise ValueError("Only Submitted exceptions can be rejected.")
        self._change_status("Rejected", user, "REJECT")


    def close(self, user):
        if self.status != "Approved":
            raise ValueError("Only Approved exceptions can be closed.")
        self._change_status("Closed", user, "CLOSE")

    def _transition(self, new_status, user):
        if new_status not in self.ALLOWED_TRANSITIONS[self.status]:
            raise ValueError("Invalid state transition")

        previous_status = self.status
        self.status = new_status
        self.save()

        AuditLog.objects.create(
            exception=self,
            action_type=new_status,
            performed_by=user,
            previous_status=previous_status,
            new_status=new_status
        )

    def save(self, *args, **kwargs):
        if self.pk:
            old = Exception.objects.get(pk=self.pk)
            if old.status != self.status:
                raise ValueError("Direct status modification not allowed")
        super().save(*args, **kwargs)





    

    
    
    

    









class AuditLog(models.Model):

    ACTION_TYPES = [
        ("STATUS_CHANGE", "Status Change"),
        ("APPROVE", "Approve"),
        ("REJECT", "Reject"),
        ("CLOSE", "Close"),
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
    ]

    exception = models.ForeignKey("exceptions.Exception", on_delete=models.CASCADE)

    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)

    previous_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20, null=True, blank=True)

    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.exception.id} - {self.action_type}"
