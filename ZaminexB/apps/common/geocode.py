from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from . import cache_utils

__all__ = [
    "GeocodeUnavailable",
    "normalize_place_key",
    "geocode",
]


class GeocodeUnavailable(Exception):
    """"""


_EQUIVALENT_LETTERS = str.maketrans(
    {
        "\u064a": "\u06cc",
        "\u0643": "\u06a9",
        "\u0629": "\u0647",
        "\u0649": "\u06cc",
        "\u0622": "\u0627",
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0671": "\u0627",
    }
)

_IGNORABLE = ("\u200c", "\u200d", "\u0640")


def normalize_place_key(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    for ch in _IGNORABLE:
        text = text.replace(ch, "")
    text = text.translate(_EQUIVALENT_LETTERS)

    text = "".join(
        ch for ch in text if not ("\u064b" <= ch <= "\u0652")
    )
    
    return re.sub(r"[\s\u200b-\u200f\u2060\ufeff]", "", text)


def clean_viewbox(raw) -> str | None:
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 4:
        return None
    numbers = []
    for part in parts:
        try:
            numbers.append(float(part))
        except ValueError:
            return None
    if any(n != n or n in (float("inf"), float("-inf")) for n in numbers):
        return None
    return ",".join(f"{n:.6f}" for n in numbers)


def _upstream_url() -> str:
    return getattr(
        settings, "GEOCODE_UPSTREAM", "https://nominatim.openstreetmap.org/search"
    )


def _user_agent() -> str:
    return getattr(
        settings,
        "GEOCODE_USER_AGENT",
        "Zaminex-CRM/1.0 (+self-hosted real-estate CRM; geocode proxy)",
    )


def _pace() -> None:
    seconds = float(getattr(settings, "GEOCODE_PACING_SECONDS", 1.1))
    slot = cache_utils.make_key("geocode", "pace")
    deadline = time.monotonic() + seconds * 3
    while time.monotonic() < deadline:
        if cache_utils.cache_add(slot, 1, seconds) is not False:
            return
        time.sleep(0.05)


def _fetch_upstream(query: str, viewbox: str | None, bounded: bool) -> list[dict]:
    params = {
        "q": query,
        "countrycodes": "ir",
        "format": "jsonv2",
        "limit": str(getattr(settings, "GEOCODE_LIMIT", 1)),
        "accept-language": "fa",
    }
    if viewbox:
        params["viewbox"] = viewbox
        if bounded:
            params["bounded"] = "1"

    url = f"{_upstream_url().rstrip('/')}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _user_agent(),
            "Accept": "application/json",
            "Accept-Language": "fa",
        },
    )
    timeout = float(getattr(settings, "GEOCODE_TIMEOUT", 8))

    _pace()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise GeocodeUnavailable(f"upstream geocoder unreachable: {exc}") from exc

    try:
        data = json.loads(body)
    except ValueError as exc:
        raise GeocodeUnavailable(f"upstream returned a non-JSON body: {exc}") from exc
    if not isinstance(data, list):
        raise GeocodeUnavailable("upstream returned an unexpected shape")

    results = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            lat = float(row.get("lat"))
            lon = float(row.get("lon"))
        except (TypeError, ValueError):
            continue
        address = row.get("address")
        results.append(
            {
                "lat": lat,
                "lon": lon,
                "address": address if isinstance(address, dict) else {},
                "displayName": row.get("display_name") or "",
            }
        )
    return results


def geocode(query: str, viewbox: str | None = None, bounded: bool = False) -> list[dict]:
    key = cache_utils.make_key(
        "geocode",
        normalize_place_key(query),
        viewbox or "",
        "bounded" if bounded else "free",
    )

    cached = cache_utils.cache_get(key)
    if isinstance(cached, list):
        return cached

    with cache_utils.with_lock(f"{key}:lock"):
        cached = cache_utils.cache_get(key)
        if isinstance(cached, list):
            return cached

        results = _fetch_upstream(query, viewbox, bounded)

        ttl = (
            getattr(settings, "GEOCODE_CACHE_TTL", 30 * 24 * 3600)
            if results
            else getattr(settings, "GEOCODE_NEGATIVE_CACHE_TTL", 7 * 24 * 3600)
        )
        cache_utils.cache_set(key, results, ttl)
        return results
