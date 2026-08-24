"""Cleanup: remove ConsultantProfile rows attached to ADMIN users.

Historically the ``/accounts/consultants/me/`` endpoint auto-created a
ConsultantProfile for *any* authenticated user, so some admin accounts ended
up with a consultant profile and showed up in the admin dashboard's
consultant list. From now on the consultant queryset only returns profiles
whose user has the AGENT role, and admins use the dedicated AdminProfile
model — this migration removes the stale rows from existing databases.
"""

from django.db import migrations


def remove_admin_consultant_profiles(apps, schema_editor):
    ConsultantProfile = apps.get_model("accounts", "ConsultantProfile")
    ConsultantProfile.objects.filter(user__role="ADMIN").delete()


def restore_admin_consultant_profiles(apps, schema_editor):
    # Intentionally not reversible: the original rows were data pollution.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_adminprofile"),
    ]

    operations = [
        migrations.RunPython(
            remove_admin_consultant_profiles,
            restore_admin_consultant_profiles,
        ),
    ]
