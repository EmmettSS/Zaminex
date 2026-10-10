import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.basics.models import (
    Attribute,
    District as BasicsDistrict,
    PropertyType as BasicsPropertyType,
    PropertyUsage,
)
from apps.common.attribute_serializers import AttributeValuesMixin
from apps.analytics.metrics import (
    cached_neighborhood_price_stats_map,
    property_market_metrics,
)

from .models import Property, PropertyAppraisalReport, PropertyAttributeValue, PropertyImage

User = get_user_model()

LEGACY_TYPE_BY_NAME = {
    "apartment": "APARTMENT",
    "villa": "VILLA",
    "townhouse": "TOWNHOUSE",
    "studio": "STUDIO",
    "penthouse": "PENTHOUSE",
    "commercial": "COMMERCIAL",
    "office": "OFFICE",
    "office_building": "OFFICE",
    "shop": "SHOP",
    "land": "LAND",
    "warehouse": "COMMERCIAL",
    "other": "OTHER",
}


class PropertyImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ["id", "url", "sort_order"]

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            url = obj.image.url
            return request.build_absolute_uri(url) if request else url
        return ""


class PropertyAppraisalReportSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    fileName = serializers.CharField(source="original_filename", read_only=True)
    fileSize = serializers.IntegerField(source="file_size", read_only=True)
    uploadedBy = serializers.SerializerMethodField()
    uploadedAt = serializers.DateTimeField(
        source="created_at", format="%Y-%m-%d %H:%M", read_only=True
    )

    class Meta:
        model = PropertyAppraisalReport
        fields = ["id", "url", "fileName", "fileSize", "uploadedBy", "uploadedAt"]

    def get_url(self, obj):
        from django.urls import reverse

        url = reverse(
            "properties:api-properties-appraisal-report-download",
            kwargs={"pk": obj.property_id},
        )
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_uploadedBy(self, obj):
        if not obj.uploaded_by:
            return None
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

class PropertySerializer(AttributeValuesMixin, serializers.ModelSerializer):
    attribute_value_model = PropertyAttributeValue
    attribute_owner_field = "property"
    attribute_entity = Attribute.Entity.PROPERTY

    attributes = serializers.SerializerMethodField()
    attributeDetails = serializers.SerializerMethodField()

    propertyTypeRef = serializers.PrimaryKeyRelatedField(
        source="property_type_ref",
        queryset=BasicsPropertyType.objects.all(),
        required=False,
        allow_null=True,
    )
    propertyTypeName = serializers.CharField(
        source="property_type_ref.name", read_only=True, default=None
    )
    propertyTypeDisplay = serializers.CharField(
        source="property_type_ref.display_name", read_only=True, default=None
    )
    propertyUsage = serializers.PrimaryKeyRelatedField(
        source="property_usage",
        queryset=PropertyUsage.objects.all(),
        required=False,
        allow_null=True,
    )
    propertyUsageName = serializers.CharField(
        source="property_usage.display_name", read_only=True, default=None
    )

    internalCode = serializers.CharField(
        source="internal_code",
        read_only=True,
    )
    constructionYear = serializers.IntegerField(source="built_year", required=False, allow_null=True)
    fullAddress = serializers.CharField(source="address", required=False, allow_blank=True)
    beds = serializers.IntegerField(source="rooms", required=False, allow_null=True)
    district = serializers.CharField(source="neighborhood", required=False, allow_blank=True)
    districtId = serializers.PrimaryKeyRelatedField(
        source="district",
        queryset=BasicsDistrict.objects.all(),
        required=False,
        allow_null=True,
    )
    cityId = serializers.IntegerField(source="district.city_id", read_only=True, default=None)
    cityName = serializers.CharField(
        source="district.city.display_name", read_only=True, default=None
    )
    provinceId = serializers.IntegerField(
        source="district.city.province_id", read_only=True, default=None
    )
    provinceName = serializers.CharField(
        source="district.city.province.display_name", read_only=True, default=None
    )
    locationPath = serializers.SerializerMethodField()

    consultant = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="AGENT"),
        required=False,
        allow_null=True,
    )
    isShared = serializers.BooleanField(source="is_shared", required=False)

    ownerFirstName = serializers.CharField(
        source="owner_first_name", required=False, allow_blank=True
    )
    ownerLastName = serializers.CharField(
        source="owner_last_name", required=False, allow_blank=True
    )
    ownerPhone = serializers.CharField(
        source="owner_phone", required=False, allow_blank=True
    )

    type = serializers.ChoiceField(
        choices=Property.PropertyType.choices,
        source="property_type",
        required=False,
    )
    transactionType = serializers.ChoiceField(
        choices=Property.DealType.choices,
        source="deal_type",
        required=False,
    )
    price = serializers.SerializerMethodField()
    propertyStatus = serializers.SerializerMethodField()
    consultantName = serializers.SerializerMethodField()
    consultantId = serializers.SerializerMethodField()
    consultantRole = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d", read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    appraisalReport = PropertyAppraisalReportSerializer(
        source="appraisal_report", read_only=True
    )
    pricePerSqm = serializers.SerializerMethodField()
    imagesCount = serializers.SerializerMethodField()
    daysOnMarket = serializers.SerializerMethodField()
    spatialDensityRatio = serializers.SerializerMethodField()
    priceDeviationIndex = serializers.SerializerMethodField()
    geoPrecisionFlag = serializers.SerializerMethodField()
    engagementHeatScore = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            "id", "internalCode", "title", "type", "transactionType",
            "floor", "constructionYear", "fullAddress", "propertyStatus",
            "price", "area", "beds", "district", "consultant", "consultantName",
            "consultantId", "consultantRole",
            "date", "description", "images", "appraisalReport", "status",
            "pricePerSqm", "imagesCount", "daysOnMarket", "spatialDensityRatio",
            "priceDeviationIndex", "geoPrecisionFlag", "engagementHeatScore", "views",
            "propertyTypeRef", "propertyTypeName", "propertyTypeDisplay",
            "propertyUsage", "propertyUsageName",
            "districtId", "cityId", "cityName", "provinceId", "provinceName",
            "locationPath", "latitude", "longitude",
            "attributes", "attributeDetails",
            "isShared",
            "ownerFirstName", "ownerLastName", "ownerPhone",
        ]

    def get_price(self, obj):
        from apps.analytics.metrics import effective_sale_price

        price = effective_sale_price(obj)
        return str(price) if price is not None else None

    def get_locationPath(self, obj):
        return obj.district.full_path if obj.district_id else None

    def get_propertyStatus(self, obj):
        return (obj.status or "").lower()

    def get_consultantName(self, obj):
        if not obj.consultant: return "نامشخص"
        return obj.consultant.get_full_name() or obj.consultant.username

    def get_consultantId(self, obj):
        return obj.consultant_id

    def get_consultantRole(self, obj):
        if not obj.consultant:
            return None
        return obj.consultant.role

    def _market_metrics(self, obj):
        cache = getattr(self, "_neighborhood_avg_cache", None)
        if cache is None:
            cache = cached_neighborhood_price_stats_map()
            setattr(self, "_neighborhood_avg_cache", cache)
        if not hasattr(self, "_property_metrics_cache"):
            setattr(self, "_property_metrics_cache", {})
        key = obj.pk
        metrics_cache = self._property_metrics_cache
        if key not in metrics_cache:
            metrics_cache[key] = property_market_metrics(obj, cache)
        return metrics_cache[key]

    def get_pricePerSqm(self, obj):
        return self._market_metrics(obj).get("pricePerSqm")

    def get_imagesCount(self, obj):
        return self._market_metrics(obj).get("imagesCount")

    def get_daysOnMarket(self, obj):
        return self._market_metrics(obj).get("daysOnMarket")

    def get_spatialDensityRatio(self, obj):
        return self._market_metrics(obj).get("spatialDensityRatio")

    def get_priceDeviationIndex(self, obj):
        return self._market_metrics(obj).get("priceDeviationIndex")

    def get_geoPrecisionFlag(self, obj):
        return self._market_metrics(obj).get("geoPrecisionFlag")

    def get_engagementHeatScore(self, obj):
        return self._market_metrics(obj).get("engagementHeatScore")

    def get_views(self, obj):
        return self.get_engagementHeatScore(obj)

    def validate(self, attrs):
        if "rooms" in attrs and attrs["rooms"] is None:
            attrs["rooms"] = 0

        if self.instance is None:
            missing = {}
            for field, label in (
                ("owner_first_name", "نام مالک"),
                ("owner_last_name", "نام خانوادگی مالک"),
                ("owner_phone", "شماره موبایل مالک"),
            ):
                if not str(attrs.get(field, "") or "").strip():
                    missing[field] = f"{label} الزامی است."
            if missing:
                raise serializers.ValidationError(missing)

        phone = str(attrs.get("owner_phone") or "").strip()
        if phone and not re.fullmatch(r"09\d{9}", phone):
            raise serializers.ValidationError(
                {
                    "owner_phone": (
                        "شماره موبایل مالک باید دقیقاً ۱۱ رقم و با ۰۹ شروع "
                        "شود (مثال: 09121234567)."
                    )
                }
            )

        request = self.context.get("request")
        if request and getattr(request.user, "role", "") != "ADMIN":
            attrs.pop("is_shared", None)
            if (
                self.instance is not None
                and getattr(self.instance, "is_shared", False)
                and "consultant" in attrs
            ):
                attrs.pop("consultant")

        district = attrs.get("district")
        if district is not None:
            attrs["neighborhood"] = district.display_name

        type_ref = attrs.get("property_type_ref")
        if type_ref is not None:
            attrs["property_usage"] = type_ref.property_usage
            legacy = LEGACY_TYPE_BY_NAME.get(type_ref.name)
            if legacy:
                attrs["property_type"] = legacy

        lat = attrs.get("latitude")
        lng = attrs.get("longitude")
        if lat is not None and lng is not None:
            duplicates = Property.objects.filter(latitude=lat, longitude=lng)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            duplicate = duplicates.first()
            if duplicate is not None:
                raise serializers.ValidationError(
                    {
                        "latitude": (
                            f"این موقعیت قبلاً برای ملک «{duplicate.title}» "
                            f"(کد {duplicate.internal_code}) ثبت شده است. "
                            "موقعیت ملک نمی‌تواند با ملک دیگری یکی باشد؛ "
                            "نقطهٔ دیگری روی نقشه انتخاب کنید یا مختصات دیگری وارد کنید."
                        )
                    }
                )

        return attrs

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()
        if data.get("transactionType") is not None:
            data["transactionType"] = str(data["transactionType"]).upper()
        if data.get("type") is not None:
            data["type"] = str(data["type"]).upper()
        return super().to_internal_value(data)

    @transaction.atomic
    def create(self, validated_data):
        payload = self._pop_attribute_payload()
        instance = super().create(validated_data)
        self._save_attribute_values(instance, payload or {})
        self._validate_required_attributes(
            instance, instance.property_type_ref, "attribute_links"
        )
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        payload = self._pop_attribute_payload()
        instance = super().update(instance, validated_data)
        if payload is not None:
            self._save_attribute_values(instance, payload)
        self._validate_required_attributes(
            instance, instance.property_type_ref, "attribute_links"
        )
        return instance

_PROPERTY_LIST_EXCLUDED = {
    "description",
    "images",
    "appraisalReport",
    "attributes",
    "attributeDetails",
    "pricePerSqm",
    "daysOnMarket",
    "spatialDensityRatio",
    "priceDeviationIndex",
    "geoPrecisionFlag",
    "engagementHeatScore",
    "views",
}


class PropertyListSerializer(PropertySerializer):
    imageUrl = serializers.SerializerMethodField()

    class Meta(PropertySerializer.Meta):
        fields = [
            field
            for field in PropertySerializer.Meta.fields
            if field not in _PROPERTY_LIST_EXCLUDED
        ] + ["imageUrl"]

    def get_imageUrl(self, obj):
        request = self.context.get("request")
        first_image = obj.images.first()
        if first_image is not None and first_image.image:
            url = first_image.image.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_imagesCount(self, obj):
        return len(obj.images.all())
