from django.db import migrations


def remove_admin_consultant_profiles(apps, schema_editor):
    ConsultantProfile = apps.get_model("accounts", "ConsultantProfile")
    ConsultantProfile.objects.filter(user__role="ADMIN").delete()


def restore_admin_consultant_profiles(apps, schema_editor):
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
