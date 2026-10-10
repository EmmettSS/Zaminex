import warnings

from django.db import migrations, transaction


def enable_pg_trgm(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception as exc:
        warnings.warn(
            "pg_trgm could not be enabled: %s. Fuzzy search will fall back to "
            "a slower path. Ask the database administrator to run "
            "'CREATE EXTENSION pg_trgm;' on this database." % exc,
            RuntimeWarning,
            stacklevel=2,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0005_alter_activitylog_options_and_more"),
    ]

    operations = [
        migrations.RunPython(enable_pg_trgm, reverse_code=migrations.RunPython.noop),
    ]
