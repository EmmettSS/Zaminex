"""Template tag that auto-resolves the hashed frontend assets.

Vite is configured to build straight into ``ZaminexB/static/frontend`` and to
emit a manifest at ``.vite/manifest.json`` mapping logical entries (e.g.
``src/main.tsx``) to their hashed JS/CSS files. This tag reads that manifest
once and renders the correct ``<script>`` / ``<link>`` tags, so you never edit
``base.html`` manually after a rebuild.

Usage in a template::

    {% load vite_assets %}
    {% vite_asset 'src/main.tsx' %}

If the manifest is missing (e.g. the frontend has not been built yet) the tag
renders an HTML comment instead of crashing, so the page still renders.
"""

import json
from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()


def _manifest_path():
    """Path to the Vite manifest; overridable via ``VITE_MANIFEST_PATH``."""
    return getattr(
        settings,
        "VITE_MANIFEST_PATH",
        settings.BASE_DIR / "static" / "frontend" / ".vite" / "manifest.json",
    )


def _load_manifest():
    """Read and parse the Vite manifest.

    The manifest is a tiny file (~200 bytes), so it is read on every call —
    this is both cheap and fully correct (a fresh build is picked up on the very
    next request, with no caching subtleties). Returns ``{}`` on any error so
    the page still renders when the frontend has not been built yet.
    """
    path = Path(_manifest_path())
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


@register.simple_tag
def vite_asset(entry: str = "src/main.tsx") -> str:
    """Render <script> and <link> tags for a Vite entry from the manifest."""
    manifest = _load_manifest()
    chunk = manifest.get(entry)
    if not chunk:
        return mark_safe(
            f"<!-- vite_asset: entry '{entry}' not found; run `npm run build` -->"
        )

    # The manifest file paths are relative to static/frontend, and Django serves
    # that tree under STATIC_URL. Prefix with "frontend/".
    tags = []

    for css in chunk.get("css", []):
        tags.append(f'<link rel="stylesheet" href="{static("frontend/" + css)}">')

    js_file = chunk.get("file")
    if js_file:
        tags.append(
            f'<script type="module" src="{static("frontend/" + js_file)}"></script>'
        )

    return mark_safe("\n".join(tags))
