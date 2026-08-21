from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttributeViewSet,
    BasicsCatalogView,
    CityViewSet,
    DistrictViewSet,
    LocationTreeView,
    ProvinceViewSet,
    DealTypeAttributeViewSet,
    DealTypeViewSet,
    ListingFormSchemaView,
    PropertyFormSchemaView,
    PropertyTypeAttributeViewSet,
    PropertyTypeViewSet,
    PropertyUsageViewSet,
    SearchSchemaView,
)

app_name = "basics"

router = DefaultRouter()
router.register(r"property-usages", PropertyUsageViewSet, basename="property-usage")
router.register(r"property-types", PropertyTypeViewSet, basename="property-type")
router.register(r"deal-types", DealTypeViewSet, basename="deal-type")
router.register(r"attributes", AttributeViewSet, basename="attribute")
router.register(
    r"property-type-attributes",
    PropertyTypeAttributeViewSet,
    basename="property-type-attribute",
)
router.register(
    r"deal-type-attributes", DealTypeAttributeViewSet, basename="deal-type-attribute"
)
router.register(r"provinces", ProvinceViewSet, basename="province")
router.register(r"cities", CityViewSet, basename="city")
router.register(r"districts", DistrictViewSet, basename="district")

urlpatterns = [
    # Everything the dynamic forms need, in one call.
    path("catalog/", BasicsCatalogView.as_view(), name="catalog"),
    # Provinces + cities + districts in one call, for the cascading selects.
    path("locations/", LocationTreeView.as_view(), name="location-tree"),
    # Form / filter schemas.
    path(
        "schema/property-form/",
        PropertyFormSchemaView.as_view(),
        name="schema-property-form",
    ),
    path(
        "schema/listing-form/",
        ListingFormSchemaView.as_view(),
        name="schema-listing-form",
    ),
    path("schema/search/", SearchSchemaView.as_view(), name="schema-search"),
    path("", include(router.urls)),
]
