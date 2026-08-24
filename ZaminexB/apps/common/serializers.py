from rest_framework import serializers

from .models import CompanySettings, District


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ["id", "name", "is_active", "created_at", "updated_at"]


class CompanySettingsSerializer(serializers.ModelSerializer):
    companyName = serializers.CharField(source="company_name")
    licenseNumber = serializers.CharField(
        source="license_number", required=False, allow_blank=True
    )

    class Meta:
        model = CompanySettings
        fields = ["companyName", "licenseNumber", "email", "phone", "address", "updated_at"]
        read_only_fields = ["updated_at"]
