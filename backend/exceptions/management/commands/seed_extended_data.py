"""
Extended Data Seed Command
Populates BusinessUnits, ExceptionTypes, RiskIssues, and demo users.

Usage:
  python manage.py seed_extended_data
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from exceptions.models import BusinessUnit, ExceptionType, RiskIssue


class Command(BaseCommand):
    help = "Seed extended data: BusinessUnits, ExceptionTypes, RiskIssues, and users"

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

    # ============================================
    # DEMO USERS BY ROLE
    # ============================================
    DEMO_USERS = [
        # Requestors
        {"username": "req_alice", "email": "alice.req@example.com", "first_name": "Alice", "last_name": "Requester", "group": "Requestor"},
        {"username": "req_bob", "email": "bob.req@example.com", "first_name": "Bob", "last_name": "Requester", "group": "Requestor"},
        {"username": "req_charlie", "email": "charlie.req@example.com", "first_name": "Charlie", "last_name": "Requester", "group": "Requestor"},
        
        # Approvers (BU CIOs)
        {"username": "cio_fin", "email": "cio.fin@example.com", "first_name": "Finance", "last_name": "CIO", "group": "Approver"},
        {"username": "cio_mfg", "email": "cio.mfg@example.com", "first_name": "Manufacturing", "last_name": "CIO", "group": "Approver"},
        {"username": "cio_hr", "email": "cio.hr@example.com", "first_name": "HR", "last_name": "CIO", "group": "Approver"},
        
        # Risk Owners
        {"username": "risk_owner1", "email": "risk.owner1@example.com", "first_name": "Risk", "last_name": "Owner1", "group": "RiskOwner"},
        {"username": "risk_owner2", "email": "risk.owner2@example.com", "first_name": "Risk", "last_name": "Owner2", "group": "RiskOwner"},
        
        # Security Team
        {"username": "sec_admin", "email": "sec.admin@example.com", "first_name": "Security", "last_name": "Admin", "group": "Security"},
        {"username": "sec_audit", "email": "sec.audit@example.com", "first_name": "Security", "last_name": "Auditor", "group": "Security"},
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="DemoPass123!",
            help="Password for all seeded users (default: DemoPass123!)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing users/BUs if they exist",
        )

    def handle(self, *args, **options):
        password = options["password"]
        force = options.get("force", False)

        self.stdout.write(self.style.HTTP_INFO("\n=== EXTENDED DATA SEEDING ===\n"))

        # Step 1: Create groups
        self._seed_groups()

        # Step 2: Create users
        self._seed_users(password, force)

        # Step 3: Create BusinessUnits and assign CIOs
        bu_map = self._seed_business_units(force)

        # Step 4: Create ExceptionTypes
        self._seed_exception_types(force)

        # Step 5: Create RiskIssues
        self._seed_risk_issues(force)

        self.stdout.write(self.style.SUCCESS("\n✅ Extended data seeding complete!\n"))
        self.stdout.write(self.style.WARNING(f"All demo users password: {password}\n"))

    def _seed_groups(self):
        """Create required groups."""
        self.stdout.write("Seeding groups...")
        groups = ["Requestor", "Approver", "RiskOwner", "Security"]
        for group_name in groups:
            _, created = Group.objects.get_or_create(name=group_name)
            status = "✓ Created" if created else "  Exists"
            self.stdout.write(f"  {status}: {group_name}")

    def _seed_users(self, password, force):
        """Create demo users and assign to groups."""
        self.stdout.write("\nSeeding users...")
        groups_map = {g.name: g for g in Group.objects.all()}

        for user_spec in self.DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=user_spec["username"],
                defaults={
                    "email": user_spec["email"],
                    "first_name": user_spec["first_name"],
                    "last_name": user_spec["last_name"],
                    "is_active": True,
                },
            )

            # Update user if force or newly created
            if created or force:
                user.email = user_spec["email"]
                user.first_name = user_spec["first_name"]
                user.last_name = user_spec["last_name"]
                user.is_active = True
                user.set_password(password)
                user.save()

            # Assign to group
            group = groups_map.get(user_spec["group"])
            if group:
                user.groups.clear()
                user.groups.add(group)

            status = "✓ Created" if created else "  Updated"
            self.stdout.write(f"  {status}: {user.username} ({user_spec['group']})")

    def _seed_business_units(self, force):
        """Create business units and assign CIOs."""
        self.stdout.write("\nSeeding business units...")
        users = {u.username: u for u in User.objects.all()}
        cio_users = [u for u in User.objects.filter(groups__name="Approver")]

        bu_map = {}
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

            bu_map[bu.bu_code] = bu
            status = "✓ Created" if created else "  Updated"
            cio_name = f"{cio.get_full_name()}" if cio else "No CIO"
            self.stdout.write(f"  {status}: {bu.bu_code} - {bu.name} (CIO: {cio_name})")

        return bu_map

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
