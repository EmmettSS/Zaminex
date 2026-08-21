from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0010_aiinsightcache"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companysettings",
            name="ai_api_key",
            field=models.CharField(
                blank=True,
                help_text="برای سرویس‌های محلی/بدون احراز هویت می‌تواند خالی بماند. این کلید به‌صورت رمزنگاری‌شده ذخیره می‌شود.",
                max_length=1024,
                verbose_name="کلید API هوش مصنوعی",
            ),
        ),
    ]
