import csv
import datetime
import io
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, UserRole
from apps.activity.models import ActivityLog
from apps.followups.models import FollowUp
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

from .caching import cached_property_report
from .services import compute_property_report, get_property_for_user_or_403

User = get_user_model()


class ReportsServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="ag", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent, full_name="Agent A", branch="B"
        )
        self.agent2 = User.objects.create_user(
            username="ag2", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent2, full_name="Agent B", branch="B"
        )
        self.prop = Property.objects.create(
            title="Apt 1",
            internal_code="R1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("1000000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
        )
        
        Property.objects.create(
            title="Apt 2",
            internal_code="R2",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("800000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )
        Property.objects.create(
            title="Apt 3",
            internal_code="R3",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("900000000"),
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N1",
        )

        self.task_overdue = Task.objects.create(
            title="T1",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() - datetime.timedelta(days=3),
            task_type=Task.TaskType.VIEWING,
            status=Task.Status.PENDING,
        )
        self.task_done = Task.objects.create(
            title="T2",
            assigned_to=self.agent,
            created_by=self.agent,
            property=self.prop,
            due_date=datetime.date.today() + datetime.timedelta(days=2),
            task_type=Task.TaskType.DOCUMENT,
            status=Task.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        self.followup = FollowUp.objects.create(
            title="F1",
            consultant=self.agent,
            contact_name="c1",
            property=self.prop,
            probability=60,
            scheduled_at=timezone.now() - datetime.timedelta(days=2),
        )
        self.listing = Listing.objects.create(
            property=self.prop,
            title="L1",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent,
            assigned_to=self.agent,
            start_date=timezone.now() - datetime.timedelta(days=5),
        )

    def test_property_kpis_and_scoping(self):
        r = compute_property_report(self.prop)
        self.assertEqual(r["property"]["id"], self.prop.pk)
        self.assertEqual(r["kpis"]["tasksOverdueCount"], 1)
        self.assertEqual(r["kpis"]["followupsOverdueCount"], 1)
        self.assertEqual(r["kpis"]["imagesCount"], 0)
        self.assertEqual(r["kpis"]["pricePerSqm"], 10_000_000.0)
        self.assertTrue(r["kpis"]["geoPrecisionFlag"])
        self.assertEqual(r["kpis"]["listingCount"], 1)
        self.assertIn("tenureHistogram", r["charts"])
        self.assertIn("priceMap", r["charts"])
        self.assertEqual(len(r["charts"]["priceMap"]), 1)
        self.assertIsNotNone(r["kpis"]["priceDeviationIndex"])

    def test_agent_cannot_access_other_agents_property(self):
        with self.assertRaises(Exception):
            get_property_for_user_or_403(self.agent2, self.prop.pk)
        
        p = get_property_for_user_or_403(self.agent, self.prop.pk)
        self.assertEqual(p.pk, self.prop.pk)
        
        p2 = get_property_for_user_or_403(self.admin, self.prop.pk)
        self.assertEqual(p2.pk, self.prop.pk)

    def test_empty_state_no_listings_tasks_followups(self):
        prop2 = Property.objects.create(
            title="Bare",
            internal_code="R4",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.RENT,
            price=Decimal("0"),
            area=0,
            rooms=0,
            address="addr",
            neighborhood="Far",
        )
        r = compute_property_report(prop2)
        self.assertIsNone(r["kpis"]["pricePerSqm"])
        self.assertIsNone(r["kpis"]["priceDeviationIndex"])
        self.assertIsNone(r["kpis"]["listingBurnRate"])
        self.assertEqual(r["kpis"]["tasksOverdueCount"], 0)
        self.assertEqual(r["kpis"]["followupsOverdueCount"], 0)
        self.assertTrue(len(r["warnings"]) >= 1)
        self.assertEqual(r["charts"]["priceMap"], [])


class ReportsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="adm2", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="ag3", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(
            user=self.agent, full_name="A", branch="B"
        )
        self.prop = Property.objects.create(
            title="P",
            internal_code="M-1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("500000000"),
            area=50,
            rooms=1,
            address="addr",
            neighborhood="N",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
        )

    def test_auth_required(self):
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertIn(res.status_code, [401, 403])

    def test_agent_403_on_other_property(self):
        other = User.objects.create_user(
            username="ag4", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(user=other, full_name="X", branch="B")
        self.client.force_authenticate(user=other)
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_owner_can_fetch(self):
        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("kpis", data)
        self.assertIn("charts", data)

    def test_csv_export_returns_csv(self):
        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/export/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv; charset=utf-8")
        text = res.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        self.assertEqual(len(rows), 1)
        self.assertIn("شناسه ملک", rows[0])

    def test_csv_export_is_logged_in_activity(self):
        from apps.activity.models import ActivityLog

        self.client.force_authenticate(user=self.agent)
        url = f"/api/reports/properties/{self.prop.pk}/export/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

        entry = ActivityLog.objects.filter(
            action=ActivityLog.ActionType.EXPORT,
            target_type=ActivityLog.TargetType.PROPERTY,
            target_id=self.prop.pk,
        ).first()
        self.assertIsNotNone(entry, "CSV export must be recorded in the activity log")
        self.assertEqual(entry.user_id, self.agent.id)
        self.assertEqual(entry.metadata.get("format"), "csv")

    def test_scope_report_returns_metrics(self):
        self.client.force_authenticate(user=self.agent)
        res = self.client.get("/api/reports/scope/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["kpis"]["propertyCount"], 1)


class PropertyReportPrintTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="pradm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="prag1", password="x" * 10, role=UserRole.AGENT,
            first_name="Sara", last_name="A",
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="Sara A", branch="B")
        self.stranger = User.objects.create_user(
            username="prag2", password="x" * 10, role=UserRole.AGENT
        )
        ConsultantProfile.objects.create(user=self.stranger, full_name="Ali B", branch="B")
        self.prop = Property.objects.create(
            title="Apt",
            internal_code="PR-1",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
        )
        self.shared = Property.objects.create(
            title="Villa shared",
            internal_code="PR-2",
            consultant=self.agent,
            property_type=Property.PropertyType.VILLA,
            deal_type=Property.DealType.SALE,
            area=300,
            address="addr2",
            neighborhood="N2",
            is_shared=True,
        )

    @property
    def url(self):
        return f"/reports/properties/{self.prop.pk}/print/"

    def _html(self, res):
        return res.content.decode("utf-8")

    def test_admin_can_print_report(self):
        self.client.force_login(self.admin)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/html; charset=utf-8")
        html = self._html(res)
        self.assertIn("گزارش کامل ملک", html)
        self.assertIn("Apt", html)
        self.assertNotIn("%PDF-", html)

    def test_owner_consultant_can_print_report(self):
        self.client.force_login(self.agent)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/html; charset=utf-8")

    def test_shared_property_printable_by_other_consultant(self):
        self.client.force_login(self.stranger)
        res = self.client.get(f"/reports/properties/{self.shared.pk}/print/")
        self.assertEqual(res.status_code, 200, self._html(res)[:200])

    def test_stranger_cannot_print_non_shared(self):
        self.client.force_login(self.stranger)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 403)
        self.assertIn("دسترسی ندارید", self._html(res))
        self.assertFalse(
            ActivityLog.objects.filter(
                action=ActivityLog.ActionType.EXPORT,
                target_type=ActivityLog.TargetType.PROPERTY,
                target_id=self.prop.pk,
            ).exists(),
            "a denied print must not be logged",
        )

    def test_anonymous_is_redirected_to_login(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res["Location"])

    def test_unknown_property_is_404(self):
        self.client.force_login(self.admin)
        res = self.client.get("/reports/properties/999999/print/")
        self.assertEqual(res.status_code, 404)
        self.assertIn("ملک مورد نظر وجود ندارد.", self._html(res))

    def test_print_report_is_logged_in_activity(self):
        self.client.force_login(self.agent)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)

        entry = ActivityLog.objects.filter(
            action=ActivityLog.ActionType.EXPORT,
            target_type=ActivityLog.TargetType.PROPERTY,
            target_id=self.prop.pk,
        ).first()
        self.assertIsNotNone(entry, "a print must be recorded in the activity log")
        self.assertEqual(entry.user_id, self.agent.id)
        self.assertEqual(entry.metadata.get("format"), "print")

    def test_date_filters_are_forwarded(self):
        self.client.force_login(self.agent)
        res = self.client.get(self.url + "?date_from=2020-01-01&date_to=2020-12-31")
        self.assertEqual(res.status_code, 200)
        entry = ActivityLog.objects.filter(
            action=ActivityLog.ActionType.EXPORT, target_id=self.prop.pk
        ).first()
        self.assertEqual(entry.metadata.get("date_from"), "2020-01-01")
        self.assertEqual(entry.metadata.get("date_to"), "2020-12-31")

    def test_print_report_header_and_footer_customization(self):
        self.client.force_login(self.admin)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        html = self._html(res)

        self.assertNotIn('<footer class="print-footer">', html)
        self.assertNotIn(".print-footer", html)

        self.assertIn("@top-left", html)
        self.assertIn('id="doc-meta-generated-at"', html)

        self.assertIn("@bottom-left", html)
        self.assertIn("ساخته شده توسط CRM زمینکس", html)
        self.assertIn("@bottom-right", html)
        self.assertIn("counter(page)", html)


SECTION_HEADERS = [
    "۱. اطلاعات ملک",
    "۲. شاخص‌های کلیدی",
    "۳. آگهی‌های ملک",
    "۴. وظایف ملک",
    "۵. پیگیری‌های ملک",
    "۶. نمودارها",
    "۷. سابقه و لاگ‌های ملک",
]


class PropertyPrintContentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="prc-adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="prc-ag", password="x" * 10, role=UserRole.AGENT,
            first_name="Sara", last_name="A",
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="Sara A", branch="B")
        self.prop = Property.objects.create(
            title="Populated",
            internal_code="PR-POP",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            price=Decimal("2000000000"),
            area=120,
            rooms=3,
            address="addr",
            neighborhood="N",
            latitude=Decimal("35.7"),
            longitude=Decimal("51.4"),
            owner_first_name="Reza",
            owner_last_name="Kh",
            owner_phone="09120000000",
        )
        Listing.objects.create(
            property=self.prop, title="آگهی اصلی",
            publish_channel=Listing.PublishChannel.WEBSITE,
            created_by=self.agent, assigned_to=self.agent,
            start_date=timezone.now() - datetime.timedelta(days=5),
            sale_price=Decimal("2000000000"),
        )
        Task.objects.create(
            title="بازدید مشتری", assigned_to=self.agent, created_by=self.agent,
            property=self.prop, due_date=datetime.date.today() + datetime.timedelta(days=2),
            task_type=Task.TaskType.VIEWING, status=Task.Status.PENDING,
        )
        FollowUp.objects.create(
            title="پیگیری اول", consultant=self.agent, contact_name="مشتری",
            property=self.prop, probability=60,
            scheduled_at=timezone.now() - datetime.timedelta(days=2),
        )
        ActivityLog.objects.create(
            user=self.agent, action=ActivityLog.ActionType.CREATE,
            target_type=ActivityLog.TargetType.PROPERTY, target_id=self.prop.pk,
            description="ملک ایجاد شد",
        )

    def _html(self):
        res = self.client.get(f"/reports/properties/{self.prop.pk}/print/")
        self.assertEqual(res.status_code, 200, res.content[:200])
        return res.content.decode("utf-8")

    def test_populated_property_renders_the_full_report(self):
        self.client.force_login(self.admin)
        html = self._html()

        for token in (
            "گزارش کامل ملک",
            "Populated",
            self.prop.internal_code,
            "Sara A",
            "Reza Kh",
            "09120000000",
            "۱۲۰ متر مربع",
        ):
            with self.subTest(token=token):
                self.assertIn(token, html)

        for token in ("آگهی اصلی", "بازدید مشتری", "پیگیری اول", "ملک ایجاد شد"):
            with self.subTest(token=token):
                self.assertIn(token, html)

    def test_sections_are_complete_and_in_order(self):
        self.client.force_login(self.admin)
        html = self._html()
        positions = []
        for header in SECTION_HEADERS:
            self.assertIn(header, html)
            positions.append(html.index(header))
        self.assertEqual(positions, sorted(positions))

    def test_legacy_english_log_rows_render_persian(self):
        ActivityLog.objects.filter(
            target_type=ActivityLog.TargetType.PROPERTY, target_id=self.prop.pk
        ).delete()
        ActivityLog.objects.create(
            user=self.agent,
            action="status_change",
            target_type="property",
            target_id=self.prop.pk,
            description="وضعیت ملک «Populated» از AVAILABLE به RESERVED تغییر کرد",
        )
        self.client.force_login(self.admin)
        html = self._html()
        for token in ("AVAILABLE", "RESERVED", "Available", "Reserved"):
            self.assertNotIn(token, html)
        self.assertIn("آماده واگذاری", html)
        self.assertIn("رزرو شده", html)


class PropertyPrintEmptyHistoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="pre-adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="pre-ag", password="x" * 10, role=UserRole.AGENT,
            first_name="E", last_name="A",
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="E A", branch="B")
        self.prop = Property.objects.create(
            title="Empty",
            internal_code="PR-EMP",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            area=80,
            rooms=2,
            address="addr",
            neighborhood="N",
        )

    def test_empty_property_still_renders(self):
        self.client.force_login(self.admin)
        res = self.client.get(f"/reports/properties/{self.prop.pk}/print/")
        self.assertEqual(res.status_code, 200)
        html = res.content.decode("utf-8")
        for header in SECTION_HEADERS:
            self.assertIn(header, html)

    def test_history_tables_render_their_placeholders(self):
        self.client.force_login(self.admin)
        html = self.client.get(f"/reports/properties/{self.prop.pk}/print/").content.decode("utf-8")
        for placeholder in (
            "برای این ملک آگهی‌ای ثبت نشده است.",
            "برای این ملک وظیفه‌ای ثبت نشده است.",
            "برای این ملک پیگیری‌ای ثبت نشده است.",
        ):
            self.assertIn(placeholder, html)

    def test_logs_builder_returns_no_rows_when_history_is_empty(self):
        from .printing import build_print_report_context

        ActivityLog.objects.filter(
            target_type=ActivityLog.TargetType.PROPERTY, target_id=self.prop.pk
        ).delete()
        context = build_print_report_context(
            self.prop, compute_property_report(self.prop), self.admin
        )
        self.assertEqual(context["logs"], [])


class _AiTripwire(BaseException):
    """"""


class PropertyPrintHasNoAiSectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="prai-adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="prai-ag", password="x" * 10, role=UserRole.AGENT,
            first_name="A", last_name="I",
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="A I", branch="B")
        self.prop = Property.objects.create(
            title="AI Prop",
            internal_code="PR-AI",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N",
        )

    def _url(self):
        return f"/reports/properties/{self.prop.pk}/print/"

    def test_report_never_consults_the_ai_pipeline(self):
        boom = _AiTripwire("the print report must not touch the AI pipeline")
        with mock.patch("apps.analytics.views._property_ai_data", side_effect=boom), \
             mock.patch("apps.analytics.ai_service.peek_cached_description", side_effect=boom), \
             mock.patch("apps.analytics.ai_service.get_cached_description", side_effect=boom), \
             mock.patch("apps.analytics.ai_service.generate_description", side_effect=boom):
            self.client.force_login(self.admin)
            res = self.client.get(self._url())

        self.assertEqual(res.status_code, 200, res.content[:200])
        self.assertEqual(res["Content-Type"], "text/html; charset=utf-8")

    def test_cached_description_changes_nothing_in_the_report(self):
        from .printing import build_print_report_context

        def _context():
            return build_print_report_context(
                self.prop, cached_property_report(self.prop), self.admin
            )

        base = _context()
        with mock.patch(
            "apps.analytics.ai_service.peek_cached_description",
            return_value={
                "positives": [
                    "موقعیت مکانی مناسب و قیمت رقابتی",
                    "دسترسی مناسب به حمل‌ونقل عمومی",
                ],
                "negatives": ["روزهای حضور در بازار نسبتاً زیاد است"],
                "summary": (
                    "این ملک با متراژ مناسب در محله‌ای پویا قرار دارد و شاخص‌های "
                    "تعامل آن بالاتر از میانگین محله است."
                ),
            },
        ):
            enriched = _context()

        for key in (
            "header_title",
            "property_info",
            "kpis",
            "listings",
            "tasks",
            "followups",
            "charts",
            "logs",
        ):
            with self.subTest(section=key):
                self.assertEqual(enriched[key], base[key])

    def test_section_numbering_has_no_gap_after_the_removal(self):
        with mock.patch(
            "apps.analytics.ai_service.peek_cached_description",
            return_value={
                "positives": ["موقعیت مکانی مناسب"],
                "negatives": ["روزهای حضور در بازار زیاد است"],
                "summary": "خلاصه‌ی ساختگی برای این تست.",
            },
        ):
            self.client.force_login(self.admin)
            res = self.client.get(self._url())

        html = res.content.decode("utf-8")
        positions = []
        for header in SECTION_HEADERS:
            self.assertIn(header, html)
            positions.append(html.index(header))
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("توصیف هوش مصنوعی", html)
        self.assertNotIn("خلاصه‌ی ساختگی برای این تست.", html)


class PropertyPrintFontTests(TestCase):
    FONT_FILES = (
        "fonts/eot/IRAN-Rounded.eot",
        "fonts/woff/IRAN-Rounded.woff",
        "fonts/ttf/IRAN-Rounded.ttf",
    )

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="prf-adm", password="x" * 10, role=UserRole.ADMIN
        )
        self.agent = User.objects.create_user(
            username="prf-ag", password="x" * 10, role=UserRole.AGENT,
            first_name="F", last_name="A",
        )
        ConsultantProfile.objects.create(user=self.agent, full_name="F A", branch="B")
        self.prop = Property.objects.create(
            title="Font Prop",
            internal_code="PR-FNT",
            consultant=self.agent,
            property_type=Property.PropertyType.APARTMENT,
            deal_type=Property.DealType.SALE,
            area=100,
            rooms=2,
            address="addr",
            neighborhood="N",
        )

    def test_font_files_exist_and_are_referenced(self):
        for rel in self.FONT_FILES:
            with self.subTest(font=rel):
                self.assertTrue(
                    (Path(settings.BASE_DIR) / "static" / rel).is_file(),
                    f"the print report depends on the font file {rel}",
                )
        self.client.force_login(self.admin)
        html = self.client.get(f"/reports/properties/{self.prop.pk}/print/").content.decode("utf-8")
        self.assertIn("IRANRounded", html)
        for rel in self.FONT_FILES:
            with self.subTest(font=rel):
                self.assertIn(rel, html)


class PropertyReportAccessMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="mx-admin", password="x" * 10, role=UserRole.ADMIN
        )
        cls.a = User.objects.create_user(
            username="mx-a", password="x" * 10, role=UserRole.AGENT, first_name="A", last_name="X"
        )
        cls.b = User.objects.create_user(
            username="mx-b", password="x" * 10, role=UserRole.AGENT, first_name="B", last_name="X"
        )
        cls.c = User.objects.create_user(
            username="mx-c", password="x" * 10, role=UserRole.AGENT, first_name="C", last_name="X"
        )
        for user in (cls.a, cls.b, cls.c):
            ConsultantProfile.objects.create(user=user, full_name=user.first_name, branch="x")

        def mk(title, code, owner, shared=False):
            return Property.objects.create(
                title=title, internal_code=code, consultant=owner,
                property_type=Property.PropertyType.APARTMENT,
                deal_type=Property.DealType.SALE,
                price=Decimal("1000000000"), area=100, rooms=2,
                address="addr", neighborhood="n", is_shared=shared,
            )

        cls.p1 = mk("P1", "P1", cls.a, shared=False)
        cls.p2 = mk("P2", "P2", cls.a, shared=True)
        cls.p3 = mk("P3", "P3", cls.b, shared=False)

    def _statuses(self, user, prop):
        client = APIClient()
        client.force_authenticate(user=user)
        json_status = client.get(f"/api/reports/properties/{prop.pk}/").status_code
        csv_status = client.get(f"/api/reports/properties/{prop.pk}/export/").status_code
        html_client = Client()
        html_client.force_login(user)
        print_status = html_client.get(f"/reports/properties/{prop.pk}/print/").status_code
        return json_status, csv_status, print_status

    def test_access_matrix_is_consistent_across_formats(self):
        matrix = [
            (self.a, self.p1, 200),
            (self.a, self.p2, 200),
            (self.a, self.p3, 403),
            (self.b, self.p1, 403),
            (self.b, self.p2, 200),
            (self.b, self.p3, 200),
            (self.c, self.p1, 403),
            (self.c, self.p2, 200),
            (self.c, self.p3, 403),
        ]
        for user, prop, expected in matrix:
            with self.subTest(user=user.username, property=prop.internal_code):
                json_status, csv_status, print_status = self._statuses(user, prop)
                self.assertEqual(json_status, expected)
                self.assertEqual(csv_status, expected)
                self.assertEqual(print_status, expected)
                self.assertEqual(json_status, csv_status)
                self.assertEqual(csv_status, print_status)

    def test_admin_can_access_every_property(self):
        for prop in (self.p1, self.p2, self.p3):
            with self.subTest(property=prop.internal_code):
                json_status, csv_status, print_status = self._statuses(self.admin, prop)
                self.assertEqual(json_status, 200)
                self.assertEqual(csv_status, 200)
                self.assertEqual(print_status, 200)
