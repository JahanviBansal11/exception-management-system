"""
Synthetic Transaction Data Seed
Generates 30-50 realistic exception records for demo/UAT.
Creates exceptions at different workflow stages (Draft, Submitted, Approved, Rejected, etc.)

Usage:
  python manage.py seed_synthetic_exceptions --count 50
  python manage.py seed_synthetic_exceptions --count 30 --stage approved
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from exceptions.models import (
    ExceptionRequest,
    BusinessUnit,
    ExceptionType,
    RiskIssue,
    AssetType,
    AssetPurpose,
    DataClassification,
    DataComponent,
    InternetExposure,
)
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Generate synthetic exception data for demo/UAT"

    STATUSES = ["Draft", "Submitted", "AwaitingRiskOwner", "Approved", "Rejected", "Expired", "Closed"]

    DESCRIPTIONS = [
        "Temporary firewall rule bypass for vendor integration",
        "Legacy system access exception for data migration",
        "Development environment elevated privileges",
        "Third-party audit access to production logs",
        "Contractor access to encrypted data pending approval",
        "Deferred security patch for legacy app compatibility",
        "Emergency database access during incident",
        "Testing firewall rule before promotion",
        "Temporary admin access for system upgrade",
        "External auditor access to compliance logs",
    ]

    REASONS = [
        "Vendor requires temporary network access for integration testing. Risk mitigation: network segmentation.",
        "Legacy data migration requires temporary elevated privileges. Compensating control: audit logging enabled.",
        "Development environment testing requires firewall bypass. Risk mitigation: isolated network, approved testers only.",
        "Third-party audit requires read access to production logs. Compensating control: read-only access, time-limited.",
        "Contractor requires temporary access to anonymized customer data. Risk mitigation: VPN + MFA enforcement.",
        "Security patch deferred 30 days due to application compatibility. Compensating control: enhanced monitoring.",
        "Incident response requires emergency database access. Risk mitigation: access audit trail, revoked after incident.",
        "Testing firewall rule before UAT deployment. Compensating control: isolated environment, short-lived exception.",
        "System upgrade requires temporary admin access. Compensating control: dual approval, post-upgrade audit.",
        "External auditor requires read-only log access. Compensating control: role-based access, audit trail enabled.",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=30,
            help="Number of synthetic exceptions to generate (default: 30)",
        )
        parser.add_argument(
            "--stage",
            type=str,
            default="mixed",
            help="Stage distribution: 'mixed' (random), or specific stage (draft, submitted, approved, etc.)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all exceptions before generating new ones",
        )

    def handle(self, *args, **options):
        count = options["count"]
        stage = options["stage"].lower()
        clear = options.get("clear", False)

        self.stdout.write(self.style.HTTP_INFO(f"\n=== SYNTHETIC DATA GENERATION ===\n"))

        if clear:
            ExceptionRequest.objects.all().delete()
            self.stdout.write(self.style.WARNING("✓ Cleared all existing exceptions\n"))

        # Validate dependencies exist
        if not self._validate_dependencies():
            self.stdout.write(self.style.ERROR("✗ Missing required master data. Run seed_extended_data first."))
            return

        # Get reference data
        bus = list(BusinessUnit.objects.all())
        exc_types = list(ExceptionType.objects.all())
        risk_issues = list(RiskIssue.objects.all())
        asset_types = list(AssetType.objects.all())
        asset_purposes = list(AssetPurpose.objects.all())
        data_classifications = list(DataClassification.objects.all())
        data_components = list(DataComponent.objects.all())
        internet_exposures = list(InternetExposure.objects.all())
        requestors = list(User.objects.filter(groups__name="Requestor"))
        approvers = list(User.objects.filter(groups__name="Approver"))
        risk_owners = list(User.objects.filter(groups__name="RiskOwner"))

        if not all([bus, exc_types, risk_issues, requestors, approvers, risk_owners]):
            self.stdout.write(self.style.ERROR("✗ Missing required users or master data"))
            return

        self.stdout.write(f"Generating {count} synthetic exceptions...\n")

        created_count = 0
        for i in range(count):
            try:
                exc = self._create_exception(
                    idx=i,
                    bus=bus,
                    exc_types=exc_types,
                    risk_issues=risk_issues,
                    asset_types=asset_types,
                    asset_purposes=asset_purposes,
                    data_classifications=data_classifications,
                    data_components=data_components,
                    internet_exposures=internet_exposures,
                    requestors=requestors,
                    approvers=approvers,
                    risk_owners=risk_owners,
                    target_stage=stage,
                )
                created_count += 1
                if (i + 1) % 10 == 0:
                    self.stdout.write(f"  ✓ Created {i + 1}/{count} exceptions...")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error creating exception {i + 1}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"\n✅ Created {created_count}/{count} synthetic exceptions\n"))

        # Print summary
        self._print_summary()

    def _validate_dependencies(self):
        """Check that all required master data exists."""
        return (
            BusinessUnit.objects.exists()
            and ExceptionType.objects.exists()
            and RiskIssue.objects.exists()
            and User.objects.filter(groups__name="Requestor").exists()
            and User.objects.filter(groups__name="Approver").exists()
        )

    def _create_exception(self, idx, bus, exc_types, risk_issues, asset_types, asset_purposes,
                         data_classifications, data_components, internet_exposures,
                         requestors, approvers, risk_owners, target_stage="mixed"):
        """Create a single synthetic exception at random workflow stage."""

        # Determine target status
        if target_stage == "mixed":
            status = random.choice(self.STATUSES)
        else:
            status = target_stage.capitalize()
            if status not in self.STATUSES:
                status = random.choice(self.STATUSES)

        # Randomly select reference data
        bu = random.choice(bus)
        exc_type = random.choice(exc_types)
        risk_issue = random.choice(risk_issues)
        asset_type = random.choice(asset_types)
        asset_purpose = random.choice(asset_purposes)
        data_class = random.choice(data_classifications)
        internet_exp = random.choice(internet_exposures)
        
        requestor = random.choice(requestors)
        approver = bu.cio or random.choice(approvers)
        risk_owner = random.choice(risk_owners)

        # Pick random description and reason
        short_desc = random.choice(self.DESCRIPTIONS)
        reason = random.choice(self.REASONS)

        # Create exception in draft state first
        exc = ExceptionRequest.objects.create(
            business_unit=bu,
            exception_type=exc_type,
            risk_issue=risk_issue,
            asset_type=asset_type,
            asset_purpose=asset_purpose,
            data_classification=data_class,
            internet_exposure=internet_exp,
            number_of_assets=random.randint(1, 50),
            short_description=short_desc,
            reason_for_exception=reason,
            compensatory_controls="Enhanced monitoring enabled. Audit trail retention extended to 90 days.",
            requested_by=requestor,
            assigned_approver=approver,
            risk_owner=risk_owner,
            exception_end_date=timezone.now() + timedelta(days=random.randint(30, 180)),
        )

        # Add data components
        components_count = random.randint(1, 3)
        exc.data_components.set(random.sample(data_components, min(components_count, len(data_components))))

        # Recalculate risk
        exc.recalculate_risk()
        exc.refresh_from_db()

        # Transition to target status if not Draft
        if status != "Draft":
            self._transition_exception(exc, status, requestor, approver, risk_owner)

        return exc

    def _transition_exception(self, exc, target_status, requestor, approver, risk_owner):
        """Transition exception through workflow to target status."""
        
        now = timezone.now()
        
        if target_status == "Draft":
            return  # Already in Draft
        
        # Submit
        if target_status in ["Submitted", "AwaitingRiskOwner", "Approved", "Rejected", "Expired", "Closed"]:
            exc.submit(requestor)
            exc.created_at = now - timedelta(days=random.randint(1, 20))
            exc.save(update_fields=["created_at"])
        
        if target_status == "Submitted":
            return
        
        # BU Approve or Reject
        if target_status in ["AwaitingRiskOwner", "Approved", "Closed"]:
            # For High/Critical, will go to AwaitingRiskOwner
            exc.bu_approve(approver, notes="BU CIO approved after risk assessment.")
        elif target_status in ["Rejected", "Expired"]:
            exc.bu_reject(approver, notes="Insufficient compensating controls.")
            return
        
        if target_status == "AwaitingRiskOwner":
            return
        
        # Risk Owner Approve or Reject (if High/Critical)
        if target_status in ["Approved", "Closed"]:
            if exc.status == "AwaitingRiskOwner":
                exc.risk_approve(risk_owner, notes="Risk owner approved after assessment.")
        elif target_status == "Rejected" and exc.status == "AwaitingRiskOwner":
            exc.risk_reject(risk_owner, notes="Risk not adequately mitigated.")
            return
        
        if target_status == "Approved":
            return
        
        # Close
        if target_status == "Closed":
            exc.close(approver)
            exc.exception_end_date = now - timedelta(days=1)
            exc.save(update_fields=["exception_end_date"])
            return
        
        # Expired
        if target_status == "Expired":
            exc.mark_expired(approver)
            exc.approval_deadline = now - timedelta(days=1)
            exc.reminder_stage = "Reminder_90"
            exc.save(update_fields=["approval_deadline", "reminder_stage"])

    def _print_summary(self):
        """Print summary statistics."""
        self.stdout.write(self.style.HTTP_INFO("\n=== SUMMARY ==="))
        
        by_status = ExceptionRequest.objects.values("status").distinct().order_by("status")
        for row in by_status:
            count = ExceptionRequest.objects.filter(status=row["status"]).count()
            self.stdout.write(f"  {row['status']:<20}: {count:>3} exceptions")
        
        avg_risk = ExceptionRequest.objects.exclude(risk_score__isnull=True).values_list("risk_score", flat=True)
        if avg_risk:
            self.stdout.write(f"  Avg risk score     : {sum(avg_risk) / len(avg_risk):.1f}")
        
        self.stdout.write("")
