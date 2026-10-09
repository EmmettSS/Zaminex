from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter

from .views import (
    AdminProfileViewSet,
    ConsultantProfileViewSet,
    CustomLoginView,
    LoginOptionsView,
    SmsLoginRequestView,
    SmsLoginVerifyView,
)

app_name = "accounts"

router = DefaultRouter()
router.register(r"consultants", ConsultantProfileViewSet, basename="consultant")
router.register(r"admins", AdminProfileViewSet, basename="admin-profile")

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("login-options/", LoginOptionsView.as_view(), name="login-options"),
    path("sms-login/request/", SmsLoginRequestView.as_view(), name="sms-login-request"),
    path("sms-login/verify/", SmsLoginVerifyView.as_view(), name="sms-login-verify"),
    path("", include(router.urls)),
]
