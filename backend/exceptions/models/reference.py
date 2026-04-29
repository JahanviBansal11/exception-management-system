from django.db import models
from django.contrib.auth.models import User


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
        help_text="Days allowed for approval before escalation",
    )
    risk_owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

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
