from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'target_type', 'description', 'created_at']
    list_filter = ['action', 'target_type', 'created_at']
    search_fields = ['description', 'user__username']
    ordering = ['-created_at']
