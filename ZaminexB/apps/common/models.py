from django.conf import settings
from django.db import models


class District(models.Model):
    """Geographical district/neighborhood for properties."""
    name = models.CharField(max_length=255, unique=True, verbose_name="نام منطقه / محله")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "منطقه / محله"
        verbose_name_plural = "مناطق و محله‌ها"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ActivityLog(models.Model):
    """Tracks user actions across the CRM for the activity feed."""

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


class CompanySettings(models.Model):
    company_name = models.CharField(max_length=255, verbose_name="نام شرکت")
    license_number = models.CharField(max_length=50, blank=True, verbose_name="شماره پروانه")
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    phone = models.CharField(max_length=50, blank=True, verbose_name="تلفن")
    address = models.TextField(blank=True, verbose_name="آدرس")
    # --- AI configuration ------------------------------------------------
    # These power the "توصیف هوش مصنوعی" sections. They are configured by the
    # admin in Django admin; the service reads them via get_solo().
    ai_enabled = models.BooleanField(
        default=False, verbose_name="فعال‌سازی هوش مصنوعی"
    )
    ai_api_base_url = models.CharField(
        max_length=500, blank=True,
        verbose_name="آدرس پایه API هوش مصنوعی",
        help_text="مثلاً https://api.openai.com/v1 (سازگار با قالب OpenAI chat/completions)",
    )
    ai_api_key = models.CharField(
        max_length=1024, blank=True,
        verbose_name="کلید API هوش مصنوعی",
        help_text="برای سرویس‌های محلی/بدون احراز هویت می‌تواند خالی بماند. این کلید به‌صورت رمزنگاری‌شده ذخیره می‌شود.",
    )
    ai_model = models.CharField(
        max_length=200,
        verbose_name="نام مدل",
        help_text="شناسه مدل سرویس‌دهنده الزامی است؛ مثلاً gpt-4o-mini، deepseek-chat، gemini-1.5-flash.",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "تنظیمات شرکت"
        verbose_name_plural = "تنظیمات شرکت"

    def __str__(self):
        return self.company_name

    @property
    def ai_api_key_plain(self) -> str:
        """Return the decrypted API key for runtime use."""
        from .crypto import decrypt_secret
        return decrypt_secret(self.ai_api_key)

    def set_ai_api_key(self, raw: str | None):
        from .crypto import encrypt_secret
        self.ai_api_key = encrypt_secret((raw or "").strip())

    def save(self, *args, **kwargs):
        # If a caller assigns a plaintext key (e.g. from Django admin),
        # encrypt it transparently on the way to the database.
        if self.ai_api_key and not self.ai_api_key.startswith("enc:v1:"):
            from .crypto import encrypt_secret
            self.ai_api_key = encrypt_secret(self.ai_api_key)
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        from apps.common.ai_url import UnsafeAIURL, assert_public_https_url

        super().clean()
        model_name = (self.ai_model or "").strip()
        if not model_name:
            raise ValidationError({"ai_model": "نام مدل هوش مصنوعی الزامی است."})
        self.ai_model = model_name
        base_url = (self.ai_api_base_url or "").strip()
        if base_url:
            try:
                self.ai_api_base_url = assert_public_https_url(base_url)
            except UnsafeAIURL as exc:
                raise ValidationError({"ai_api_base_url": str(exc)}) from exc

    DEFAULTS = {
        "company_name": "مشاور املاک زمینکس",
        "license_number": "3541/1402",
        "email": "admin@zaminex.ir",
        "phone": "011-3322-5500",
        "address": "مازندران، ساری، بلوار کشاورز، نبش خیابان فرهنگ، ساختمان زمینکس، طبقه دوم",
        "ai_enabled": False,
        "ai_api_base_url": "",
        "ai_api_key": "",
        "ai_model": "",
    }

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults=cls.DEFAULTS)
        return obj

    @classmethod
    @property
    def DistrictModel(cls):
        return District


class AIInsightCache(models.Model):
    """Persisted AI description, keyed by entity so workers cannot mix records.

    LocMemCache is per-process; without a shared store the same property is
    re-sent to the model on every request that hits a different worker, and a
    stale in-memory entry can be served for the wrong record. One row per
    (entity, entity_id) is the source of truth; the in-process cache is only a
    fast path in front of it.
    """

    entity = models.CharField(max_length=20, verbose_name="موجودیت")
    entity_id = models.PositiveIntegerField(verbose_name="شناسه")
    fingerprint = models.CharField(max_length=64, verbose_name="اثر انگشت داده")
    payload = models.JSONField(verbose_name="خروجی مدل")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "کش تحلیل هوش مصنوعی"
        verbose_name_plural = "کش تحلیل هوش مصنوعی"
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "entity_id"], name="uniq_ai_insight_entity"
            ),
        ]

    def __str__(self):
        return f"{self.entity}:{self.entity_id}"


class Notification(models.Model):
    """Notification system for user actions and system events."""
    
    class NotificationType(models.TextChoices):
        PASSWORD_RESET_REQUEST = 'password_reset_request', 'درخواست تغییر رمز عبور'
        PASSWORD_CHANGED = 'password_changed', 'تغییر رمز عبور'
        TASK_ASSIGNED = 'task_assigned', 'وظیفه جدید'
        TASK_STATUS_CHANGED = 'task_status_changed', 'تغییر وضعیت وظیفه'
        FOLLOWUP_CREATED = 'followup_created', 'پیگیری جدید'
        PROPERTY_ASSIGNED = 'property_assigned', 'ملک جدید'
        LISTING_APPROVED = 'listing_approved', 'تایید آگهی'
        LISTING_REJECTED = 'listing_rejected', 'رد آگهی'
    
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
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"