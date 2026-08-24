from django.db import migrations


def enable_pg_trgm(apps, schema_editor):
    """Enable the pg_trgm extension on PostgreSQL (used by fuzzy search).

    Only runs on PostgreSQL — the extension does not exist on other backends.
    """
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0005_alter_activitylog_options_and_more"),
    ]

    operations = [
        migrations.RunPython(enable_pg_trgm, reverse_code=migrations.RunPython.noop),
    ]
