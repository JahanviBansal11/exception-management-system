"""Shared helpers used across view modules."""

from django.db.models import Q

from exceptions.models import ExceptionRequest
from exceptions.permissions import RISK_OWNER_GROUP_NAMES


def resolve_role(user) -> str:
    """Return the canonical dashboard role for a user."""
    groups = set(user.groups.values_list("name", flat=True))
    if "Security" in groups:
        return "security"
    if "Approver" in groups:
        return "approver"
    if groups & set(RISK_OWNER_GROUP_NAMES):
        return "risk-owner"
    return "requestor"


def get_visible_exceptions(user):
    """Return (queryset, role) scoped to what the user may see."""
    role = resolve_role(user)

    if role == "security":
        qs = ExceptionRequest.objects.exclude(status="Draft")
    elif role == "approver":
        qs = ExceptionRequest.objects.filter(assigned_approver=user).exclude(status="Draft")
    elif role == "risk-owner":
        qs = ExceptionRequest.objects.filter(risk_owner=user).filter(
            Q(status="AwaitingRiskOwner") | Q(
                status__in=["Approved", "Rejected", "ApprovalDeadlinePassed", "Expired",
                            "Modified", "Extended", "Closed"],
                checkpoints__checkpoint="risk_assessment_notified",
                checkpoints__status__in=["pending", "completed", "escalated"],
            )
        ).distinct()
    else:
        qs = ExceptionRequest.objects.filter(requested_by=user)

    return qs, role


def is_security(user) -> bool:
    return user.groups.filter(name="Security").exists() or user.is_superuser or user.is_staff
