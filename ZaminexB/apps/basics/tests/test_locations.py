"""Tests for the Province → City → District hierarchy (phase 4)."""

import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from apps.basics.models import City, District, Province, PropertyType
from apps.common.models import District as LegacyDistrict
from apps.properties.models import Property

User = get_user_model()


class HierarchyModelTests(TestCase):
    def setUp(self):
        self.province = Province.objects.create(name="mazandaran", display_name="مازندران")
        self.city = City.objects.create(
            province=self.province, name="sari", display_name="ساری"
        )

    def test_full_path_reads_the_whole_chain(self):
        district = District.objects.create(
            city=self.city, name="markazi", display_name="مرکزی"
        )
        self.assertEqual(district.full_path, "مازندران / ساری / مرکزی")

    def test_a_city_name_may_repeat_across_provinces(self):
        other = Province.objects.create(name="tehran", display_name="تهران")
        City.objects.create(province=other, name="sari-2", display_name="ساری")

        self.assertEqual(City.objects.filter(display_name="ساری").count(), 2)

    def test_a_city_name_cannot_repeat_inside_one_province(self):
        with self.assertRaises(IntegrityError):
            City.objects.create(
                province=self.province, name="sari", display_name="ساری دوم"
            )

    def test_a_district_name_may_repeat_across_cities(self):
        other_city = City.objects.create(
            province=self.province, name="babol", display_name="بابل"
        )
        District.objects.create(city=self.city, name="markazi", display_name="مرکزی")
        District.objects.create(city=other_city, name="markazi-2", display_name="مرکزی")

        self.assertEqual(District.objects.filter(display_name="مرکزی").count(), 2)

    def test_a_district_name_cannot_repeat_inside_one_city(self):
        District.objects.create(city=self.city, name="markazi", display_name="مرکزی")
        with self.assertRaises(IntegrityError):
            District.objects.create(city=self.city, name="markazi", display_name="دیگر")

    def test_deleting_is_soft(self):
        district = District.objects.create(
            city=self.city, name="markazi", display_name="مرکزی"
        )
        district.delete()

        self.assertEqual(District.objects.count(), 0)
        self.assertEqual(District.all_objects.count(), 1)


class NeighborhoodSyncTests(TestCase):
    """The legacy text column must track the linked district."""

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="loc-agent", password="pw", role="AGENT"
        )
        province = Province.objects.create(name="mazandaran", display_name="مازندران")
        cls.city = City.objects.create(
            province=province, name="sari", display_name="ساری"
        )
        cls.district = District.objects.create(
            city=cls.city, name="markazi", display_name="مرکزی"
        )

    def _property(self, **kwargs):
        defaults = dict(
            title="ملک",
            internal_code="SYNC-1",
            consultant=self.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
        )
        defaults.update(kwargs)
        return Property.objects.create(**defaults)

    def test_linking_a_district_fills_the_legacy_text(self):
        prop = self._property(district=self.district)
        self.assertEqual(prop.neighborhood, "مرکزی")

    def test_renaming_a_district_propagates_on_the_next_save(self):
        """Reports group by the text column, so it cannot go stale."""
        prop = self._property(district=self.district)

        self.district.display_name = "مرکزی جدید"
        self.district.save()
        prop.save()

        prop.refresh_from_db()
        self.assertEqual(prop.neighborhood, "مرکزی جدید")

    def test_a_property_without_a_district_keeps_its_free_text(self):
        prop = self._property(neighborhood="محله دستی")
        self.assertEqual(prop.neighborhood, "محله دستی")
        self.assertIsNone(prop.district)

    def test_a_district_in_use_cannot_be_removed(self):
        """Property.district is PROTECT, guarding the history."""
        from django.db.models import ProtectedError

        self._property(district=self.district)
        with self.assertRaises(ProtectedError):
            self.district.delete(hard=True)


class LocationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="loc-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="loc-agent2", password="pw", role="AGENT"
        )
        cls.province = Province.objects.create(
            name="mazandaran", display_name="مازندران"
        )
        cls.city = City.objects.create(
            province=cls.province, name="sari", display_name="ساری"
        )
        cls.district = District.objects.create(
            city=cls.city, name="markazi", display_name="مرکزی"
        )

    def test_the_tree_returns_all_three_levels_in_one_call(self):
        self.client.force_login(self.agent)
        payload = self.client.get("/basics/api/locations/").json()

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["displayName"], "مازندران")
        self.assertEqual(payload[0]["cities"][0]["displayName"], "ساری")
        self.assertEqual(
            payload[0]["cities"][0]["districts"][0]["displayName"], "مرکزی"
        )

    def test_the_tree_hides_deactivated_rows(self):
        self.district.is_active = False
        self.district.save()

        self.client.force_login(self.agent)
        payload = self.client.get("/basics/api/locations/").json()
        self.assertEqual(payload[0]["cities"][0]["districts"], [])

    def test_an_admin_creates_a_province_from_the_label_alone(self):
        """The UI only asks for the Persian name; the key is derived."""
        self.client.force_login(self.admin)
        response = self.client.post(
            "/basics/api/provinces/", {"displayName": "گیلان"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(response.json()["name"])

    def test_a_duplicate_province_label_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/basics/api/provinces/",
            {"displayName": "مازندران"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_a_duplicate_district_label_in_the_same_city_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/basics/api/districts/",
            {"displayName": "مرکزی", "city": self.city.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_the_same_district_label_in_another_city_is_allowed(self):
        other = City.objects.create(
            province=self.province, name="babol", display_name="بابل"
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            "/basics/api/districts/",
            {"displayName": "مرکزی", "city": other.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:300])

    def test_cities_can_be_filtered_by_province(self):
        self.client.force_login(self.agent)
        payload = self.client.get(
            f"/basics/api/cities/?province={self.province.pk}"
        ).json()
        self.assertEqual(len(payload), 1)

    def test_districts_can_be_filtered_by_city(self):
        self.client.force_login(self.agent)
        payload = self.client.get(f"/basics/api/districts/?city={self.city.pk}").json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["fullPath"], "مازندران / ساری / مرکزی")

    def test_a_province_with_cities_cannot_be_deleted(self):
        self.client.force_login(self.admin)
        response = self.client.delete(f"/basics/api/provinces/{self.province.pk}/")
        self.assertEqual(response.status_code, 400)

    def test_a_city_with_districts_cannot_be_deleted(self):
        self.client.force_login(self.admin)
        response = self.client.delete(f"/basics/api/cities/{self.city.pk}/")
        self.assertEqual(response.status_code, 400)

    def test_a_district_with_properties_cannot_be_deleted(self):
        Property.objects.create(
            title="ملک",
            internal_code="DEL-1",
            consultant=self.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            district=self.district,
        )
        self.client.force_login(self.admin)
        response = self.client.delete(f"/basics/api/districts/{self.district.pk}/")
        self.assertEqual(response.status_code, 400)

    def test_an_empty_district_can_be_deleted(self):
        self.client.force_login(self.admin)
        response = self.client.delete(f"/basics/api/districts/{self.district.pk}/")
        self.assertEqual(response.status_code, 204)

    def test_a_consultant_cannot_create_locations(self):
        self.client.force_login(self.agent)
        response = self.client.post(
            "/basics/api/provinces/", {"displayName": "قم"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

    def test_the_legacy_name_list_reads_from_the_hierarchy(self):
        """DistrictCombobox and the property filter still call this."""
        self.client.force_login(self.agent)
        payload = self.client.get("/common/api/districts/").json()
        self.assertIn("مرکزی", payload)


class PropertyLocationAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="ploc-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="ploc-agent", password="pw", role="AGENT"
        )
        province = Province.objects.create(name="mazandaran", display_name="مازندران")
        cls.city = City.objects.create(
            province=province, name="sari", display_name="ساری"
        )
        cls.district = District.objects.create(
            city=cls.city, name="markazi", display_name="مرکزی"
        )
        cls.apartment = PropertyType.objects.get(name="apartment")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_creating_with_district_id_fills_the_location_fields(self):
        response = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک",
                "internalCode": "LOC-1",
                "propertyTypeRef": self.apartment.pk,
                "area": 120,
                "districtId": self.district.pk,
                "fullAddress": "ساری",
                "consultant": self.agent.pk,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])

        body = response.json()
        self.assertEqual(body["districtId"], self.district.pk)
        self.assertEqual(body["cityName"], "ساری")
        self.assertEqual(body["provinceName"], "مازندران")
        self.assertEqual(body["locationPath"], "مازندران / ساری / مرکزی")
        self.assertEqual(
            body["district"], "مرکزی", "the legacy text is derived from the link"
        )

    def test_the_legacy_text_only_payload_still_works(self):
        """Older callers send a plain name and must keep working."""
        response = self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک",
                "internalCode": "LOC-2",
                "propertyTypeRef": self.apartment.pk,
                "area": 90,
                "district": "محله آزاد",
                "fullAddress": "ساری",
                "consultant": self.agent.pk,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content[:400])
        self.assertEqual(response.json()["district"], "محله آزاد")
        self.assertIsNone(response.json()["districtId"])

    def test_filtering_by_district_name_still_works(self):
        self.client.post(
            "/properties/api/properties/",
            {
                "title": "ملک",
                "internalCode": "LOC-3",
                "propertyTypeRef": self.apartment.pk,
                "area": 120,
                "districtId": self.district.pk,
                "fullAddress": "ساری",
                "consultant": self.agent.pk,
            },
            content_type="application/json",
        )
        response = self.client.get("/properties/api/properties/?district=مرکزی")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)


class DistrictMigrationCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="mig-loc", password="pw", role="AGENT"
        )

    def _property(self, code, neighborhood):
        return Property.objects.create(
            title=f"ملک {code}",
            internal_code=code,
            consultant=self.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            neighborhood=neighborhood,
        )

    def test_it_builds_the_hierarchy_and_links_properties(self):
        LegacyDistrict.objects.create(name="بلوار کشاورز")
        prop = self._property("H-1", "میدان ساعت")

        call_command(
            "migrate_districts_to_hierarchy",
            province="مازندران",
            city="ساری",
            stdout=io.StringIO(),
        )

        prop.refresh_from_db()
        self.assertIsNotNone(prop.district)
        self.assertEqual(prop.district.full_path, "مازندران / ساری / میدان ساعت")
        self.assertTrue(District.objects.filter(display_name="بلوار کشاورز").exists())

    def test_dry_run_writes_nothing(self):
        self._property("H-2", "میدان ساعت")

        call_command(
            "migrate_districts_to_hierarchy",
            province="مازندران",
            city="ساری",
            dry_run=True,
            stdout=io.StringIO(),
        )

        self.assertEqual(Province.objects.count(), 0)
        self.assertEqual(District.objects.count(), 0)

    def test_running_it_twice_creates_nothing_extra(self):
        self._property("H-3", "میدان ساعت")
        options = dict(province="مازندران", city="ساری", stdout=io.StringIO())

        call_command("migrate_districts_to_hierarchy", **options)
        counts = (Province.objects.count(), City.objects.count(), District.objects.count())

        call_command("migrate_districts_to_hierarchy", **options)

        self.assertEqual(
            counts,
            (Province.objects.count(), City.objects.count(), District.objects.count()),
        )

    def test_an_already_linked_property_is_left_alone(self):
        prop = self._property("H-4", "میدان ساعت")
        call_command(
            "migrate_districts_to_hierarchy",
            province="مازندران",
            city="ساری",
            stdout=io.StringIO(),
        )
        prop.refresh_from_db()
        first = prop.district_id

        call_command(
            "migrate_districts_to_hierarchy",
            province="مازندران",
            city="ساری",
            stdout=io.StringIO(),
        )

        prop.refresh_from_db()
        self.assertEqual(prop.district_id, first)

    def test_duplicate_neighbourhood_names_collapse_into_one_district(self):
        self._property("H-5", "میدان ساعت")
        self._property("H-6", "میدان ساعت")

        call_command(
            "migrate_districts_to_hierarchy",
            province="مازندران",
            city="ساری",
            stdout=io.StringIO(),
        )

        self.assertEqual(District.objects.filter(display_name="میدان ساعت").count(), 1)
        self.assertEqual(
            District.objects.get(display_name="میدان ساعت").properties.count(), 2
        )


class LocationCreateAPITests(TestCase):
    """Province/City/District creation must persist and return immediately."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="loc-create-admin", password="pw", role="ADMIN"
        )

    def _post(self, url, payload):
        self.client.force_login(self.admin)
        return self.client.post(url, payload, content_type="application/json")

    def test_create_province_persists_and_appears_first(self):
        first = self._post("/basics/api/provinces/", {"displayName": "اول"})
        self.assertEqual(first.status_code, 201, first.content[:300])
        second = self._post("/basics/api/provinces/", {"displayName": "دوم"})
        self.assertEqual(second.status_code, 201, second.content[:300])

        rows = self.client.get("/basics/api/provinces/?all=1").json()
        self.assertEqual(rows[0]["displayName"], "دوم")
        self.assertEqual(rows[1]["displayName"], "اول")

    def test_create_city_persists_and_appears_first(self):
        province = Province.objects.create(
            name="khorasan", display_name="خراسان"
        )
        first = self._post(
            "/basics/api/cities/",
            {"displayName": "مشهد", "province": province.pk},
        )
        self.assertEqual(first.status_code, 201, first.content[:300])
        second = self._post(
            "/basics/api/cities/",
            {"displayName": "نیشابور", "province": province.pk},
        )
        self.assertEqual(second.status_code, 201, second.content[:300])

        rows = self.client.get("/basics/api/cities/?all=1").json()
        self.assertEqual(rows[0]["displayName"], "نیشابور")
        self.assertEqual(rows[1]["displayName"], "مشهد")

    def test_create_district_persists_and_appears_first(self):
        province = Province.objects.create(name="qom", display_name="قم")
        city = City.objects.create(
            province=province, name="qom-city", display_name="قم"
        )
        first = self._post(
            "/basics/api/districts/",
            {"displayName": "مرکزی", "city": city.pk},
        )
        self.assertEqual(first.status_code, 201, first.content[:300])
        second = self._post(
            "/basics/api/districts/",
            {"displayName": "صفاشهر", "city": city.pk},
        )
        self.assertEqual(second.status_code, 201, second.content[:300])

        rows = self.client.get("/basics/api/districts/?all=1").json()
        self.assertEqual(rows[0]["displayName"], "صفاشهر")
        self.assertEqual(rows[1]["displayName"], "مرکزی")

    def test_city_requires_province_with_a_clear_message(self):
        """A city without its parent must fail validation and name the field."""
        response = self._post("/basics/api/cities/", {"displayName": "بدون استان"})
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("province", payload)
        self.assertEqual(str(payload["province"][0]), "انتخاب استان الزامی است.")

    def test_district_requires_city_with_a_clear_message(self):
        """A district without its parent must fail validation and name the field."""
        response = self._post(
            "/basics/api/districts/", {"displayName": "بدون شهر"}
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("city", payload)
        self.assertEqual(str(payload["city"][0]), "انتخاب شهر الزامی است.")

    def test_city_accepts_parent_as_string_like_the_spa_sends(self):
        """The SPA sends the parent id as a string; DRF must coerce it."""
        province = Province.objects.create(
            name="string-parent", display_name="استان رشته‌ای"
        )
        response = self._post(
            "/basics/api/cities/",
            {"displayName": "ساری", "province": str(province.pk)},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(City.objects.get(pk=response.json()["id"]).province, province)

    def test_district_accepts_parent_as_string_like_the_spa_sends(self):
        """The SPA sends the parent id as a string; DRF must coerce it."""
        province = Province.objects.create(
            name="string-parent-2", display_name="استان رشته‌ای ۲"
        )
        city = City.objects.create(
            province=province, name="string-city", display_name="شهر رشته‌ای"
        )
        response = self._post(
            "/basics/api/districts/",
            {"displayName": "مرکزی", "city": str(city.pk)},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(
            District.objects.get(pk=response.json()["id"]).city, city
        )


class SystemKeyGenerationTests(TestCase):
    """The label alone must be enough to create a row.

    The management screen never asks for ``name`` — the English system key —
    so the API has to derive it. It used to be filled in ``validate()``, which
    only runs *after* every field has been validated: the moment ``name`` was
    treated as required the request died first with a bare
    "این مقدار لازم است." naming a field the form does not even show, and cities
    and districts could not be added at all (provinces were unaffected).

    The key is now supplied in ``to_internal_value``, before field validation,
    so these tests pin the behaviour from the outside: label in, row created.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="key-admin", password="pw", role="ADMIN"
        )
        cls.province = Province.objects.create(name="gilan", display_name="گیلان")
        cls.city = City.objects.create(
            province=cls.province, name="rasht", display_name="رشت"
        )

    def _post(self, url, payload):
        self.client.force_login(self.admin)
        return self.client.post(url, payload, content_type="application/json")

    def test_city_is_created_from_the_label_alone(self):
        response = self._post(
            "/basics/api/cities/",
            {"displayName": "لاهیجان", "province": self.province.pk},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(response.json()["name"], "لاهیجان")

    def test_district_is_created_from_the_label_alone(self):
        response = self._post(
            "/basics/api/districts/",
            {"displayName": "گلسار", "city": self.city.pk},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(response.json()["name"], "گلسار")

    def test_a_label_with_no_slug_still_yields_a_key(self):
        """Punctuation-only labels slugify to "", which must not blank the key."""
        response = self._post(
            "/basics/api/cities/",
            {"displayName": "...", "province": self.province.pk},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertTrue(response.json()["name"])

    def test_keys_stay_unique_when_two_labels_share_a_slug(self):
        first = self._post(
            "/basics/api/districts/", {"displayName": "!!!", "city": self.city.pk}
        )
        second = self._post(
            "/basics/api/districts/", {"displayName": "???", "city": self.city.pk}
        )
        self.assertEqual(first.status_code, 201, first.content[:300])
        self.assertEqual(second.status_code, 201, second.content[:300])
        self.assertNotEqual(first.json()["name"], second.json()["name"])

    def test_an_explicit_key_is_respected(self):
        response = self._post(
            "/basics/api/cities/",
            {
                "name": "custom-key",
                "displayName": "شهر با کلید",
                "province": self.province.pk,
            },
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        self.assertEqual(response.json()["name"], "custom-key")

    def test_an_over_long_label_does_not_overflow_the_key_column(self):
        """A long label must not reach the database as an oversized varchar."""
        response = self._post(
            "/basics/api/cities/",
            {"displayName": "شهر " * 30, "province": self.province.pk},
        )
        self.assertEqual(response.status_code, 201, response.content[:300])
        max_length = City._meta.get_field("name").max_length
        self.assertLessEqual(len(response.json()["name"]), max_length)

    def test_editing_keeps_the_original_key(self):
        """A rename must not rewrite the key — other rows may reference it."""
        original = self.city.name
        self.client.force_login(self.admin)
        response = self.client.patch(
            f"/basics/api/cities/{self.city.pk}/",
            {"displayName": "رشت مرکزی"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content[:300])
        self.city.refresh_from_db()
        self.assertEqual(self.city.name, original)
        self.assertEqual(self.city.display_name, "رشت مرکزی")

    def test_a_soft_deleted_row_still_reserves_its_key(self):
        """Re-using a label after a delete must not collide on the key."""
        first = self._post(
            "/basics/api/districts/", {"displayName": "سبزه‌میدان", "city": self.city.pk}
        )
        self.assertEqual(first.status_code, 201, first.content[:300])
        District.objects.get(pk=first.json()["id"]).delete()  # soft delete

        second = self._post(
            "/basics/api/districts/", {"displayName": "سبزه‌میدان", "city": self.city.pk}
        )
        self.assertEqual(second.status_code, 201, second.content[:300])
        self.assertNotEqual(second.json()["name"], first.json()["name"])
