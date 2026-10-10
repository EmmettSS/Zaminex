from django.db.models import Q


def user_is_admin(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False) and getattr(user, "role", "") == "ADMIN")


def can_access_property(user, prop) -> bool:
    if prop is None:
        return True
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user_is_admin(user):
        return True
    return prop.consultant_id == user.pk or bool(getattr(prop, "is_shared", False))


def can_manage_property(user, prop) -> bool:
    if prop is None:
        return False
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user_is_admin(user):
        return True
    return prop.consultant_id == user.pk


def accessible_properties_q(user):
    if user_is_admin(user):
        return Q()
    return Q(consultant=user) | Q(is_shared=True)
