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
from apps.common.metrics import build_neighborhood_price_stats_map, property_market_metrics

from .models import Property, PropertyAppraisalReport, PropertyAttributeValue, PropertyImage

User = get_user_model()

# Reverse of the mapping used by `link_properties_to_basics`: keeps the legacy
# Property.property_type column in sync when the new reference field is set.
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
    """Metadata of the (single) appraisal PDF attached to a property.

    `url` points at the authenticated download endpoint rather than the raw
    media path: it re-checks read access on every request, keeps the
    consultant's original filename in the Content-Disposition, and works
    uniformly for the download button and the inline preview.
    """

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
    # --- dynamic attributes (phase 3) --------------------------------------
    attribute_value_model = PropertyAttributeValue
    attribute_owner_field = "property"
    attribute_entity = Attribute.Entity.PROPERTY

    attributes = serializers.SerializerMethodField()
    attributeDetails = serializers.SerializerMethodField()

    # Reference-data links. `propertyTypeRef` is the new source of truth;
    # the legacy `type` column is still written for backwards compatibility
    # until every reader has moved over.
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
    # `district` stays the neighbourhood *name*: existing callers, the property
    # list and the search filter all send and read a string, and phase 4 must
    # not break them. `districtId` is the new foreign key; when it is supplied
    # the name is derived from it, so the two can never disagree.
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

    # Owner contact. Optional on the wire for edit/backfill, but the `validate`
    # hook below makes all three mandatory when a new property is created.
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
    # `price` is no longer a stored value on the property: it is the headline
    # sale figure of the property's listings, falling back to the legacy column
    # for records created before the split. Exposing it under the original name
    # keeps every existing consumer — the property list, the detail page, the
    # comboboxes — working without a change.
    price = serializers.SerializerMethodField()
    propertyStatus = serializers.SerializerMethodField()
    consultantName = serializers.SerializerMethodField()
    consultantId = serializers.SerializerMethodField()
    consultantRole = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source="created_at", format="%Y-%m-%d", read_only=True)
    images = PropertyImageSerializer(many=True, read_only=True)
    # Reverse one-to-one: DRF resolves it as None when no report is attached
    # (see rest_framework.fields.get_attribute).
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
        """The headline sale price, derived from the property's listings."""
        from apps.common.metrics import effective_sale_price

        price = effective_sale_price(obj)
        return str(price) if price is not None else None

    def get_locationPath(self, obj):
        """"استان / شهر / محله" when the property is linked to the hierarchy."""
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
            cache = build_neighborhood_price_stats_map()
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

        # Owner contact is mandatory when creating a property. It is not forced
        # on updates so existing rows and partial edits (which may predate the
        # field) can still be saved; the front-end form prompts for it.
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

        # Consultants cannot change the consultant field on shared properties.
        request = self.context.get("request")
        if request and getattr(request.user, "role", "") != "ADMIN":
            attrs.pop("is_shared", None)
            if (
                self.instance is not None
                and getattr(self.instance, "is_shared", False)
                and "consultant" in attrs
            ):
                attrs.pop("consultant")

        # Keep the legacy `property_type` column and the new reference row in
        # step. Readers still use the old column, so an update through either
        # field has to end up consistent.
        # When a district is chosen, its name is authoritative: it keeps the
        # legacy `neighborhood` text correct without the caller having to send
        # both, and stops the two from drifting apart.
        district = attrs.get("district")
        if district is not None:
            attrs["neighborhood"] = district.display_name

        type_ref = attrs.get("property_type_ref")
        if type_ref is not None:
            attrs["property_usage"] = type_ref.property_usage
            legacy = LEGACY_TYPE_BY_NAME.get(type_ref.name)
            if legacy:
                attrs["property_type"] = legacy

        return attrs

    def to_internal_value(self, data):
        if hasattr(data, "copy"):
            data = data.copy()
        if data.get("transactionType") is not None:
            data["transactionType"] = str(data["transactionType"]).upper()
        if data.get("type") is not None:
            data["type"] = str(data["type"]).upper()
        return super().to_internal_value(data)

    # -- persistence --------------------------------------------------------

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
