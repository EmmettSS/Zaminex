from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.listings.models import Listing
from apps.properties.models import Property


def _make_property(consultant, **kwargs):
    defaults = dict(
        property_type="APARTMENT",
        deal_type="SALE",
        area=100,
        address="تهران",
    )
    defaults.update(kwargs)
    return Property.objects.create(consultant=consultant, **defaults)


def _sale_listing(prop, amount, consultant):
    return Listing.objects.create(
        property=prop,
        title=f"آگهی {prop.id}",
        publish_channel=Listing.PublishChannel.WEBSITE,
        created_by=consultant,
        assigned_to=consultant,
        sale_price=amount,
        start_date=timezone.now(),
    )


OPTION_KEYS = {
    "id",
    "title",
    "internalCode",
    "district",
    "price",
    "propertyStatus",
    "area",
    "latitude",
    "longitude",
    "isShared",
    "consultantId",
    "consultantName",
}


class _OptionsBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="opt-admin", password="pw", role="ADMIN",
            first_name="سارا", last_name="مدیری",
        )
        self.agent = User.objects.create_user(
            username="opt-agent", password="pw", role="AGENT",
            first_name="علی", last_name="رضایی",
        )
        self.other = User.objects.create_user(
            username="opt-other", password="pw", role="AGENT",
            first_name="رضا", last_name="کریمی",
        )
        self.client = APIClient()
        self.url = "/properties/api/properties/options/"


class OptionsShapeTests(_OptionsBase):
    def test_requires_authentication(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_returns_a_bare_list_not_a_paginated_envelope(self):
        self.client.force_authenticate(user=self.admin)
        _make_property(self.admin, title="تنها")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_carries_exactly_the_columns_consumers_read(self):
        self.client.force_authenticate(user=self.admin)
        _make_property(self.admin, title="نمونه")
        row = self.client.get(self.url).json()[0]
        self.assertEqual(set(row), OPTION_KEYS)

    def test_rows_come_back_for_every_property(self):
        self.client.force_authenticate(user=self.admin)
        for i in range(5):
            _make_property(self.admin, title=f"P{i}")
        data = self.client.get(self.url).json()
        self.assertEqual(len(data), 5)
        self.assertEqual({row["title"] for row in data}, {f"P{i}" for i in range(5)})


class OptionsAgreementTests(_OptionsBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin)
        self.priced = _make_property(
            self.agent, title="قیمت‌دار", neighborhood="سعادت آباد",
            status=Property.Status.AVAILABLE, area=120, latitude=35.8, longitude=51.4,
        )
        _sale_listing(self.priced, 2_400_000_000, self.agent)
        _sale_listing(self.priced, 2_900_000_000, self.agent)
        self.unpriced = _make_property(
            self.agent, title="بدون آگهی", neighborhood="نیاوران",
            status=Property.Status.SOLD, price=1_750_000_000, area=90,
        )

    def _option(self, title):
        return next(r for r in self.client.get(self.url).json() if r["title"] == title)

    def _list_row(self, title):
        data = self.client.get("/properties/api/properties/?page_size=100").json()
        rows = data["results"] if isinstance(data, dict) else data
        return next(r for r in rows if r["title"] == title)

    def test_price_matches_the_list_serializer(self):
        for title in ("قیمت‌دار", "بدون آگهی"):
            self.assertEqual(
                self._option(title)["price"],
                self._list_row(title)["price"],
                f"price diverged for {title}",
            )

    def test_price_prefers_the_highest_sale_listing(self):
        self.assertEqual(self._option("قیمت‌دار")["price"], "2900000000")

    def test_price_falls_back_to_the_property_column(self):
        self.assertEqual(self._option("بدون آگهی")["price"], "1750000000")

    def test_scalar_fields_match_the_list_serializer(self):
        for title in ("قیمت‌دار", "بدون آگهی"):
            option, listed = self._option(title), self._list_row(title)
            for field in ("id", "title", "district", "propertyStatus",
                          "consultantId", "consultantName", "area"):
                self.assertEqual(
                    option[field], listed.get(field), f"{field} diverged for {title}"
                )

    def test_district_is_the_neighbourhood(self):
        self.assertEqual(self._option("قیمت‌دار")["district"], "سعادت آباد")

    def test_status_is_lowercased_like_the_list_serializer(self):
        self.assertEqual(self._option("بدون آگهی")["propertyStatus"], "sold")

    def test_consultant_name_is_the_full_name(self):
        self.assertEqual(self._option("قیمت‌دار")["consultantName"], "علی رضایی")

    def test_coordinates_are_passed_through(self):
        row = self._option("قیمت‌دار")
        self.assertEqual(float(row["latitude"]), 35.8)
        self.assertEqual(float(row["longitude"]), 51.4)

    def test_internal_code_is_the_stored_one(self):
        self.assertEqual(
            self._option("قیمت‌دار")["internalCode"], self.priced.internal_code
        )

    def test_is_shared_matches_the_list_serializer(self):
        Property.objects.filter(pk=self.priced.pk).update(is_shared=True)
        self.assertIs(self._option("قیمت‌دار")["isShared"], True)
        self.assertIs(self._option("بدون آگهی")["isShared"], False)
        for title in ("قیمت‌دار", "بدون آگهی"):
            self.assertEqual(
                self._option(title)["isShared"],
                self._list_row(title)["isShared"],
                f"isShared diverged for {title}",
            )


class OptionsAccessTests(_OptionsBase):
    def setUp(self):
        super().setUp()
        self.mine = _make_property(self.agent, title="مال من")
        self.theirs = _make_property(self.other, title="مال دیگری")

    def _titles(self, client, query=""):
        return {r["title"] for r in client.get(self.url + query).json()}

    def test_consultant_sees_only_own_properties(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)
        self.assertEqual(self._titles(client), {"مال من"})

    def test_consultant_also_sees_shared_properties_of_others(self):
        _make_property(self.other, title="اشتراکی دیگری", is_shared=True)
        client = APIClient()
        client.force_authenticate(user=self.agent)
        self.assertEqual(self._titles(client), {"مال من", "اشتراکی دیگری"})

    def test_admin_sees_everything(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        self.assertEqual(self._titles(client), {"مال من", "مال دیگری"})

    def test_scope_all_matches_the_list_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.agent)

        options = self._titles(client, "?scope=all")

        listed = client.get("/properties/api/properties/?scope=all&page_size=100").json()
        rows = listed["results"] if isinstance(listed, dict) else listed
        self.assertEqual(options, {r["title"] for r in rows})
        self.assertEqual(options, {"مال من", "مال دیگری"})

    def test_filters_are_honoured(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        _make_property(self.admin, title="فروخته", status=Property.Status.SOLD)
        self.assertEqual(
            self._titles(client, "?propertyStatus=AVAILABLE"),
            {"مال من", "مال دیگری"},
        )

    def test_search_is_honoured(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        self.assertEqual(self._titles(client, "?q=مال من"), {"مال من"})


class OptionsQueryScaleTests(_OptionsBase):
    def _bulk(self, n, tag):
        Property.objects.bulk_create(
            [
                Property(
                    consultant=self.agent,
                    title=f"{tag}{i}",
                    property_type="APARTMENT",
                    deal_type="SALE",
                    status=Property.Status.AVAILABLE,
                    area=100,
                    address="تهران",
                    neighborhood=f"محله {i % 10}",
                    price=1_000_000_000 + i,
                    internal_code=f"Z{tag}_{i:05d}",
                )
                for i in range(n)
            ]
        )

    def _queries(self):
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return len(ctx)

    def test_query_count_is_bounded(self):
        self.client.force_authenticate(user=self.admin)
        self._bulk(200, "X")
        count = self._queries()
        self.assertLessEqual(count, 12, f"200 rows cost {count} queries")

    def test_query_count_does_not_grow_with_rows(self):
        self.client.force_authenticate(user=self.admin)
        self._bulk(50, "A")
        small = self._queries()
        self._bulk(150, "B")
        large = self._queries()
        self.assertEqual(small, large, f"{small} -> {large} as rows grew")

    def test_no_per_row_listing_query(self):
        import re

        self.client.force_authenticate(user=self.admin)
        prop = _make_property(self.agent, title="با آگهی")
        _sale_listing(prop, 3_000_000_000, self.agent)
        self._bulk(40, "C")
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)
        hits = [
            q for q in ctx
            if re.search(r'FROM "listings_listing"', re.sub(r"\s+", " ", q["sql"]))
        ]
        self.assertLessEqual(len(hits), 1, f"{len(hits)} listing queries")
