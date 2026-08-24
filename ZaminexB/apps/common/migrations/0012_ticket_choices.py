from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0011_encrypt_ai_api_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activitylog",
            name="target_type",
            field=models.CharField(
                choices=[
                    ("property", "ملک"),
                    ("listing", "آگهی"),
                    ("task", "وظیفه"),
                    ("followup", "پیگیری"),
                    ("ticket", "تیکت"),
                    ("consultant", "مشاور"),
                    ("system", "سیستم"),
                ],
                db_index=True,
                max_length=20,
                verbose_name="نوع هدف",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("password_reset_request", "درخواست تغییر رمز عبور"),
                    ("password_changed", "تغییر رمز عبور"),
                    ("task_assigned", "وظیفه جدید"),
                    ("task_status_changed", "تغییر وضعیت وظیفه"),
                    ("followup_created", "پیگیری جدید"),
                    ("property_assigned", "ملک جدید"),
                    ("listing_approved", "تایید آگهی"),
                    ("listing_rejected", "رد آگهی"),
                    ("ticket_created", "تیکت جدید"),
                    ("ticket_reply", "پاسخ جدید تیکت"),
                    ("ticket_status_changed", "تغییر وضعیت تیکت"),
                ],
                max_length=50,
                verbose_name="نوع اعلان",
            ),
        ),
    ]
