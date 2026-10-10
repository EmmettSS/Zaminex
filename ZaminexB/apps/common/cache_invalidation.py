from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save

from . import cache_utils

logger = logging.getLogger(__name__)


def _admin_ids() -> list[int]:
    from apps.accounts.models import User

    return list(User.objects.filter(role="ADMIN").values_list("id", flat=True))


def _invalidate_property(prop_id) -> None:
    if not prop_id:
        return
    cache_utils.cache_delete(cache_utils.make_key("report", "property", prop_id))


def _invalidate_users(user_ids) -> None:
    try:
        ids = set(user_ids or ()) | set(_admin_ids())
    except Exception:
        logger.debug("invalidation: admin lookup failed; relying on TTLs", exc_info=True)
        ids = set(user_ids or ())
    for uid in ids:
        if not uid:
            continue
        cache_utils.cache_delete(cache_utils.make_key("report", "consultant", uid))
        cache_utils.cache_delete(cache_utils.make_key("dashboard", uid))


def _invalidate_stats() -> None:
    cache_utils.cache_delete(cache_utils.make_key("stats", "neighborhoods"))


def _on_property(sender, instance, **kwargs) -> None:
    _invalidate_property(instance.pk)
    _invalidate_users({instance.consultant_id})
    _invalidate_stats()


def _on_listing(sender, instance, **kwargs) -> None:
    _invalidate_property(instance.property_id)
    _invalidate_users({instance.created_by_id, instance.assigned_to_id})
    _invalidate_stats()


def _on_task(sender, instance, **kwargs) -> None:
    _invalidate_property(instance.property_id)
    _invalidate_users({instance.assigned_to_id, instance.created_by_id})


def _on_followup(sender, instance, **kwargs) -> None:
    _invalidate_property(instance.property_id)
    _invalidate_users({instance.consultant_id})


def _on_image(sender, instance, **kwargs) -> None:
    _invalidate_property(instance.property_id)
    if instance.property_id:
        from apps.properties.models import Property

        prop = Property.objects.filter(pk=instance.property_id).only("consultant_id").first()
        if prop is not None:
            _invalidate_users({prop.consultant_id})


def invalidate_property_caches(prop) -> None:
    prop_id = getattr(prop, "pk", prop)
    _invalidate_property(prop_id)
    consultant_id = getattr(prop, "consultant_id", None)
    if consultant_id is None and prop_id:
        from apps.properties.models import Property

        found = Property.objects.filter(pk=prop_id).only("consultant_id").first()
        consultant_id = found.consultant_id if found is not None else None
    _invalidate_users({consultant_id})


def register() -> None:
    from apps.followups.models import FollowUp
    from apps.listings.models import Listing
    from apps.properties.models import Property, PropertyImage
    from apps.tasks.models import Task

    pairs = [
        (Property, _on_property),
        (Listing, _on_listing),
        (Task, _on_task),
        (FollowUp, _on_followup),
        (PropertyImage, _on_image),
    ]
    for model, receiver in pairs:
        post_save.connect(receiver, sender=model, dispatch_uid=f"phase4_{model.__name__}_save")
        post_delete.connect(receiver, sender=model, dispatch_uid=f"phase4_{model.__name__}_delete")


register()
