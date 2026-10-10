import datetime
import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.basics.models import DealType, PropertyType
from apps.analytics.metrics import (
    annotate_effective_prices,
    build_neighborhood_price_per_sqm_map,
    effective_sale_price,
    property_market_metrics,
)
from apps.listings.models import Listing
from apps.properties.models import Property

User = get_user_model()


class EffectivePriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.agent = User.objects.create_user(
            username="price-agent", password="pw", role="AGENT"
        )
        cls.apartment = PropertyType.objects.get(name="apartment")
        cls.sale = DealType.objects.get(name="sale")
        cls.rent = DealType.objects.get(name="mortgage_rent")
        cls.presale = DealType.objects.get(name="presale")

    def _property(self, code, **kwargs):
        defaults = dict(
            title=f"ملک {code}",
            internal_code=code,
            consultant=self.agent,
            property_type="APARTMENT",
            property_type_ref=self.apartment,
            area=100,
            address="آدرس",
            neighborhood="محله",
        )
        defaults.update(kwargs)
        return Property.objects.create(**defaults)

    def _listing(self, prop, deal, **kwargs):
        return Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            deal_type=deal,
            **kwargs,
        )

    def test_the_price_comes_from_the_sale_listing(self):
        prop = self._property("EP-1")
        self._listing(prop, self.sale, sale_price=10_000_000_000)

        self.assertEqual(effective_sale_price(prop), 10_000_000_000)

    def test_a_rental_listing_contributes_no_sale_price(self):
        prop = self._property("EP-2")
        self._listing(prop, self.rent, deposit=900_000_000, monthly_rent=50_000_000)

        self.assertIsNone(effective_sale_price(prop))

    def test_a_rental_alongside_a_sale_does_not_change_the_price(self):
        prop = self._property("EP-3")
        self._listing(prop, self.sale, sale_price=10_000_000_000)
        self._listing(prop, self.rent, deposit=900_000_000)

        self.assertEqual(effective_sale_price(prop), 10_000_000_000)

    def test_the_highest_sale_listing_wins(self):
        prop = self._property("EP-4")
        self._listing(prop, self.sale, sale_price=9_000_000_000)
        self._listing(prop, self.presale, sale_price=11_000_000_000)

        self.assertEqual(effective_sale_price(prop), 11_000_000_000)

    def test_it_falls_back_to_the_legacy_column(self):
        prop = self._property("EP-5", price=7_000_000_000)
        self.assertEqual(effective_sale_price(prop), 7_000_000_000)

    def test_a_listing_price_overrides_the_legacy_column(self):
        prop = self._property("EP-6", price=7_000_000_000)
        self._listing(prop, self.sale, sale_price=8_000_000_000)

        self.assertEqual(effective_sale_price(prop), 8_000_000_000)

    def test_a_listing_without_a_deal_type_counts_as_a_sale(self):
        prop = self._property("EP-7")
        Listing.objects.create(
            property=prop,
            title="آگهی قدیمی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            sale_price=5_000_000_000,
        )
        self.assertEqual(effective_sale_price(prop), 5_000_000_000)

    def test_a_property_with_nothing_recorded_has_no_price(self):
        self.assertIsNone(effective_sale_price(self._property("EP-8")))


class MarketMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.agent = User.objects.create_user(
            username="metric-agent", password="pw", role="AGENT"
        )
        cls.sale = DealType.objects.get(name="sale")

    def _priced(self, code, price, area=100, neighborhood="محله"):
        prop = Property.objects.create(
            title=f"ملک {code}",
            internal_code=code,
            consultant=self.agent,
            property_type="APARTMENT",
            area=area,
            address="آدرس",
            neighborhood=neighborhood,
        )
        Listing.objects.create(
            property=prop,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=self.agent,
            deal_type=self.sale,
            sale_price=price,
        )
        return prop

    def test_price_per_sqm_uses_the_listing_price(self):
        prop = self._priced("MM-1", 10_000_000_000, area=100)

        metrics = property_market_metrics(prop)
        self.assertEqual(metrics["pricePerSqm"], 100_000_000.0)

    def test_the_neighbourhood_average_uses_listing_prices(self):
        self._priced("MM-2", 10_000_000_000, area=100, neighborhood="نمونه")
        self._priced("MM-3", 20_000_000_000, area=100, neighborhood="نمونه")

        averages = build_neighborhood_price_per_sqm_map()
        self.assertEqual(averages["نمونه"], 150_000_000.0)

    def test_properties_without_a_price_are_left_out_of_the_average(self):
        self._priced("MM-4", 10_000_000_000, area=100, neighborhood="تکی")
        Property.objects.create(
            title="بدون قیمت",
            internal_code="MM-5",
            consultant=self.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            neighborhood="تکی",
        )

        averages = build_neighborhood_price_per_sqm_map()
        self.assertEqual(averages["تکی"], 100_000_000.0)

    def test_the_deviation_index_is_computed_from_listing_prices(self):
        self._priced("MM-6", 10_000_000_000, area=100, neighborhood="انحراف")
        expensive = self._priced("MM-7", 20_000_000_000, area=100, neighborhood="انحراف")

        metrics = property_market_metrics(expensive)
        self.assertAlmostEqual(metrics["priceDeviationIndex"], 1.0, places=3)

    def test_bulk_resolution_matches_the_single_lookup(self):
        a = self._priced("MM-8", 10_000_000_000)
        b = self._priced("MM-9", 20_000_000_000)

        bulk = annotate_effective_prices([a, b])
        self.assertEqual(bulk[a.id], 10_000_000_000)
        self.assertEqual(bulk[b.id], 20_000_000_000)

    def test_days_on_market_reads_from_listing_start_date(self):
        prop = self._priced("MM-10", 10_000_000_000)
        Property.objects.filter(pk=prop.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=60)
        )
        listing = prop.listings.first()
        listing.start_date = (
            timezone.now() - datetime.timedelta(days=30)
        ).date()
        listing.save()

        metrics = property_market_metrics(prop)
        self.assertEqual(metrics["daysOnMarket"], 30)

    def test_days_on_market_with_no_listing_falls_back_to_created_at(self):
        prop = self._priced("MM-11", 10_000_000_000)
        Property.objects.filter(pk=prop.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=12)
        )
        prop.refresh_from_db()
        metrics = property_market_metrics(prop)
        self.assertEqual(metrics["daysOnMarket"], 12)

    def test_deviation_is_none_when_no_comparables_exist(self):
        prop = self._priced("MM-12", 10_000_000_000, neighborhood="منفرد")
        metrics = property_market_metrics(prop)
        self.assertIsNone(metrics["priceDeviationIndex"])


class SerializedPriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="ser-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="ser-agent", password="pw", role="AGENT"
        )
        cls.property = Property.objects.create(
            title="ملک",
            internal_code="ZF_9051",
            consultant=cls.agent,
            property_type="APARTMENT",
            area=100,
            address="آدرس",
            neighborhood="محله",
        )
        Listing.objects.create(
            property=cls.property,
            title="آگهی",
            publish_channel="WEBSITE",
            created_by=cls.agent,
            deal_type=DealType.objects.get(name="sale"),
            sale_price=10_000_000_000,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_the_list_endpoint_reports_the_derived_price(self):
        response = self.client.get("/properties/api/properties/")
        self.assertEqual(response.status_code, 200)

        row = next(p for p in response.json()["results"] if p["internalCode"] == "ZF_9051")
        self.assertEqual(int(float(row["price"])), 10_000_000_000)
        detail = self.client.get(f"/properties/api/properties/{self.property.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["pricePerSqm"], 100_000_000.0)

    def test_an_unpriced_property_reports_null_rather_than_zero(self):
        Property.objects.create(
            title="بدون آگهی",
            internal_code="ZF_9052",
            consultant=self.agent,
            property_type="APARTMENT",
            area=80,
            address="آدرس",
            neighborhood="محله",
        )
        response = self.client.get("/properties/api/properties/")
        row = next(p for p in response.json()["results"] if p["internalCode"] == "ZF_9052")
        self.assertIsNone(row["price"])

    def test_the_property_report_uses_the_derived_price(self):
        response = self.client.get(
            f"/api/reports/properties/{self.property.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kpis"]["pricePerSqm"], 100_000_000.0)

    def test_the_scope_report_still_renders(self):
        response = self.client.get("/api/reports/scope/")
        self.assertEqual(response.status_code, 200)


class QueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="qc-admin", password="pw", role="ADMIN"
        )
        agent = User.objects.create_user(username="qc-agent", password="pw", role="AGENT")
        sale = DealType.objects.get(name="sale")
        for index in range(6):
            prop = Property.objects.create(
                title=f"ملک {index}",
                internal_code=f"QC-{index}",
                consultant=agent,
                property_type="APARTMENT",
                area=100,
                address="آدرس",
                neighborhood="محله",
            )
            Listing.objects.create(
                property=prop,
                title="آگهی",
                publish_channel="WEBSITE",
                created_by=agent,
                deal_type=sale,
                sale_price=1_000_000_000 * (index + 1),
            )

    def test_the_query_count_does_not_grow_with_the_number_of_rows(self):
        self.client.force_login(self.admin)

        with self.assertNumQueries(9):
            response = self.client.get("/properties/api/properties/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 6)
