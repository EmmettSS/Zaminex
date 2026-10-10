from django.db import migrations


def _split_full_name(full_name):
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def backfill_owner_info(apps, schema_editor):
    Property = apps.get_model("properties", "Property")

    properties = Property.objects.filter(
        owner_first_name="", owner_last_name="", owner_phone=""
    ).select_related("consultant__consultant_profile")

    updated = 0
    for prop in properties.iterator():
        consultant = prop.consultant
        if consultant is None:
            continue

        profile = getattr(consultant, "consultant_profile", None)
        first, last = _split_full_name(
            getattr(profile, "full_name", None) or ""
        )
        mobile = getattr(profile, "mobile", None) if profile else None

        if not first and not last and not mobile:
            continue

        prop.owner_first_name = first or ""
        prop.owner_last_name = last or ""
        prop.owner_phone = (mobile or "")[:20] if mobile else ""
        prop.save(
            update_fields=[
                "owner_first_name",
                "owner_last_name",
                "owner_phone",
            ]
        )
        updated += 1


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0012_property_owner_first_name_property_owner_last_name_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_owner_info, noop_reverse),
    ]
