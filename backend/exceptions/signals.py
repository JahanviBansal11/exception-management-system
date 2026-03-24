from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from .models import ExceptionRequest


# -----------------------------------
# Recalculate on ForeignKey updates
# -----------------------------------

@receiver(post_save, sender=ExceptionRequest)
def recalculate_on_save(sender, instance, created, **kwargs):
    update_fields = kwargs.get("update_fields")

    # Avoid recalculating if risk fields are already updated
    if update_fields and \
       ("risk_score" in update_fields or
        "risk_rating" in update_fields):
        return

    if update_fields:
        risk_related_fields = {
            "asset_type",
            "asset_purpose",
            "data_classification",
            "internet_exposure",
            "number_of_assets",
        }

        if not risk_related_fields.intersection(set(update_fields)):
            return

    if created:
        return

    instance.recalculate_risk()


# -----------------------------------
# Recalculate when ManyToMany changes
# -----------------------------------

@receiver(m2m_changed, sender=ExceptionRequest.data_components.through)
def recalculate_on_m2m_change(sender, instance, action, **kwargs):

    if action in ["post_add", "post_remove", "post_clear"]:
        instance.recalculate_risk()


# -----------------------------------
# Audit Logging Removed
# -----------------------------------
# Previously, log_exception_changes created duplicate AuditLog entries.
# All audit logging now happens explicitly in model methods (_change_status).
# Rationale: Signals create implicit side effects that are hard to trace.