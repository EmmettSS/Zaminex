from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "listings"

router = DefaultRouter()
router.register(r'api/listings', views.ListingViewSet, basename='listing-api')

urlpatterns = [
    path("", views.listing_list, name="listing-list"),
    path("", include(router.urls)),
]
