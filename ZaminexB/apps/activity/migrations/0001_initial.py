import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("common", "0013_remove_aiinsightcache"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="ActivityLog",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("action", models.CharField(choices=[("create", "ایجاد"), ("update", "بروزرسانی"), ("delete", "حذف"), ("archive", "بایگانی"), ("complete", "تکمیل"), ("status_change", "تغییر وضعیت"), ("approve", "تایید"), ("reject", "رد"), ("export", "خروجی")], db_index=True, max_length=20, verbose_name="عملیات")),
                        ("target_type", models.CharField(choices=[("property", "ملک"), ("listing", "آگهی"), ("task", "وظیفه"), ("followup", "پیگیری"), ("ticket", "تیکت"), ("consultant", "مشاور"), ("system", "سیستم")], db_index=True, max_length=20, verbose_name="نوع هدف")),
                        ("target_id", models.IntegerField(blank=True, null=True, verbose_name="شناسه هدف")),
                        ("description", models.CharField(max_length=500, verbose_name="توضیحات")),
                        ("metadata", models.JSONField(blank=True, default=dict, verbose_name="جزئیات")),
                        ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="تاریخ ایجاد")),
                        ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activity_logs", to=settings.AUTH_USER_MODEL, verbose_name="کاربر")),
                    ],
                    options={
                        "db_table": "common_activitylog",
                        "verbose_name": "لاگ فعالیت",
                        "verbose_name_plural": "لاگ\u200cهای فعالیت",
                        "ordering": ["-created_at"],
                        "indexes": [
                            models.Index(fields=["user", "-created_at"], name="common_acti_user_id_b871d5_idx"),
                            models.Index(fields=["target_type", "-created_at"], name="common_acti_target__f4408e_idx"),
                            models.Index(fields=["action", "-created_at"], name="common_acti_action_e166bf_idx"),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
