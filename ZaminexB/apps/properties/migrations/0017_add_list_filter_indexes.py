from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("basics", "0004_attributecategory"),
        ("properties", "0016_fuzzy_search_trgm_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(
                fields=["-created_at"], name="idx_property_created_at"
            ),
        ),
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(
                fields=["status", "-created_at"], name="idx_property_status_created"
            ),
        ),
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(
                fields=["deal_type", "-created_at"], name="idx_property_deal_created"
            ),
        ),
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(
                fields=["property_type"], name="idx_property_type"
            ),
        ),
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(fields=["area"], name="idx_property_area"),
        ),
        AddIndexConcurrently(
            model_name="property",
            index=models.Index(fields=["price"], name="idx_property_price"),
        ),
    ]
