from rest_framework import serializers
from .models import Exception


class ExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exception
        fields = "__all__"
        read_only_fields = (
            "risk_score",
            "risk_rating",
            "status",
        )
