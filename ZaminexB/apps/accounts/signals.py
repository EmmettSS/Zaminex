from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import UserRole


@receiver(post_migrate)
def ensure_auth_groups(sender, **kwargs):
    if sender.name != "accounts":
        return

    Group.objects.get_or_create(name=UserRole.ADMIN)
    Group.objects.get_or_create(name=UserRole.AGENT)
