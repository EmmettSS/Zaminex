"""API for the reference data and the dynamic form schemas.

Two groups of endpoints:

* **Management** (`/basics/api/...`) — CRUD over usages, property types, deal
  types, attributes and their bindings. Reading is open to any authenticated
  user (the property form needs the catalogue); writing is admin-only.

* **Schema** (`/basics/api/schema/...`) — the payload that drives the dynamic
  "افزودن ملک" / "ساخت آگهی" forms and the search filters.
"""

from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole

from .models import (
    Attribute,
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
    """Everyone signed in may read; only admins may modify.

    Consultants need the catalogue to fill in the property form, but the
    catalogue itself is administrator-owned.
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    message = "فقط مدیر می‌تواند اطلاعات پایه را ویرایش کند."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in self.SAFE_METHODS:
            return True
        return getattr(request.user, "role", "") == UserRole.ADMIN


class BasicsViewSet(viewsets.ModelViewSet):
    """Shared behaviour for the reference-data endpoints."""

    permission_classes = [ReadAnyWriteAdmin]

    def get_queryset(self):
        """Hide deactivated rows from *lists* unless the caller asks for them.

        The property form only ever wants active options; the management screen
        passes ``?all=1`` to show everything so an administrator can reactivate
        something.

        The filter is limited to list responses on purpose. Applying it to
        detail routes as well would make a deactivated row unreachable by its
        own id, so the management screen could switch something off and then be
        unable to delete or reactivate it.
        """
        queryset = self.queryset
        if self.action == "list" and self.request.query_params.get("all") not in {
            "1",
            "true",
            "yes",
        }:
            queryset = queryset.filter(is_active=True)
        return queryset

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Bring back a soft-deleted row."""
        instance = self.queryset.model.all_objects.filter(pk=pk).first()
        if instance is None:
            return Response({"detail": "مورد یافت نشد."}, status=status.HTTP_404_NOT_FOUND)
        instance.restore()
        return Response(self.get_serializer(instance).data)


class PropertyUsageViewSet(BasicsViewSet):
    queryset = PropertyUsage.objects.all()
    serializer_class = PropertyUsageSerializer

    def perform_destroy(self, instance):
        """Refuse to remove a usage that still has property types."""
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
            # Accept either the numeric id or the system key.
            if str(usage).isdigit():
                queryset = queryset.filter(property_usage_id=usage)
            else:
                queryset = queryset.filter(property_usage__name=usage)
        return queryset

    @action(detail=True, methods=["get"], url_path="attributes")
    def attributes(self, request, pk=None):
        """Attribute bindings for this property type (management view)."""
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
        """Core attributes are wired to real columns and cannot be removed."""
        if instance.is_core:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "ویژگی‌های ثابت به ستون‌های پایگاه داده متصل هستند و قابل حذف نیستند."
            )
        instance.delete()

    @action(detail=True, methods=["get", "post"], url_path="options")
    def options(self, request, pk=None):
        """List or add the choices of a select/multiselect attribute."""
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
        """Remove one choice from a select/multiselect attribute.

        Refused while a stored value still uses it: deleting the option would
        leave those records pointing at a key that no longer resolves to a
        label, so they would render as a raw system key.
        """
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
    """Keep list/search filters in step with form bindings.

    Binding an attribute to a type is what the admin screen does. The
    property list reads a *separate* search-binding table, so a newly
    attached field would otherwise never appear as a filter. Attributes
    marked «بدون فیلتر» stay off the bar on purpose.
    """
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
    """Bind attributes to property types (which fields the form shows)."""

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
        """Persist a drag-and-drop reordering in one round trip."""
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

        for item in payload:
            link_id = item.get("id")
            sort_order = item.get("sortOrder", item.get("sort_order"))
            if link_id is None or sort_order is None:
                continue
            PropertyTypeAttribute.objects.filter(pk=link_id).update(sort_order=sort_order)

        return Response({"detail": "ترتیب ذخیره شد."})


class DealTypeAttributeViewSet(viewsets.ModelViewSet):
    """Bind attributes to deal types (which fields the listing form shows)."""

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


# ---------------------------------------------------------------------------
#  Form schema
# ---------------------------------------------------------------------------

def _active_links(manager):
    """Active bindings, with everything the serializer touches prefetched."""
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


class PropertyFormSchemaView(APIView):
    """Fields the "افزودن ملک" form should render for a property type.

    ``GET /basics/api/schema/property-form/?propertyType=<id|name>``

    Core attributes are returned alongside dynamic ones so the frontend can
    render one ordered form; ``isCore`` tells it whether the value belongs in a
    model column or in the attribute-values payload.
    """

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

        links = _active_links(property_type.attribute_links)
        fields = FormFieldSerializer(links, many=True).data

        return Response(
            {
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
                # Split out so the form can group facilities into a checkbox
                # block without re-deriving the grouping client-side.
                "fields": [f for f in fields if not f["isFacility"]],
                "facilities": [f for f in fields if f["isFacility"]],
            }
        )


class ListingFormSchemaView(APIView):
    """Fields the "ساخت آگهی" form should render for a deal type.

    ``GET /basics/api/schema/listing-form/?dealType=<id|name>``
    """

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

        links = _active_links(deal_type.attribute_links)
        fields = FormFieldSerializer(links, many=True).data

        return Response(
            {
                "dealType": {
                    "id": deal_type.id,
                    "name": deal_type.name,
                    "displayName": deal_type.display_name,
                },
                "fields": [f for f in fields if not f["isFacility"]],
                "facilities": [f for f in fields if f["isFacility"]],
            }
        )


class SearchSchemaView(APIView):
    """Filters the search bar should offer.

    ``GET /basics/api/schema/search/?propertyType=<id|name>``
    ``GET /basics/api/schema/search/?dealType=<id|name>``

    With neither parameter it returns the filters shared by every type, which
    is what the unfiltered listing page needs.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        property_type_raw = request.query_params.get("propertyType")
        deal_type_raw = request.query_params.get("dealType")

        property_filters = []
        deal_filters = []

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
            property_filters = SearchFilterSerializer(
                _active_links(property_type.search_attribute_links), many=True
            ).data

        if deal_type_raw:
            lookup = (
                {"pk": deal_type_raw}
                if str(deal_type_raw).isdigit()
                else {"name": deal_type_raw}
            )
            deal_type = DealType.objects.filter(**lookup).first()
            if deal_type is None:
                return Response(
                    {"detail": "نوع معامله یافت نشد."}, status=status.HTTP_404_NOT_FOUND
                )
            deal_filters = SearchFilterSerializer(
                _active_links(deal_type.search_attribute_links), many=True
            ).data

        return Response(
            {"propertyFilters": property_filters, "dealFilters": deal_filters}
        )


class BasicsCatalogView(APIView):
    """The whole catalogue in one request.

    The property form needs usages, types and deal types together; fetching
    them separately would mean three round trips before the first field can be
    drawn.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        usages = PropertyUsage.objects.filter(is_active=True)
        types = PropertyType.objects.filter(is_active=True).select_related("property_usage")
        deals = DealType.objects.filter(is_active=True)

        return Response(
            {
                "usages": PropertyUsageSerializer(usages, many=True).data,
                "propertyTypes": PropertyTypeSerializer(types, many=True).data,
                "dealTypes": DealTypeSerializer(deals, many=True).data,
            }
        )


# ---------------------------------------------------------------------------
#  Geography: Province → City → District
# ---------------------------------------------------------------------------

class _GeographyViewSet(BasicsViewSet):
    """Shared behaviour for the Province/City/District admin endpoints.

    New rows are created with a ``sort_order`` greater than every existing row
    so that freshly added items appear at the top of the management list (the
    model's default ordering is ``sort_order`` first). This keeps the "add and
    see it immediately" workflow working without requiring manual reordering.
    """

    def perform_create(self, serializer):
        model = serializer.Meta.model
        last = model.objects.order_by("-sort_order").values_list(
            "sort_order", flat=True
        ).first()
        next_order = (last or 0) + 1
        serializer.save(sort_order=next_order)


class ProvinceViewSet(_GeographyViewSet):
    """Provinces. Administrator-managed; nothing is seeded."""

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
    """Cities, filterable by province for the cascading selects."""

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
        # Newest rows first within each province so the just-added city shows
        # up at the top of the list and the parent dropdown.
        return queryset.order_by("-sort_order", "-id")

    def perform_destroy(self, instance):
        if instance.districts.filter(is_active=True).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                "این شهر دارای محله فعال است؛ ابتدا محله‌های آن را حذف یا غیرفعال کنید."
            )
        instance.delete()


class DistrictViewSet(_GeographyViewSet):
    """Districts, filterable by city (and by province, for convenience)."""

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
        """Refuse to remove a district that properties still point at.

        Property.district is PROTECT, so the delete would fail at the database
        level anyway; catching it here returns a message the UI can show.
        """
        if instance.properties.exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError(
                f"{instance.properties.count()} ملک در این محله ثبت شده است؛ "
                "ابتدا آن‌ها را به محله دیگری منتقل کنید."
            )
        instance.delete()


class LocationTreeView(APIView):
    """The whole geography in one call, for cascading selects.

    Returns provinces, each with its cities, each with its districts. One
    request is enough to populate all three dropdowns, which matters because the
    property form needs them before the first field can be drawn.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
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

        return Response(
            [
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
        )
