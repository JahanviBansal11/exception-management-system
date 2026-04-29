"""
Signals for ExceptionRequest.

Only handles risk recalculation triggered by model saves and M2M changes.
All other side effects (notifications, checkpoints) are handled explicitly
by WorkflowService — not via signals.
"""

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from exceptions.models import ExceptionRequest


_RISK_FIELDS = {"asset_type", "asset_purpose", "data_classification", "internet_exposure", "number_of_assets"}


@receiver(post_save, sender=ExceptionRequest)
def recalculate_risk_on_save(sender, instance, created, **kwargs):
    """Recalculate risk when risk-relevant FK fields change."""
    if created:
        return  # No risk data yet on creation

    update_fields = kwargs.get("update_fields")

    # Skip if we're already writing risk fields (avoids recursion)
    if update_fields and {"risk_score", "risk_rating"} & set(update_fields):
        return

    # Only recalculate if a risk-relevant field was actually updated
    if update_fields and not (_RISK_FIELDS & set(update_fields)):
        return

    from exceptions.services.risk_service import RiskService
    RiskService.recalculate_and_persist(instance)


@receiver(m2m_changed, sender=ExceptionRequest.data_components.through)
def recalculate_risk_on_m2m_change(sender, instance, action, **kwargs):
    """Recalculate risk when data_components M2M changes."""
    if action in {"post_add", "post_remove", "post_clear"}:
        from exceptions.services.risk_service import RiskService
        RiskService.recalculate_and_persist(instance)