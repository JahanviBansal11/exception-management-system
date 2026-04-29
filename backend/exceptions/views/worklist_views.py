from datetime import timedelta

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Case, Count, IntegerField, When
from django.utils import timezone

from exceptions.models import AuditLog, ReminderLog
from .helpers import get_visible_exceptions


class WorklistSummaryView(APIView):
    """Role-aware queue summary counters for dashboard cards."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        visible, role = get_visible_exceptions(request.user)

        stats = visible.aggregate(
            my_queue_total=Count("id"),
            draft=Count(Case(When(status="Draft", then=1), output_field=IntegerField())),
            submitted=Count(Case(When(status="Submitted", then=1), output_field=IntegerField())),
            awaiting_risk_owner=Count(Case(When(status="AwaitingRiskOwner", then=1), output_field=IntegerField())),
            approved=Count(Case(When(status="Approved", then=1), output_field=IntegerField())),
            rejected=Count(Case(When(status="Rejected", then=1), output_field=IntegerField())),
            approval_deadline_passed=Count(Case(When(status="ApprovalDeadlinePassed", then=1), output_field=IntegerField())),
            expired=Count(Case(When(status="Expired", then=1), output_field=IntegerField())),
            modified=Count(Case(When(status="Modified", then=1), output_field=IntegerField())),
            extended=Count(Case(When(status="Extended", then=1), output_field=IntegerField())),
            closed=Count(Case(When(status="Closed", then=1), output_field=IntegerField())),
            overdue_approval=Count(Case(When(
                status__in=["Submitted", "AwaitingRiskOwner"],
                approval_deadline__isnull=False,
                approval_deadline__lt=now,
                then=1,
            ), output_field=IntegerField())),
            pending_action=Count(Case(When(
                status__in=["Submitted", "AwaitingRiskOwner"], then=1,
            ), output_field=IntegerField())),
        )

        return Response({"view": role, **stats})


class WorklistNotificationsView(APIView):
    """Role-aware notification feed for dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        now = timezone.now()
        soon = now + timedelta(hours=24)
        visible, role = get_visible_exceptions(user)

        events = []

        # Overdue approvals
        for exc in visible.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
            approval_deadline__lt=now,
        ).order_by("approval_deadline")[:10]:
            events.append({
                "event_type": "deadline_overdue", "severity": "danger",
                "title": "Approval overdue",
                "message": f"Exception #{exc.id} is overdue for action.",
                "exception_id": exc.id, "status": exc.status,
                "timestamp": exc.approval_deadline,
            })

        # Due within 24 hours
        for exc in visible.filter(
            status__in=["Submitted", "AwaitingRiskOwner"],
            approval_deadline__isnull=False,
            approval_deadline__gte=now,
            approval_deadline__lte=soon,
        ).order_by("approval_deadline")[:10]:
            events.append({
                "event_type": "deadline_due_soon", "severity": "warning",
                "title": "Approval due soon",
                "message": f"Exception #{exc.id} is due within 24 hours.",
                "exception_id": exc.id, "status": exc.status,
                "timestamp": exc.approval_deadline,
            })

        # Reminder logs
        reminder_qs = ReminderLog.objects.filter(exception_request__in=visible)
        if role in {"approver", "risk-owner", "requestor"}:
            reminder_qs = reminder_qs.filter(sent_to=user)
        for log in reminder_qs.select_related("exception_request", "sent_to").order_by("-sent_at")[:20]:
            message = f"Exception #{log.exception_request_id}: {log.reminder_type}"
            title = f"Reminder {log.delivery_status}"
            if (log.message_content or "").startswith("ACTIVE_EXPIRY:"):
                stage = (log.message_content or "").split("\n", 1)[0].split(":", 1)[-1]
                message = f"Exception #{log.exception_request_id} reached expiry stage {stage}."
                title = "Active exception expiry reminder"
            events.append({
                "event_type": "reminder_sent" if log.delivery_status == "sent" else "reminder_failed",
                "severity": "info" if log.delivery_status == "sent" else "danger",
                "title": title, "message": message,
                "exception_id": log.exception_request_id,
                "status": log.exception_request.status if log.exception_request else None,
                "timestamp": log.sent_at,
            })

        # Requestor-specific: status change updates
        if role == "requestor":
            for log in (
                AuditLog.objects.filter(exception_request__in=visible)
                .exclude(action_type="SUBMIT")
                .exclude(performed_by=user)
                .select_related("exception_request", "performed_by")
                .order_by("-timestamp")[:40]
            ):
                details = log.details or {}
                actor = log.performed_by
                actor_label = (actor.get_full_name() or actor.username) if actor else "System"
                feedback = details.get("feedback")

                event_map = {
                    "REJECT": ("request_rejected", "danger", "Request rejected"),
                    "APPROVE": ("request_approved", "info", "Request approved"),
                    "EXPIRE": ("request_expired", "warning", "Request expired"),
                    "CLOSE": ("request_closed", "info", "Request closed"),
                }
                event_type, severity, title = event_map.get(
                    log.action_type, ("request_updated", "info", "Request updated")
                )
                message = details.get("message") or (
                    f"Exception #{log.exception_request_id}: "
                    f"{actor_label} changed request to {log.new_status or log.action_type}."
                )
                if feedback:
                    message = f"{message} Feedback: {feedback}"
                events.append({
                    "event_type": event_type, "severity": severity, "title": title,
                    "message": f"Exception #{log.exception_request_id}: {message}",
                    "exception_id": log.exception_request_id,
                    "status": log.new_status, "feedback": feedback,
                    "timestamp": log.timestamp,
                })

        events.sort(key=lambda e: e["timestamp"] or now, reverse=True)

        return Response({
            "view": role,
            "items": [
                {**e, "timestamp": e["timestamp"].isoformat() if e["timestamp"] else None}
                for e in events[:25]
            ],
        })
