from django.urls import path

from .views import (
    ConsultantScopeReportView,
    PropertyOptionsView,
    PropertyReportExportView,
    PropertyReportView,
)

app_name = "reports"

urlpatterns = [
    path(
        "api/reports/properties/<int:property_id>/export/",
        PropertyReportExportView.as_view(),
        name="property-report-export",
    ),
    path(
        "api/reports/properties/<int:property_id>/",
        PropertyReportView.as_view(),
        name="property-report",
    ),
    path(
        "api/reports/scope/",
        ConsultantScopeReportView.as_view(),
        name="consultant-scope-report",
    ),
    path(
        "api/reports/property-options/",
        PropertyOptionsView.as_view(),
        name="property-report-options",
    ),
]
