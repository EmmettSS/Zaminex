from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class FollowUpType(models.TextChoices):
    CALL = "Call", "Call"
    MEETING = "Meeting", "Meeting"
    EMAIL = "Email", "Email"
    SITE_VISIT = "Site Visit", "Site Visit"


class FollowUpStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"


class FollowUpQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def archived(self):
        return self.filter(is_archived=True)

    def scheduled(self):
        return self.filter(status=FollowUpStatus.SCHEDULED, is_archived=False)

    def completed(self):
        return self.filter(status=FollowUpStatus.COMPLETED, is_archived=False)

    def overdue(self):
        return self.filter(
            status=FollowUpStatus.SCHEDULED,
            is_archived=False,
            scheduled_at__lt=timezone.now(),
        )


class FollowUp(models.Model):
    title = models.CharField(max_length=255, verbose_name="عنوان")
    follow_up_type = models.CharField(
        max_length=20,
        choices=FollowUpType.choices,
        default=FollowUpType.CALL,
        verbose_name="نوع پیگیری",
    )
    contact_name = models.CharField(max_length=255, verbose_name="نام مشتری / مخاطب")
    scheduled_at = models.DateTimeField(default=timezone.now, verbose_name="تاریخ و زمان سررسید")

    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="followups",
        limit_choices_to={"role": "AGENT"},
        verbose_name="مشاور",
    )
    consultant_name = models.CharField(max_length=255, blank=True, verbose_name="نام مشاور")

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        related_name="followups",
        blank=True,
        null=True,
        verbose_name="ملک",
    )
    property_title = models.CharField(max_length=255, blank=True, null=True, verbose_name="عنوان ملک")

    notes = models.TextField(blank=True, null=True, verbose_name="یادداشت‌ها")
    outcome = models.TextField(blank=True, null=True, verbose_name="نتیجه")
    status = models.CharField(
        max_length=20,
        choices=FollowUpStatus.choices,
        default=FollowUpStatus.SCHEDULED,
        verbose_name="وضعیت",
    )
    probability = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Probability of closing from 0 to 100",
        verbose_name="احتمال موفقیت",
    )

    is_archived = models.BooleanField(default=False, verbose_name="بایگانی شده")
    archived_at = models.DateTimeField(blank=True, null=True, verbose_name="تاریخ بایگانی")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    objects = FollowUpQuerySet.as_manager()

    class Meta:
        verbose_name = "پیگیری"
        verbose_name_plural = "پیگیری‌ها"
        # Newest activity first: most recently created or edited first, with
        # the creation time as the tie-breaker.
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["consultant", "status"]),
            models.Index(fields=["property"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["is_archived"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.follow_up_type}]"

    def save(self, *args, **kwargs):
        if self.consultant:
            self.consultant_name = (self.consultant.get_full_name() or self.consultant.username)
        else:
            self.consultant_name = ""
        if self.property:
            self.property_title = self.property.title
        else:
            self.property_title = None
        super().save(*args, **kwargs)

    def is_overdue(self):
        if self.is_archived or self.status != FollowUpStatus.SCHEDULED:
            return False
        if not self.scheduled_at:
            return False
        return self.scheduled_at < timezone.now()

    def archive(self):
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.save(update_fields=["is_archived", "archived_at", "updated_at"])

    def unarchive(self):
        if self.is_archived:
            self.is_archived = False
            self.archived_at = None
            self.save(update_fields=["is_archived", "archived_at", "updated_at"])
