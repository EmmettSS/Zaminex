# Generated manually for account-scoped login throttling and Persian-facing labels.

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_remove_admin_consultant_profiles"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(db_index=True, max_length=255, unique=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_failed_at", models.DateTimeField(blank=True, null=True)),
                ("last_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("last_user_agent", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "محدودیت ورود",
                "verbose_name_plural": "محدودیت‌های ورود",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AlterModelOptions(
            name="user",
            options={"verbose_name": "کاربر", "verbose_name_plural": "کاربران"},
        ),
        migrations.AlterModelOptions(
            name="consultantprofile",
            options={
                "ordering": ["full_name"],
                "verbose_name": "پروفایل مشاور",
                "verbose_name_plural": "پروفایل‌های مشاوران",
            },
        ),
        migrations.AlterModelOptions(
            name="adminprofile",
            options={
                "ordering": ["full_name"],
                "verbose_name": "پروفایل مدیر",
                "verbose_name_plural": "پروفایل‌های مدیران",
            },
        ),
        migrations.AlterField(
            model_name="consultantprofile",
            name="mobile",
            field=models.CharField(
                blank=True,
                max_length=11,
                null=True,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد.",
                        regex="^09\\d{9}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="adminprofile",
            name="mobile",
            field=models.CharField(
                blank=True,
                max_length=11,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد.",
                        regex="^09\\d{9}$",
                    )
                ],
            ),
        ),
    ]
