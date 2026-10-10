from django.db import connection, transaction
from django.test import TestCase

from apps.accounts.models import AdminProfile, ConsultantProfile
from apps.properties.models import PropertyImage

INDEXED_FIELDS = [
    (PropertyImage, "image"),
    (ConsultantProfile, "profile_image"),
    (AdminProfile, "profile_image"),
]


class MediaLookupIndexTests(TestCase):
    def test_every_media_lookup_column_is_indexed(self):
        for model, field_name in INDEXED_FIELDS:
            field = model._meta.get_field(field_name)
            self.assertTrue(
                field.db_index,
                f"{model.__name__}.{field_name} is looked up on every served "
                "image but has no index",
            )

    def test_the_indexes_exist_in_the_database(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename, indexdef FROM pg_indexes WHERE tablename = ANY(%s)",
                [[model._meta.db_table for model, _ in INDEXED_FIELDS]],
            )
            by_table = {}
            for table, indexdef in cursor.fetchall():
                by_table.setdefault(table, []).append(indexdef)

        for model, field_name in INDEXED_FIELDS:
            definitions = by_table.get(model._meta.db_table, [])
            self.assertTrue(
                any(f"({field_name})" in d for d in definitions),
                f"no index on {model._meta.db_table}.{field_name}: {definitions}",
            )

    def test_the_property_gallery_lookup_uses_an_index(self):
        self._check_plan()

    def _check_plan(self):
        with transaction.atomic():
            queryset = PropertyImage.objects.filter(
                image="properties/images/none.jpg"
            )
            sql, params = queryset.query.sql_with_params()
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL enable_seqscan = off")
                try:
                    cursor.execute("EXPLAIN " + sql, params)
                    plan = "\n".join(row[0] for row in cursor.fetchall())
                finally:
                    cursor.execute("SET LOCAL enable_seqscan = on")
            self.assertIn("Index", plan)
            self.assertIn("properties_propertyimage_image", plan)
