from unittest import mock

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.properties.models import (
    CODE_INSERT_ATTEMPTS,
    CODE_PREFIX,
    FIRST_CODE_VALUE,
    MAX_CODE_VALUE,
    Property,
    _generate_next_internal_code,
    _has_sequential_code,
    _highest_code_value,
)

User = get_user_model()


def _make_property(agent, code="", **extra):
    return Property(
        title="ملک",
        internal_code=code,
        consultant=agent,
        property_type="APARTMENT",
        deal_type="SALE",
        area=100,
        address="ساری",
        **extra,
    )


class InternalCodeSequenceTestCase(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="seq-agent", password="pw", role="AGENT"
        )

    def test_first_code_starts_the_sequence(self):
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}1111")

    def test_codes_increase_one_at_a_time(self):
        for expected in (1111, 1112, 1113):
            _make_property(self.agent).save()
            self.assertEqual(
                Property.objects.order_by("-id").first().internal_code,
                f"{CODE_PREFIX}{expected}",
            )

    def test_no_generated_code_ever_contains_a_zero(self):
        for seed in (1111, 1198, 1899, 8999, 9998):
            with self.subTest(seed=seed):
                Property.objects.all().delete()
                _make_property(self.agent, f"{CODE_PREFIX}{seed}").save()
                code = _generate_next_internal_code()
                self.assertNotIn("0", code)

    def test_values_containing_zero_are_skipped(self):
        _make_property(self.agent, f"{CODE_PREFIX}1999").save()
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}2111")


class FourToFiveDigitSwitchTestCase(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="tier-agent", password="pw", role="AGENT"
        )

    def _fill_four_digit_tier(self):
        codes = [
            f"{CODE_PREFIX}{v}"
            for v in range(FIRST_CODE_VALUE, 10000)
            if "0" not in str(v)
        ]
        Property.objects.bulk_create(
            [_make_property(self.agent, c) for c in codes], batch_size=5000
        )
        return len(codes)

    def test_four_digit_tier_holds_exactly_nine_to_the_four(self):
        self.assertEqual(self._fill_four_digit_tier(), 9 ** 4)

    def test_next_code_after_the_last_four_digit_one_is_five_digits(self):
        self._fill_four_digit_tier()
        self.assertEqual(
            Property.objects.order_by("-internal_code").first().internal_code,
            f"{CODE_PREFIX}9999",
        )
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}11111")

    def test_a_five_digit_code_is_visible_to_the_next_call(self):
        _make_property(self.agent, f"{CODE_PREFIX}9999").save()
        _make_property(self.agent, f"{CODE_PREFIX}11111").save()
        self.assertEqual(_highest_code_value(), 11111)
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}11112")

    def test_two_calls_never_return_the_same_code(self):
        _make_property(self.agent, f"{CODE_PREFIX}11111").save()
        first = _generate_next_internal_code()
        self.assertEqual(first, f"{CODE_PREFIX}11112")
        _make_property(self.agent, first).save()
        second = _generate_next_internal_code()
        self.assertNotEqual(first, second)
        self.assertEqual(second, f"{CODE_PREFIX}11113")

    def test_properties_keep_being_creatable_past_the_old_ceiling(self):
        count = self._fill_four_digit_tier()

        first = _make_property(self.agent)
        first.save()
        self.assertEqual(first.internal_code, f"{CODE_PREFIX}11111")

        for i in range(4):
            prop = _make_property(self.agent)
            prop.save()
            self.assertEqual(
                prop.internal_code,
                f"{CODE_PREFIX}{11112 + i}",
                f"property #{count + 2 + i} got the wrong code",
            )
        self.assertEqual(Property.objects.count(), count + 5)

    def test_codes_stay_unique_across_the_tier_change(self):
        self._fill_four_digit_tier()
        for _ in range(5):
            _make_property(self.agent).save()
        codes = list(Property.objects.values_list("internal_code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))

    def test_five_digit_tier_also_advances_past_its_own_zero_gaps(self):
        _make_property(self.agent, f"{CODE_PREFIX}11999").save()
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}12111")


class ExhaustionGuardTestCase(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="exh-agent", password="pw", role="AGENT"
        )

    def test_guard_is_reachable_and_reports_clearly(self):
        _make_property(self.agent, f"{CODE_PREFIX}{MAX_CODE_VALUE}").save()
        with self.assertRaises(RuntimeError) as ctx:
            _generate_next_internal_code()
        self.assertIn(str(MAX_CODE_VALUE), str(ctx.exception))

    def test_the_last_usable_code_still_works(self):
        _make_property(self.agent, f"{CODE_PREFIX}99998").save()
        self.assertEqual(
            _generate_next_internal_code(), f"{CODE_PREFIX}{MAX_CODE_VALUE}"
        )

    def test_total_capacity(self):
        self.assertEqual(MAX_CODE_VALUE, 99999)
        self.assertEqual(9 ** 4 + 9 ** 5, 65610)


class CodeRecognitionTestCase(TestCase):
    def test_sequential_prefix_is_recognised(self):
        self.assertTrue(_has_sequential_code("ZF_1111"))
        self.assertTrue(_has_sequential_code("ZF_11111"))

    def test_blank_and_foreign_codes_are_not(self):
        for value in ("", None, "DEL-1", "FORGED-1", "zf_1111"):
            with self.subTest(value=value):
                self.assertFalse(_has_sequential_code(value))

    def test_foreign_codes_do_not_disturb_the_sequence(self):
        agent = User.objects.create_user(
            username="legacy-agent", password="pw", role="AGENT"
        )
        Property.objects.bulk_create(
            [_make_property(agent, code) for code in ("DEL-1", "IMG-1", "APPR-2", "R1", "M-001")]
        )
        self.assertEqual(Property.objects.count(), 5)
        self.assertEqual(_highest_code_value(), FIRST_CODE_VALUE - 1)
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}1111")

    def test_a_longer_manual_code_is_left_alone(self):
        agent = User.objects.create_user(
            username="wide-agent", password="pw", role="AGENT"
        )
        _make_property(agent, f"{CODE_PREFIX}1234567").save()
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}1111")

    def test_manual_zf_code_on_a_new_row_is_preserved(self):
        agent = User.objects.create_user(
            username="manual-agent", password="pw", role="AGENT"
        )
        prop = _make_property(agent, f"{CODE_PREFIX}4242")
        prop.save()
        self.assertEqual(prop.internal_code, f"{CODE_PREFIX}4242")

    def test_update_does_not_regenerate_the_code(self):
        agent = User.objects.create_user(
            username="upd-agent", password="pw", role="AGENT"
        )
        prop = _make_property(agent)
        prop.save()
        original = prop.internal_code
        prop.title = "ویرایش شده"
        prop.save()
        self.assertEqual(prop.internal_code, original)


class ConcurrentInsertTestCase(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="race-agent", password="pw", role="AGENT"
        )

    def test_loser_of_the_race_takes_the_following_code(self):
        real = _highest_code_value
        calls = {"n": 0}

        def stale_once():
            calls["n"] += 1
            if calls["n"] == 1:
                return FIRST_CODE_VALUE - 1
            return real()

        _make_property(self.agent).save()
        self.assertEqual(Property.objects.count(), 1)

        with mock.patch(
            "apps.properties.models._highest_code_value", side_effect=stale_once
        ):
            contender = _make_property(self.agent)
            contender.save()

        self.assertEqual(contender.internal_code, f"{CODE_PREFIX}1112")
        self.assertEqual(Property.objects.count(), 2)
        self.assertGreaterEqual(calls["n"], 2, "the maximum was not re-read")

    def test_giving_up_after_the_attempt_budget_still_raises(self):
        _make_property(self.agent).save()
        with mock.patch(
            "apps.properties.models._highest_code_value",
            return_value=FIRST_CODE_VALUE - 1,
        ):
            with self.assertRaises(IntegrityError):
                _make_property(self.agent).save()

    def test_attempt_budget_is_bounded(self):
        self.assertGreater(CODE_INSERT_ATTEMPTS, 1)
        self.assertLess(CODE_INSERT_ATTEMPTS, 20)


class GeneratorCostTestCase(TestCase):
    def setUp(self):
        self.agent = User.objects.create_user(
            username="cost-agent", password="pw", role="AGENT"
        )

    def _fill(self, n):
        Property.objects.all().delete()
        codes = []
        v = FIRST_CODE_VALUE
        while len(codes) < n:
            if "0" not in str(v):
                codes.append(f"{CODE_PREFIX}{v}")
            v += 1
        Property.objects.bulk_create(
            [_make_property(self.agent, c) for c in codes], batch_size=5000
        )

    def test_query_count_does_not_grow_with_the_row_count(self):
        for n in (50, 3000):
            with self.subTest(rows=n):
                self._fill(n)
                with self.assertNumQueries(1):
                    _generate_next_internal_code()

    def test_result_is_still_correct_at_volume(self):
        self._fill(3000)
        self.assertEqual(_highest_code_value(), 5213)
        self.assertEqual(_generate_next_internal_code(), f"{CODE_PREFIX}5214")
