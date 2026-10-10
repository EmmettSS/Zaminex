import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("common", "0014_remove_activitylog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Notification",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("type", models.CharField(choices=[("password_reset_request", "درخواست تغییر رمز عبور"), ("password_changed", "تغییر رمز عبور"), ("task_assigned", "وظیفه جدید"), ("task_status_changed", "تغییر وضعیت وظیفه"), ("followup_created", "پیگیری جدید"), ("property_assigned", "ملک جدید"), ("listing_approved", "تایید آگهی"), ("listing_rejected", "رد آگهی"), ("ticket_created", "تیکت جدید"), ("ticket_reply", "پاسخ جدید تیکت"), ("ticket_status_changed", "تغییر وضعیت تیکت")], max_length=50, verbose_name="نوع اعلان")),
                        ("title", models.CharField(max_length=255, verbose_name="عنوان")),
                        ("message", models.TextField(verbose_name="متن پیام")),
                        ("is_read", models.BooleanField(default=False, verbose_name="خوانده شده")),
                        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")),
                        ("metadata", models.JSONField(blank=True, default=dict, verbose_name="جزئیات")),
                        ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL, verbose_name="کاربر")),
                    ],
                    options={
                        "db_table": "common_notification",
                        "verbose_name": "اعلان",
                        "verbose_name_plural": "اعلان\u200cها",
                        "ordering": ["-created_at"],
                        "indexes": [
                            models.Index(fields=["user", "-created_at"], name="common_noti_user_id_053883_idx"),
                            models.Index(fields=["user", "is_read"], name="common_noti_user_id_aae5b0_idx"),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
