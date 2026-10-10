from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = "عمومی و سیستم"

    def ready(self):
        import apps.common.cache_invalidation
        from apps.common import checks
