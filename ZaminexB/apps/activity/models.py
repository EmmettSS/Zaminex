from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    class ActionType(models.TextChoices):
        CREATE = "create", "ایجاد"
        UPDATE = "update", "بروزرسانی"
        DELETE = "delete", "حذف"
        ARCHIVE = "archive", "بایگانی"
        COMPLETE = "complete", "تکمیل"
        STATUS_CHANGE = "status_change", "تغییر وضعیت"
        APPROVE = "approve", "تایید"
        REJECT = "reject", "رد"
        EXPORT = "export", "خروجی"

    class TargetType(models.TextChoices):
        PROPERTY = "property", "ملک"
        LISTING = "listing", "آگهی"
        TASK = "task", "وظیفه"
        FOLLOWUP = "followup", "پیگیری"
        TICKET = "ticket", "تیکت"
        CONSULTANT = "consultant", "مشاور"
        SYSTEM = "system", "سیستم"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        verbose_name="کاربر",
    )
    action = models.CharField(max_length=20, choices=ActionType.choices, db_index=True, verbose_name="عملیات")
    target_type = models.CharField(max_length=20, choices=TargetType.choices, db_index=True, verbose_name="نوع هدف")
    target_id = models.IntegerField(null=True, blank=True, verbose_name="شناسه هدف")
    description = models.CharField(max_length=500, verbose_name="توضیحات")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="جزئیات")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = "common_activitylog"
        verbose_name = "لاگ فعالیت"
        verbose_name_plural = "لاگ‌های فعالیت"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["target_type", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        user_name = (
            (self.user.get_full_name().strip() or self.user.username)
            if self.user
            else "سیستم"
        )
        return f"[{self.get_action_display()}] {user_name}: {self.description}"
