"""Shared model building blocks for the reference-data ("basics") tables.

The client's PostgreSQL schema gives every lookup table the same shape:

    name          VARCHAR UNIQUE   -- immutable system key (english)
    display_name  VARCHAR          -- label shown in the UI (persian)
    sort_order    DECIMAL(10,2)    -- manual ordering
    meta_data     JSONB            -- open-ended extension point
    is_active     BOOLEAN
    deleted_at    TIMESTAMP NULL   -- soft delete
    created_at / updated_at

Their SQL enforces the behaviour with PostgreSQL triggers
(``update_updated_at_column``, ``set_status_inactive_on_delete``). We implement
the same rules in Python instead:

* ``updated_at`` → Django's ``auto_now``
* "deleting sets the row inactive" → :meth:`SoftDeleteModel.delete`

Keeping the logic in the ORM means it is visible in code review, covered by the
test suite, and portable across backends — triggers are invisible to Django and
silently bypassed by ``bulk_create`` / ``update``.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """Queryset helpers shared by every soft-deletable model."""

    def alive(self):
        """Rows that have not been soft-deleted."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Rows that have been soft-deleted."""
        return self.filter(deleted_at__isnull=False)

    def active(self):
        """Rows that are both alive and switched on — the usual public list."""
        return self.filter(deleted_at__isnull=True, is_active=True)

    def delete(self):
        """Soft-delete the whole queryset in a single UPDATE."""
        return self.update(
            deleted_at=timezone.now(),
            is_active=False,
            updated_at=timezone.now(),
        )

    def hard_delete(self):
        """Permanently remove the rows (escape hatch, mainly for tests)."""
        return super().delete()


class AliveManager(models.Manager):
    """Default manager: hides soft-deleted rows.

    ``Model.objects`` therefore behaves like the table only ever contained live
    rows, which is what nearly all application code wants. Use
    ``Model.all_objects`` to reach soft-deleted records (admin, audit, restore).
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )

    def active(self):
        return self.get_queryset().filter(is_active=True)


class AllObjectsManager(models.Manager):
    """Unfiltered manager, including soft-deleted rows."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class TimeStampedModel(models.Model):
    """``created_at`` / ``updated_at`` maintained by Django, not by triggers."""

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="تاریخ ایجاد"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Adds ``is_active`` + ``deleted_at`` with matching delete semantics.

    Reference data is referenced by historical records, so rows must never be
    physically removed: deleting a property type that older properties point at
    would either fail on the foreign key or corrupt the history. Soft deletion
    hides the row from new entries while leaving existing data readable.
    """

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
        """Soft-delete by default.

        Mirrors the client's ``set_status_inactive_on_delete`` trigger: a
        deleted row is always inactive, so it can never resurface in a
        "list the active options" query.

        Pass ``hard=True`` to remove the row for good.
        """
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)

        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active", "updated_at"])
        return (1, {self._meta.label: 1})

    def restore(self):
        """Bring a soft-deleted row back.

        ``is_active`` is intentionally left off: restoring makes the row exist
        again, an operator still decides whether it should be selectable.
        """
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])


class ReferenceDataModel(SoftDeleteModel):
    """Base class for the lookup tables managed under "اطلاعات پایه".

    ``name`` is the stable system key used by code and integrations; it must not
    change once rows reference it. ``display_name`` is the Persian label and is
    free to be edited at any time.
    """

    # Deliberately not `unique=True`. A plain unique index would count
    # soft-deleted rows, so deleting "apartment" and re-creating it later would
    # fail on a row the user can no longer see. Each concrete model instead
    # declares a UniqueConstraint limited to live rows (see `alive_name_unique`).
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
        """Unique `name`, but only among rows that are not soft-deleted."""
        return models.UniqueConstraint(
            fields=["name"],
            condition=models.Q(deleted_at__isnull=True),
            name=f"uq_{model_name}_name_alive",
        )
