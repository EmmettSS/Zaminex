from django.apps import AppConfig


class BasicsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.basics"
    verbose_name = "اطلاعات پایه"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import views
        from .models import (
            Attribute,
            AttributeOption,
            City,
            DealType,
            DealTypeAttribute,
            DealTypeSearchAttribute,
            District,
            Province,
            PropertyType,
            PropertyTypeAttribute,
            PropertyTypeSearchAttribute,
            PropertyUsage,
        )

        for model in (
            PropertyUsage,
            PropertyType,
            PropertyTypeAttribute,
            PropertyTypeSearchAttribute,
            DealType,
            DealTypeAttribute,
            DealTypeSearchAttribute,
            Attribute,
            AttributeOption,
            Province,
            City,
            District,
        ):
            post_save.connect(
                views.invalidate_reference_caches,
                sender=model,
                dispatch_uid=f"phase5_{model.__name__}_save",
            )
            post_delete.connect(
                views.invalidate_reference_caches,
                sender=model,
                dispatch_uid=f"phase5_{model.__name__}_delete",
            )
