from django.db import models
from django.conf import settings
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "در انتظار انجام"
        IN_PROGRESS = "IN_PROGRESS", "در حال انجام"
        COMPLETED = "COMPLETED", "تکمیل‌شده"
        CANCELLED = "CANCELLED", "لغوشده"

    class Priority(models.TextChoices):
        LOW = "LOW", "اولویت کم"
        MEDIUM = "MEDIUM", "اولویت عادی"
        HIGH = "HIGH", "اولویت بالا"
        URGENT = "URGENT", "اولویت فوری"

    class TaskType(models.TextChoices):
        VIEWING = "VIEWING", "بازدید ملک"
        DOCUMENT = "DOCUMENT", "بررسی مدارک"
        NEGOTIATION = "NEGOTIATION", "مذاکره و نشست"
        FOLLOW_UP = "FOLLOW_UP", "پیگیری مستمر"
        ADMINISTRATIVE = "ADMINISTRATIVE", "امور اداری و دفتری"
        SITE_VISIT = "SITE_VISIT", "کارشناسی میدانی"
        CONTRACT = "CONTRACT", "عقد قرارداد"
        INSPECTION = "INSPECTION", "بازرسی فنی"

    title = models.CharField(
        max_length=255,
        help_text="Brief title of the task",
        verbose_name="عنوان وظیفه",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the task",
        verbose_name="توضیحات",
    )
    note = models.TextField(
        blank=True,
        default="",
        help_text="Free-form internal note added from the task detail modal",
        verbose_name="یادداشت",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت",
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        verbose_name="اولویت",
    )
    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
        default=TaskType.VIEWING,
        verbose_name="نوع وظیفه",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        limit_choices_to={"role": "AGENT"},
        help_text="Consultant assigned to this task",
        verbose_name="مسئول انجام",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
        help_text="Admin or consultant who created the task",
        verbose_name="ایجاد کننده",
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        help_text="Property related to this task (optional)",
        verbose_name="ملک مرتبط",
    )

    due_date = models.DateField(
        help_text="When the task should be completed",
        verbose_name="تاریخ سررسید",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task was marked completed",
        verbose_name="تاریخ تکمیل",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        verbose_name = "وظیفه"
        verbose_name_plural = "وظایف"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["due_date", "status"]),
        ]

    def __str__(self):
        return self.title

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def is_overdue(self):
        if self.status in {self.Status.COMPLETED, self.Status.CANCELLED}:
            return False
        if not self.due_date:
            return False
        return self.due_date < timezone.now().date()