"""
Extended Data Seed Command
Populates BusinessUnits, ExceptionTypes, and RiskIssues.

Usage:
  python manage.py seed_extended_data
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from exceptions.models import BusinessUnit, ExceptionType, RiskIssue


class Command(BaseCommand):
    help = "Seed extended data: BusinessUnits, ExceptionTypes, and RiskIssues"

    # ============================================
    # BUSINESS UNITS (with CIO assignments)
    # ============================================
    BUSINESS_UNITS = [
        {"bu_code": "FIN", "name": "Finance & Accounting"},
        {"bu_code": "MFG", "name": "Manufacturing & Operations"},
        {"bu_code": "HR", "name": "Human Resources"},
        {"bu_code": "IT", "name": "Information Technology"},
        {"bu_code": "LEGAL", "name": "Legal & Compliance"},
        {"bu_code": "SALES", "name": "Sales & Distribution"},
    ]

    # ============================================
    # EXCEPTION TYPES (with SLA days)
    # ============================================
    EXCEPTION_TYPES = [
        {"name": "Firewall Exception", "description": "Non-standard firewall rule", "approval_sla_days": 28},
        {"name": "Access Exception", "description": "Access control deviation", "approval_sla_days": 21},
        {"name": "Encryption Exception", "description": "Encryption requirement waiver", "approval_sla_days": 35},
        {"name": "Patch Exception", "description": "Deferred security patch", "approval_sla_days": 14},
        {"name": "Audit Exception", "description": "Audit control bypass", "approval_sla_days": 56},
        {"name": "Data Retention Exception", "description": "Data retention policy waiver", "approval_sla_days": 30},
    ]

    # ============================================
    # RISK ISSUES
    # ============================================
    RISK_ISSUES = [
        {
            "title": "Firewall Rule Deviation",
            "description": "Non-standard inbound/outbound rule allowing unexpected traffic",
            "inherent_risk_score": 6,
        },
        {
            "title": "Privileged Access Elevation",
            "description": "Temporary elevation of privileges beyond normal scope",
            "inherent_risk_score": 9,
        },
        {
            "title": "Encryption Bypass",
            "description": "Temporary exemption from data encryption requirements",
            "inherent_risk_score": 8,
        },
        {
            "title": "Unpatched System",
            "description": "Known security patch deferred beyond standard timeline",
            "inherent_risk_score": 7,
        },
        {
            "title": "Audit Logging Bypass",
            "description": "Audit logging disabled or restricted temporarily",
            "inherent_risk_score": 8,
        },
        {
            "title": "Data Access Outside Boundary",
            "description": "Access to sensitive data from unexpected network location",
            "inherent_risk_score": 7,
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing BUs/ExceptionTypes/RiskIssues if they exist",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        self.stdout.write(self.style.HTTP_INFO("\n=== EXTENDED DATA SEEDING ===\n"))

        # Step 1: Create BusinessUnits and assign CIOs from existing approvers
        self._seed_business_units(force)

        # Step 2: Create ExceptionTypes
        self._seed_exception_types(force)

        # Step 3: Create RiskIssues
        self._seed_risk_issues(force)

        self.stdout.write(self.style.SUCCESS("\n✅ Extended data seeding complete!\n"))

    def _seed_business_units(self, force):
        """Create business units and assign CIOs."""
        self.stdout.write("\nSeeding business units...")
        cio_users = [u for u in User.objects.filter(groups__name="Approver")]

        if not cio_users:
            self.stdout.write(self.style.WARNING("  No users in Approver group found; CIO fields will be left empty."))

        for idx, bu_spec in enumerate(self.BUSINESS_UNITS):
            # Assign CIO from available approvers (round-robin)
            cio = cio_users[idx % len(cio_users)] if cio_users else None

            bu, created = BusinessUnit.objects.get_or_create(
                bu_code=bu_spec["bu_code"],
                defaults={
                    "name": bu_spec["name"],
                    "cio": cio,
                },
            )

            if force or created:
                bu.name = bu_spec["name"]
                bu.cio = cio
                bu.save()

            status = "✓ Created" if created else "  Updated"
            cio_name = f"{cio.get_full_name()}" if cio else "No CIO"
            self.stdout.write(f"  {status}: {bu.bu_code} - {bu.name} (CIO: {cio_name})")

    def _seed_exception_types(self, force):
        """Create exception types."""
        self.stdout.write("\nSeeding exception types...")
        for exc_spec in self.EXCEPTION_TYPES:
            exc_type, created = ExceptionType.objects.get_or_create(
                name=exc_spec["name"],
                defaults={
                    "description": exc_spec["description"],
                    "approval_sla_days": exc_spec["approval_sla_days"],
                },
            )

            if force or created:
                exc_type.description = exc_spec["description"]
                exc_type.approval_sla_days = exc_spec["approval_sla_days"]
                exc_type.save()

            status = "✓ Created" if created else "  Updated"
            self.stdout.write(f"  {status}: {exc_type.name} ({exc_spec['approval_sla_days']} days)")

    def _seed_risk_issues(self, force):
        """Create risk issues."""
        self.stdout.write("\nSeeding risk issues...")
        for issue_spec in self.RISK_ISSUES:
            risk_issue, created = RiskIssue.objects.get_or_create(
                title=issue_spec["title"],
                defaults={
                    "description": issue_spec["description"],
                    "inherent_risk_score": issue_spec["inherent_risk_score"],
                },
            )

            if force or created:
                risk_issue.description = issue_spec["description"]
                risk_issue.inherent_risk_score = issue_spec["inherent_risk_score"]
                risk_issue.save()

            status = "✓ Created" if created else "  Updated"
            self.stdout.write(f"  {status}: {risk_issue.title} (score: {issue_spec['inherent_risk_score']})")
