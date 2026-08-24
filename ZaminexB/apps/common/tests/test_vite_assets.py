"""Tests for the vite_asset template tag (manifest-driven asset resolution)."""

import json
import tempfile

from django.template import Context, Template
from django.test import TestCase, override_settings


class ViteAssetsTagTests(TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _write_manifest(self, data):
        root = self._tmpdir.name
        mdir = f"{root}/.vite"
        import os

        os.makedirs(mdir, exist_ok=True)
        mpath = f"{mdir}/manifest.json"
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return mpath

    def test_renders_script_and_link_from_manifest(self):
        manifest = self._write_manifest(
            {
                "src/main.tsx": {
                    "file": "assets/main-abc123.js",
                    "name": "main",
                    "src": "src/main.tsx",
                    "isEntry": True,
                    "css": ["assets/main-abc123.css"],
                }
            }
        )
        with override_settings(VITE_MANIFEST_PATH=manifest):
            tpl = Template("{% load vite_assets %}{% vite_asset 'src/main.tsx' %}")
            html = tpl.render(Context({}))

        self.assertIn('href="/static/frontend/assets/main-abc123.css"', html)
        self.assertIn('src="/static/frontend/assets/main-abc123.js"', html)
        self.assertIn('type="module"', html)
        # Output is safe (not HTML-escaped).
        self.assertNotIn("&lt;", html)

    def test_missing_entry_renders_comment(self):
        manifest = self._write_manifest(
            {"src/other.tsx": {"file": "assets/other.js", "css": []}}
        )
        with override_settings(VITE_MANIFEST_PATH=manifest):
            tpl = Template("{% load vite_assets %}{% vite_asset 'src/main.tsx' %}")
            html = tpl.render(Context({}))
        self.assertIn("vite_asset", html)
        self.assertNotIn("<script", html)

    def test_missing_manifest_renders_comment(self):
        missing = f"{self._tmpdir.name}/nope/manifest.json"
        with override_settings(VITE_MANIFEST_PATH=missing):
            tpl = Template("{% load vite_assets %}{% vite_asset 'src/main.tsx' %}")
            html = tpl.render(Context({}))
        self.assertIn("vite_asset", html)
