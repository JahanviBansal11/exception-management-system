from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User

from exceptions.models import (
    BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification,
    DataComponent, InternetExposure,
)
from exceptions.serializers import (
    BusinessUnitSerializer, ExceptionTypeSerializer, RiskIssueSerializer,
    AssetTypeSerializer, AssetPurposeSerializer, DataClassificationSerializer,
    DataComponentSerializer, InternetExposureSerializer, UserBriefSerializer,
)
from exceptions.permissions import RISK_OWNER_GROUP_NAMES


class ReferenceDataView(APIView):
    """Single endpoint returning all lookup data needed to populate create/edit forms."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_users = User.objects.filter(is_active=True).order_by("last_name", "first_name")
        approvers = active_users.filter(groups__name="Approver").distinct()
        risk_owners = active_users.filter(groups__name__in=RISK_OWNER_GROUP_NAMES).distinct()

        return Response({
            "business_units":       BusinessUnitSerializer(BusinessUnit.objects.select_related("cio").all(), many=True).data,
            "exception_types":      ExceptionTypeSerializer(ExceptionType.objects.all(), many=True).data,
            "risk_issues":          RiskIssueSerializer(RiskIssue.objects.all(), many=True).data,
            "asset_types":          AssetTypeSerializer(AssetType.objects.all(), many=True).data,
            "asset_purposes":       AssetPurposeSerializer(AssetPurpose.objects.all(), many=True).data,
            "data_classifications": DataClassificationSerializer(DataClassification.objects.all(), many=True).data,
            "data_components":      DataComponentSerializer(DataComponent.objects.all(), many=True).data,
            "internet_exposures":   InternetExposureSerializer(InternetExposure.objects.all(), many=True).data,
            "users":                UserBriefSerializer(active_users, many=True).data,
            "approvers":            UserBriefSerializer(approvers, many=True).data,
            "risk_owners":          UserBriefSerializer(risk_owners, many=True).data,
        })
