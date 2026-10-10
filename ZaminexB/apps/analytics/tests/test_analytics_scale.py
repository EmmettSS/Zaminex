from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache as django_cache
from rest_framework.test import APIClient

from apps.accounts.models import UserRole

from apps.analytics.metrics import (
    channel_marketing_summary,
    generated_high_prob_leads_for_listing,
    high_prob_leads_by_property,
    images_count_by_property,
    images_count_for_property,
    listing_marketing_metrics,
)
from apps.listings.models import Listing
from apps.properties.models import Property, PropertyImage

User = get_user_model()


class _AnalyticsDataMixin:
    def _make_users(self):
        self.admin = User.objects.create_user(
            username="scale_admin", password="pw", role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="scale_agent", password="pw", role=UserRole.AGENT
        )

    def _make_property(self, consultant, title, neighborhood="Saadat", price=1_000_000_000):
        return Property.objects.create(
            consultant=consultant,
            title=title,
            deal_type=Property.DealType.SALE,
            status=Property.Status.AVAILABLE,
            price=price,
            area=100,
            rooms=3,
            address=f"{title} address",
            neighborhood=neighborhood,
        )

    def _make_listing(self, prop, title, channel=Listing.PublishChannel.WEBSITE, **kwargs):
        return Listing.objects.create(
            property=prop,
            title=title,
            publish_channel=channel,
            created_by=self.agent,
            assigned_to=self.agent,
            start_date=timezone.now() - timedelta(days=10),
            **kwargs,
        )


class BatchedLookupEquivalenceTests(_AnalyticsDataMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.p1 = self._make_property(self.admin, "P1")
        self.p2 = self._make_property(self.admin, "P2")
        self.p3 = self._make_property(self.admin, "P3")

        from apps.followups.models import FollowUp

        for i, (probability, archived) in enumerate(
            ((90, False), (75, False), (40, False), (95, True))
        ):
            FollowUp.objects.create(
                title=f"F{i}",
                contact_name="مشتری",
                consultant=self.agent,
                property=self.p1,
                probability=probability,
                is_archived=archived,
            )
        FollowUp.objects.create(
            title="F-sole",
            contact_name="مشتری",
            consultant=self.agent,
            property=self.p2,
            probability=80,
            is_archived=False,
        )

        PropertyImage.objects.create(property=self.p1, image="a1.jpg", sort_order=0)
        PropertyImage.objects.create(property=self.p1, image="a2.jpg", sort_order=1)
        PropertyImage.objects.create(property=self.p2, image="b1.jpg", sort_order=0)

        self.l1 = self._make_listing(self.p1, "L1")
        self.l2 = self._make_listing(self.p2, "L2")
        self.l3 = self._make_listing(self.p3, "L3")

    def test_high_prob_map_matches_per_listing_count(self):
        batched = high_prob_leads_by_property([self.p1.id, self.p2.id, self.p3.id])
        for listing in (self.l1, self.l2, self.l3):
            self.assertEqual(
                generated_high_prob_leads_for_listing(listing, batched),
                generated_high_prob_leads_for_listing(listing),
                f"mismatch for listing {listing.id}",
            )
        self.assertEqual(batched[self.p1.id], 2)
        self.assertEqual(batched[self.p2.id], 1)
        self.assertNotIn(self.p3.id, batched)

    def test_high_prob_map_deduplicates_and_drops_none(self):
        ids = [self.p1.id, self.p1.id, None, 0, self.p2.id]
        batched = high_prob_leads_by_property(ids)
        self.assertEqual(batched, {self.p1.id: 2, self.p2.id: 1})

    def test_high_prob_map_empty_input(self):
        self.assertEqual(high_prob_leads_by_property([]), {})

    def test_images_map_matches_per_property_count(self):
        batched = images_count_by_property([self.p1.id, self.p2.id, self.p3.id])
        for prop in (self.p1, self.p2, self.p3):
            self.assertEqual(
                batched.get(prop.id, 0), images_count_for_property(prop)
            )
        self.assertEqual(batched, {self.p1.id: 2, self.p2.id: 1})

    def test_images_map_empty_input(self):
        self.assertEqual(images_count_by_property([]), {})

    def test_listing_metrics_identical_with_and_without_map(self):
        batched = high_prob_leads_by_property([self.p1.id, self.p2.id, self.p3.id])
        for listing in (self.l1, self.l2, self.l3):
            self.assertEqual(
                listing_marketing_metrics(listing, batched),
                listing_marketing_metrics(listing),
            )

    def test_channel_summary_identical_with_and_without_maps(self):
        listings = [self.l1, self.l2, self.l3]
        ids = [lst.property_id for lst in listings]
        self.assertEqual(
            channel_marketing_summary(
                listings, high_prob_leads_by_property(ids), images_count_by_property(ids)
            ),
            channel_marketing_summary(listings),
        )


class AnalyticsQueryScaleTests(_AnalyticsDataMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.props = [
            self._make_property(self.admin, f"P{i}", neighborhood=f"N{i % 3}")
            for i in range(6)
        ]
        for i, prop in enumerate(self.props):
            self._make_listing(
                prop,
                f"L{i}",
                channel=(
                    Listing.PublishChannel.WEBSITE
                    if i % 2
                    else Listing.PublishChannel.INSTAGRAM
                ),
            )
        django_cache.clear()

    def _query_count(self, path):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        warm = self.client.get(path)
        self.assertEqual(warm.status_code, 200)

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return len(ctx), response

    def test_listings_endpoint_query_count_is_bounded(self):
        with_page, _ = self._query_count("/common/api/analytics/listings/")
        self.assertLessEqual(with_page, 15, f"too many queries: {with_page}")

    def test_listings_queries_do_not_scale_with_rows(self):
        before, _ = self._query_count("/common/api/analytics/listings/")
        for i in range(24):
            self._make_listing(self.props[i % len(self.props)], f"X{i}")
        after, _ = self._query_count("/common/api/analytics/listings/")
        self.assertEqual(before, after, "query count grew with row count")

    def test_properties_endpoint_query_count_is_bounded(self):
        count, _ = self._query_count("/common/api/analytics/properties/")
        self.assertLessEqual(count, 15, f"too many queries: {count}")

    def test_properties_queries_do_not_scale_with_rows(self):
        before, _ = self._query_count("/common/api/analytics/properties/")
        for i in range(24):
            self._make_property(self.admin, f"Q{i}")
        after, _ = self._query_count("/common/api/analytics/properties/")
        self.assertEqual(before, after, "query count grew with row count")

    def test_dashboard_query_count_is_bounded(self):
        count, _ = self._query_count("/common/api/analytics/dashboard/")
        self.assertLessEqual(count, 60, f"too many queries: {count}")


class AnalyticsPaginationTests(_AnalyticsDataMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.props = [self._make_property(self.admin, f"P{i}") for i in range(25)]
        for i, prop in enumerate(self.props):
            self._make_listing(prop, f"L{i}")

    def test_properties_endpoint_uses_standard_envelope(self):
        response = self.client.get("/common/api/analytics/properties/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        self.assertEqual(data["count"], 25)
        self.assertEqual(len(data["results"]), 20, "default page size is 20")
        self.assertIsNotNone(data["next"])
        self.assertIsNone(data["previous"])

    def test_properties_second_page(self):
        response = self.client.get("/common/api/analytics/properties/?page=2")
        data = response.json()
        self.assertEqual(len(data["results"]), 5)
        self.assertIsNone(data["next"])
        self.assertIsNotNone(data["previous"])

    def test_listings_endpoint_uses_standard_envelope_and_keeps_channels(self):
        response = self.client.get("/common/api/analytics/listings/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data), {"count", "next", "previous", "results", "channels"}
        )
        self.assertEqual(data["count"], 25)
        self.assertEqual(len(data["results"]), 20)

    def test_channels_span_whole_table_not_just_the_page(self):
        response = self.client.get("/common/api/analytics/listings/")
        data = response.json()
        self.assertEqual(
            sum(row["listingCount"] for row in data["channels"]), 25
        )
        self.assertLess(len(data["results"]), 25, "precondition: page is partial")


class DashboardAggregateTests(_AnalyticsDataMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.props = [self._make_property(self.admin, f"P{i}") for i in range(7)]
        for i, prop in enumerate(self.props):
            self._make_listing(prop, f"L{i}")

    def _dashboard(self):
        django_cache.clear()
        response = self.client.get("/common/api/analytics/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_counts_are_whole_table(self):
        data = self._dashboard()
        self.assertEqual(data["propertyCount"], 7)
        self.assertEqual(data["listingCount"], 7)
        self.assertEqual(data["kpis"]["totalProperties"], 7)

    def test_hot_properties_capped_at_five(self):
        data = self._dashboard()
        self.assertLessEqual(len(data["hotProperties"]), 5)

    def test_hot_properties_carry_market_metrics(self):
        data = self._dashboard()
        for row in data["hotProperties"]:
            self.assertIn("engagementHeatScore", row)
            self.assertIn("pricePerSqm", row)
            self.assertIn("title", row)

    def test_channel_summary_present(self):
        data = self._dashboard()
        self.assertTrue(data["channelSummary"])
        self.assertEqual(
            sum(row["listingCount"] for row in data["channelSummary"]), 7
        )


class RoleScopingTests(_AnalyticsDataMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.other = User.objects.create_user(
            username="scale_other", password="pw", role=UserRole.AGENT
        )
        mine = self._make_property(self.agent, "Mine")
        theirs = self._make_property(self.other, "Theirs")
        self.mine_listing = self._make_listing(mine, "L-mine")
        Listing.objects.create(
            property=theirs,
            title="L-theirs",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.other,
            assigned_to=self.other,
            start_date=timezone.now() - timedelta(days=1),
        )

    def test_consultant_sees_only_own_rows(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.agent)
        props = self.client.get("/common/api/analytics/properties/").json()
        self.assertEqual(props["count"], 1)
        self.assertEqual(props["results"][0]["title"], "Mine")

        listings = self.client.get("/common/api/analytics/listings/").json()
        self.assertEqual(listings["count"], 1)
        self.assertEqual(listings["results"][0]["listingId"], self.mine_listing.id)
        self.assertEqual(
            sum(row["listingCount"] for row in listings["channels"]), 1
        )

    def test_admin_sees_everything(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get("/common/api/analytics/properties/").json()["count"], 2)
        self.assertEqual(self.client.get("/common/api/analytics/listings/").json()["count"], 2)
