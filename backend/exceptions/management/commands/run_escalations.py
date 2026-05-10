"""
Management command to manually run all scheduled escalation checks.

Usage:
  python manage.py run_escalations              # run all checks
  python manage.py run_escalations --only expire # run only expire_active_exceptions
"""

from django.core.management.base import BaseCommand


CHECKS = {
    "expire":   ("expire_active_exceptions",          "Approved -> Expired (end date passed)"),
    "deadline": ("escalate_expired_approvals",        "Submitted/AwaitingRiskOwner -> ApprovalDeadlinePassed"),
    "overdue":  ("notify_unresolved_expired_exceptions", "Notify risk owner - 14-day grace passed"),
}


class Command(BaseCommand):
    help = "Run scheduled escalation checks synchronously (no Celery required)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=list(CHECKS.keys()),
            help="Run only one specific check instead of all three.",
        )

    def handle(self, *args, **options):
        from exceptions.services.escalation_engine import EscalationEngine

        only = options.get("only")
        targets = {only: CHECKS[only]} if only else CHECKS

        for key, (method_name, description) in targets.items():
            self.stdout.write(f"  Running: {description} ...")
            try:
                count = getattr(EscalationEngine, method_name)()
                self.stdout.write(self.style.SUCCESS(f"    Done — {count} affected."))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"    Failed: {exc}"))

        self.stdout.write(self.style.SUCCESS("Escalation checks complete."))
