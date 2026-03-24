from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
	help = "Seed required org roles and demo users for workflow testing"

	REQUIRED_GROUPS = ["Requestor", "Approver", "RiskOwner", "Security"]

	REQUIRED_USERS = [
		{
			"username": "req_user",
			"email": "req_user@example.com",
			"first_name": "Req",
			"last_name": "User",
			"group": "Requestor",
		},
		{
			"username": "bu_approver",
			"email": "bu_approver@example.com",
			"first_name": "BU",
			"last_name": "Approver",
			"group": "Approver",
		},
		{
			"username": "risk_owner",
			"email": "risk_owner@example.com",
			"first_name": "Risk",
			"last_name": "Owner",
			"group": "RiskOwner",
		},
		{
			"username": "sec_user",
			"email": "sec_user@example.com",
			"first_name": "Security",
			"last_name": "User",
			"group": "Security",
		},
	]

	def add_arguments(self, parser):
		parser.add_argument(
			"--password",
			default="testpass123",
			help="Password to set for all seeded users (default: testpass123)",
		)

	def handle(self, *args, **options):
		password = options["password"]

		groups = {}
		for group_name in self.REQUIRED_GROUPS:
			group, created = Group.objects.get_or_create(name=group_name)
			groups[group_name] = group
			verb = "Created" if created else "Exists"
			self.stdout.write(f"{verb} group: {group_name}")

		for user_spec in self.REQUIRED_USERS:
			user, created = User.objects.get_or_create(
				username=user_spec["username"],
				defaults={
					"email": user_spec["email"],
					"first_name": user_spec["first_name"],
					"last_name": user_spec["last_name"],
					"is_active": True,
				},
			)

			user.email = user_spec["email"]
			user.first_name = user_spec["first_name"]
			user.last_name = user_spec["last_name"]
			user.is_active = True
			user.set_password(password)
			user.save(update_fields=["email", "first_name", "last_name", "is_active", "password"])

			user.groups.set([groups[user_spec["group"]]])

			verb = "Created" if created else "Updated"
			self.stdout.write(f"{verb} user: {user.username} -> {user_spec['group']}")

		self.stdout.write(self.style.SUCCESS("Org roles/users seeded successfully."))
		self.stdout.write(self.style.WARNING(f"Seeded password for all users: {password}"))
