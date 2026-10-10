from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import LoginSettings, SmsProviderSettings, UserRole


@receiver(post_migrate)
def ensure_auth_groups(sender, **kwargs):
    if sender.name != "accounts":
        return

    Group.objects.get_or_create(name=UserRole.ADMIN)
    Group.objects.get_or_create(name=UserRole.AGENT)


@receiver(post_migrate)
def ensure_login_singletons(sender, **kwargs):
    if sender.name != "accounts":
        return

    LoginSettings.get_solo()
    SmsProviderSettings.get_solo()
