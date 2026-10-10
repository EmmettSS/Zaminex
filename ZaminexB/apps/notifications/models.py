from django.conf import settings
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        PASSWORD_RESET_REQUEST = 'password_reset_request', 'درخواست تغییر رمز عبور'
        PASSWORD_CHANGED = 'password_changed', 'تغییر رمز عبور'
        TASK_ASSIGNED = 'task_assigned', 'وظیفه جدید'
        TASK_STATUS_CHANGED = 'task_status_changed', 'تغییر وضعیت وظیفه'
        FOLLOWUP_CREATED = 'followup_created', 'پیگیری جدید'
        PROPERTY_ASSIGNED = 'property_assigned', 'ملک جدید'
        LISTING_APPROVED = 'listing_approved', 'تایید آگهی'
        LISTING_REJECTED = 'listing_rejected', 'رد آگهی'
        TICKET_CREATED = 'ticket_created', 'تیکت جدید'
        TICKET_REPLY = 'ticket_reply', 'پاسخ جدید تیکت'
        TICKET_STATUS_CHANGED = 'ticket_status_changed', 'تغییر وضعیت تیکت'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="کاربر"
    )
    type = models.CharField(max_length=50, choices=NotificationType.choices, verbose_name="نوع اعلان")
    title = models.CharField(max_length=255, verbose_name="عنوان")
    message = models.TextField(verbose_name="متن پیام")
    is_read = models.BooleanField(default=False, verbose_name="خوانده شده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="جزئیات")

    class Meta:
        db_table = "common_notification"
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.title}"
