from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
import datetime


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    AGENT = "AGENT", "Agent"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.AGENT,
        db_index=True,
        verbose_name="نقش کاربری",
    )

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN

    @property
    def is_agent_role(self):
        return self.role == UserRole.AGENT


class LoginAttempt(models.Model):
    """Account-scoped failed login counter and temporary lock state."""

    username = models.CharField(max_length=255, unique=True, db_index=True, verbose_name="نام کاربری")
    failed_attempts = models.PositiveSmallIntegerField(default=0, verbose_name="تلاش‌های ناموفق")
    locked_until = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="قفل تا تاریخ")
    last_failed_at = models.DateTimeField(null=True, blank=True, verbose_name="آخرین تلاش ناموفق")
    last_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="آی‌پی")
    last_user_agent = models.CharField(max_length=255, blank=True, verbose_name="مرورگر")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "محدودیت ورود"
        verbose_name_plural = "محدودیت‌های ورود"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.username


class ConsultantProfile(models.Model):
    mobile_validator = RegexValidator(
        regex=r"^09\d{9}$",
        message="شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد.",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consultant_profile",
        verbose_name="حساب کاربری",
    )
    full_name = models.CharField(max_length=255, verbose_name="نام و نام خانوادگی")
    mobile = models.CharField(max_length=11, validators=[mobile_validator], unique=True, null=True, blank=True, verbose_name="شماره موبایل")
    branch = models.CharField(max_length=255, verbose_name="شعبه")
    profile_image = models.ImageField(upload_to="consultants/profile/", blank=True, null=True, verbose_name="تصویر پروفایل")
    hired_at = models.DateField(default=datetime.date.today, verbose_name="تاریخ استخدام")
    notes = models.TextField(blank=True, verbose_name="یادداشت‌ها")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "پروفایل مشاور"
        verbose_name_plural = "پروفایل‌های مشاوران"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class LoginMethod(models.TextChoices):
    PASSWORD = "password", "رمز عبور"
    SMS = "sms", "کد پیامکی"


class LoginSettings(models.Model):
    """Singleton: which login method the whole system uses right now.

    Edited by the admin from «پروفایل من → گزینه‌های ورود» (and also exposed in
    Django admin as a fallback surface). When ``method`` is ``sms`` the
    password form is rejected and vice versa, so the switch is always
    authoritative for the entire CRM.
    """

    method = models.CharField(
        max_length=20,
        choices=LoginMethod.choices,
        default=LoginMethod.PASSWORD,
        verbose_name="روش ورود",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "روش ورود"
        verbose_name_plural = "روش ورود"

    def __str__(self):
        return self.get_method_display()

    DEFAULTS = {"method": LoginMethod.PASSWORD}

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults=cls.DEFAULTS)
        return obj


class SmsProviderSettings(models.Model):
    """Singleton SMS gateway configuration.

    Credentials are entered exclusively through Django admin (never committed
    to the code base) and stored encrypted at rest, exactly like the AI API
    key on ``CompanySettings``. sms.ir is the primary provider and kavenegar
    is the automatic fallback.
    """

    # --- sms.ir (primary) -------------------------------------------------
    smsir_api_key = models.CharField(
        max_length=1024, blank=True, verbose_name="کلید API اسمس‌دات‌آی‌آر"
    )
    smsir_line_number = models.CharField(
        max_length=32,
        blank=True,
        verbose_name="شماره خط اسمس‌دات‌آی‌آر",
        help_text="اختیاری؛ فقط اگر سرویس‌دهنده نیاز دارد وارد شود.",
    )
    smsir_template_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="شناسه قالب (templateId)",
        help_text="قالب تأیید (verify) در پنل اسمس‌دات‌آی‌آر.",
    )

    # --- kavenegar (backup) ----------------------------------------------
    kavenegar_api_key = models.CharField(
        max_length=1024, blank=True, verbose_name="کلید API کاوه‌نگار"
    )
    kavenegar_sender = models.CharField(
        max_length=32,
        blank=True,
        default="20006535",
        verbose_name="شماره فرستنده کاوه‌نگار",
    )
    kavenegar_template_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="نام قالب احراز هویت کاوه‌نگار",
        help_text="اختیاری؛ اگر تنظیم شود کد از طریق قالب (lookup) ارسال می‌شود، وگرنه پیام متنی ساده.",
    )
    kavenegar_message = models.CharField(
        max_length=500,
        blank=True,
        default="کد ورود شما به زمینکس: {code}",
        verbose_name="متن پیام (در صورت نبود قالب)",
        help_text="متن سادهٔ پیامک؛ {code} با کد تأیید جایگزین می‌شود.",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "تنظیمات پیامک"
        verbose_name_plural = "تنظیمات پیامک"

    def __str__(self):
        return "تنظیمات سرویس پیامک"

    @property
    def smsir_api_key_plain(self) -> str:
        from apps.common.crypto import decrypt_secret

        return decrypt_secret(self.smsir_api_key)

    @property
    def kavenegar_api_key_plain(self) -> str:
        from apps.common.crypto import decrypt_secret

        return decrypt_secret(self.kavenegar_api_key)

    def save(self, *args, **kwargs):
        # If a caller assigns a plaintext key (e.g. from Django admin),
        # encrypt it transparently on the way to the database.
        from apps.common.crypto import encrypt_secret

        if self.smsir_api_key and not self.smsir_api_key.startswith("enc:v1:"):
            self.smsir_api_key = encrypt_secret(self.smsir_api_key)
        if self.kavenegar_api_key and not self.kavenegar_api_key.startswith("enc:v1:"):
            self.kavenegar_api_key = encrypt_secret(self.kavenegar_api_key)
        super().save(*args, **kwargs)

    DEFAULTS = {
        "smsir_api_key": "",
        "smsir_line_number": "",
        "smsir_template_id": "",
        "kavenegar_api_key": "",
        "kavenegar_sender": "20006535",
        "kavenegar_template_name": "",
        "kavenegar_message": "کد ورود شما به زمینکس: {code}",
    }

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults=cls.DEFAULTS)
        return obj


class SmsLoginCode(models.Model):
    """A single-use, expiring OTP issued for SMS login.

    The code itself is stored as a salted hash (Django ``make_password``), so a
    database leak never exposes usable codes. Rate limits and the expiry window
    are enforced in ``apps.accounts.sms``.
    """

    mobile = models.CharField(max_length=16, db_index=True, verbose_name="شماره موبایل")
    code_hash = models.CharField(max_length=255, verbose_name="کد (هش‌شده)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    expires_at = models.DateTimeField(db_index=True, verbose_name="انقضا")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="تلاش‌های ناموفق")
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ مصرف")

    class Meta:
        verbose_name = "کد ورود پیامکی"
        verbose_name_plural = "کدهای ورود پیامکی"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.mobile} ({self.created_at:%Y-%m-%d %H:%M})"


class AdminProfile(models.Model):
    """Profile for ADMIN users.

    Mirrors ConsultantProfile so the admin "My Profile" screen can reuse the
    exact same data shape/serializer as the consultant one, while keeping
    admin accounts completely separate from the consultant list.
    """

    mobile_validator = RegexValidator(
        regex=r"^09\d{9}$",
        message="شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد.",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_profile",
        verbose_name="حساب کاربری",
    )
    full_name = models.CharField(max_length=255, blank=True, verbose_name="نام و نام خانوادگی")
    mobile = models.CharField(max_length=11, validators=[mobile_validator], null=True, blank=True, verbose_name="شماره موبایل")
    branch = models.CharField(max_length=255, blank=True, default="شعبه مرکزی", verbose_name="شعبه")
    profile_image = models.ImageField(upload_to="admins/profile/", blank=True, null=True, verbose_name="تصویر پروفایل")
    hired_at = models.DateField(default=datetime.date.today, verbose_name="تاریخ استخدام")
    notes = models.TextField(blank=True, verbose_name="یادداشت‌ها")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "پروفایل مدیر"
        verbose_name_plural = "پروفایل‌های مدیران"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name or self.user.username