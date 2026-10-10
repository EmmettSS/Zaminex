import datetime
import io
import json
from unittest import mock

from django.core.cache import cache as django_cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import ConsultantProfile, User, UserRole
from apps.common import cache_utils
from apps.analytics.metrics import (
    build_neighborhood_price_stats_map,
    cached_neighborhood_price_stats_map,
)
from apps.followups.models import FollowUp
from apps.listings.models import Listing
from apps.properties.models import Property, PropertyImage
from apps.reports.caching import (
    cached_consultant_scope_report,
    cached_property_report,
)
from apps.reports.services import (
    compute_consultant_scope_report,
    compute_property_report,
)
from apps.tasks.models import Task

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000a0000000a0802000000025058ea"
    "0000001249444154789c63fccf800f30e1951db1d200412c0113b10a73130000000049454e44ae426082"
)


class _DeadCache:
    def __getattr__(self, _name):
        raise ConnectionError("redis is down")


class Phase4Base(TestCase):
    def setUp(self):
        call_command("seed_basics", stdout=io.StringIO())
        django_cache.clear()
        self.admin = User.objects.create_user(
            username="p4-admin", password="pw", role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="p4-agent", password="pw", role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="آگنت", branch="مرکزی")
        self.agent2 = User.objects.create_user(
            username="p4-agent2", password="pw", role=UserRole.AGENT
        )
        self.prop = Property.objects.create(
            title="آپارتمان پ4",
            internal_code="ZF_4101",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=1_000_000_000,
            area=100,
            rooms=2,
            address="آدرس",
            neighborhood="نیاوران",
            latitude=35.7,
            longitude=51.4,
        )
        self.prop2 = Property.objects.create(
            title="ویلا پ4",
            internal_code="ZF_4102",
            consultant=self.agent2,
            property_type=Property.PropertyType.VILLA,
            deal_type=Property.DealType.SALE,
            price=2_000_000_000,
            area=200,
            rooms=4,
            address="آدرس2",
            neighborhood="نیاوران",
        )
        self.listing = Listing.objects.create(
            property=self.prop,
            title="فروش پ4",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            sale_price=1_000_000_000,
        )
        self.task = Task.objects.create(
            title="مراجعه پ4",
            task_type=Task.TaskType.VIEWING,
            status=Task.Status.PENDING,
            priority=Task.Priority.MEDIUM,
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today(),
        )
        self.followup = FollowUp.objects.create(
            title="پیگیری پ4",
            consultant=self.agent,
            property=self.prop,
            contact_name="مالک",
        )


class PropertyReportCacheTests(Phase4Base):
    def test_second_read_is_a_cache_hit(self):
        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m:
            r1 = cached_property_report(self.prop)
            r2 = cached_property_report(self.prop)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(r1, r2)

    def test_range_variants_coexist(self):
        from datetime import date

        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m:
            r1 = cached_property_report(self.prop, filters={"date_from": date(2026, 1, 1)})
            r2 = cached_property_report(self.prop, filters={"date_to": date(2026, 6, 30)})
            r1b = cached_property_report(self.prop, filters={"date_from": date(2026, 1, 1)})

        self.assertEqual(m.call_count, 2)
        self.assertEqual(r1, r1b)
        self.assertEqual(r1["meta"]["filters"]["date_from"], "2026-01-01")
        self.assertNotIn("date_from", r2["meta"]["filters"])

    def test_listing_save_invalidates_the_report(self):
        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m:
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 1)
            self.listing.save()
            cached_property_report(self.prop)
        self.assertEqual(m.call_count, 2)

    def test_every_related_model_invalidates(self):
        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m:
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 1)

            self.prop.save()
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 2)

            self.task.save()
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 3)

            self.followup.save()
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 4)

            image = PropertyImage.objects.create(
                property=self.prop, image=SimpleUploadedFile("p4.png", _PNG)
            )
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 5)

            image.delete()
            cached_property_report(self.prop)
        self.assertEqual(m.call_count, 6)

    def test_fail_open_with_dead_cache(self):
        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m, mock.patch.object(
            cache_utils, "_cache", return_value=_DeadCache()
        ):
            r1 = cached_property_report(self.prop)
            r2 = cached_property_report(self.prop)
        self.assertEqual(m.call_count, 2)
        r1["meta"].pop("generatedAt", None)
        r2["meta"].pop("generatedAt", None)
        self.assertEqual(r1, r2)


class ScopeReportCacheTests(Phase4Base):
    def test_second_read_is_a_cache_hit(self):
        with mock.patch(
            "apps.reports.caching.compute_consultant_scope_report",
            wraps=compute_consultant_scope_report,
        ) as m:
            r1 = cached_consultant_scope_report(self.agent)
            r2 = cached_consultant_scope_report(self.agent)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(r1, r2)

    def test_task_save_invalidates(self):
        with mock.patch(
            "apps.reports.caching.compute_consultant_scope_report",
            wraps=compute_consultant_scope_report,
        ) as m:
            cached_consultant_scope_report(self.agent)
            self.assertEqual(m.call_count, 1)
            self.task.save()
            cached_consultant_scope_report(self.agent)
        self.assertEqual(m.call_count, 2)

    def test_per_user_keys_do_not_leak(self):
        r_agent = cached_consultant_scope_report(self.agent)
        r_admin = cached_consultant_scope_report(self.admin)
        self.assertEqual(r_agent["meta"]["scope"], "OWNED")
        self.assertEqual(r_admin["meta"]["scope"], "ALL")


class StatsMapCacheTests(Phase4Base):
    def test_second_read_is_a_cache_hit(self):
        with mock.patch(
            "apps.analytics.metrics.build_neighborhood_price_stats_map",
            wraps=build_neighborhood_price_stats_map,
        ) as m:
            s1 = cached_neighborhood_price_stats_map()
            s2 = cached_neighborhood_price_stats_map()
        self.assertEqual(m.call_count, 1)
        self.assertEqual(s1, s2)
        self.assertIn("نیاوران", s1)

    def test_listing_save_invalidates(self):
        with mock.patch(
            "apps.analytics.metrics.build_neighborhood_price_stats_map",
            wraps=build_neighborhood_price_stats_map,
        ) as m:
            cached_neighborhood_price_stats_map()
            self.assertEqual(m.call_count, 1)
            self.listing.save()
            cached_neighborhood_price_stats_map()
        self.assertEqual(m.call_count, 2)

    def test_property_save_invalidates(self):
        with mock.patch(
            "apps.analytics.metrics.build_neighborhood_price_stats_map",
            wraps=build_neighborhood_price_stats_map,
        ) as m:
            cached_neighborhood_price_stats_map()
            self.prop.save()
            cached_neighborhood_price_stats_map()
        self.assertEqual(m.call_count, 2)

    def test_fail_open_with_dead_cache(self):
        with mock.patch(
            "apps.analytics.metrics.build_neighborhood_price_stats_map",
            wraps=build_neighborhood_price_stats_map,
        ) as m, mock.patch.object(
            cache_utils, "_cache", return_value=_DeadCache()
        ):
            s1 = cached_neighborhood_price_stats_map()
            s2 = cached_neighborhood_price_stats_map()
        self.assertEqual(m.call_count, 2)
        self.assertEqual(s1, s2)


class DashboardCacheTests(Phase4Base):
    def _get(self, client):
        with CaptureQueriesContext(connection) as ctx:
            res = client.get("/common/api/analytics/dashboard/")
        self.assertEqual(res.status_code, 200)
        return res.json(), len(ctx.captured_queries)

    def test_second_read_is_a_cache_hit(self):
        client = Client(SERVER_NAME="localhost")
        client.force_login(self.agent)

        bundle1, queries1 = self._get(client)
        bundle2, queries2 = self._get(client)

        self.assertEqual(bundle1, bundle2)
        self.assertLess(queries2, queries1)

    def test_listing_save_invalidates(self):
        client = Client(SERVER_NAME="localhost")
        client.force_login(self.agent)

        _, queries1 = self._get(client)
        _, queries2 = self._get(client)
        self.assertLess(queries2, queries1)

        self.listing.save()
        _, queries3 = self._get(client)
        self.assertGreater(queries3, queries2)

    def test_dashboard_is_per_user(self):
        admin_client = Client(SERVER_NAME="localhost")
        admin_client.force_login(self.admin)
        agent_client = Client(SERVER_NAME="localhost")
        agent_client.force_login(self.agent)

        admin_bundle, admin_q1 = self._get(admin_client)
        agent_bundle, _ = self._get(agent_client)

        self.assertNotEqual(
            admin_bundle["kpis"]["totalProperties"],
            agent_bundle["kpis"]["totalProperties"],
        )
        self.assertEqual(admin_bundle["kpis"]["totalProperties"], 2)
        self.assertEqual(agent_bundle["kpis"]["totalProperties"], 1)

        agent_bundle2, _ = self._get(agent_client)
        self.assertEqual(agent_bundle2, agent_bundle)
        self.assertEqual(agent_bundle2["kpis"]["totalProperties"], 1)


class InvalidationFailOpenTests(Phase4Base):
    def test_saves_succeed_with_a_dead_cache(self):
        with mock.patch.object(cache_utils, "_cache", return_value=_DeadCache()):
            self.listing.save()
            self.task.save()
            self.prop.save()
            image = PropertyImage.objects.create(
                property=self.prop, image=SimpleUploadedFile("p4f.png", _PNG)
            )
            image.delete()
        self.assertIsNotNone(self.listing.pk)
        self.assertEqual(
            PropertyImage.objects.filter(property=self.prop).count(), 0
        )

    def test_dashboard_succeeds_with_a_dead_cache(self):
        client = Client(SERVER_NAME="localhost")
        client.force_login(self.agent)
        with mock.patch.object(cache_utils, "_cache", return_value=_DeadCache()):
            res = client.get("/common/api/analytics/dashboard/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("kpis", res.json())


class PropertyImageReorderInvalidationTests(Phase4Base):
    URL_TMPL = "/properties/api/properties/{pk}/images-reorder/"

    def setUp(self):
        super().setUp()
        self.images = [
            PropertyImage.objects.create(
                property=self.prop,
                image=SimpleUploadedFile(f"p4-{i}.png", _PNG),
                sort_order=i,
            )
            for i in range(3)
        ]
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.agent)

    def _reorder(self, order, client=None):
        return (client or self.client).patch(
            self.URL_TMPL.format(pk=self.prop.pk),
            data=json.dumps({"order": order}),
            content_type="application/json",
        )

    def _report_key(self):
        return cache_utils.make_key("report", "property", self.prop.pk)

    def test_reorder_drops_the_cached_property_report(self):
        with mock.patch(
            "apps.reports.caching.compute_property_report",
            wraps=compute_property_report,
        ) as m:
            cached_property_report(self.prop)
            self.assertEqual(m.call_count, 1)

            res = self._reorder([{"id": self.images[2].pk, "sort_order": 0}])
            self.assertEqual(res.status_code, 200)
            self.assertEqual(
                PropertyImage.objects.get(pk=self.images[2].pk).sort_order, 0
            )

            cached_property_report(self.prop)
        self.assertEqual(m.call_count, 2, "the report must be recomputed, not served stale")

    def test_reorder_drops_the_consultant_and_dashboard_keys(self):
        for domain in ("report:consultant", "dashboard"):
            key = cache_utils.make_key(*domain.split(":"), self.agent.pk)
            cache_utils.cache_set(key, {"seeded": True}, 120)
            self.assertIsNotNone(cache_utils.cache_get(key))

        self.assertEqual(
            self._reorder([{"id": self.images[0].pk, "sort_order": 9}]).status_code, 200
        )
        for domain in ("report:consultant", "dashboard"):
            key = cache_utils.make_key(*domain.split(":"), self.agent.pk)
            self.assertIsNone(cache_utils.cache_get(key), domain)

    def test_a_noop_payload_leaves_the_cache_alone(self):
        cache_utils.cache_set(self._report_key(), {"seeded": True}, 120)
        res = self._reorder([{"id": None, "sort_order": None}])
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(cache_utils.cache_get(self._report_key()))

    def test_a_rejected_reorder_leaves_the_cache_alone(self):
        cache_utils.cache_set(self._report_key(), {"seeded": True}, 120)
        intruder = Client(SERVER_NAME="localhost")
        intruder.force_login(self.agent2)
        res = self._reorder([{"id": self.images[0].pk, "sort_order": 9}], client=intruder)
        self.assertIn(res.status_code, (403, 404))
        self.assertEqual(
            PropertyImage.objects.get(pk=self.images[0].pk).sort_order, 0, "no write"
        )
        self.assertIsNotNone(cache_utils.cache_get(self._report_key()))

    def test_invalidation_survives_a_dead_cache(self):
        with mock.patch.object(cache_utils, "_cache", return_value=_DeadCache()):
            res = self._reorder([{"id": self.images[1].pk, "sort_order": 7}])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(PropertyImage.objects.get(pk=self.images[1].pk).sort_order, 7)
