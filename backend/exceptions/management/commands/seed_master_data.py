from django.core.management.base import BaseCommand
from exceptions.models import (
    AssetType,
    AssetPurpose,
    DataClassification,
    DataComponent,
    InternetExposure
)


class Command(BaseCommand):
    help = "Seed master data for risk engine"

    def handle(self, *args, **kwargs):

        # --------------------
        # Asset Types
        # --------------------
        asset_types = {
            "Cloud": 5,
            "Application": 5,
            "Database": 5,
            "Endpoint": 2,
            "Operating System": 4,
            "Security Device": 4,
            "Network Hardware": 3,
            "Mobile": 1,
        }

        for name, weight in asset_types.items():
            AssetType.objects.get_or_create(name=name, weight=weight)

        # --------------------
        # Asset Purpose
        # --------------------
        purposes = {
            "Factory Operations": 5,
            "Finance & Accounting": 5,
            "Marketing & Communications": 1,
            "Training": 2,
            "Sales & Distribution": 3,
            "Inventory Management": 4,
            "Digital": 4,
            "Government Relations": 5,
            "Human Resources": 5,
            "Legal": 5,
            "Services & Aftermarket": 3,
            "Others": 3,
        }

        for name, weight in purposes.items():
            AssetPurpose.objects.get_or_create(name=name, weight=weight)

        # --------------------
        # Data Classification
        # --------------------
        classifications = {
            "Public": 1,
            "Confidential - Low": 2,
            "Confidential - High": 3,
            "Restricted": 4,
            "Controlled Information": 5,
        }

        for name, weight in classifications.items():
            DataClassification.objects.get_or_create(level=name, weight=weight)

        # --------------------
        # Data Components
        # --------------------
        components = {
            "Product Information": 2,
            "Pricing Information": 4,
            "Customer or Vendor Details": 5,
            "Employee or Contractor Details": 5,
            "Financial Data": 5,
            "Authentication and Access Data": 5,
            "Intellectual Property": 5,
            "Legal and Compliance Data": 5,
            "Government and National Security Data": 5,
            "Source Code": 4,
            "Others": 3,
        }

        for name, weight in components.items():
            DataComponent.objects.get_or_create(name=name, weight=weight)

        # --------------------
        # Internet Exposure
        # --------------------
        exposure = {
            "Yes, accessible from Internet": 3,
            "No, accessible internally": 1,
        }

        for name, weight in exposure.items():
            InternetExposure.objects.get_or_create(label=name, weight=weight)

        self.stdout.write(self.style.SUCCESS("Master data seeded successfully"))
