from django.contrib import admin
from django.urls import path, include
from apps.common.media import serve_media
from . import views 

admin.site.site_header = "مدیریت زمینکس"
admin.site.site_title = "مدیریت زمینکس"
admin.site.index_title = "مدیریت زمینکس"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("accounts/", include("apps.accounts.urls")),
    path("properties/", include("apps.properties.urls")),
    path("listings/", include("apps.listings.urls")),
    path("followupa/api/", include("apps.followups.urls")),
    path("tasks/api/", include("apps.tasks.urls")),
    path("common/api/", include("apps.common.urls")),
    path("basics/api/", include("apps.basics.urls")),
    path("", include("apps.reports.urls")),
    path("media/<path:path>", serve_media, name="protected-media"),
]
