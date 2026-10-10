import importlib

from django.db import connection
from django.test import TestCase

from apps.properties.models import Property

migration = importlib.import_module(
    "apps.properties.migrations.0017_add_list_filter_indexes"
)

DECLARED = {
    "idx_property_created_at": ["-created_at"],
    "idx_property_status_created": ["status", "-created_at"],
    "idx_property_deal_created": ["deal_type", "-created_at"],
    "idx_property_type": ["property_type"],
    "idx_property_area": ["area"],
    "idx_property_price": ["price"],
}


class IndexDeclarationTests(TestCase):
    def test_model_declares_every_index(self):
        declared = {index.name: index.fields for index in Property._meta.indexes}
        self.assertEqual(declared, DECLARED)

    def test_migration_declares_the_same_indexes_as_the_model(self):
        in_migration = {
            operation.index.name: operation.index.fields
            for operation in migration.Migration.operations
        }
        self.assertEqual(
            in_migration,
            {index.name: index.fields for index in Property._meta.indexes},
        )

    def test_migration_runs_outside_a_transaction(self):
        self.assertFalse(migration.Migration.atomic)

    def test_the_default_ordering_is_indexed(self):
        first = Property._meta.ordering[0]
        self.assertEqual(first, "-created_at")
        leading = [
            index.name
            for index in Property._meta.indexes
            if index.fields and index.fields[0] == "-created_at"
        ]
        self.assertIn("idx_property_created_at", leading)

    def test_the_indexes_really_exist_in_the_database(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes"
                " WHERE tablename = 'properties_property'"
            )
            present = {row[0] for row in cursor.fetchall()}
        for name in DECLARED:
            self.assertIn(name, present)


class IndexDefinitionTests(TestCase):
    def _indexdef(self, name):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexdef FROM pg_indexes WHERE indexname = %s", [name]
            )
            row = cursor.fetchone()
        self.assertIsNotNone(row, f"{name} is missing from the database")
        return row[0]

    def test_ordering_index_covers_created_at_descending(self):
        self.assertIn("(created_at DESC)", self._indexdef("idx_property_created_at"))

    def test_status_index_covers_status_then_created_at(self):
        definition = self._indexdef("idx_property_status_created")
        self.assertIn("(status, created_at DESC)", definition)

    def test_deal_type_index_covers_deal_type_then_created_at(self):
        definition = self._indexdef("idx_property_deal_created")
        self.assertIn("(deal_type, created_at DESC)", definition)

    def test_the_single_column_indexes_cover_their_filter(self):
        for name, column in (
            ("idx_property_type", "property_type"),
            ("idx_property_area", "area"),
            ("idx_property_price", "price"),
        ):
            self.assertIn(f"({column})", self._indexdef(name))

    def test_every_declared_index_really_exists(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes"
                " WHERE tablename = 'properties_property'"
            )
            present = {row[0] for row in cursor.fetchall()}
        for name in DECLARED:
            self.assertIn(name, present)
