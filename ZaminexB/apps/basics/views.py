from __future__ import annotations

import logging

from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.common import cache_utils

logger = logging.getLogger(__name__)

from .models import (
    Attribute,
    AttributeCategory,
    City,
    District,
    Province,
    AttributeOption,
    DealType,
    DealTypeAttribute,
    DealTypeSearchAttribute,
    PropertyType,
    PropertyTypeAttribute,
    PropertyTypeSearchAttribute,
    PropertyUsage,
)
from .serializers import (
    AttributeOptionSerializer,
    AttributeCategorySerializer,
    CitySerializer,
    DistrictSerializer,
    ProvinceSerializer,
    AttributeSerializer,
    DealTypeAttributeSerializer,
    DealTypeSerializer,
    FormFieldSerializer,
    PropertyTypeAttributeSerializer,
    PropertyTypeSerializer,
    PropertyUsageSerializer,
    SearchFilterSerializer,
)


class ReadAnyWriteAdmin(IsAuthenticated):
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    message = "فقط مدیر می‌تواند اطلاعات پایه را ویرایش کند."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return getattr(request.user, "role", "") == UserRole.ADMIN


class BasicsViewSet(viewsets.ModelViewSet):
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        queryset = self.queryset.all()
        if self.action == "list" and self.request.query_params.get("all") not in {
            "1",
            "true",
            "yes",
        }:
            queryset = queryset.filter(is_active=True)
        return queryset

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        instance = self.queryset.model.all_objects.filter(pk=pk).first()
        if instance is None:
            return Response({"detail": "مورد یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        instance.restore()
        return Response(self.get_serializer(instance).data)


class PropertyUsageViewSet(BasicsViewSet):
    queryset = PropertyUsage.objects.all()
    serializer_class = PropertyUsageSerializer

    def perform_destroy(self, instance):
        if instance.property_types.filter(is_active=True).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "این کاربری دارای نوع ملک فعال است؛ ابتدا آن‌ها را منتقل یا غیرفعال کنید."
            )
        instance.delete()


class PropertyTypeViewSet(BasicsViewSet):
    queryset = PropertyType.objects.select_related("property_usage")
    serializer_class = PropertyTypeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        usage = self.request.query_params.get("usage")
        if usage:
            if str(usage).isdigit():
                queryset = queryset.filter(property_usage_id=usage)
            else:
                queryset = queryset.filter(property_usage__name=usage)
        return queryset

    @action(detail=True, methods=["get"], url_path="attributes")
    def attributes(self, request, pk=None):
        property_type = self.get_object()
        links = (
            property_type.attribute_links.select_related("attribute")
            .prefetch_related("attribute__options")
            .order_by("sort_order")
        )
        return Response(PropertyTypeAttributeSerializer(links, many=True).data)


class DealTypeViewSet(BasicsViewSet):
    queryset = DealType.objects.all()
    serializer_class = DealTypeSerializer

    @action(detail=True, methods=["get"], url_path="attributes")
    def attributes(self, request, pk=None):
        deal_type = self.get_object()
        links = (
            deal_type.attribute_links.select_related("attribute")
            .prefetch_related("attribute__options")
            .order_by("sort_order")
        )
        return Response(DealTypeAttributeSerializer(links, many=True).data)


class AttributeCategoryViewSet(BasicsViewSet):
    queryset = AttributeCategory.objects.all()
    serializer_class = AttributeCategorySerializer

    def perform_create(self, serializer):
        last = AttributeCategory.objects.order_by("-sort_order").values_list(
            "sort_order", flat=True
        ).first()
        serializer.save(sort_order=(last or 0) + 1)

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError

        if instance.is_system_category:
            raise ValidationError(
                f"«{instance.display_name}» یکی از دسته‌بندی‌های پایهٔ سیستم است و "
                "حذف آن امکان‌پذیر نیست؛ در صورت عدم نیاز آن را غیرفعال کنید."
            )

        count = instance.attribute_count()
        if count:
            raise ValidationError(
                f"«{instance.display_name}» شامل {count} ویژگی است؛ ابتدا آن ویژگی‌ها "
                "را به دسته‌بندی دیگری منتقل کنید تا این دسته‌بندی خالی شود."
            )

        instance.delete()


class AttributeViewSet(BasicsViewSet):
    queryset = Attribute.objects.prefetch_related("options")
    serializer_class = AttributeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        entity = self.request.query_params.get("entity")
        if entity in {Attribute.Entity.PROPERTY, Attribute.Entity.LISTING}:
            queryset = queryset.filter(entity=entity)
        if self.request.query_params.get("facility") in {"1", "true"}:
            queryset = queryset.filter(is_facility=True)
        return queryset

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError

        if instance.is_core:
            raise ValidationError(
                "ویژگی‌های ثابت به ستون‌های پایگاه داده متصل هستند و قابل حذف نیستند."
            )

        bound_count = PropertyTypeAttribute.objects.filter(
            attribute=instance, is_active=True
        ).count() + DealTypeAttribute.objects.filter(
            attribute=instance, is_active=True
        ).count()
        if bound_count:
            raise ValidationError(
                f"این ویژگی به {bound_count} نوع متصل است؛ ابتدا اتصالات را حذف کنید."
            )

        instance.delete()

    @action(detail=True, methods=["get", "post"], url_path="options")
    def options(self, request, pk=None):
        attribute = self.get_object()

        if request.method == "GET":
            options = attribute.options.all()
            return Response(AttributeOptionSerializer(options, many=True).data)

        if getattr(request.user, "role", "") != UserRole.ADMIN:
            return Response(
                {"detail": "فقط مدیر می‌تواند گزینه‌ها را ویرایش کند."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AttributeOptionSerializer(
            data=request.data, context={"attribute": attribute}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(attribute=attribute)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"options/(?P<option_id>\d+)",
    )
    def delete_option(self, request, pk=None, option_id=None):
        if getattr(request.user, "role", "") != UserRole.ADMIN:
            return Response(
                {"detail": "فقط مدیر می‌تواند گزینه‌ها را ویرایش کند."},
                status=status.HTTP_403_FORBIDDEN,
            )

        attribute = self.get_object()
        option = attribute.options.filter(pk=option_id).first()
        if option is None:
            return Response(
                {"detail": "گزینه یافت نشد."}, status=status.HTTP_404_NOT_FOUND
            )

        from apps.listings.models import ListingAttributeValue
        from apps.properties.models import PropertyAttributeValue

        in_use = (
            PropertyAttributeValue.objects.filter(
                attribute=attribute, value_text=option.value
            ).exists()
            or ListingAttributeValue.objects.filter(
                attribute=attribute, value_text=option.value
            ).exists()
        )
        if in_use:
            return Response(
                {
                    "detail": (
                        f"«{option.display_name}» در رکوردهای ثبت‌شده استفاده شده است؛ "
                        "به‌جای حذف، آن را غیرفعال کنید."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _sync_search_binding(form_link):
    attribute = form_link.attribute
    if isinstance(form_link, PropertyTypeAttribute):
        search_model = PropertyTypeSearchAttribute
        scope = {"property_type": form_link.property_type, "attribute": attribute}
    else:
        search_model = DealTypeSearchAttribute
        scope = {"deal_type": form_link.deal_type, "attribute": attribute}

    if attribute.filter_type == Attribute.FilterType.NONE:
        search_model.objects.filter(**scope).delete()
        return

    search_model.objects.update_or_create(
        **scope,
        defaults={
            "is_active": form_link.is_active,
            "sort_order": form_link.sort_order,
        },
    )


def _drop_search_binding(form_link):
    if isinstance(form_link, PropertyTypeAttribute):
        PropertyTypeSearchAttribute.objects.filter(
            property_type=form_link.property_type, attribute=form_link.attribute
        ).delete()
    else:
        DealTypeSearchAttribute.objects.filter(
            deal_type=form_link.deal_type, attribute=form_link.attribute
        ).delete()


class PropertyTypeAttributeViewSet(viewsets.ModelViewSet):
    queryset = PropertyTypeAttribute.objects.select_related(
        "attribute", "property_type"
    ).prefetch_related("attribute__options")
    serializer_class = PropertyTypeAttributeSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        property_type = self.request.query_params.get("propertyType")
        if property_type:
            queryset = queryset.filter(property_type_id=property_type)
        return queryset.order_by("sort_order")

    def perform_create(self, serializer):
        link = serializer.save()
        _sync_search_binding(link)

    def perform_update(self, serializer):
        link = serializer.save()
        _sync_search_binding(link)

    def perform_destroy(self, instance):
        _drop_search_binding(instance)
        instance.delete()

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        if getattr(request.user, "role", "") != UserRole.ADMIN:
            return Response(
                {"detail": "فقط مدیر می‌تواند ترتیب را تغییر دهد."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data if isinstance(request.data, list) else request.data.get("order", [])
        if not isinstance(payload, list):
            return Response(
                {"detail": "فرمت ورودی نامعتبر است؛ لیستی از {id, sortOrder} انتظار می‌رود."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        changed = 0
        for item in payload:
            link_id = item.get("id")
            sort_order = item.get("sortOrder", item.get("sort_order"))
            if link_id is None or sort_order is None:
                continue
            PropertyTypeAttribute.objects.filter(pk=link_id).update(sort_order=sort_order)
            changed += 1

        if changed:
            invalidate_reference_caches()

        return Response({"detail": "ترتیب ذخیره شد."})


class DealTypeAttributeViewSet(viewsets.ModelViewSet):
    queryset = DealTypeAttribute.objects.select_related(
        "attribute", "deal_type"
    ).prefetch_related("attribute__options")
    serializer_class = DealTypeAttributeSerializer
    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        deal_type = self.request.query_params.get("dealType")
        if deal_type:
            queryset = queryset.filter(deal_type_id=deal_type)
        return queryset.order_by("sort_order")

    def perform_create(self, serializer):
        link = serializer.save()
        _sync_search_binding(link)

    def perform_update(self, serializer):
        link = serializer.save()
        _sync_search_binding(link)

    def perform_destroy(self, instance):
        _drop_search_binding(instance)
        instance.delete()


def _active_links(manager):
    return (
        manager.filter(is_active=True, attribute__is_active=True)
        .filter(attribute__deleted_at__isnull=True)
        .select_related("attribute")
        .prefetch_related(
            Prefetch(
                "attribute__options",
                queryset=AttributeOption.objects.filter(is_active=True),
            )
        )
        .order_by("sort_order")
    )


REFERENCE_TTL = 600


def _build_catalog_payload() -> dict:
    usages = PropertyUsage.objects.filter(is_active=True)
    types = (
        PropertyType.objects.filter(is_active=True)
        .select_related("property_usage")
    )
    deals = DealType.objects.filter(is_active=True)
    return {
        "usages": PropertyUsageSerializer(usages, many=True).data,
        "propertyTypes": PropertyTypeSerializer(types, many=True).data,
        "dealTypes": DealTypeSerializer(deals, many=True).data,
    }


def cached_basics_catalog() -> dict:
    key = cache_utils.make_key("catalog")
    return cache_utils.cache_or_compute(key, _build_catalog_payload, REFERENCE_TTL)


def _build_location_tree_payload() -> list:
    provinces = (
        Province.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch("cities", queryset=City.objects.filter(is_active=True)),
            Prefetch(
                "cities__districts",
                queryset=District.objects.filter(is_active=True),
            ),
        )
    )
    return [
        {
            "id": province.id,
            "name": province.name,
            "displayName": province.display_name,
            "cities": [
                {
                    "id": city.id,
                    "name": city.name,
                    "displayName": city.display_name,
                    "districts": [
                        {
                            "id": district.id,
                            "name": district.name,
                            "displayName": district.display_name,
                        }
                        for district in city.districts.all()
                    ],
                }
                for city in province.cities.all()
            ],
        }
        for province in provinces
    ]


def cached_location_tree() -> list:
    key = cache_utils.make_key("location-tree")
    return cache_utils.cache_or_compute(
        key, _build_location_tree_payload, REFERENCE_TTL
    )


def _build_property_form_payload(property_type: PropertyType) -> dict:
    links = _active_links(property_type.attribute_links)
    fields = FormFieldSerializer(links, many=True).data
    return {
        "propertyType": {
            "id": property_type.id,
            "name": property_type.name,
            "displayName": property_type.display_name,
        },
        "propertyUsage": {
            "id": property_type.property_usage_id,
            "name": property_type.property_usage.name,
            "displayName": property_type.property_usage.display_name,
        },
        "fields": [f for f in fields if not f["isFacility"]],
        "facilities": [f for f in fields if f["isFacility"]],
    }


def cached_property_form_schema(property_type_pk: int) -> dict:
    key = cache_utils.make_key("schema", "property-form", property_type_pk)

    def compute():
        property_type = (
            PropertyType.objects.select_related("property_usage")
            .filter(pk=property_type_pk)
            .first()
        )
        if property_type is None:
            return None
        return _build_property_form_payload(property_type)

    return cache_utils.cache_or_compute(key, compute, REFERENCE_TTL)


def _build_listing_form_payload(deal_type: DealType) -> dict:
    links = _active_links(deal_type.attribute_links)
    fields = FormFieldSerializer(links, many=True).data
    return {
        "dealType": {
            "id": deal_type.id,
            "name": deal_type.name,
            "displayName": deal_type.display_name,
        },
        "fields": [f for f in fields if not f["isFacility"]],
        "facilities": [f for f in fields if f["isFacility"]],
    }


def cached_listing_form_schema(deal_type_pk: int) -> dict:
    key = cache_utils.make_key("schema", "listing-form", deal_type_pk)

    def compute():
        deal_type = DealType.objects.filter(pk=deal_type_pk).first()
        if deal_type is None:
            return None
        return _build_listing_form_payload(deal_type)

    return cache_utils.cache_or_compute(key, compute, REFERENCE_TTL)


def _build_search_payload(property_type, deal_type) -> dict:
    property_filters = (
        SearchFilterSerializer(
            _active_links(property_type.search_attribute_links), many=True
        ).data
        if property_type is not None
        else []
    )
    deal_filters = (
        SearchFilterSerializer(
            _active_links(deal_type.search_attribute_links), many=True
        ).data
        if deal_type is not None
        else []
    )
    return {"propertyFilters": property_filters, "dealFilters": deal_filters}


def cached_search_schema(property_type_pk, deal_type_pk) -> dict:
    key = cache_utils.make_key(
        "schema", "search", property_type_pk or "-", deal_type_pk or "-"
    )

    def compute():
        property_type = (
            PropertyType.objects.filter(pk=property_type_pk).first()
            if property_type_pk
            else None
        )
        deal_type = (
            DealType.objects.filter(pk=deal_type_pk).first()
            if deal_type_pk
            else None
        )
        return _build_search_payload(property_type, deal_type)

    return cache_utils.cache_or_compute(key, compute, REFERENCE_TTL)


def _all_reference_keys(extra_pts=(), extra_dts=()) -> list:
    pts = list(PropertyType.objects.values_list("pk", flat=True))
    dts = list(DealType.objects.values_list("pk", flat=True))
    for pk in extra_pts:
        if pk not in pts:
            pts.append(pk)
    for pk in extra_dts:
        if pk not in dts:
            dts.append(pk)
    keys = [
        cache_utils.make_key("catalog"),
        cache_utils.make_key("location-tree"),
    ]
    for pt in pts:
        keys.append(cache_utils.make_key("schema", "property-form", pt))
    for dt in dts:
        keys.append(cache_utils.make_key("schema", "listing-form", dt))
    for pt in [*pts, None]:
        for dt in [*dts, None]:
            keys.append(
                cache_utils.make_key("schema", "search", pt or "-", dt or "-")
            )
    return keys


def invalidate_reference_caches(sender=None, instance=None, **kwargs) -> None:
    extra_pts = (instance.pk,) if instance is not None and sender is PropertyType else ()
    extra_dts = (instance.pk,) if instance is not None and sender is DealType else ()
    try:
        for key in _all_reference_keys(extra_pts, extra_dts):
            cache_utils.cache_delete(key)
    except Exception:
        logger.debug(
            "reference cache invalidation failed; the TTL is the backstop",
            exc_info=True,
        )


class PropertyFormSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw = request.query_params.get("propertyType")
        if not raw:
            return Response(
                {"detail": "پارامتر propertyType الزامی است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lookup = {"pk": raw} if str(raw).isdigit() else {"name": raw}
        property_type = (
            PropertyType.objects.select_related("property_usage").filter(**lookup).first()
        )
        if property_type is None:
            return Response(
                {"detail": "نوع ملک یافت نشد."}, status=status.HTTP_404_NOT_FOUND
            )

        payload = cached_property_form_schema(property_type.pk)
        return Response(payload)


class ListingFormSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw = request.query_params.get("dealType")
        if not raw:
            return Response(
                {"detail": "پارامتر dealType الزامی است."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lookup = {"pk": raw} if str(raw).isdigit() else {"name": raw}
        deal_type = DealType.objects.filter(**lookup).first()
        if deal_type is None:
            return Response(
                {"detail": "نوع معامله یافت نشد."}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(cached_listing_form_schema(deal_type.pk))


class SearchSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        property_type_raw = request.query_params.get("propertyType")
        deal_type_raw = request.query_params.get("dealType")

        property_type_pk = None
        deal_type_pk = None

        if property_type_raw:
            lookup = (
                {"pk": property_type_raw}
                if str(property_type_raw).isdigit()
                else {"name": property_type_raw}
            )
            property_type = PropertyType.objects.filter(**lookup).first()
            if property_type is None:
                return Response(
                    {"detail": "نوع ملک یافت نشد."}, status=status.HTTP_404_NOT_FOUND
                )
            property_type_pk = property_type.pk

        if deal_type_raw:
            lookup = (
                {"pk": deal_type_raw}
                if str(deal_type_raw).isdigit()
                else {"name": deal_type_raw}
            )
            deal_type = DealType.objects.filter(**lookup).first()
            if deal_type is None:
                return Response(
                    {"detail": "نوع معامله یافت نشد."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            deal_type_pk = deal_type.pk

        return Response(cached_search_schema(property_type_pk, deal_type_pk))


class BasicsCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(cached_basics_catalog())


class _GeographyViewSet(BasicsViewSet):
    def perform_create(self, serializer):
        model = serializer.Meta.model
        last = model.objects.order_by("-sort_order").values_list(
            "sort_order", flat=True
        ).first()
        next_order = (last or 0) + 1
        serializer.save(sort_order=next_order)


class ProvinceViewSet(_GeographyViewSet):
    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer

    def get_queryset(self):
        return super().get_queryset().order_by("-sort_order", "-id")

    def perform_destroy(self, instance):
        if instance.cities.filter(is_active=True).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "این استان دارای شهر فعال است؛ ابتدا شهرهای آن را حذف یا غیرفعال کنید."
            )
        instance.delete()


class CityViewSet(_GeographyViewSet):
    queryset = City.objects.select_related("province")
    serializer_class = CitySerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related("province")
        province = self.request.query_params.get("province")
        if province:
            if str(province).isdigit():
                queryset = queryset.filter(province_id=province)
            else:
                queryset = queryset.filter(province__name=province)
        return queryset.order_by("-sort_order", "-id")

    def perform_destroy(self, instance):
        if instance.districts.filter(is_active=True).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "این شهر دارای محله فعال است؛ ابتدا محله‌های آن را حذف یا غیرفعال کنید."
            )
        instance.delete()


class DistrictViewSet(_GeographyViewSet):
    queryset = District.objects.select_related("city", "city__province")
    serializer_class = DistrictSerializer

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "city", "city__province"
        )
        city = self.request.query_params.get("city")
        if city:
            if str(city).isdigit():
                queryset = queryset.filter(city_id=city)
            else:
                queryset = queryset.filter(city__name=city)
        province = self.request.query_params.get("province")
        if province:
            if str(province).isdigit():
                queryset = queryset.filter(city__province_id=province)
            else:
                queryset = queryset.filter(city__province__name=province)
        # Newest rows first so a freshly added neighbourhood appears at top.
        return queryset.order_by("-sort_order", "-id")

    def perform_destroy(self, instance):
        if instance.properties.exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"{instance.properties.count()} ملک در این محله ثبت شده است؛ "
                "ابتدا آن‌ها را به محله دیگری منتقل کنید."
            )
        instance.delete()


class LocationTreeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(cached_location_tree())
