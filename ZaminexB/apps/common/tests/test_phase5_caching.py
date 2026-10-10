import datetime
from unittest import mock

from django.core.cache import cache as django_cache
from django.db import connection
from django.test import TestCase, Client
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User, UserRole
from apps.basics.models import (
    Attribute,
    City,
    DealType,
    District,
    Province,
    PropertyType,
    PropertyUsage,
)
from apps.basics import views as basics_views
from apps.common import cache_utils
from apps.properties.models import Property
from apps.tickets import services as ticket_services

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000a0000000a0802000000025058ea"
    "0000001249444154789c63fccf800f30e1951db1d200412c0113b10a73130000000049454e44ae426082"
)


class _DeadCache:
    def __getattr__(self, _name):
        raise ConnectionError("redis is down")


class Phase5Base(TestCase):
    def setUp(self):
        django_cache.clear()
        self.admin = User.objects.create_user(
            username="p5-admin", password="pw", role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="p5-agent", password="pw", role=UserRole.AGENT
        )
        self.client = Client(SERVER_NAME="localhost")
        self.client.force_login(self.admin)


class ReferenceCatalogTests(Phase5Base):
    def test_second_read_is_a_hit(self):
        calls = []
        with mock.patch.object(
            basics_views, "_build_catalog_payload", side_effect=lambda: calls.append(1) or {"usages": []}
        ):
            r1 = self.client.get("/basics/api/catalog/")
            r2 = self.client.get("/basics/api/catalog/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(calls, [1])
        self.assertEqual(r1.json(), r2.json())

    def test_location_tree_second_read_is_a_hit(self):
        calls = []
        with mock.patch.object(
            basics_views, "_build_location_tree_payload", side_effect=lambda: calls.append(1) or []
        ):
            r1 = self.client.get("/basics/api/locations/")
            r2 = self.client.get("/basics/api/locations/")
        self.assertEqual(calls, [1])
        self.assertEqual(r1.json(), r2.json())

    def test_property_form_schema_is_cached_per_type(self):
        usage = PropertyUsage.objects.create(name="res", display_name="مسکونی")
        t1 = PropertyType.objects.create(
            name="apartment", display_name="آپارتمان", property_usage=usage
        )
        t2 = PropertyType.objects.create(
            name="villa", display_name="ویلا", property_usage=usage
        )
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_property_form_payload",
            side_effect=lambda pt: calls.append(pt.pk) or {"propertyType": {"id": pt.pk}},
        ):
            self.client.get(f"/basics/api/schema/property-form/?propertyType={t1.pk}")
            self.client.get(f"/basics/api/schema/property-form/?propertyType={t2.pk}")
            
            r1 = self.client.get(f"/basics/api/schema/property-form/?propertyType={t1.pk}")
            r2 = self.client.get(f"/basics/api/schema/property-form/?propertyType={t2.pk}")
        self.assertEqual(calls, [t1.pk, t2.pk])
        self.assertEqual(r1.json()["propertyType"]["id"], t1.pk)
        self.assertEqual(r2.json()["propertyType"]["id"], t2.pk)

    def test_listing_form_and_search_schema_cached_per_type(self):
        dt1 = DealType.objects.create(name="sale", display_name="فروش")
        dt2 = DealType.objects.create(name="rent", display_name="اجاره")
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_listing_form_payload",
            side_effect=lambda dt: calls.append(("listing", dt.pk)) or {"dealType": {"id": dt.pk}},
        ):
            self.client.get(f"/basics/api/schema/listing-form/?dealType={dt1.pk}")
            self.client.get(f"/basics/api/schema/listing-form/?dealType={dt2.pk}")
            self.client.get(f"/basics/api/schema/listing-form/?dealType={dt1.pk}")
            self.client.get(f"/basics/api/schema/listing-form/?dealType={dt2.pk}")
        self.assertEqual(calls, [("listing", dt1.pk), ("listing", dt2.pk)])

        scalls = []
        with mock.patch.object(
            basics_views,
            "_build_search_payload",
            side_effect=lambda pt, dt: scalls.append((pt.pk if pt else None, dt.pk if dt else None)) or {"propertyFilters": [], "dealFilters": []},
        ):
            self.client.get("/basics/api/schema/search/")
            self.client.get(f"/basics/api/schema/search/?propertyType={PropertyType.objects.first().pk if PropertyType.objects.exists() else 999}")
            self.client.get("/basics/api/schema/search/")
            
        self.assertEqual(scalls.count((None, None)), 1)


class ReferenceInvalidationTests(Phase5Base):
    def _seed_reference(self):
        usage = PropertyUsage.objects.create(name="res", display_name="مسکونی")
        self.pt = PropertyType.objects.create(
            name="apartment", display_name="آپارتمان", property_usage=usage
        )
        self.dt = DealType.objects.create(name="sale", display_name="فروش")
        self.province = Province.objects.create(name="tehran", display_name="تهران")
        self.city = City.objects.create(
            name="tehran-city", display_name="تهران", province=self.province
        )
        self.district = District.objects.create(
            name="niaوران-x", display_name="نیاوران", city=self.city
        )
        self.attribute = Attribute.objects.create(
            name="balcony", display_name="بalkonی".replace("alkon", "الکون")
        )

    def test_property_type_save_invalidates_schemas_and_catalog(self):
        self._seed_reference()
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_property_form_payload",
            side_effect=lambda pt: calls.append("form") or {"fields": []},
        ), mock.patch.object(
            basics_views, "_build_catalog_payload", side_effect=lambda: calls.append("catalog") or {"usages": []}
        ):
            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
            self.client.get("/basics/api/catalog/")
            self.assertEqual(calls, ["form", "catalog"])

            self.pt.display_name = "آپارتمان جدید"
            self.pt.save()

            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
            self.client.get("/basics/api/catalog/")
        self.assertEqual(calls, ["form", "catalog", "form", "catalog"])

    def test_district_save_invalidates_the_location_tree(self):
        self._seed_reference()
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_location_tree_payload",
            side_effect=lambda: calls.append(1) or [],
        ):
            self.client.get("/basics/api/locations/")
            self.assertEqual(calls, [1])

            self.district.display_name = "نیاوران جدید"
            self.district.save()

            self.client.get("/basics/api/locations/")
        self.assertEqual(calls, [1, 1])

    def test_attribute_save_invalidates_the_form_schema(self):
        self._seed_reference()
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_property_form_payload",
            side_effect=lambda pt: calls.append(1) or {"fields": []},
        ):
            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
            self.assertEqual(calls, [1])

            self.attribute.display_name = "بالکن"
            self.attribute.save()

            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
        self.assertEqual(calls, [1, 1])

    def test_deal_type_delete_invalidates_the_listing_schema(self):
        self._seed_reference()
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_listing_form_payload",
            side_effect=lambda dt: calls.append(1) or {"fields": []},
        ):
            self.client.get(f"/basics/api/schema/listing-form/?dealType={self.dt.pk}")
            self.assertEqual(calls, [1])

            self.dt.delete()

            res = self.client.get(f"/basics/api/schema/listing-form/?dealType={self.dt.pk}")
            self.assertEqual(res.status_code, 404)
        self.assertEqual(calls, [1])
        key = cache_utils.make_key("schema", "listing-form", self.dt.pk)
        self.assertIsNone(cache_utils.cache_get(key))

    def test_reorder_invalidates_the_form_schema(self):
        self._seed_reference()
        from apps.basics.models import PropertyTypeAttribute

        link = PropertyTypeAttribute.objects.create(
            property_type=self.pt, attribute=self.attribute, sort_order=1
        )
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_property_form_payload",
            side_effect=lambda pt: calls.append(1) or {"fields": []},
        ):
            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
            self.assertEqual(calls, [1])

            res = self.client.post(
                "/basics/api/property-type-attributes/reorder/",
                data={"order": [{"id": link.pk, "sortOrder": 2}]},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(PropertyTypeAttribute.objects.get(pk=link.pk).sort_order, 2)

            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
        self.assertEqual(calls, [1, 1])

    def test_reorder_noop_payload_keeps_the_cache(self):
        self._seed_reference()
        calls = []
        with mock.patch.object(
            basics_views,
            "_build_property_form_payload",
            side_effect=lambda pt: calls.append(1) or {"fields": []},
        ):
            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
            res = self.client.post(
                "/basics/api/property-type-attributes/reorder/",
                data={"order": []},
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 200)
            self.client.get(f"/basics/api/schema/property-form/?propertyType={self.pt.pk}")
        self.assertEqual(calls, [1])


class PollCacheTests(Phase5Base):
    def test_notifications_poll_second_read_is_a_hit(self):
        from apps.notifications.models import Notification

        Notification.objects.create(
            user=self.agent,
            type=Notification.NotificationType.TASK_ASSIGNED,
            title="سلام",
            message="تست",
        )
        self.client.force_login(self.agent)
        with CaptureQueriesContext(connection) as ctx1:
            r1 = self.client.get("/common/api/notifications/")
        with CaptureQueriesContext(connection) as ctx2:
            r2 = self.client.get("/common/api/notifications/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json(), r2.json())
        self.assertLess(len(ctx2.captured_queries), len(ctx1.captured_queries))

    def test_notifications_are_isolated_per_user(self):
        from apps.notifications.models import Notification

        Notification.objects.create(
            user=self.admin,
            type=Notification.NotificationType.TASK_ASSIGNED,
            title="برای مدیر",
            message="a",
        )
        Notification.objects.create(
            user=self.agent,
            type=Notification.NotificationType.TASK_ASSIGNED,
            title="برای مشاور",
            message="b",
        )
        self.client.force_login(self.agent)
        res_agent = self.client.get("/common/api/notifications/")
        agent_titles = [n["title"] for n in res_agent.json()["notifications"]]
        self.assertEqual(agent_titles, ["برای مشاور"])

        admin_client = Client(SERVER_NAME="localhost")
        admin_client.force_login(self.admin)
        res_admin = admin_client.get("/common/api/notifications/")
        admin_titles = [n["title"] for n in res_admin.json()["notifications"]]
        self.assertEqual(admin_titles, ["برای مدیر"])

    def test_mark_read_invalidates_the_notifications_poll(self):
        from apps.notifications.models import Notification

        notif = Notification.objects.create(
            user=self.agent,
            type=Notification.NotificationType.TASK_ASSIGNED,
            title="خوانده نشده",
            message="x",
        )
        self.client.force_login(self.agent)
        r1 = self.client.get("/common/api/notifications/")
        self.assertEqual(r1.json()["unreadCount"], 1)
        res = self.client.post(f"/common/api/notifications/{notif.pk}/read/")
        self.assertEqual(res.status_code, 200)
        r2 = self.client.get("/common/api/notifications/")
        self.assertEqual(r2.json()["unreadCount"], 0)
        self.assertFalse(r2.json()["notifications"][0]["isRead"] is True and r1.json()["notifications"][0]["isRead"])

    def test_ticket_unread_poll_second_read_is_a_hit(self):
        with CaptureQueriesContext(connection) as ctx1:
            r1 = self.client.get("/tickets/api/unread-count/")
        with CaptureQueriesContext(connection) as ctx2:
            r2 = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(r1.json(), r2.json())
        self.assertLess(len(ctx2.captured_queries), len(ctx1.captured_queries))

    def test_mark_read_invalidates_the_ticket_unread_poll(self):
        from apps.tickets.models import (
            Ticket,
            TicketParticipant,
            TicketParticipantRole,
            TicketPriority,
            TicketStatus,
        )
        from apps.tickets.models import TicketSubject

        prop = Property.objects.create(
            title="ملک تیکت",
            internal_code="ZF_5901",
            consultant=self.agent,
            area=80,
            address="آدرس",
        )
        ticket = Ticket.objects.create(
            title="تیکت تست",
            ticket_type="OTHER",
            priority=TicketPriority.NORMAL,
            status=TicketStatus.OPEN,
            subject_type=TicketSubject.PROPERTY,
            subject_id=prop.pk,
            property=prop,
            created_by=self.admin,
        )
        TicketParticipant.objects.create(
            ticket=ticket,
            user=self.agent,
            role=TicketParticipantRole.RECIPIENT,
            is_read=False,
        )
        self.client.force_login(self.agent)
        r1 = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(r1.json()["count"], 1)

        ticket_services.mark_read(ticket=ticket, actor=self.agent)

        r2 = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(r2.json()["count"], 0)

    def test_poll_fail_open_with_dead_cache(self):
        from apps.notifications.models import Notification

        Notification.objects.create(
            user=self.agent,
            type=Notification.NotificationType.TASK_ASSIGNED,
            title="x",
            message="y",
        )
        self.client.force_login(self.agent)
        with mock.patch.object(cache_utils, "_cache", return_value=_DeadCache()):
            r1 = self.client.get("/common/api/notifications/")
            r2 = self.client.get("/common/api/notifications/")
            r3 = self.client.get("/tickets/api/unread-count/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.json()["unreadCount"], 1)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["count"], 0)


class CountCacheTests(Phase5Base):
    def _make_properties(self, n, consultant, offset=0):
        props = []
        for i in range(n):
            props.append(
                Property.objects.create(
                    title=f"ملک {offset + i}",
                    internal_code=f"ZF_5{offset + i:03d}",
                    consultant=consultant,
                    property_type=Property.PropertyType.APARTMENT,
                    deal_type=Property.DealType.SALE,
                    area=80,
                    address="آدرس",
                )
            )
        return props

    def test_count_is_cached_across_pages(self):
        self._make_properties(25, self.agent)
        with CaptureQueriesContext(connection) as ctx1:
            r1 = self.client.get("/properties/api/properties/?page=1&page_size=20")
        with CaptureQueriesContext(connection) as ctx2:
            r2 = self.client.get("/properties/api/properties/?page=2&page_size=20")
        self.assertEqual(r1.json()["count"], 25)
        self.assertEqual(r2.json()["count"], 25)
        self.assertLess(len(ctx2.captured_queries), len(ctx1.captured_queries))
        self.assertEqual(len(r2.json()["results"]), 5)

    def test_count_is_isolated_per_user(self):
        self._make_properties(25, self.agent)

        admin = self.admin
        for p in self._make_properties(5, admin, offset=1000):
            p.is_shared = False
            p.save(update_fields=["is_shared"])
            
        res_admin = self.client.get("/properties/api/properties/?page=1&page_size=20")
        self.assertEqual(res_admin.json()["count"], 30)

        agent_client = Client(SERVER_NAME="localhost")
        agent_client.force_login(self.agent)
        res_agent = agent_client.get("/properties/api/properties/?page=1&page_size=20")
        self.assertEqual(res_agent.json()["count"], 25)

    def test_count_is_isolated_per_filter(self):
        self._make_properties(5, self.agent)
        with CaptureQueriesContext(connection) as ctx1:
            r1 = self.client.get("/properties/api/properties/?page=1&page_size=20")
        with CaptureQueriesContext(connection) as ctx2:
            r2 = self.client.get(
                "/properties/api/properties/?page=1&page_size=20&propertyStatus=AVAILABLE"
            )

        self.assertEqual(r1.json()["count"], 5)
        self.assertEqual(r2.json()["count"], 5)
        
        count_queries = sum(
            1
            for q in ctx2.captured_queries
            if "COUNT(*)" in q["sql"].upper() and "properties_property" in q["sql"]
        )
        self.assertGreaterEqual(count_queries, 1)

    def test_count_cache_fail_open_with_dead_cache(self):
        self._make_properties(5, self.agent)
        with mock.patch.object(cache_utils, "_cache", return_value=_DeadCache()):
            r1 = self.client.get("/properties/api/properties/?page=1&page_size=20")
            r2 = self.client.get("/properties/api/properties/?page=1&page_size=20")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["count"], 5)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["count"], 5)

    def test_stale_count_never_breaks_a_request(self):
        self._make_properties(25, self.agent)
        r1 = self.client.get("/properties/api/properties/?page=2&page_size=20")
        self.assertEqual(r1.json()["count"], 25)
        self.assertEqual(len(r1.json()["results"]), 5)

        page2_ids = [r["id"] for r in r1.json()["results"]][:3]
        Property.objects.filter(id__in=page2_ids).delete()

        res = self.client.get("/properties/api/properties/?page=2&page_size=20")
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["results"]), 2)
