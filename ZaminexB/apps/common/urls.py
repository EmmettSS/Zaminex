from django.urls import path

from apps.activity.views import ActivityLogListView, ActivityLogUserListView
from apps.analytics.views import (
    AIInsightView,
    AnalyticsDashboardView,
    ConsultantAnalyticsView,
    ConsultantDetailAnalyticsView,
    ListingAnalyticsView,
    PropertyAnalyticsView,
)
from apps.notifications.views import NotificationListView, NotificationMarkReadView
from .views import (
    CompanySettingsView,
    DistrictListView,
    DistrictManageView,
    GeocodeView,
    LoginStatsView,
    PasswordResetRequestView,
    AdminPasswordChangeView,
)

urlpatterns = [
    path("company-settings/", CompanySettingsView.as_view(), name="company-settings"),
    path("districts/", DistrictListView.as_view(), name="districts-list"),
    path("districts/manage/", DistrictManageView.as_view(), name="districts-manage"),
    path("districts/manage/<int:pk>/", DistrictManageView.as_view(), name="districts-manage-detail"),
    path("geocode/", GeocodeView.as_view(), name="geocode"),
    path("analytics/consultants/", ConsultantAnalyticsView.as_view(), name="analytics-consultants"),
    path("analytics/consultants/<int:pk>/", ConsultantDetailAnalyticsView.as_view(), name="analytics-consultant-detail"),
    path("analytics/properties/", PropertyAnalyticsView.as_view(), name="analytics-properties"),
    path("analytics/listings/", ListingAnalyticsView.as_view(), name="analytics-listings"),
    path("analytics/dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
    path("ai/<str:entity>/<int:pk>/", AIInsightView.as_view(), name="ai-insight"),
    path("activity-log/users/", ActivityLogUserListView.as_view(), name="activity-log-users"),
    path("activity-log/", ActivityLogListView.as_view(), name="activity-log"),
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path("notifications/<int:pk>/read/", NotificationMarkReadView.as_view(), name="notification-mark-read"),
    path("login-stats/", LoginStatsView.as_view(), name="login-stats"),
    path("password-reset-request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("admin-password-change/<int:user_id>/", AdminPasswordChangeView.as_view(), name="admin-password-change"),
]
