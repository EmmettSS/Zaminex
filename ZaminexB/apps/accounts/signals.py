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

    # Guarantee the singleton rows exist so Django admin always has an object
    # to edit (their admins disable "add") and the login flow never races to
    # create them on the first request.
    LoginSettings.get_solo()
    SmsProviderSettings.get_solo()
