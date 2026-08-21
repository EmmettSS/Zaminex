"""
Automatic activity logging via Django signals.

Logs are created when key models are created, updated, or deleted.
"""
from functools import wraps

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .activity import log_activity


def skip_on_raw(handler):
    """Ignore signals fired while loading fixtures.

    ``loaddata`` sends save signals with ``raw=True``. Without this guard a
    ``manage.py loaddata`` run would fabricate a brand-new activity entry for
    every restored row, polluting the feed with events that never happened —
    and it would do so with the *current* timestamp, not the original one.

    Applies to every handler in this module so restoring a backup or seeding a
    fresh database reproduces the source data byte for byte.
    """

    @wraps(handler)
    def wrapper(sender, instance, *args, **kwargs):
        if kwargs.get("raw", False):
            return None
        return handler(sender, instance, *args, **kwargs)

    return wrapper


# =============================================================================
#  Property signals
# =============================================================================

@receiver(pre_save, sender="properties.Property")
@skip_on_raw
def cache_old_property_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender="properties.Property")
@skip_on_raw
def log_property_save(sender, instance, created, **kwargs):
    if created:
        log_activity(
            user=instance.consultant,
            action="create",
            target_type="property",
            target_id=instance.pk,
            description=f"ملک «{instance.title}» (کد {instance.internal_code}) ایجاد شد",
            metadata={"internal_code": instance.internal_code, "title": instance.title},
        )
    else:
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            action = "archive" if instance.status == "INACTIVE" else "status_change"
            log_activity(
                user=instance.consultant,
                action=action,
                target_type="property",
                target_id=instance.pk,
                description=f"وضعیت ملک «{instance.title}» از {old_status} به {instance.status} تغییر کرد",
                metadata={"old_status": old_status, "new_status": instance.status},
            )
        else:
            log_activity(
                user=instance.consultant,
                action="update",
                target_type="property",
                target_id=instance.pk,
                description=f"ملک «{instance.title}» (کد {instance.internal_code}) ویرایش شد",
                metadata={"internal_code": instance.internal_code, "title": instance.title},
            )


@receiver(post_delete, sender="properties.Property")
@skip_on_raw
def log_property_delete(sender, instance, **kwargs):
    log_activity(
        user=instance.consultant,
        action="delete",
        target_type="property",
        target_id=instance.pk,
        description=f"ملک «{instance.title}» حذف شد",
    )


# =============================================================================
#  Listing signals
# =============================================================================

@receiver(pre_save, sender="listings.Listing")
@skip_on_raw
def cache_old_listing_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_listing_status = old.status
        except sender.DoesNotExist:
            instance._old_listing_status = None


@receiver(post_save, sender="listings.Listing")
@skip_on_raw
def log_listing_save(sender, instance, created, **kwargs):
    if created:
        log_activity(
            user=instance.created_by,
            action="create",
            target_type="listing",
            target_id=instance.pk,
            description=f"آگهی «{instance.title}» ایجاد شد",
            metadata={"title": instance.title, "channel": instance.publish_channel},
        )
    else:
        old_status = getattr(instance, "_old_listing_status", None)
        if old_status and old_status != instance.status:
            action_map = {
                "ACTIVE": "approve",
                "DRAFT": "reject",
                "PAUSED": "update",
                "SOLD": "complete",
                "ARCHIVED": "archive",
                "EXPIRED": "archive",
            }
            action = action_map.get(instance.status, "status_change")
            log_activity(
                user=instance.created_by,
                action=action,
                target_type="listing",
                target_id=instance.pk,
                description=f"وضعیت آگهی «{instance.title}» به {instance.get_status_display()} تغییر کرد",
                metadata={"old_status": old_status, "new_status": instance.status},
            )
        else:
            log_activity(
                user=instance.created_by,
                action="update",
                target_type="listing",
                target_id=instance.pk,
                description=f"آگهی «{instance.title}» ویرایش شد",
                metadata={"title": instance.title},
            )


@receiver(post_delete, sender="listings.Listing")
@skip_on_raw
def log_listing_delete(sender, instance, **kwargs):
    log_activity(
        user=instance.created_by,
        action="delete",
        target_type="listing",
        target_id=instance.pk,
        description=f"آگهی «{instance.title}» حذف شد",
    )


# =============================================================================
#  Task signals
# =============================================================================

@receiver(pre_save, sender="tasks.Task")
@skip_on_raw
def cache_old_task_snapshot(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            from apps.tasks.history import snapshot_task

            instance._task_snapshot = snapshot_task(old)
        except sender.DoesNotExist:
            instance._task_snapshot = None
    else:
        instance._task_snapshot = None


@receiver(post_save, sender="tasks.Task")
@skip_on_raw
def log_task_save(sender, instance, created, **kwargs):
    from apps.tasks.history import (
        build_description,
        classify_task_event,
        diff_task,
        snapshot_task,
    )

    if created:
        log_activity(
            user=instance.created_by,
            action="create",
            target_type="task",
            target_id=instance.pk,
            description=build_description(instance.title, "create", "ایجاد وظیفه", []),
            metadata={
                "title": instance.title,
                "assigned_to": instance.assigned_to_id,
                "event_title": "ایجاد وظیفه",
                "changes": [],
            },
        )
        return

    old = getattr(instance, "_task_snapshot", None)
    if not old:
        return
    changes = diff_task(old, snapshot_task(instance))
    if not changes:
        return
    action, event_title = classify_task_event(changes)
    log_activity(
        user=None,
        action=action,
        target_type="task",
        target_id=instance.pk,
        description=build_description(instance.title, action, event_title, changes),
        metadata={
            "title": instance.title,
            "event_title": event_title,
            "changes": changes,
        },
    )


@receiver(post_delete, sender="tasks.Task")
@skip_on_raw
def log_task_delete(sender, instance, **kwargs):
    log_activity(
        user=instance.created_by,
        action="delete",
        target_type="task",
        target_id=instance.pk,
        description=f"وظیفه «{instance.title}» حذف شد",
    )


# =============================================================================
#  FollowUp signals
# =============================================================================

@receiver(pre_save, sender="followups.FollowUp")
@skip_on_raw
def cache_old_followup_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_fu_status = old.status
            instance._old_fu_archived = old.is_archived
        except sender.DoesNotExist:
            instance._old_fu_status = None
            instance._old_fu_archived = None


@receiver(post_save, sender="followups.FollowUp")
@skip_on_raw
def log_followup_save(sender, instance, created, **kwargs):
    if created:
        log_activity(
            user=instance.consultant,
            action="create",
            target_type="followup",
            target_id=instance.pk,
            description=f"پیگیری «{instance.title}» برای {instance.contact_name} ایجاد شد",
            metadata={"title": instance.title, "type": instance.follow_up_type},
        )
    else:
        old_status = getattr(instance, "_old_fu_status", None)
        old_archive = getattr(instance, "_old_fu_archived", None)
        if old_status and old_status != instance.status:
            if instance.status == "completed":
                log_activity(
                    user=instance.consultant,
                    action="complete",
                    target_type="followup",
                    target_id=instance.pk,
                    description=f"پیگیری «{instance.title}» تکمیل شد",
                )
            else:
                log_activity(
                    user=instance.consultant,
                    action="update",
                    target_type="followup",
                    target_id=instance.pk,
                    description=f"پیگیری «{instance.title}» برای {instance.contact_name} ویرایش شد",
                    metadata={"title": instance.title},
                )
        elif old_archive is not None and old_archive != instance.is_archived:
            if instance.is_archived:
                log_activity(
                    user=instance.consultant,
                    action="archive",
                    target_type="followup",
                    target_id=instance.pk,
                    description=f"پیگیری «{instance.title}» بایگانی شد",
                )
        else:
            log_activity(
                user=instance.consultant,
                action="update",
                target_type="followup",
                target_id=instance.pk,
                description=f"پیگیری «{instance.title}» برای {instance.contact_name} ویرایش شد",
                metadata={"title": instance.title},
            )


@receiver(post_delete, sender="followups.FollowUp")
@skip_on_raw
def log_followup_delete(sender, instance, **kwargs):
    log_activity(
        user=instance.consultant,
        action="delete",
        target_type="followup",
        target_id=instance.pk,
        description=f"پیگیری «{instance.title}» حذف شد",
    )


# =============================================================================
#  ConsultantProfile signals
# =============================================================================

@receiver(pre_save, sender="accounts.ConsultantProfile")
@skip_on_raw
def cache_old_consultant_active(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_cp_active = old.is_active
        except sender.DoesNotExist:
            instance._old_cp_active = None


@receiver(post_save, sender="accounts.ConsultantProfile")
@skip_on_raw
def log_consultant_save(sender, instance, created, **kwargs):
    if created:
        log_activity(
            user=instance.user,
            action="create",
            target_type="consultant",
            target_id=instance.pk,
            description=f"مشاور «{instance.full_name}» به سیستم اضافه شد",
            metadata={"full_name": instance.full_name, "branch": instance.branch},
        )
    else:
        old_active = getattr(instance, "_old_cp_active", None)
        if old_active is not None and old_active != instance.is_active:
            action = "archive" if not instance.is_active else "update"
            status_text = "غیرفعال" if not instance.is_active else "فعال"
            log_activity(
                user=instance.user,
                action=action,
                target_type="consultant",
                target_id=instance.pk,
                description=f"حساب مشاور «{instance.full_name}» {status_text} شد",
                metadata={"is_active": instance.is_active},
            )
        else:
            log_activity(
                user=instance.user,
                action="update",
                target_type="consultant",
                target_id=instance.pk,
                description=f"اطلاعات مشاور «{instance.full_name}» ویرایش شد",
                metadata={"full_name": instance.full_name, "branch": instance.branch},
            )
