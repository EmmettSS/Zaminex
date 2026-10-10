from __future__ import annotations

from django.db import models
from django.db.models.signals import post_delete
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def active(self):
        return self.filter(deleted_at__isnull=True, is_active=True)

    def delete(self):
        now = timezone.now()
        listeners = post_delete.has_listeners(self.model)
        instances = list(self.filter(deleted_at__isnull=True)) if listeners else []
        updated = self.update(
            deleted_at=now,
            is_active=False,
            updated_at=now,
        )
        for instance in instances:
            instance.deleted_at = now
            instance.is_active = False
            post_delete.send(sender=self.model, instance=instance)
        return updated

    def hard_delete(self):
        return super().delete()


class AliveManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )

    def active(self):
        return self.get_queryset().filter(is_active=True)


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="تاریخ ایجاد"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="فعال")
    deleted_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="تاریخ حذف"
    )

    objects = AliveManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False, hard=False):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)

        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])


class ReferenceDataModel(SoftDeleteModel):
    name = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="کلید سیستمی",
        help_text="شناسه انگلیسی و ثابت (مانند apartment). پس از ایجاد تغییر نکند.",
    )
    display_name = models.CharField(max_length=255, verbose_name="نام نمایشی")
    sort_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="ترتیب نمایش",
    )
    meta_data = models.JSONField(default=dict, blank=True, verbose_name="متادیتا")

    class Meta:
        abstract = True
        ordering = ["sort_order", "display_name"]

    def __str__(self):
        return self.display_name or self.name

    @staticmethod
    def alive_name_unique(model_name: str) -> models.UniqueConstraint:
        return models.UniqueConstraint(
            fields=["name"],
            condition=models.Q(deleted_at__isnull=True),
            name=f"uq_{model_name}_name_alive",
        )
