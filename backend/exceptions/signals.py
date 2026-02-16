from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from .models import Exception
from .models import AuditLog


# -----------------------------------
# Recalculate on ForeignKey updates
# -----------------------------------

@receiver(post_save, sender=Exception)
def recalculate_on_save(sender, instance, created, **kwargs):

    # Avoid recalculating if risk fields are already updated
    if kwargs.get("update_fields") and \
       ("risk_score" in kwargs["update_fields"] or
        "risk_rating" in kwargs["update_fields"]):
        return

    instance.recalculate_risk()


# -----------------------------------
# Recalculate when ManyToMany changes
# -----------------------------------

@receiver(m2m_changed, sender=Exception.data_components.through)
def recalculate_on_m2m_change(sender, instance, action, **kwargs):

    if action in ["post_add", "post_remove", "post_clear"]:
        instance.recalculate_risk()
        

@receiver(post_save, sender=Exception)
def log_exception_changes(sender, instance, created, **kwargs):

    if created:
        AuditLog.objects.create(
            exception=instance,
            action_type="CREATE",
            performed_by=instance.requestor
        )
    else:
        AuditLog.objects.create(
            exception=instance,
            action_type="UPDATE",
            performed_by=instance.requestor
        )