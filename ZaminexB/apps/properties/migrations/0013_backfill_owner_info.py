# Generated manually: backfills the new owner-contact columns for properties
# that existed before the fields were added.
#
# No real owner contact was stored for those records, so the only reliable
# source available is the consultant each property is assigned to. We mirror
# their profile (full name split into first/last name, mobile) into the new
# fields so every pre-existing row is complete under the new structure. New
# records continue to be created with the real owner info from the wizard.
from django.db import migrations


def _split_full_name(full_name):
    """Split a full name like 'احسان محمدی' into (first, last).

    Persian names are space-separated; the first token is the given name and
    everything after it the surname. A single-token name is treated as the
    given name only.
    """
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

        # The consultant's contact lives on their ConsultantProfile; the User
        # row itself carries no full name or mobile.
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
    # Deliberately irreversible: once the placeholder owner info is written
    # there is no meaningful original value to restore.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("properties", "0012_property_owner_first_name_property_owner_last_name_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_owner_info, noop_reverse),
    ]
