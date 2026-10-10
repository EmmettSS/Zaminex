import json
import logging
from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

logger = logging.getLogger(__name__)

register = template.Library()


def _manifest_path():
    return Path(
        getattr(
            settings,
            "VITE_MANIFEST_PATH",
            settings.BASE_DIR / "static" / "frontend" / ".vite" / "manifest.json",
        )
    )


def _frontend_root():
    override = getattr(settings, "VITE_FRONTEND_ROOT", "")
    if override:
        return Path(override)
    return _manifest_path().parent.parent


def _load_manifest():
    path = _manifest_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def _chunk_targets(chunk):
    if not isinstance(chunk, dict):
        return []
    css = chunk.get("css") or []
    if not isinstance(css, (list, tuple)):
        css = [css]
    return [rel for rel in [chunk.get("file"), *css] if rel]


def find_missing_assets():
    manifest = _load_manifest()
    if not manifest:
        return None
    root = _frontend_root()
    missing = {}
    for entry, chunk in manifest.items():
        absent = [rel for rel in _chunk_targets(chunk) if not (root / rel).is_file()]
        if absent:
            missing[entry] = absent
    return missing


@register.simple_tag
def vite_asset(entry: str = "src/main.tsx") -> str:
    manifest = _load_manifest()
    chunk = manifest.get(entry)
    if not chunk:
        return mark_safe(
            f"<!-- vite_asset: entry '{entry}' not found; run `npm run build` -->"
        )

    absent = [
        rel for rel in _chunk_targets(chunk) if not (_frontend_root() / rel).is_file()
    ]
    if absent:
        logger.error(
            "vite_asset: manifest entry %r points at %s, which is not under %s. "
            "The manifest and the built assets have come apart, so every page "
            "will render blank. Rebuild the frontend so both are written "
            "together: cd ZaminexF && npm run build",
            entry,
            ", ".join(absent),
            _frontend_root(),
        )
        return mark_safe(
            f"<!-- vite_asset: entry '{entry}' points at missing file(s) "
            f"{', '.join(absent)}; run `npm run build` -->"
        )

    tags = []

    for css in chunk.get("css", []):
        tags.append(f'<link rel="stylesheet" href="{static("frontend/" + css)}">')

    js_file = chunk.get("file")
    if js_file:
        tags.append(
            f'<script type="module" src="{static("frontend/" + js_file)}"></script>'
        )

    return mark_safe("\n".join(tags))
