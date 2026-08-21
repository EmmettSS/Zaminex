from django.contrib import admin
from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "status", "publish_channel", "priority", "is_featured")
    list_filter = ("status", "publish_channel", "priority", "is_featured")
    search_fields = ("title", "property__title")
