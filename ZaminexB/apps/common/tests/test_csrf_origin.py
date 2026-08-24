"""Regression tests for the CSRF ``Origin`` failure that blocked logging in.

The bug
-------
``SecurityHeadersMiddleware`` used to send ``Referrer-Policy: no-referrer``.
That header does more than hide the referrer: per the Fetch Standard's
"append a request Origin header" algorithm, for a request whose mode is not
``cors`` and whose method is neither ``GET`` nor ``HEAD``, a referrer policy
of ``no-referrer`` makes the browser send ``Origin: null``.

An HTML ``<form method="post">`` submit — which is exactly how this project
logs a user in — is such a request. Django (>= 4.0) checks ``Origin`` against
the trusted origins on every unsafe request, and ``null`` matches nothing, so
the login POST was rejected with:

    CSRF verification failed. Request aborted.
    Origin checking failed - null does not match any trusted origins.

The fix is ``Referrer-Policy: same-origin`` (also Django's own default for
``SECURE_REFERRER_POLICY``): the referrer is still withheld from every
cross-origin destination, but our own same-origin POSTs keep a real ``Origin``
so CSRF validation can actually run.

These tests pin all three halves of that contract: the header we emit, the
browser behaviour it implies, and the fact that a genuinely opaque or
cross-site origin is still refused.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.common.middleware import SecurityHeadersMiddleware

User = get_user_model()

PASSWORD = "pw-secret-1"

# Referrer policies that make a browser send `Origin: null` for a same-origin,
# non-CORS POST (i.e. an HTML form submit) served over plain HTTP.
ORIGIN_NULLING_POLICIES = {"no-referrer"}


def browser_origin_for_form_post(referrer_policy, site_origin):
    """The ``Origin`` a browser sends for a form submit under this policy.

    Mirrors the Fetch Standard so the tests exercise what a real browser does
    instead of hard-coding a header we happen to expect.
    """
    if (referrer_policy or "").strip().lower() in ORIGIN_NULLING_POLICIES:
        return "null"
    return site_origin


class ReferrerPolicyTests(TestCase):
    """The emitted policy must never null out the Origin header again."""

    def test_referrer_policy_is_not_origin_nulling(self):
        resp = self.client.get("/accounts/login/")
        policy = resp.headers.get("Referrer-Policy")
        self.assertNotIn(
            (policy or "").lower(),
            ORIGIN_NULLING_POLICIES,
            "Referrer-Policy must not be a value that makes browsers send "
            "Origin: null for form submits — that breaks Django's CSRF check.",
        )

    def test_referrer_policy_still_protects_privacy(self):
        """Relaxing the policy must not start leaking referrers off-site."""
        resp = self.client.get("/accounts/login/")
        self.assertIn(
            resp.headers.get("Referrer-Policy"),
            {"same-origin", "strict-origin", "strict-origin-when-cross-origin"},
            "The policy must still withhold the referrer from cross-origin "
            "destinations.",
        )

    def test_middleware_constant_matches_response(self):
        resp = self.client.get("/accounts/login/")
        self.assertEqual(
            resp.headers.get("Referrer-Policy"),
            SecurityHeadersMiddleware.REFERRER_POLICY,
        )

    def test_other_security_headers_are_unchanged(self):
        """The fix must not weaken the rest of the hardening pass."""
        resp = self.client.get("/accounts/login/")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("frame-ancestors 'none'", resp.headers.get("Content-Security-Policy", ""))
        self.assertIn("geolocation=()", resp.headers.get("Permissions-Policy", ""))


class LoginOriginTests(TestCase):
    """The reported reproduction: log in, log out, log in again."""

    SITE_ORIGIN = "http://testserver"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="origin-user", password=PASSWORD, role="ADMIN"
        )

    def _submit_login_like_a_browser(self, client):
        """POST the login form with the Origin a real browser would send."""
        page = client.get("/accounts/login/")
        origin = browser_origin_for_form_post(
            page.headers.get("Referrer-Policy"), self.SITE_ORIGIN
        )
        return client.post(
            "/accounts/login/",
            {
                "username": "origin-user",
                "password": PASSWORD,
                "csrfmiddlewaretoken": page.cookies["csrftoken"].value,
            },
            HTTP_ORIGIN=origin,
        )

    def test_login_form_submit_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        resp = self._submit_login_like_a_browser(client)
        self.assertEqual(resp.status_code, 302, "The login form submit was rejected.")

    def test_login_after_logout_succeeds(self):
        """Logging out must not lock the user out of logging back in."""
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self._submit_login_like_a_browser(client).status_code, 302)
        self.assertEqual(client.get("/").status_code, 200)

        logout = client.post(
            "/accounts/logout/",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            HTTP_ORIGIN=self.SITE_ORIGIN,
        )
        self.assertEqual(logout.status_code, 302)

        # Django rotates the CSRF token on login/logout, so this second pass is
        # the one that used to fail.
        again = self._submit_login_like_a_browser(client)
        self.assertEqual(
            again.status_code, 302, "Could not log in again after logging out."
        )
        self.assertEqual(client.get("/").status_code, 200)

    def test_repeated_login_logout_cycles(self):
        """Three full cycles — nothing may accumulate across sessions."""
        client = Client(enforce_csrf_checks=True)
        for attempt in range(3):
            resp = self._submit_login_like_a_browser(client)
            self.assertEqual(resp.status_code, 302, f"Login cycle {attempt + 1} failed.")
            client.post(
                "/accounts/logout/",
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
                HTTP_ORIGIN=self.SITE_ORIGIN,
            )


class CsrfStillProtectsTests(TestCase):
    """The fix removes a false positive; it must not remove the protection."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="victim", password=PASSWORD, role="ADMIN"
        )

    def _login_post(self, client, origin):
        page = client.get("/accounts/login/")
        return client.post(
            "/accounts/login/",
            {
                "username": "victim",
                "password": PASSWORD,
                "csrfmiddlewaretoken": page.cookies["csrftoken"].value,
            },
            HTTP_ORIGIN=origin,
        )

    def test_cross_site_origin_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        resp = self._login_post(client, "https://evil.example.com")
        self.assertEqual(resp.status_code, 403)

    def test_opaque_null_origin_is_still_rejected(self):
        """A sandboxed iframe or data: URL genuinely sends Origin: null.

        We fixed the cause of the spurious null; we did not start trusting it.
        """
        client = Client(enforce_csrf_checks=True)
        resp = self._login_post(client, "null")
        self.assertEqual(resp.status_code, 403)

    def test_missing_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/accounts/login/")
        resp = client.post(
            "/accounts/login/",
            {"username": "victim", "password": PASSWORD},
            HTTP_ORIGIN="http://testserver",
        )
        self.assertEqual(resp.status_code, 403)

    def test_api_write_from_cross_site_origin_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        client.get("/accounts/login/")
        resp = client.post(
            "/basics/api/provinces/",
            data='{"displayName": "مازندران"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            HTTP_ORIGIN="https://evil.example.com",
        )
        self.assertEqual(resp.status_code, 403)


class CsrfTrustedOriginsTests(TestCase):
    """Every allowed host must also be a trusted CSRF origin."""

    def test_allowed_hosts_are_trusted_origins(self):
        for host in settings.ALLOWED_HOSTS:
            if host == "*":
                continue
            expected = f"*{host}" if host.startswith(".") else host
            self.assertIn(
                f"https://{expected}",
                settings.CSRF_TRUSTED_ORIGINS,
                f"ALLOWED_HOSTS entry {host!r} has no matching trusted origin; "
                "a POST from that host would fail the Origin check.",
            )

    def test_wildcard_host_does_not_become_an_origin(self):
        """`*` must never be turned into an origin that trusts everything."""
        self.assertNotIn("https://*", settings.CSRF_TRUSTED_ORIGINS)
        self.assertNotIn("http://*", settings.CSRF_TRUSTED_ORIGINS)

    def test_allowed_hosts_is_not_overwritten(self):
        """A stray second assignment used to discard the configured hosts."""
        self.assertTrue(settings.ALLOWED_HOSTS, "ALLOWED_HOSTS must not be empty.")


class ApiWriteOriginTests(TestCase):
    """The SPA's fetch-based writes must work under the shipped headers."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="api-admin", password=PASSWORD, role="ADMIN"
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.client.get("/accounts/login/")
        self.csrf = self.client.cookies["csrftoken"].value

    def _post(self, url, payload):
        return self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
            # fetch() defaults to mode "cors", so the browser always sends the
            # real origin here regardless of the referrer policy.
            HTTP_ORIGIN="http://testserver",
        )

    def test_create_province_city_and_district(self):
        """The three levels of the regions screen, end to end."""
        province = self._post("/basics/api/provinces/", '{"displayName": "مازندران"}')
        self.assertEqual(province.status_code, 201, province.content)
        province_id = province.json()["id"]

        city = self._post(
            "/basics/api/cities/",
            f'{{"displayName": "ساری", "province": {province_id}}}',
        )
        self.assertEqual(city.status_code, 201, city.content)
        city_id = city.json()["id"]

        district = self._post(
            "/basics/api/districts/",
            f'{{"displayName": "میدان ساعت", "city": {city_id}}}',
        )
        self.assertEqual(district.status_code, 201, district.content)


class GeographyErrorMessageTests(TestCase):
    """Parent-field errors must be actionable Persian sentences.

    Adding a city or a district can fail for a reason that has nothing to do
    with its label — no province chosen, or a parent that was deleted in
    another tab. DRF reports those against the parent key, and the UI showed a
    generic "خطا در اضافه کردن شهر" for all of them. These tests pin the
    wording so the operator is told what to actually fix.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="geo-admin", password=PASSWORD, role="ADMIN"
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def _post(self, url, payload):
        return self.client.post(url, data=payload, content_type="application/json")

    def test_city_without_province_names_the_field(self):
        resp = self._post("/basics/api/cities/", '{"displayName": "ساری"}')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["province"], ["انتخاب استان الزامی است."])

    def test_city_with_null_province_names_the_field(self):
        resp = self._post(
            "/basics/api/cities/", '{"displayName": "ساری", "province": null}'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["province"], ["انتخاب استان الزامی است."])

    def test_city_with_unknown_province_is_explained(self):
        resp = self._post(
            "/basics/api/cities/", '{"displayName": "ساری", "province": 999999}'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json()["province"], ["استان انتخاب‌شده وجود ندارد یا حذف شده است."]
        )

    def test_district_without_city_names_the_field(self):
        resp = self._post("/basics/api/districts/", '{"displayName": "آزادی"}')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["city"], ["انتخاب شهر الزامی است."])

    def test_district_with_unknown_city_is_explained(self):
        resp = self._post(
            "/basics/api/districts/", '{"displayName": "آزادی", "city": 999999}'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json()["city"], ["شهر انتخاب‌شده وجود ندارد یا حذف شده است."]
        )

    def test_duplicate_label_message_is_unchanged(self):
        """The existing, already-good duplicate message must not regress."""
        province = self._post(
            "/basics/api/provinces/", '{"displayName": "مازندران"}'
        ).json()
        payload = f'{{"displayName": "ساری", "province": {province["id"]}}}'
        self.assertEqual(self._post("/basics/api/cities/", payload).status_code, 201)

        duplicate = self._post("/basics/api/cities/", payload)
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("قبلاً ثبت شده است", duplicate.json()["displayName"][0])
