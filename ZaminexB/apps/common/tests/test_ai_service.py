"""Tests for the reusable AI description service and its endpoints."""

import io
import json
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import ConsultantProfile, User
from apps.basics.models import DealType
from apps.common.ai_service import (
    AIError,
    _extract_json,
    _parse_description,
    build_consultant_prompt,
    build_property_prompt,
    data_fingerprint,
    generate_description,
    get_cached_description,
    is_ai_configured,
)
from apps.common.models import CompanySettings
from apps.listings.models import Listing
from apps.properties.models import Property


class AIServiceUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())

    def setUp(self):
        s = CompanySettings.get_solo()
        s.ai_enabled = True
        s.ai_api_base_url = "https://mock.example/v1"
        s.ai_api_key = "test-key"
        s.ai_model = "test-model"
        s.save()

    def test_is_configured_reflects_fields(self):
        self.assertTrue(is_ai_configured())
        s = CompanySettings.get_solo()
        s.ai_enabled = False
        s.save()
        self.assertFalse(is_ai_configured())

    def test_is_configured_without_model_name(self):
        """Model name is optional — AI is configured even without it."""
        s = CompanySettings.get_solo()
        s.ai_model = ""
        s.save()
        self.assertTrue(is_ai_configured())

    def test_is_configured_requires_base_url(self):
        s = CompanySettings.get_solo()
        s.ai_api_base_url = ""
        s.save()
        self.assertFalse(is_ai_configured())

    def test_chat_payload_omits_model_when_empty(self):
        """When the model is empty, the request payload must not send model=''."""
        from apps.common import ai_service
        s = CompanySettings.get_solo()
        s.ai_model = ""
        s.save()

        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["headers"] = req.headers
            import io as _io
            from http.client import HTTPResponse
            # minimal response stub
            class R(HTTPResponse):
                def __init__(self, *a, **k):
                    self.body = _io.BytesIO(
                        b'{"choices":[{"message":{"content":"{\\"positives\\":[\\"a\\"],\\"negatives\\":[\\"b\\"],\\"summary\\":\\"s\\"}"}}]}'
                    )
                    self.msg = None
                def read(self, *a, **k):
                    return self.body.read()
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()

        with mock.patch("apps.common.ai_service._urlopen", side_effect=fake_urlopen):
            out = ai_service.generate_description({"x": 1}, entity="consultant")

        self.assertNotIn("model", captured["body"])
        self.assertEqual(out["summary"], "s")

    def test_chat_payload_includes_model_when_set(self):
        from apps.common import ai_service
        s = CompanySettings.get_solo()
        s.ai_model = "gpt-4o-mini"
        s.save()

        captured = {}

        def fake_urlopen(req, timeout):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            import io as _io
            from http.client import HTTPResponse
            class R(HTTPResponse):
                def __init__(self, *a, **k):
                    self.body = _io.BytesIO(
                        b'{"choices":[{"message":{"content":"{\\"positives\\":[\\"a\\"],\\"negatives\\":[\\"b\\"],\\"summary\\":\\"s\\"}"}}]}'
                    )
                    self.msg = None
                def read(self, *a, **k):
                    return self.body.read()
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()

        with mock.patch("apps.common.ai_service._urlopen", side_effect=fake_urlopen):
            ai_service.generate_description({"x": 1}, entity="consultant")

        self.assertEqual(captured["body"]["model"], "gpt-4o-mini")

    def test_generate_description_parses_clean_json(self):
        raw = '{"positives":["یک","دو","سه"],"negatives":["الف","ب","ج"],"summary":"خلاصه"}'
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw):
            out = generate_description({"kpis": {}}, entity="consultant")
        self.assertEqual(out["positives"], ["یک", "دو", "سه"])
        self.assertEqual(out["negatives"], ["الف", "ب", "ج"])
        self.assertEqual(out["summary"], "خلاصه")

    def test_parse_handles_markdown_fence(self):
        raw = '```json\n{"positives":["x"],"negatives":[],"summary":"s"}\n```'
        self.assertEqual(_extract_json(raw)["positives"], ["x"])

    def test_parse_handles_prose_around_json(self):
        raw = 'البته! این تحلیل است:\n{"positives":["a"],"negatives":["b"],"summary":"c"}'
        self.assertEqual(_parse_description(raw)["summary"], "c")

    def test_generate_raises_when_disabled(self):
        s = CompanySettings.get_solo()
        s.ai_enabled = False
        s.save()
        with self.assertRaises(AIError):
            generate_description({}, entity="consultant")

    def test_prompts_contain_output_contract(self):
        for prompt in (
            build_consultant_prompt({"fullName": "علی", "id": 7}),
            build_property_prompt({"title": "ملک", "internalCode": "ZX-1"}),
        ):
            self.assertIn("positives", prompt)
            self.assertIn("negatives", prompt)
            self.assertIn("summary", prompt)
            self.assertIn("بند", prompt)
            self.assertIn("هویت قطعی", prompt)


class AIEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="ai2-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="ai2-agent", password="pw", role="AGENT"
        )
        cls.profile = ConsultantProfile.objects.create(
            user=cls.agent, full_name="مریم", branch="شمال"
        )

    def setUp(self):
        s = CompanySettings.get_solo()
        s.ai_enabled = True
        s.ai_api_base_url = "https://mock.example/v1"
        s.ai_api_key = "k"
        s.ai_model = "m"
        s.save()

    def test_consultant_endpoint(self):
        raw = (
            '{"positives":["عملکرد خوب","پیگیری دقیق","تکمیل به‌موقع"],'
            '"negatives":["تنوع آگهی کم","تأخیر در برخی وظایف","پیگیری محدود"],'
            '"summary":"مشاوری فعال و منظم"}'
        )
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw):
            c = APIClient()
            c.force_authenticate(user=self.admin)
            r = c.post(f"/common/api/ai/consultant/{self.profile.pk}/")
        self.assertEqual(r.status_code, 200, r.content[:200])
        body = r.json()
        self.assertEqual(len(body["positives"]), 3)
        self.assertEqual(len(body["negatives"]), 3)
        self.assertTrue(body["summary"])

    def test_property_endpoint(self):
        prop = Property.objects.create(
            title="آپارتمان", internal_code="AIP-1", consultant=self.agent,
            area=120, address="تهران", property_type="APARTMENT",
            latitude=Decimal("35.7"), longitude=Decimal("51.4"),
        )
        sale = DealType.objects.get(name="sale")
        Listing.objects.create(
            property=prop, title="آگهی", publish_channel="WEBSITE",
            created_by=self.agent, deal_type=sale,
            sale_price=Decimal("12000000000"), status="ACTIVE",
        )
        raw = (
            '{"positives":["موقعیت خوب","قیمت مناسب","متراژ مناسب"],'
            '"negatives":["تصاویر کم","سن بنا","بدون آسانسور"],'
            '"summary":"ملکی مناسب برای سرمایه‌گذاری"}'
        )
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw):
            c = APIClient()
            c.force_authenticate(user=self.admin)
            r = c.post(f"/common/api/ai/property/{prop.pk}/")
        self.assertEqual(r.status_code, 200, r.content[:200])
        body = r.json()
        self.assertEqual(len(body["positives"]), 3)
        self.assertEqual(len(body["negatives"]), 3)
        self.assertTrue(body["summary"])

    def test_returns_503_when_disabled(self):
        s = CompanySettings.get_solo()
        s.ai_enabled = False
        s.save()
        c = APIClient()
        c.force_authenticate(user=self.admin)
        r = c.post(f"/common/api/ai/consultant/{self.profile.pk}/")
        self.assertEqual(r.status_code, 503)


class AICacheAndIsolationTests(TestCase):
    """Fingerprint + cache, and per-entity isolation."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_basics", stdout=io.StringIO())
        cls.admin = User.objects.create_user(
            username="aic-admin", password="pw", role="ADMIN"
        )
        cls.agent = User.objects.create_user(
            username="aic-agent", password="pw", role="AGENT"
        )
        cls.agent2 = User.objects.create_user(
            username="aic-agent2", password="pw", role="AGENT"
        )
        cls.p1 = ConsultantProfile.objects.create(
            user=cls.agent, full_name="احمد", branch="مرکزی"
        )
        cls.p2 = ConsultantProfile.objects.create(
            user=cls.agent2, full_name="سارا", branch="شمال"
        )

    def setUp(self):
        from django.core.cache import cache

        from apps.common.models import AIInsightCache

        cache.clear()  # LocMemCache persists across tests within a process
        AIInsightCache.objects.all().delete()
        s = CompanySettings.get_solo()
        s.ai_enabled = True
        s.ai_api_base_url = "https://mock.example/v1"
        s.ai_api_key = "k"
        s.ai_model = "m"
        s.save()

    def _raw(self, name):
        return (
            '{"positives":["+1","+2","+3"],"negatives":["-1","-2","-3"],'
            f'"summary":"خلاصه برای {name}"}}'
        )

    def test_cache_returns_same_result_without_new_call(self):
        raw = self._raw("احمد")
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw) as m:
            first = get_cached_description(
                {"name": "احمد", "kpis": {"openTasks": 3}}, entity="consultant", entity_id=self.p1.pk
            )
            second = get_cached_description(
                {"name": "احمد", "kpis": {"openTasks": 3}}, entity="consultant", entity_id=self.p1.pk
            )
        # Same fingerprint → only one upstream call (cached).
        self.assertEqual(m.call_count, 1)
        self.assertEqual(first, second)

    def test_changed_data_triggers_new_call(self):
        raw = self._raw("احمد")
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw) as m:
            get_cached_description(
                {"name": "احمد", "kpis": {"openTasks": 3}}, entity="consultant", entity_id=self.p1.pk
            )
            get_cached_description(
                {"name": "احمد", "kpis": {"openTasks": 10}}, entity="consultant", entity_id=self.p1.pk
            )
        # Different fingerprint (data changed) → a second upstream call.
        self.assertEqual(m.call_count, 2)

    def test_different_entities_are_isolated(self):
        """Each consultant keeps its own description; data is never mixed."""
        raw1 = self._raw("احمد")
        raw2 = self._raw("سارا")
        seen = {"احمد": 0, "سارا": 0}

        def fake_chat(system, user):
            # The prompt embeds the entity's own data (its name).
            if "احمد" in user:
                seen["احمد"] += 1
                return raw1
            if "سارا" in user:
                seen["سارا"] += 1
                return raw2
            raise AssertionError("Unexpected data in prompt!")

        with mock.patch(
            "apps.common.ai_service._chat_completion", side_effect=fake_chat
        ):
            a1 = get_cached_description(
                {"name": "احمد"}, entity="consultant", entity_id=self.p1.pk
            )
            s1 = get_cached_description(
                {"name": "سارا"}, entity="consultant", entity_id=self.p2.pk
            )
            # Repeat: should be served from cache, no extra calls.
            a2 = get_cached_description(
                {"name": "احمد"}, entity="consultant", entity_id=self.p1.pk
            )
            s2 = get_cached_description(
                {"name": "سارا"}, entity="consultant", entity_id=self.p2.pk
            )

        # Each consultant described exactly once.
        self.assertEqual(seen["احمد"], 1)
        self.assertEqual(seen["سارا"], 1)
        # The cached results are correct per entity and identical across repeats.
        self.assertEqual(a1["summary"], "خلاصه برای احمد")
        self.assertEqual(s1["summary"], "خلاصه برای سارا")
        self.assertEqual(a1, a2)
        self.assertEqual(s1, s2)
        # Ahmed's summary must not leak into Sara's.
        self.assertNotEqual(a1["summary"], s1["summary"])

    def test_fingerprint_differs_across_entities(self):
        fp1 = data_fingerprint({"name": "احمد"}, entity="consultant", entity_id=1)
        fp2 = data_fingerprint({"name": "سارا"}, entity="consultant", entity_id=2)
        self.assertNotEqual(fp1, fp2)

    def test_fingerprint_includes_entity_id(self):
        payload = {"kpis": {"openTasks": 3}}
        self.assertNotEqual(
            data_fingerprint(payload, entity="property", entity_id=1),
            data_fingerprint(payload, entity="property", entity_id=2),
        )

    def test_fingerprint_ignores_clock_fields(self):
        base = {"title": "ملک الف", "kpis": {"imagesCount": 4, "daysOnMarket": 10}}
        other = {
            "title": "ملک الف",
            "kpis": {"imagesCount": 4, "daysOnMarket": 11},
            "generatedAt": "2026-08-13T10:00:00",
            "meta": {"generatedAt": "now"},
        }
        self.assertEqual(
            data_fingerprint(base, entity="property", entity_id=9),
            data_fingerprint(other, entity="property", entity_id=9),
        )

    def test_clock_fields_do_not_bust_the_cache(self):
        raw = self._raw("ملک")
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw) as m:
            get_cached_description(
                {"title": "الف", "kpis": {"daysOnMarket": 3}},
                entity="property",
                entity_id=91,
            )
            get_cached_description(
                {"title": "الف", "kpis": {"daysOnMarket": 4}, "generatedAt": "x"},
                entity="property",
                entity_id=91,
            )
        self.assertEqual(m.call_count, 1)

    def test_db_cache_survives_locmem_clear(self):
        raw = self._raw("احمد")
        with mock.patch("apps.common.ai_service._chat_completion", return_value=raw) as m:
            first = get_cached_description(
                {"name": "احمد"}, entity="consultant", entity_id=self.p1.pk
            )
            from django.core.cache import cache

            cache.clear()
            second = get_cached_description(
                {"name": "احمد"}, entity="consultant", entity_id=self.p1.pk
            )
        self.assertEqual(m.call_count, 1)
        self.assertEqual(first, second)

    def test_raises_when_disabled(self):
        s = CompanySettings.get_solo()
        s.ai_enabled = False
        s.save()
        with self.assertRaises(AIError):
            get_cached_description(
                {"name": "احمد"}, entity="consultant", entity_id=self.p1.pk
            )


class AIModelAdminRequiredTests(TestCase):
    """The Django admin «تنظیمات سایت» form must require the AI model name."""

    def _form(self, **overrides):
        from django.contrib.admin.sites import AdminSite

        from apps.common.admin import CompanySettingsAdmin

        obj = CompanySettings.get_solo()
        data = {
            "company_name": obj.company_name,
            "license_number": obj.license_number,
            "email": obj.email,
            "phone": obj.phone,
            "address": obj.address,
            "ai_enabled": False,
            "ai_api_base_url": "",
            "ai_api_key": "",
            "ai_model": "gpt-4o-mini",
        }
        data.update(overrides)
        return CompanySettingsAdmin(CompanySettings, AdminSite()).get_form(None)(
            instance=obj, data=data
        )

    def test_admin_rejects_an_empty_model_name(self):
        form = self._form(ai_model="")
        self.assertFalse(form.is_valid())
        self.assertIn("ai_model", form.errors)

    def test_admin_rejects_whitespace_only_model_name(self):
        form = self._form(ai_model="   ")
        self.assertFalse(form.is_valid())
        self.assertIn("ai_model", form.errors)

    def test_admin_accepts_a_model_name(self):
        form = self._form(ai_model=" deepseek-chat ")
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.ai_model, "deepseek-chat")

    def test_full_clean_requires_the_model(self):
        from django.core.exceptions import ValidationError

        obj = CompanySettings.get_solo()
        obj.ai_model = ""
        with self.assertRaises(ValidationError) as ctx:
            obj.full_clean()
        self.assertIn("ai_model", ctx.exception.message_dict)
