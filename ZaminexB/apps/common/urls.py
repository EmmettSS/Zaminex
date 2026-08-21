from django.urls import path

from .activity_views import ActivityLogListView
from .analytics_views import (
    AIInsightView,
    AnalyticsDashboardView,
    ConsultantAnalyticsView,
    ConsultantDetailAnalyticsView,
    ListingAnalyticsView,
    PropertyAnalyticsView,
)
from .views import (
    CompanySettingsView,
    DistrictListView,
    DistrictManageView,
    LoginStatsView,
    NotificationListView,
    NotificationMarkReadView,
    PasswordResetRequestView,
    AdminPasswordChangeView,
)

urlpatterns = [
    path("company-settings/", CompanySettingsView.as_view(), name="company-settings"),
    path("districts/", DistrictListView.as_view(), name="districts-list"),
    path("districts/manage/", DistrictManageView.as_view(), name="districts-manage"),
    path("districts/manage/<int:pk>/", DistrictManageView.as_view(), name="districts-manage-detail"),
    path("analytics/consultants/", ConsultantAnalyticsView.as_view(), name="analytics-consultants"),
    path("analytics/consultants/<int:pk>/", ConsultantDetailAnalyticsView.as_view(), name="analytics-consultant-detail"),
    path("analytics/properties/", PropertyAnalyticsView.as_view(), name="analytics-properties"),
    path("analytics/listings/", ListingAnalyticsView.as_view(), name="analytics-listings"),
    path("analytics/dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    path("ai/<str:entity>/<int:pk>/", AIInsightView.as_view(), name="ai-insight"),
    path("activity-log/", ActivityLogListView.as_view(), name="activity-log"),
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("login-stats/", LoginStatsView.as_view(), name="login-stats"),
    path("password-reset-request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("admin-password-change/<int:user_id>/", AdminPasswordChangeView.as_view(), name="admin-password-change"),
]
