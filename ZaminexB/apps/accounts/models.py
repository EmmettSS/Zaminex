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