from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.basics.categorization import ESSENTIAL, NON_ESSENTIAL
from apps.basics.models import Attribute, AttributeCategory

User = get_user_model()

ENDPOINT = "/basics/api/attribute-categories/"


def detail_of(response):
    data = response.json()
    if isinstance(data, list):
        return data[0]
    detail = data.get("detail")
    return detail[0] if isinstance(detail, list) else detail


class AttributeCategorySeedTests(TestCase):
    def test_builtin_categories_are_seeded(self):
        names = list(
            AttributeCategory.objects.order_by("sort_order").values_list(
                "name", flat=True
            )
        )
        self.assertEqual(names, [ESSENTIAL, NON_ESSENTIAL])

    def test_builtin_categories_are_flagged_as_system(self):
        for name in (ESSENTIAL, NON_ESSENTIAL):
            with self.subTest(category=name):
                self.assertTrue(
                    AttributeCategory.objects.get(name=name).is_system_category
                )

    def test_a_user_created_category_is_not_system(self):
        category = AttributeCategory.objects.create(
            name="luxury", display_name="ویژگی لوکس", sort_order=3
        )
        self.assertFalse(category.is_system_category)

    def test_every_attribute_resolves_to_a_seeded_category(self):
        agent = User.objects.create_user(
            username="seed-agent", password="pw", role="AGENT"
        )
        Attribute.objects.create(
            name="seeded-attr",
            display_name="ویژگی seed",
            data_type=Attribute.DataType.TEXT,
            entity=Attribute.Entity.PROPERTY,
        )
        known = set(AttributeCategory.objects.values_list("name", flat=True))
        for attribute in Attribute.objects.all():
            self.assertIn(attribute.category, known)

        self.assertTrue(agent)


class AttributeCategoryApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="cat-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="cat-agent", password="pw", role="AGENT"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _create_attribute(self, label, **overrides):
        payload = {
            "displayName": label,
            "dataType": "text",
            "entity": "property",
        }
        payload.update(overrides)
        response = self.client.post(
            "/basics/api/attributes/", payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        return response.json()

    def _create_category(self, label, **overrides):
        payload = {"displayName": label}
        payload.update(overrides)
        response = self.client.post(
            ENDPOINT, payload, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        return response.json()

    def test_list_returns_the_builtin_categories(self):
        response = self.client.get(ENDPOINT)
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.json()]
        self.assertEqual(names, [ESSENTIAL, NON_ESSENTIAL])

    def test_list_reports_attribute_counts(self):
        rows = {row["name"]: row for row in self.client.get(ENDPOINT).json()}
        self.assertEqual(
            rows[NON_ESSENTIAL]["attributeCount"],
            Attribute.objects.filter(category=NON_ESSENTIAL).count(),
        )

    def test_list_exposes_the_system_flag(self):
        rows = {row["name"]: row for row in self.client.get(ENDPOINT).json()}
        self.assertTrue(rows[ESSENTIAL]["isSystem"])
        self.assertTrue(rows[NON_ESSENTIAL]["isSystem"])

    def test_create_derives_the_system_key_from_the_label(self):
        created = self._create_category("امکانات رفاهی")
        self.assertEqual(created["displayName"], "امکانات رفاهی")
        self.assertTrue(created["name"])
        self.assertNotEqual(created["name"], created["displayName"])
        self.assertEqual(created["attributeCount"], 0)
        self.assertFalse(created["isSystem"])

    def test_new_category_is_appended_after_the_existing_ones(self):
        before = [row["name"] for row in self.client.get(ENDPOINT).json()]
        created = self._create_category("ویژگی مالی")
        after = [row["name"] for row in self.client.get(ENDPOINT).json()]
        self.assertEqual(after, before + [created["name"]])

    def test_duplicate_label_is_rejected(self):
        self._create_category("ویژگی مالی")
        response = self.client.post(
            ENDPOINT, {"displayName": "ویژگی مالی"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        message = response.json()["displayName"][0]
        self.assertIn("قبلاً ثبت شده است", message)
        self.assertEqual(
            AttributeCategory.objects.filter(display_name="ویژگی مالی").count(), 1
        )

    def test_blank_label_is_rejected(self):
        for label in ("", "   "):
            with self.subTest(label=repr(label)):
                response = self.client.post(
                    ENDPOINT, {"displayName": label}, content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "خالی", response.json()["displayName"][0]
                )

    def test_label_is_trimmed_before_storing(self):
        created = self._create_category("  ویژگی مالی  ")
        self.assertEqual(created["displayName"], "ویژگی مالی")

    def test_creating_the_same_label_twice_as_a_key_is_impossible(self):
        response = self.client.post(
            ENDPOINT,
            {"displayName": "دسته تکراری", "name": ESSENTIAL},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            AttributeCategory.objects.filter(name=ESSENTIAL).count(), 1
        )


    def test_new_attribute_can_be_filed_under_a_custom_category(self):
        category = self._create_category("ویژگی مالی")
        created = self._create_attribute("قیمت کل", category=category["name"])
        self.assertEqual(created["category"], category["name"])
        self.assertEqual(
            Attribute.objects.get(pk=created["id"]).category, category["name"]
        )

    def test_creating_an_attribute_counts_towards_its_category(self):
        category = self._create_category("ویژگی مالی")
        self.assertEqual(category["attributeCount"], 0)

        self._create_attribute("قیمت کل", category=category["name"])

        rows = {row["name"]: row for row in self.client.get(ENDPOINT).json()}
        self.assertEqual(rows[category["name"]]["attributeCount"], 1)

    def test_creating_an_attribute_under_an_unknown_category_is_rejected(self):
        before = Attribute.objects.count()
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "قیمت کل", "dataType": "text", "entity": "property",
             "category": "no-such-category"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("وجود ندارد", response.json()["category"][0])
        self.assertEqual(Attribute.objects.count(), before)

    def test_creating_an_attribute_without_a_category_is_rejected(self):
        before = Attribute.objects.count()
        response = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "قیمت کل", "dataType": "text", "entity": "property",
             "category": "   "},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["category"][0], "انتخاب دسته‌بندی الزامی است."
        )
        self.assertEqual(Attribute.objects.count(), before)

        omitted = self.client.post(
            "/basics/api/attributes/",
            {"displayName": "قیمت کل", "dataType": "text", "entity": "property"},
            content_type="application/json",
        )
        self.assertEqual(omitted.status_code, 201, omitted.content[:300])
        self.assertEqual(omitted.json()["category"], NON_ESSENTIAL)

    def test_move_updates_both_categories_counts(self):
        category = self._create_category("ویژگی مالی")
        attribute = self._create_attribute("قیمت کل")
        self.assertEqual(attribute["category"], NON_ESSENTIAL)

        before = {row["name"]: row for row in self.client.get(ENDPOINT).json()}
        self.assertEqual(before[category["name"]]["attributeCount"], 0)

        response = self.client.patch(
            f"/basics/api/attributes/{attribute['id']}/",
            {"category": category["name"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.assertEqual(response.json()["category"], category["name"])

        after = {row["name"]: row for row in self.client.get(ENDPOINT).json()}
        self.assertEqual(after[category["name"]]["attributeCount"], 1)
        self.assertEqual(
            after[NON_ESSENTIAL]["attributeCount"],
            before[NON_ESSENTIAL]["attributeCount"] - 1,
        )

    def test_move_to_an_unknown_category_is_rejected(self):
        attribute = self._create_attribute("قیمت کل")
        response = self.client.patch(
            f"/basics/api/attributes/{attribute['id']}/",
            {"category": "no-such-category"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("وجود ندارد", response.json()["category"][0])
        self.assertEqual(
            Attribute.objects.get(pk=attribute["id"]).category, NON_ESSENTIAL
        )

    def test_move_to_an_empty_category_is_rejected(self):
        attribute = self._create_attribute("قیمت کل")
        response = self.client.patch(
            f"/basics/api/attributes/{attribute['id']}/",
            {"category": ""},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Attribute.objects.get(pk=attribute["id"]).category, NON_ESSENTIAL
        )

    def test_move_to_a_soft_deleted_category_is_rejected(self):
        category = AttributeCategory.objects.create(
            name="gone", display_name="حذف‌شده", sort_order=9
        )
        category.delete()
        attribute = self._create_attribute("قیمت کل")
        response = self.client.patch(
            f"/basics/api/attributes/{attribute['id']}/",
            {"category": "gone"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("وجود ندارد", response.json()["category"][0])

    def test_empty_category_can_be_deleted(self):
        category = self._create_category("ویژگی مالی")
        response = self.client.delete(f"{ENDPOINT}{category['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(AttributeCategory.objects.filter(pk=category["id"]).exists())

    def test_non_empty_category_cannot_be_deleted(self):
        category = self._create_category("ویژگی مالی")
        self._create_attribute("قیمت کل", category=category["name"])
        self._create_attribute("قیمت هر متر", category=category["name"])

        response = self.client.delete(f"{ENDPOINT}{category['id']}/")
        self.assertEqual(response.status_code, 400)

        detail = detail_of(response)
        self.assertIn("2 ویژگی", detail)
        self.assertIn("ویژگی مالی", detail)
        self.assertTrue(AttributeCategory.objects.filter(pk=category["id"]).exists())
        self.assertEqual(
            Attribute.objects.filter(category=category["name"]).count(), 2
        )

    def test_category_becomes_deletable_once_emptied(self):
        category = self._create_category("ویژگی مالی")
        attribute = self._create_attribute("قیمت کل", category=category["name"])

        self.assertEqual(self.client.delete(f"{ENDPOINT}{category['id']}/").status_code, 400)

        self.client.patch(
            f"/basics/api/attributes/{attribute['id']}/",
            {"category": ESSENTIAL},
            content_type="application/json",
        )
        self.assertEqual(self.client.delete(f"{ENDPOINT}{category['id']}/").status_code, 204)

    def test_builtin_categories_cannot_be_deleted_even_when_empty(self):
        category = AttributeCategory.objects.get(name=NON_ESSENTIAL)
        Attribute.objects.filter(category=NON_ESSENTIAL).update(category=ESSENTIAL)
        self.assertEqual(category.attribute_count(), 0)

        response = self.client.delete(f"{ENDPOINT}{category.pk}/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("پایهٔ سیستم", detail_of(response))
        self.assertTrue(AttributeCategory.objects.filter(pk=category.pk).exists())

    def test_deleting_a_category_soft_deletes_it(self):
        category = self._create_category("ویژگی مالی")
        self.client.delete(f"{ENDPOINT}{category['id']}/")
        self.assertTrue(
            AttributeCategory.all_objects.filter(pk=category["id"]).exists()
        )
        self.assertIsNotNone(
            AttributeCategory.all_objects.get(pk=category["id"]).deleted_at
        )


    def test_deactivated_category_is_hidden_from_the_default_list(self):
        category = self._create_category("ویژگی مالی")
        self.client.patch(
            f"{ENDPOINT}{category['id']}/",
            {"isActive": False},
            content_type="application/json",
        )
        names = [row["name"] for row in self.client.get(ENDPOINT).json()]
        self.assertNotIn(category["name"], names)

        all_names = [row["name"] for row in self.client.get(f"{ENDPOINT}?all=1").json()]
        self.assertIn(category["name"], all_names)

    def test_consultant_can_read_but_not_write(self):
        self.client.force_login(self.agent)

        self.assertEqual(self.client.get(ENDPOINT).status_code, 200)

        response = self.client.post(
            ENDPOINT, {"displayName": "غیرمجاز"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AttributeCategory.objects.filter(display_name="غیرمجاز").exists()
        )

    def test_consultant_cannot_delete_a_category(self):
        category = self._create_category("ویژگی مالی")
        self.client.force_login(self.agent)
        self.assertEqual(self.client.delete(f"{ENDPOINT}{category['id']}/").status_code, 403)
        self.assertTrue(AttributeCategory.objects.filter(pk=category["id"]).exists())

    def test_anonymous_request_is_rejected(self):
        self.client.logout()
        self.assertEqual(self.client.get(ENDPOINT).status_code, 403)
