import functools
import os
import tempfile

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import RequestFactory, TestCase, override_settings

from apps.common.staticfiles import (
    IMMUTABLE_CACHE_CONTROL,
    REVALIDATE_CACHE_CONTROL,
    CachedStaticFilesHandler,
    static_files_handler,
)

HASHED_JS = "frontend/assets/main-CX4Z6jdi.js"
HASHED_CSS = "frontend/assets/main-hBm57PfM.css"


def _wsgi_call(handler, path, method="GET"):
    captured = {}
    body = bytearray()

    def start_response(status, headers, exc_info=None):
        captured["status"] = int(status.split()[0])
        captured["headers"] = {k.lower(): v for k, v in headers}
        return body.extend

    environ = RequestFactory().generic(method, path).environ
    result = handler(environ, start_response)
    try:
        for chunk in result:
            body.extend(chunk)
    finally:
        if hasattr(result, "close"):
            result.close()
    return captured["status"], captured["headers"], bytes(body)


class StaticFilesServingTestCase(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = self._tmpdir.name

        self._write(HASHED_JS, b"console.log('app');")
        self._write(HASHED_CSS, b"body{color:red}")
        self._write("favicon.ico", b"\x00\x00\x01\x00")
        self._write("fonts/woff/IRAN-Rounded.woff", b"wOFF")
        self._write("frontend/.vite/manifest.json", b"{}")
        self._write("frontend/assets/handwritten.js", b"var a = 1;")

        self.finder_cache_clear = functools.partial(finders.get_finder.cache_clear)
        self.finder_cache_clear()
        self.addCleanup(self.finder_cache_clear)

        self._override = override_settings(STATICFILES_DIRS=[self.root])
        self._override.enable()
        self.addCleanup(self._override.disable)

        from django.core.wsgi import get_wsgi_application

        self.handler = CachedStaticFilesHandler(get_wsgi_application())

    def _write(self, relpath, content):
        path = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)

    def _get(self, path):
        return _wsgi_call(self.handler, path)


    def test_hashed_js_bundle_is_served_with_debug_off(self):
        status, headers, body = self._get(f"/static/{HASHED_JS}")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"console.log('app');")
        self.assertEqual(headers["content-type"], "text/javascript")

    def test_hashed_css_bundle_is_served_with_debug_off(self):
        status, headers, body = self._get(f"/static/{HASHED_CSS}")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"body{color:red}")
        self.assertEqual(headers["content-type"], "text/css")

    def test_every_static_file_in_the_tree_is_reachable(self):
        for relpath in (HASHED_JS, HASHED_CSS, "favicon.ico",
                        "fonts/woff/IRAN-Rounded.woff",
                        "frontend/.vite/manifest.json"):
            with self.subTest(relpath=relpath):
                self.assertEqual(self._get(f"/static/{relpath}")[0], 200)


    def test_hashed_assets_are_immutable(self):
        for relpath in (HASHED_JS, HASHED_CSS):
            with self.subTest(relpath=relpath):
                headers = self._get(f"/static/{relpath}")[1]
                self.assertEqual(headers["cache-control"], IMMUTABLE_CACHE_CONTROL)

    def test_unhashed_static_files_must_revalidate(self):
        for relpath in ("favicon.ico", "fonts/woff/IRAN-Rounded.woff",
                        "frontend/.vite/manifest.json"):
            with self.subTest(relpath=relpath):
                headers = self._get(f"/static/{relpath}")[1]
                self.assertEqual(headers["cache-control"], REVALIDATE_CACHE_CONTROL)

    def test_hand_placed_file_in_hashed_dir_is_not_frozen(self):
        headers = self._get("/static/frontend/assets/handwritten.js")[1]
        self.assertEqual(headers["cache-control"], REVALIDATE_CACHE_CONTROL)

    def test_last_modified_is_preserved(self):
        headers = self._get(f"/static/{HASHED_CSS}")[1]
        self.assertIn("last-modified", headers)

    def test_conditional_request_returns_304(self):
        last_modified = self._get(f"/static/{HASHED_CSS}")[1]["last-modified"]
        environ = RequestFactory().generic(
            "GET", f"/static/{HASHED_CSS}",
            HTTP_IF_MODIFIED_SINCE=last_modified,
        ).environ
        captured = {}
        result = self.handler(
            environ,
            lambda status, headers, exc_info=None: captured.setdefault(
                "status", int(status.split()[0])
            ),
        )
        if hasattr(result, "close"):
            result.close()
        self.assertEqual(captured["status"], 304)


    def test_missing_file_is_a_clean_404(self):
        status, _headers, _body = self._get("/static/does-not-exist.js")
        self.assertEqual(status, 404)

    def test_traversal_probes_are_404_and_do_not_raise(self):
        probes = (
            "/static/../config/settings.py",
            "/static/..%2fconfig/settings.py",
            "/static/%2e%2e/config/settings.py",
            "/static/%2e%2e%2f%2e%2e%2fetc/passwd",
            "/static/frontend/../../config/settings.py",
            "/static/./../../etc/passwd",
        )
        for probe in probes:
            with self.subTest(probe=probe):
                status, _headers, body = self._get(probe)
                self.assertEqual(status, 404)
                self.assertNotIn(b"SECRET_KEY", body)
                self.assertNotIn(b"root:", body)

    def test_null_byte_in_path_is_rejected(self):
        status, _headers, _body = self._get("/static/%00evil.js")
        self.assertIn(status, (400, 404))


    def test_media_urls_are_not_intercepted(self):
        self.assertFalse(self.handler._should_handle("/media/properties/1.jpg"))

    def test_sibling_prefix_is_not_intercepted(self):
        self.assertFalse(self.handler._should_handle("/staticfiles/evil.js"))

    def test_non_static_paths_pass_through_to_the_application(self):
        status, _headers, _body = self._get("/accounts/login/")
        self.assertNotEqual(status, 404)

    def test_head_request_reports_size_without_breaking(self):
        status, headers, _body = _wsgi_call(
            self.handler, f"/static/{HASHED_JS}", method="HEAD"
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-length"], str(len(b"console.log('app');")))
        self.assertEqual(headers["content-type"], "text/javascript")


class CacheControlPolicyTestCase(TestCase):
    def setUp(self):
        self.handler = CachedStaticFilesHandler(lambda environ, sr: [])

    def test_policy_for_representative_paths(self):
        cases = {
            "/static/frontend/assets/main-CX4Z6jdi.js": IMMUTABLE_CACHE_CONTROL,
            "/static/frontend/assets/main-hBm57PfM.css": IMMUTABLE_CACHE_CONTROL,
            "/static/frontend/assets/chunk-DbK3x9LqZtQ1r2.js": IMMUTABLE_CACHE_CONTROL,
            "/static/frontend/.vite/manifest.json": REVALIDATE_CACHE_CONTROL,
            "/static/frontend/assets/handwritten.js": REVALIDATE_CACHE_CONTROL,
            "/static/fonts/woff/IRAN-Rounded.woff": REVALIDATE_CACHE_CONTROL,
            "/static/favicon.ico": REVALIDATE_CACHE_CONTROL,
            "/static/admin/css/base.css": REVALIDATE_CACHE_CONTROL,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(self.handler.cache_control_for(path), expected)

    def test_prefix_follows_static_url(self):
        with override_settings(STATIC_URL="https://cdn.example.com/static/"):
            finders.get_finder.cache_clear()
            handler = CachedStaticFilesHandler(lambda environ, sr: [])
            self.addCleanup(finders.get_finder.cache_clear)
            self.assertEqual(
                handler.cache_control_for(
                    "https://cdn.example.com/static/frontend/assets/main-CX4Z6jdi.js"
                ),
                IMMUTABLE_CACHE_CONTROL,
            )


class StaticFilesHandlerWiringTestCase(TestCase):
    def setUp(self):
        self.application = lambda environ, start_response: []

    def test_is_a_noop_under_debug(self):
        """``runserver`` already installs a handler when ``DEBUG`` is on."""
        with override_settings(DEBUG=True):
            self.assertIs(
                static_files_handler(self.application), self.application
            )

    def test_wraps_when_debug_is_off(self):
        with override_settings(DEBUG=False):
            wrapped = static_files_handler(self.application)
        self.assertIsInstance(wrapped, CachedStaticFilesHandler)
        self.assertIs(wrapped.application, self.application)

    def test_wsgi_module_exposes_a_wrapped_application_in_production(self):
        import importlib

        import config.wsgi

        with override_settings(DEBUG=False):
            importlib.reload(config.wsgi)
        self.addCleanup(importlib.reload, config.wsgi)
        self.assertIsInstance(
            config.wsgi.application, CachedStaticFilesHandler,
            "config.wsgi.application must be wrapped when DEBUG is off, or "
            "every /static/ URL 404s in production and the site renders blank.",
        )

    def test_wsgi_module_stays_unwrapped_under_debug(self):
        import importlib

        import config.wsgi

        with override_settings(DEBUG=True):
            importlib.reload(config.wsgi)
        self.addCleanup(importlib.reload, config.wsgi)
        self.assertNotIsInstance(config.wsgi.application, CachedStaticFilesHandler)

    def test_settings_declares_this_wsgi_module(self):
        self.assertEqual(settings.WSGI_APPLICATION, "config.wsgi.application")
