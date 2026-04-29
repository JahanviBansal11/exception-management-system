from rest_framework import serializers
from django.contrib.auth.models import User

from exceptions.models import (
    BusinessUnit, ExceptionType, RiskIssue,
    AssetType, AssetPurpose, DataClassification,
    DataComponent, InternetExposure,
)


class BusinessUnitSerializer(serializers.ModelSerializer):
    cio_name = serializers.SerializerMethodField()

    class Meta:
        model = BusinessUnit
        fields = ['id', 'name', 'bu_code', 'cio', 'cio_name']

    def get_cio_name(self, obj):
        if obj.cio:
            return obj.cio.get_full_name() or obj.cio.username
        return None


class ExceptionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExceptionType
        fields = ['id', 'name', 'description', 'approval_sla_days']


class RiskIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskIssue
        fields = ['id', 'title', 'description', 'inherent_risk_score']


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ['id', 'name', 'weight']


class AssetPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPurpose
        fields = ['id', 'name', 'weight']


class DataClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataClassification
        fields = ['id', 'level', 'weight']


class DataComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataComponent
        fields = ['id', 'name', 'weight']


class InternetExposureSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternetExposure
        fields = ['id', 'label', 'weight']


class UserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
