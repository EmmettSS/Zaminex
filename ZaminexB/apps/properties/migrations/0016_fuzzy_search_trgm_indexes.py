from django.db import migrations

ZWNJ = "\u200c"

_TARGETS = [
    ("properties_property", "title", "properties_property_title_trgm_idx"),
    ("properties_property", "internal_code", "properties_property_code_trgm_idx"),
    ("properties_property", "address", "properties_property_address_trgm_idx"),
    ("properties_property", "neighborhood", "properties_property_hood_trgm_idx"),
]


def _expression(column: str) -> str:
    return f"upper(replace({column}::text, '{ZWNJ}'::text, ''::text))"


def _trgm_available(connection) -> bool:
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
        )
        return cursor.fetchone() is not None


def create_indexes(apps, schema_editor):
    connection = schema_editor.connection
    if not _trgm_available(connection):
        return
    with connection.cursor() as cursor:
        for table, column, name in _TARGETS:
            cursor.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} "
                f"ON {table} USING gin ({_expression(column)} gin_trgm_ops)"
            )


def drop_indexes(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for _, _, name in reversed(_TARGETS):
            cursor.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("properties", "0015_alter_property_deal_type_and_more"),
        ("common", "0006_pg_trgm_extension"),
    ]

    operations = [
        migrations.RunPython(create_indexes, reverse_code=drop_indexes),
    ]
