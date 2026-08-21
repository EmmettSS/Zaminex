from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, UserRole
from apps.common.metrics import (
    consultant_ranking_metrics,
    content_richness_score,
    delegation_indicator,
    effective_exposure_days,
    geo_precision_flag,
    is_burned_listing,
    price_deviation_index,
    price_per_sqm,
    property_market_metrics,
    spatial_density_ratio,
)
from apps.followups.models import FollowUp, FollowUpStatus
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

User = get_user_model()


class MetricsUnitTests(TestCase):
    def test_price_per_sqm_and_spatial_density(self):
        self.assertIsNone(price_per_sqm(100, 0))
        self.assertEqual(price_per_sqm(200_000_000, 100), 2_000_000.0)
        self.assertIsNone(spatial_density_ratio(3, 0))
        self.assertEqual(spatial_density_ratio(3, 80), 0.0375)

    def test_geo_precision_flag(self):
        self.assertFalse(geo_precision_flag(None, None))
        self.assertFalse(geo_precision_flag(0, 0))
        self.assertTrue(geo_precision_flag(Decimal("35.7"), Decimal("51.4")))

    def test_price_deviation_index(self):
        agent = User.objects.create_user(username="a1", password="pass12345", role=UserRole.AGENT)
        p1 = Property.objects.create(
            title="P1",
            internal_code="IC1",
            consultant=agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=120_000_000,
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )
        Property.objects.create(
            title="P2",
            internal_code="IC2",
            consultant=agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=80_000_000,
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )
        idx = price_deviation_index(p1)
        self.assertIsNotNone(idx)
        self.assertGreater(idx, 0)

    def test_delegation_and_exposure(self):
        admin = User.objects.create_user(username="adm", password="pass12345", role=UserRole.ADMIN)
        agent = User.objects.create_user(username="ag", password="pass12345", role=UserRole.AGENT)
        prop = Property.objects.create(
            title="P",
            internal_code="IC3",
            consultant=agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=1,
            area=100,
            address="a",
            neighborhood="N",
        )
        start = timezone.now() - timedelta(days=10)
        listing = Listing.objects.create(
            property=prop,
            title="L",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=admin,
            assigned_to=agent,
            start_date=start,
        )
        self.assertEqual(delegation_indicator(listing), "DELEGATED")
        self.assertEqual(effective_exposure_days(listing), 10)

        solo = Listing.objects.create(
            property=prop,
            title="L2",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=agent,
            assigned_to=agent,
            start_date=start,
        )
        self.assertEqual(delegation_indicator(solo), "SELF_MANAGED")

    def test_burned_and_content_score(self):
        agent = User.objects.create_user(username="ag2", password="pass12345", role=UserRole.AGENT)
        prop = Property.objects.create(
            title="P",
            internal_code="IC4",
            consultant=agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=1,
            area=100,
            address="a",
            neighborhood="N",
        )
        listing = Listing.objects.create(
            property=prop,
            title="Long title",
            description="x" * 600,
            publish_channel=Listing.PublishChannel.INSTAGRAM,
            created_by=agent,
            status=Listing.Status.EXPIRED,
        )
        self.assertTrue(is_burned_listing(listing))
        self.assertGreaterEqual(content_richness_score(listing, images_count=6), 4)

    def test_property_market_metrics_engagement(self):
        agent = User.objects.create_user(username="ag3", password="pass12345", role=UserRole.AGENT)
        prop = Property.objects.create(
            title="P",
            internal_code="IC5",
            consultant=agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=100_000_000,
            area=50,
            rooms=2,
            address="a",
            neighborhood="N",
            latitude=Decimal("36.5"),
            longitude=Decimal("52.5"),
        )
        FollowUp.objects.create(
            title="f",
            consultant=agent,
            property=prop,
            contact_name="c",
            probability=80,
        )
        Task.objects.create(
            title="visit",
            assigned_to=agent,
            created_by=agent,
            property=prop,
            due_date=date.today() + timedelta(days=1),
            task_type=Task.TaskType.VIEWING,
        )
        metrics = property_market_metrics(prop)
        self.assertEqual(metrics["pricePerSqm"], 2_000_000.0)
        self.assertTrue(metrics["geoPrecisionFlag"])
        self.assertGreaterEqual(metrics["engagementHeatScore"], 4)


class AnalyticsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin_metrics",
            password="pass12345",
            role=UserRole.ADMIN,
        )
        self.agent = User.objects.create_user(
            username="agent_metrics",
            password="pass12345",
            role=UserRole.AGENT,
        )
        ConsultantProfile.objects.create(
            user=self.agent,
            full_name="Agent One",
            branch="Central",
            hired_at=date.today() - timedelta(days=100),
        )
        self.prop = Property.objects.create(
            title="Test Property",
            internal_code="M-001",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=500_000_000,
            area=100,
            rooms=3,
            address="Test address",
            neighborhood="Saadat",
        )
        self.listing = Listing.objects.create(
            property=self.prop,
            title="Listing",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            start_date=timezone.now() - timedelta(days=5),
        )

    def test_analytics_endpoints_require_auth(self):
        for path in [
            "/common/api/analytics/consultants/",
            "/common/api/analytics/properties/",
            "/common/api/analytics/listings/",
            "/common/api/analytics/dashboard/",
        ]:
            res = self.client.get(path)
            self.assertIn(res.status_code, [401, 403])

    def test_analytics_dashboard_admin(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/common/api/analytics/dashboard/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("topConsultants", data)
        self.assertIn("hotProperties", data)
        self.assertGreaterEqual(data["propertyCount"], 1)
        self.assertIn("kpis", data)
        self.assertEqual(data["kpis"]["totalProperties"], 1)
        self.assertEqual(data["kpis"]["activeListings"], 1)
        self.assertEqual(len(data["revenueMonthly"]), 6)
        self.assertTrue(all("month" in row and "revenue" in row for row in data["revenueMonthly"]))
        self.assertTrue(data["propertyComposition"])
        self.assertEqual(data["propertyComposition"][0]["name"], "آپارتمان")
        self.assertIsNone(data.get("myReport"))
        if data["topConsultants"]:
            top = data["topConsultants"][0]
            self.assertIn("headlineValue", top)
            self.assertIn("headlineLabel", top)
            self.assertIn("closedDealsCount", top)
            self.assertNotIn("avgDealProbability", top)

    def test_analytics_dashboard_consultant_scoped_report(self):
        self.client.force_authenticate(user=self.agent)
        res = self.client.get("/common/api/analytics/dashboard/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNotNone(data.get("myReport"))
        self.assertIn("performanceProfile", data["myReport"]["charts"])
        self.assertEqual(len(data["myReport"]["charts"]["monthlyActivity"]), 6)
        self.assertTrue(all("label" in row for row in data["myReport"]["charts"]["monthlyActivity"]))
        self.assertEqual(data["kpis"]["totalProperties"], 1)

    def test_monthly_revenue_counts_all_deal_types(self):
        from apps.common.analytics_views import _get_monthly_revenue

        rent = Listing.objects.create(
            property=self.prop,
            title="Rent listing",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            status=Listing.Status.SOLD,
            deposit=50_000_000,
            monthly_rent=5_000_000,
        )
        sale = Listing.objects.create(
            property=self.prop,
            title="Sale listing",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            status=Listing.Status.SOLD,
            sale_price=2_000_000_000,
        )
        bundle = _get_monthly_revenue()
        rows = bundle["months"]
        self.assertEqual(len(rows), 6)
        # Both SOLD listings belong to the same property and neither has a
        # deal type, so they collapse into one closed deal. The chart counts
        # closed deals per (property, deal type), not per listing row.
        self.assertEqual(sum(r["count"] for r in rows), 1)
        # The sale listing is the authoritative closed deal; the rent row
        # without a deal type is de-duplicated away.
        self.assertAlmostEqual(
            sum(r["revenue"] for r in rows),
            2.0,
            places=2,
        )
        self.assertTrue(bundle["dealTypes"])
        rent.delete()
        sale.delete()

    def test_property_api_includes_metrics(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/properties/api/properties/")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        if isinstance(items, dict):
            items = items.get("results", [])
        self.assertTrue(any("pricePerSqm" in p for p in items))

    def test_listing_api_includes_metrics(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/listings/api/listings/")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        if isinstance(items, dict):
            items = items.get("results", [])
        self.assertTrue(any("contentRichnessScore" in item for item in items))


class ConsultantRankingMetricsTests(TestCase):
    def setUp(self):
        self.closer = User.objects.create_user(username="closer", password="pw", role=UserRole.AGENT)
        self.worker = User.objects.create_user(username="worker", password="pw", role=UserRole.AGENT)
        self.idle = User.objects.create_user(username="idle", password="pw", role=UserRole.AGENT)
        for u, name in ((self.closer, "Closer"), (self.worker, "Worker"), (self.idle, "Idle")):
            ConsultantProfile.objects.create(user=u, full_name=name, branch="C", hired_at=date.today())
        self.prop = Property.objects.create(
            title="P",
            internal_code="RK-1",
            consultant=self.closer,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=1,
            area=80,
            address="a",
            neighborhood="N",
        )

    def test_closed_deal_beats_completed_work(self):
        Listing.objects.create(
            property=self.prop,
            title="Sold",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.closer,
            assigned_to=self.closer,
            status=Listing.Status.SOLD,
            sale_price=1_000_000_000,
        )
        FollowUp.objects.create(
            title="done",
            consultant=self.worker,
            contact_name="c",
            status=FollowUpStatus.COMPLETED,
        )
        closer = consultant_ranking_metrics(self.closer)
        worker = consultant_ranking_metrics(self.worker)
        self.assertEqual(closer["closedDealsCount"], 1)
        self.assertEqual(closer["headlineLabel"], "معاملات بسته‌شده")
        self.assertEqual(worker["closedDealsCount"], 0)
        self.assertEqual(worker["headlineLabel"], "کارهای تکمیل‌شده")
        self.assertGreater(worker["completedWorkCount"], 0)
        self.assertGreater(
            (closer["closedDealsCount"], closer["completedWorkCount"], -closer["overdueWorkCount"]),
            (worker["closedDealsCount"], worker["completedWorkCount"], -worker["overdueWorkCount"]),
        )

    def test_completed_work_ranks_when_no_sales(self):
        FollowUp.objects.create(
            title="one",
            consultant=self.worker,
            contact_name="c",
            status=FollowUpStatus.COMPLETED,
        )
        FollowUp.objects.create(
            title="two",
            consultant=self.worker,
            contact_name="c",
            status=FollowUpStatus.COMPLETED,
        )
        idle = consultant_ranking_metrics(self.idle)
        worker = consultant_ranking_metrics(self.worker)
        self.assertEqual(idle["headlineValue"], 0)
        self.assertEqual(worker["completedWorkCount"], 2)
        self.assertGreater(worker["completedWorkCount"], idle["completedWorkCount"])

    def test_overdue_is_tie_breaker(self):
        Task.objects.create(
            title="late",
            assigned_to=self.worker,
            created_by=self.worker,
            due_date=date.today() - timedelta(days=2),
            status=Task.Status.PENDING,
        )
        late = consultant_ranking_metrics(self.worker)
        clean = consultant_ranking_metrics(self.idle)
        self.assertGreater(late["overdueWorkCount"], clean["overdueWorkCount"])
        self.assertEqual(late["closedDealsCount"], clean["closedDealsCount"])
        self.assertLess(
            -late["overdueWorkCount"],
            -clean["overdueWorkCount"],
        )
