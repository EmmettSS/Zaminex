import datetime
from decimal import Decimal

import jdatetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.analytics_views import _get_monthly_revenue, PERSIAN_MONTHS
from apps.listings.models import Listing
from apps.properties.models import Property

User = get_user_model()


class ListingSoldAndRevenueTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin_user", password="pw", role="ADMIN")
        self.agent = User.objects.create_user(username="agent_user", password="pw", role="AGENT")
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.property = Property.objects.create(
            title="آپارتمان نیاوران",
            internal_code="P-100",
            consultant=self.agent,
            area=120,
            address="تهران نیاوران",
        )

        self.listing_sale = Listing.objects.create(
            property=self.property,
            title="فروش آپارتمان نیاوران",
            publish_channel="WEBSITE",
            created_by=self.agent,
            status=Listing.Status.ACTIVE,
            sale_price=Decimal("5000000000"),
        )

        self.listing_rent = Listing.objects.create(
            property=self.property,
            title="اجاره آپارتمان نیاوران",
            publish_channel="WEBSITE",
            created_by=self.agent,
            status=Listing.Status.ACTIVE,
            deposit=Decimal("500000000"),
            monthly_rent=Decimal("10000000"),
        )

    def test_mark_listing_as_sold_action(self):
        resp = self.client.post(f"/listings/api/listings/{self.listing_sale.id}/sold/")
        self.assertEqual(resp.status_code, 200)
        self.listing_sale.refresh_from_db()
        self.assertEqual(self.listing_sale.status, Listing.Status.SOLD)
        self.assertEqual(self.listing_sale.property.status, Property.Status.SOLD)

    def test_set_status_to_sold_updates_related_property(self):
        # Setting a listing to SOLD via the generic set_status action must also
        # flip the linked property to SOLD, so the property mirrors the listing.
        resp = self.client.post(
            f"/listings/api/listings/{self.listing_sale.id}/set_status/",
            {"status": "SOLD"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.listing_sale.refresh_from_db()
        self.assertEqual(self.listing_sale.status, Listing.Status.SOLD)
        self.assertEqual(self.listing_sale.property.status, Property.Status.SOLD)

    def test_set_status_consultant_owner_can_change_status(self):
        # The consultant who created the listing may change its status too.
        client = APIClient()
        client.force_authenticate(user=self.agent)
        resp = client.post(
            f"/listings/api/listings/{self.listing_sale.id}/set_status/",
            {"status": "PAUSED"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.listing_sale.refresh_from_db()
        self.assertEqual(self.listing_sale.status, Listing.Status.PAUSED)

    def test_set_status_invalid_status_rejected(self):
        resp = self.client.post(
            f"/listings/api/listings/{self.listing_sale.id}/set_status/",
            {"status": "NOT_A_STATUS"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.listing_sale.refresh_from_db()
        self.assertEqual(self.listing_sale.status, Listing.Status.ACTIVE)


    def test_show_sold_filtering(self):
        # Mark listing_sale as sold
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        # By default (without show_sold), SOLD listings should be hidden
        res_default = self.client.get("/listings/api/listings/")
        self.assertEqual(res_default.status_code, 200)
        results = res_default.json()["results"]
        ids = [row["id"] for row in results]
        self.assertNotIn(self.listing_sale.id, ids)
        self.assertIn(self.listing_rent.id, ids)

        # With show_sold=true, ONLY SOLD listings should be shown
        res_sold = self.client.get("/listings/api/listings/?show_sold=true")
        self.assertEqual(res_sold.status_code, 200)
        sold_results = res_sold.json()["results"]
        sold_ids = [row["id"] for row in sold_results]
        self.assertIn(self.listing_sale.id, sold_ids)
        self.assertNotIn(self.listing_rent.id, sold_ids)

    def test_archived_listing_stays_in_default_list(self):
        """Archiving must not hide the listing from the default list."""
        self.listing_sale.status = Listing.Status.ARCHIVED
        self.listing_sale.save()

        res = self.client.get("/listings/api/listings/")
        self.assertEqual(res.status_code, 200)
        results = res.json()["results"]
        ids = [row["id"] for row in results]
        self.assertIn(self.listing_sale.id, ids)
        self.assertIn(self.listing_rent.id, ids)
        archived = next(row for row in results if row["id"] == self.listing_sale.id)
        self.assertEqual(archived["status"], "ARCHIVED")

    def test_status_filter_archived_only(self):
        self.listing_sale.status = Listing.Status.ARCHIVED
        self.listing_sale.save()

        res = self.client.get("/listings/api/listings/?status=ARCHIVED")
        self.assertEqual(res.status_code, 200)
        ids = [row["id"] for row in res.json()["results"]]
        self.assertIn(self.listing_sale.id, ids)
        self.assertNotIn(self.listing_rent.id, ids)

    def test_archive_action_then_list_shows_archived(self):
        resp = self.client.post(f"/listings/api/listings/{self.listing_sale.id}/archive/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ARCHIVED")

        res = self.client.get("/listings/api/listings/")
        self.assertEqual(res.status_code, 200)
        archived = next(row for row in res.json()["results"] if row["id"] == self.listing_sale.id)
        self.assertEqual(archived["status"], "ARCHIVED")

    def test_delete_removes_listing(self):
        listing_id = self.listing_sale.id
        resp = self.client.delete(f"/listings/api/listings/{listing_id}/")
        self.assertIn(resp.status_code, (200, 204))
        self.assertFalse(Listing.objects.filter(pk=listing_id).exists())

        res = self.client.get("/listings/api/listings/")
        self.assertEqual(res.status_code, 200)
        ids = [row["id"] for row in res.json()["results"]]
        self.assertNotIn(listing_id, ids)

    def test_consultant_sees_own_archived_and_can_delete(self):
        self.listing_sale.status = Listing.Status.ARCHIVED
        self.listing_sale.save()

        agent = APIClient()
        agent.force_authenticate(user=self.agent)
        res = agent.get("/listings/api/listings/")
        self.assertEqual(res.status_code, 200)
        results = res.json()["results"]
        ids = [row["id"] for row in results]
        self.assertIn(self.listing_sale.id, ids)
        archived = next(row for row in results if row["id"] == self.listing_sale.id)
        self.assertEqual(archived["status"], "ARCHIVED")

        listing_id = self.listing_sale.id
        resp = agent.delete(f"/listings/api/listings/{listing_id}/")
        self.assertIn(resp.status_code, (200, 204))
        self.assertFalse(Listing.objects.filter(pk=listing_id).exists())

    def test_property_filter_returns_all_pages_for_that_property(self):
        """`?property=` must hit the DB filter, not rely on the first page of 20."""
        other = Property.objects.create(
            title="ملک دیگر",
            internal_code="P-OTHER",
            consultant=self.agent,
            area=80,
            address="تهران",
        )
        extras = []
        for i in range(25):
            extras.append(
                Listing.objects.create(
                    property=other,
                    title=f"آگهی متفرقه {i}",
                    publish_channel="WEBSITE",
                    created_by=self.agent,
                    status=Listing.Status.ACTIVE,
                )
            )

        res = self.client.get(f"/listings/api/listings/?property={self.property.id}")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        results = payload["results"]
        ids = [row["id"] for row in results]
        self.assertIn(self.listing_sale.id, ids)
        self.assertIn(self.listing_rent.id, ids)
        self.assertEqual(payload["count"], 2)
        for extra in extras:
            self.assertNotIn(extra.id, ids)

    def test_property_filter_include_sold(self):
        """Property-scoped tab must be able to include SOLD listings."""
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        hidden = self.client.get(f"/listings/api/listings/?property={self.property.id}")
        self.assertEqual(hidden.status_code, 200)
        hidden_ids = [row["id"] for row in hidden.json()["results"]]
        self.assertNotIn(self.listing_sale.id, hidden_ids)
        self.assertIn(self.listing_rent.id, hidden_ids)

        shown = self.client.get(
            f"/listings/api/listings/?property={self.property.id}&include_sold=true&page_size=1000"
        )
        self.assertEqual(shown.status_code, 200)
        shown_payload = shown.json()
        shown_ids = [row["id"] for row in shown_payload["results"]]
        self.assertIn(self.listing_sale.id, shown_ids)
        self.assertIn(self.listing_rent.id, shown_ids)
        self.assertEqual(shown_payload["count"], 2)

    def test_sold_listing_detail_is_reachable(self):
        """The list hides sold rows by default; the detail page must still load."""
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        res = self.client.get(f"/listings/api/listings/{self.listing_sale.id}/")
        self.assertEqual(res.status_code, 200, res.content[:300])
        self.assertEqual(res.json()["id"], self.listing_sale.id)
        self.assertEqual(res.json()["status"], "SOLD")

        agent = APIClient()
        agent.force_authenticate(user=self.agent)
        res_agent = agent.get(f"/listings/api/listings/{self.listing_sale.id}/")
        self.assertEqual(res_agent.status_code, 200, res_agent.content[:300])
        self.assertEqual(res_agent.json()["status"], "SOLD")

    def test_monthly_revenue_calculation_includes_sale_and_rent(self):
        # Mark both as sold
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        self.listing_rent.status = Listing.Status.SOLD
        self.listing_rent.save()

        revenue_bundle = _get_monthly_revenue()
        revenue_data = revenue_bundle["months"]
        self.assertTrue(len(revenue_data) > 0)
        total_rev = sum(item["revenue"] for item in revenue_data)
        self.assertGreater(total_rev, 0)

    def test_revenue_chart_reflects_listing_reopened_to_active(self):
        """Reopening a SOLD listing must remove it from the sales chart."""
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        before = _get_monthly_revenue()["months"]
        self.assertEqual(sum(m["count"] for m in before), 1)
        self.assertGreater(sum(m["revenue"] for m in before), 0)

        # User changes the listing back to ACTIVE
        resp = self.client.post(
            f"/listings/api/listings/{self.listing_sale.id}/set_status/",
            {"status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        after = _get_monthly_revenue()["months"]
        self.assertEqual(sum(m["count"] for m in after), 0)
        self.assertEqual(sum(m["total"] for m in after), 0)

        self.property.refresh_from_db()
        self.assertNotEqual(self.property.status, Property.Status.SOLD)

    def test_revenue_chart_keeps_sold_property_when_other_listing_still_sold(self):
        """If two listings are SOLD and one is reopened, the property remains
        sold because another listing is still closed."""
        other = Listing.objects.create(
            property=self.property,
            title="فروش دیگر",
            publish_channel="WEBSITE",
            created_by=self.agent,
            status=Listing.Status.SOLD,
            sale_price=Decimal("4000000000"),
        )
        self.listing_sale.status = Listing.Status.SOLD
        self.listing_sale.save()

        resp = self.client.post(
            f"/listings/api/listings/{other.id}/set_status/",
            {"status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        after = _get_monthly_revenue()["months"]
        # The first sale listing is still SOLD and should remain.
        self.assertEqual(sum(m["count"] for m in after), 1)


class MonthlyRevenueJalaliTests(TestCase):
    """The revenue chart must follow the real Jalali (Shamsi) calendar:
    the current Persian month plus the five months before it, ordered
    oldest → newest (so the current month renders at the right in RTL).
    """

    @classmethod
    def setUpTestData(cls):
        cls.agent = User.objects.create_user(
            username="rev-agent", password="pw", role="AGENT"
        )

    @staticmethod
    def _force_updated(obj, jalali_ym):
        """Move an object's updated_at into a specific Jalali month.

        Uses queryset .update() to bypass the auto_now on save().
        """
        y, m = jalali_ym
        g = jdatetime.date(year=y, month=m, day=15).togregorian()
        dt = datetime.datetime.combine(
            g, datetime.time(12, 0, 0), tzinfo=timezone.get_current_timezone()
        )
        type(obj).objects.filter(pk=obj.pk).update(updated_at=dt)

    def _sold_listing(self, code, price):
        prop = Property.objects.create(
            title=f"ملک {code}", internal_code=code, consultant=self.agent,
            area=100, address="تهران", status=Property.Status.SOLD,
        )
        return Listing.objects.create(
            property=prop, title=f"آگهی {code}", publish_channel="WEBSITE",
            created_by=self.agent, status=Listing.Status.SOLD,
            sale_price=Decimal(str(price)),
        )

    def test_returns_exactly_six_months_with_current_jalali_month_last(self):
        jtoday = jdatetime.date.today()
        lst = self._sold_listing("R1", 1000000000)  # 1 billion
        self._force_updated(lst, (jtoday.year, jtoday.month))

        data = _get_monthly_revenue()["months"]
        self.assertEqual(len(data), 6, "chart must show exactly 6 months")

        expected = []
        for offset in range(-5, 1):
            m = jtoday.month + offset
            y = jtoday.year
            while m <= 0:
                m += 12
                y -= 1
            expected.append(PERSIAN_MONTHS[m - 1])

        self.assertEqual([d["month"] for d in data], expected)
        # current Jalali month is the last (right-most) bucket in RTL
        self.assertEqual(data[-1]["month"], PERSIAN_MONTHS[jtoday.month - 1])
        self.assertEqual(data[-1]["count"], 1)

    def test_sale_in_previous_jalali_month_lands_in_previous_bucket(self):
        jtoday = jdatetime.date.today()
        prev_m = jtoday.month - 1
        prev_y = jtoday.year
        if prev_m <= 0:
            prev_m += 12
            prev_y -= 1

        lst = self._sold_listing("R2", 2000000000)
        self._force_updated(lst, (prev_y, prev_m))

        data = _get_monthly_revenue()["months"]
        self.assertEqual(data[-2]["month"], PERSIAN_MONTHS[prev_m - 1])
        self.assertEqual(data[-2]["count"], 1)

    def test_oldest_bucket_wraps_year_correctly(self):
        jtoday = jdatetime.date.today()
        m = jtoday.month - 5
        y = jtoday.year
        while m <= 0:
            m += 12
            y -= 1

        lst = self._sold_listing("R3", 5000000000)
        self._force_updated(lst, (y, m))

        data = _get_monthly_revenue()["months"]
        self.assertEqual(data[0]["month"], PERSIAN_MONTHS[m - 1])
        self.assertEqual(data[0]["count"], 1)

    def test_count_and_revenue_include_sale_rent_mortgage(self):
        """The 'last 3 months' cards must count every property type priced in
        the chart: sale (sale_price), rent (deposit + monthly_rent*30) and
        rahn/mortgage (deposit). Volumes are grouped by deal type."""
        from apps.basics.models import DealType

        jtoday = jdatetime.date.today()

        deal_sale, _ = DealType.objects.get_or_create(
            name="sale",
            defaults={"display_name": "فروش", "sort_order": 1},
        )
        deal_mortgage_rent, _ = DealType.objects.get_or_create(
            name="mortgage_rent",
            defaults={"display_name": "رهن و اجاره", "sort_order": 2},
        )
        deal_full_mortgage, _ = DealType.objects.get_or_create(
            name="full_mortgage",
            defaults={"display_name": "رهن کامل", "sort_order": 3},
        )

        # Sale
        p1 = Property.objects.create(
            title="ملک فروش", internal_code="C1", consultant=self.agent,
            area=100, address="تهران", status=Property.Status.SOLD,
        )
        l1 = Listing.objects.create(
            property=p1, title="فروش", publish_channel="WEBSITE",
            created_by=self.agent, status=Listing.Status.SOLD,
            sale_price=Decimal("3000000000"), deal_type=deal_sale,
        )
        self._force_updated(l1, (jtoday.year, jtoday.month))

        # Rent (deposit + monthly_rent*30)
        p2 = Property.objects.create(
            title="ملک اجاره", internal_code="C2", consultant=self.agent,
            area=100, address="تهران", status=Property.Status.SOLD,
        )
        l2 = Listing.objects.create(
            property=p2, title="اجاره", publish_channel="WEBSITE",
            created_by=self.agent, status=Listing.Status.SOLD,
            deposit=Decimal("500000000"), monthly_rent=Decimal("10000000"),
            deal_type=deal_mortgage_rent,
        )
        self._force_updated(l2, (jtoday.year, jtoday.month))

        # Rahn / mortgage (deposit only)
        p3 = Property.objects.create(
            title="ملک رهن", internal_code="C3", consultant=self.agent,
            area=100, address="تهران", status=Property.Status.SOLD,
        )
        l3 = Listing.objects.create(
            property=p3, title="رهن", publish_channel="WEBSITE",
            created_by=self.agent, status=Listing.Status.SOLD,
            deposit=Decimal("2000000000"), deal_type=deal_full_mortgage,
        )
        self._force_updated(l3, (jtoday.year, jtoday.month))

        bundle = _get_monthly_revenue()
        data = bundle["months"]
        cur = data[-1]
        # 3 deals counted in the current month
        self.assertEqual(cur["count"], 3)
        # rent => 500M + (10M×30) = 800M; sale => 3000M; rahn => 2000M = 5.8B total
        self.assertEqual(cur["total"], 5800000000)

        # Per-deal-type breakdown must be present and add up to the total.
        deal_names = {dt["name"] for dt in bundle["dealTypes"]}
        self.assertIn("sale", deal_names)
        self.assertIn("mortgage_rent", deal_names)
        self.assertIn("full_mortgage", deal_names)
        volumes = cur["dealVolumes"]
        self.assertAlmostEqual(volumes["sale"], 3.0)
        self.assertAlmostEqual(volumes["mortgage_rent"], 0.8)
        self.assertAlmostEqual(volumes["full_mortgage"], 2.0)
