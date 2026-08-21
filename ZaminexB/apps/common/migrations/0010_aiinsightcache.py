from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0009_require_companysettings_ai_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIInsightCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entity", models.CharField(max_length=20, verbose_name="موجودیت")),
                ("entity_id", models.PositiveIntegerField(verbose_name="شناسه")),
                ("fingerprint", models.CharField(max_length=64, verbose_name="اثر انگشت داده")),
                ("payload", models.JSONField(verbose_name="خروجی مدل")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")),
            ],
            options={
                "verbose_name": "کش تحلیل هوش مصنوعی",
                "verbose_name_plural": "کش تحلیل هوش مصنوعی",
            },
        ),
        migrations.AddConstraint(
            model_name="aiinsightcache",
            constraint=models.UniqueConstraint(
                fields=("entity", "entity_id"), name="uniq_ai_insight_entity"
            ),
        ),
    ]
