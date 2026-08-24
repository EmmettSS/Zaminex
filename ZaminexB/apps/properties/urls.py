from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "properties"

router = DefaultRouter()
router.register(r"", views.PropertyViewSet, basename="api-properties")

urlpatterns = [
    path("", views.property_list, name="property-list"),
    path("add/", views.property_create_view, name="property-create"),
    path("<int:pk>/", views.property_detail, name="property-detail"),
    path("<int:pk>/edit/", views.property_edit_view, name="property-update"),
    path("<int:pk>/archive/", views.property_archive, name="property-archive"),
    path("<int:pk>/images/", views.property_image_manage, name="property-image-manage"),

    path("api/properties/", include(router.urls)),
]
