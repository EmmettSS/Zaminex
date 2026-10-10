from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.basics.categorization import (
    ESSENTIAL,
    NON_ESSENTIAL,
    classify_attribute,
)
from apps.basics.models import Attribute

User = get_user_model()


class ClassifyAttributeTests(SimpleTestCase):
    def test_core_is_essential_even_with_no_binding(self):
        self.assertEqual(classify_attribute(is_core=True, active_binding_count=0), ESSENTIAL)

    def test_active_binding_is_essential(self):
        self.assertEqual(classify_attribute(is_core=False, active_binding_count=1), ESSENTIAL)
        self.assertEqual(classify_attribute(is_core=False, active_binding_count=7), ESSENTIAL)

    def test_unbound_non_core_is_non_essential(self):
        self.assertEqual(classify_attribute(is_core=False, active_binding_count=0), NON_ESSENTIAL)

    def test_core_with_bindings_is_still_essential(self):
        self.assertEqual(classify_attribute(is_core=True, active_binding_count=12), ESSENTIAL)

    def test_categories_match_the_model_choices(self):
        self.assertIn(ESSENTIAL, Attribute.Category.values)
        self.assertIn(NON_ESSENTIAL, Attribute.Category.values)


class AttributeCategoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="cat-admin", password="pw", role="ADMIN"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _create_attribute(self, **overrides):
        payload = {
            "displayName": "ویژگی دسته‌بندی",
            "dataType": "text",
            "entity": "property",
        }
        payload.update(overrides)
        response = self.client.post(
            "/basics/api/attributes/",
            payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        return response.json()

    def test_new_attribute_defaults_to_non_essential(self):
        created = self._create_attribute()
        self.assertEqual(created["category"], NON_ESSENTIAL)
        self.assertEqual(
            Attribute.objects.get(pk=created["id"]).category, NON_ESSENTIAL
        )

    def test_list_response_includes_category(self):
        self._create_attribute()
        response = self.client.get("/basics/api/attributes/?all=1")
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("category", row)

    def test_patch_category_persists(self):
        created = self._create_attribute()
        response = self.client.patch(
            f"/basics/api/attributes/{created['id']}/",
            {"category": ESSENTIAL},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["category"], ESSENTIAL)
        self.assertEqual(
            Attribute.objects.get(pk=created["id"]).category, ESSENTIAL
        )

    def test_patch_category_back_to_non_essential(self):
        created = self._create_attribute()
        self.client.patch(
            f"/basics/api/attributes/{created['id']}/",
            {"category": ESSENTIAL},
            content_type="application/json",
        )
        response = self.client.patch(
            f"/basics/api/attributes/{created['id']}/",
            {"category": NON_ESSENTIAL},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Attribute.objects.get(pk=created["id"]).category, NON_ESSENTIAL
        )

    def test_invalid_category_is_rejected(self):
        created = self._create_attribute()
        response = self.client.patch(
            f"/basics/api/attributes/{created['id']}/",
            {"category": "bogus"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Attribute.objects.get(pk=created["id"]).category, NON_ESSENTIAL
        )
