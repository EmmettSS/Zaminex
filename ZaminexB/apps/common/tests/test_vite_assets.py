import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.checks import Error, Warning
from django.template import Context, Template
from django.test import TestCase, override_settings

from apps.common.checks import check_frontend_assets
from apps.common.templatetags.vite_assets import find_missing_assets

GOOD_MANIFEST = {
    "src/main.tsx": {
        "file": "assets/main-abc123.js",
        "name": "main",
        "src": "src/main.tsx",
        "isEntry": True,
        "css": ["assets/main-abc123.css"],
    }
}


class ViteAssetsTestCase(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = self._tmpdir.name

    def _write_manifest(self, data):
        mdir = os.path.join(self.root, ".vite")
        os.makedirs(mdir, exist_ok=True)
        mpath = os.path.join(mdir, "manifest.json")
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return mpath

    def _write_asset(self, rel, body="x"):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def _render(self, manifest_path):
        with override_settings(VITE_MANIFEST_PATH=manifest_path):
            tpl = Template("{% load vite_assets %}{% vite_asset 'src/main.tsx' %}")
            return tpl.render(Context({}))


class ViteAssetsTagTests(ViteAssetsTestCase):
    def test_renders_script_and_link_from_manifest(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        for rel in ("assets/main-abc123.js", "assets/main-abc123.css"):
            self._write_asset(rel)

        html = self._render(manifest)

        self.assertIn('href="/static/frontend/assets/main-abc123.css"', html)
        self.assertIn('src="/static/frontend/assets/main-abc123.js"', html)
        self.assertIn('type="module"', html)
        self.assertNotIn("&lt;", html)

    def test_missing_entry_renders_comment(self):
        manifest = self._write_manifest(
            {"src/other.tsx": {"file": "assets/other.js", "css": []}}
        )
        html = self._render(manifest)
        self.assertIn("vite_asset", html)
        self.assertNotIn("<script", html)

    def test_missing_manifest_renders_comment(self):
        missing = os.path.join(self.root, "nope", "manifest.json")
        html = self._render(missing)
        self.assertIn("vite_asset", html)


class ViteAssetsMissingTargetTests(ViteAssetsTestCase):
    def test_missing_js_is_not_rendered_as_a_broken_url(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        self._write_asset("assets/main-abc123.css")

        html = self._render(manifest)

        self.assertNotIn("<script", html)
        self.assertNotIn("<link", html)
        self.assertNotIn('src="', html)
        self.assertNotIn('href="', html)
        self.assertTrue(html.startswith("<!--"))
        self.assertIn("main-abc123.js", html)

    def test_missing_css_is_not_rendered_as_a_broken_url(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        self._write_asset("assets/main-abc123.js")

        html = self._render(manifest)

        self.assertNotIn("<link", html)
        self.assertNotIn("<script", html)
        self.assertNotIn('src="', html)
        self.assertNotIn('href="', html)
        self.assertTrue(html.startswith("<!--"))
        self.assertIn("main-abc123.css", html)

    def test_missing_targets_are_logged_with_the_rebuild_command(self):
        manifest = self._write_manifest(GOOD_MANIFEST)

        with self.assertLogs(
            "apps.common.templatetags.vite_assets", level="ERROR"
        ) as captured:
            html = self._render(manifest)

        self.assertEqual(len(captured.records), 1)
        message = captured.records[0].getMessage()
        self.assertIn("main-abc123.js", message)
        self.assertIn("main-abc123.css", message)
        self.assertIn("npm run build", message)
        self.assertNotIn("<script", html)

    def test_complete_build_renders_and_logs_nothing(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        for rel in ("assets/main-abc123.js", "assets/main-abc123.css"):
            self._write_asset(rel)

        with self.assertNoLogs("apps.common.templatetags.vite_assets", level="ERROR"):
            html = self._render(manifest)

        self.assertIn("<script", html)
        self.assertIn("<link", html)

    def test_find_missing_assets_distinguishes_the_three_states(self):
        absent = os.path.join(self.root, "nope", "manifest.json")
        with override_settings(VITE_MANIFEST_PATH=absent):
            self.assertIsNone(find_missing_assets())

        manifest = self._write_manifest(GOOD_MANIFEST)
        for rel in ("assets/main-abc123.js", "assets/main-abc123.css"):
            self._write_asset(rel)
        with override_settings(VITE_MANIFEST_PATH=manifest):
            self.assertEqual(find_missing_assets(), {})

        for rel in ("assets/main-abc123.js", "assets/main-abc123.css"):
            os.remove(os.path.join(self.root, rel))
        with override_settings(VITE_MANIFEST_PATH=manifest):
            self.assertEqual(
                find_missing_assets(),
                {
                    "src/main.tsx": [
                        "assets/main-abc123.js",
                        "assets/main-abc123.css",
                    ]
                },
            )


class FrontendAssetsCheckTests(ViteAssetsTestCase):
    def _run(self, manifest_path):
        with override_settings(VITE_MANIFEST_PATH=manifest_path):
            return check_frontend_assets(app_configs=None)

    def test_consistent_build_reports_nothing(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        for rel in ("assets/main-abc123.js", "assets/main-abc123.css"):
            self._write_asset(rel)
        self.assertEqual(self._run(manifest), [])

    def test_missing_target_is_an_error_that_blocks_the_deploy(self):
        manifest = self._write_manifest(GOOD_MANIFEST)
        problems = self._run(manifest)

        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], Error)
        self.assertEqual(problems[0].id, "vite_assets.E002")
        self.assertIn("main-abc123.js", problems[0].msg)
        self.assertIn("npm run build", problems[0].hint)

    def test_no_manifest_is_only_a_warning_under_the_test_runner(self):
        absent = os.path.join(self.root, "nope", "manifest.json")
        problems = self._run(absent)

        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], Warning)
        self.assertEqual(problems[0].id, "vite_assets.W001")

    def test_no_manifest_is_an_error_in_production(self):
        absent = os.path.join(self.root, "nope", "manifest.json")
        with override_settings(VITE_MANIFEST_PATH=absent, DEBUG=False), mock.patch(
            "apps.common.checks._under_test_runner", return_value=False
        ):
            problems = check_frontend_assets(app_configs=None)

        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], Error)
        self.assertEqual(problems[0].id, "vite_assets.E001")

    def test_no_manifest_is_a_warning_while_developing(self):
        absent = os.path.join(self.root, "nope", "manifest.json")
        with override_settings(VITE_MANIFEST_PATH=absent, DEBUG=True), mock.patch(
            "apps.common.checks._under_test_runner", return_value=False
        ):
            problems = check_frontend_assets(app_configs=None)

        self.assertEqual(len(problems), 1)
        self.assertIsInstance(problems[0], Warning)
        self.assertEqual(problems[0].id, "vite_assets.W001")

    def test_the_check_is_registered_on_a_cold_start(self):
        code = textwrap.dedent(
            """
            import os, django
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            django.setup()
            from django.core.checks.registry import registry
            names = {getattr(c, "__name__", "") for c in registry.registered_checks}
            print("REGISTERED" if "check_frontend_assets" in names else "MISSING")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=Path(settings.BASE_DIR),
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("REGISTERED", result.stdout)
