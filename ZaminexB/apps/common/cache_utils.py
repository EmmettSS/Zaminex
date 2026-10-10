from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)

__all__ = [
    "CACHE_VERSION",
    "make_key",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_add",
    "cache_or_compute",
    "with_lock",
    "backend_reports_delivery",
    "note_cache_delivered",
    "cache_backend_available",
]

CACHE_VERSION = "v1"

_LOCK_SUFFIX = ":lock"
_LOCK_TIMEOUT = 10
_LOCK_POLL_SECONDS = 0.1
_LOCK_MAX_WAIT = 5.0


class _DecimalJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return {"__zaminex_decimal__": str(o)}
        return str(o)


def _decimal_object_hook(values: dict) -> Any:
    if list(values.keys()) == ["__zaminex_decimal__"]:
        return Decimal(values["__zaminex_decimal__"])
    return values


def _encode(value: Any) -> str:
    return json.dumps(value, cls=_DecimalJSONEncoder, ensure_ascii=False)


def _decode(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", "replace")
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw, object_hook=_decimal_object_hook)
    except (ValueError, TypeError):
        return None


def _cache():
    from django.core.cache import cache

    return cache


BACKEND_REPROBE_SECONDS = 5.0

_backend_key: str | None = None
_backend_reports_delivery = False
_backend_marked_down = False
_backend_down_until = 0.0
_backend_state_lock = threading.Lock()


def _sync_backend() -> None:
    global _backend_key, _backend_reports_delivery, _backend_marked_down
    global _backend_down_until
    from django.conf import settings

    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if backend == _backend_key:
        return
    with _backend_state_lock:
        _backend_key = backend
        _backend_reports_delivery = "django_redis" in backend
        _backend_marked_down = False
        _backend_down_until = 0.0


def backend_reports_delivery() -> bool:
    _sync_backend()
    return _backend_reports_delivery


def note_cache_delivered(delivered: Any) -> None:
    if not backend_reports_delivery():
        return
    global _backend_marked_down, _backend_down_until
    now = time.monotonic()
    with _backend_state_lock:
        was_marked_down = _backend_marked_down
        if delivered:
            _backend_marked_down = False
            _backend_down_until = 0.0
        else:
            _backend_marked_down = True
            _backend_down_until = now + BACKEND_REPROBE_SECONDS
    if delivered:
        if was_marked_down:
            logger.info("Cache backend is delivering writes again.")
    elif not was_marked_down:
        logger.warning(
            "Cache backend is not delivering writes — serving degraded for "
            "%.1fs before re-probing. Underlying error is logged by "
            "django_redis.cache.",
            BACKEND_REPROBE_SECONDS,
        )


def cache_backend_available() -> bool:
    _sync_backend()
    if not _backend_marked_down:
        return True
    return time.monotonic() >= _backend_down_until


def reset_backend_availability() -> None:
    global _backend_key, _backend_reports_delivery, _backend_marked_down
    global _backend_down_until
    with _backend_state_lock:
        _backend_key = None
        _backend_reports_delivery = False
        _backend_marked_down = False
        _backend_down_until = 0.0


def make_key(domain: str, *parts: Any) -> str:
    cleaned: list[str] = []
    for part in parts:
        text = str(part).strip().replace(":", "_").replace("/", "_")
        if text:
            cleaned.append(text)
    return ":".join([f"zaminex:{CACHE_VERSION}:{domain}"] + cleaned)


def cache_get(key: str) -> Any:
    if not cache_backend_available():
        return None
    try:
        return _decode(_cache().get(key))
    except Exception:
        return None


def cache_set(key: str, value: Any, timeout: int | float | None) -> bool:
    if not cache_backend_available():
        return False
    try:
        delivered = _cache().set(key, _encode(value), timeout)
    except Exception:
        note_cache_delivered(None)
        return False
    note_cache_delivered(delivered)
    return True


def cache_delete(key: str) -> None:
    if not cache_backend_available():
        return
    try:
        _cache().delete(key)
    except Exception:
        pass


def cache_add(key: str, value: Any, timeout: int | float | None) -> bool | None:
    if not cache_backend_available():
        return None
    try:
        acquired = _cache().add(key, _encode(value), timeout)
    except Exception:
        acquired = None

    note_cache_delivered(acquired is not None)
    return acquired


def cache_or_compute(
    key: str,
    compute: Callable[[], Any],
    timeout: int | float | None,
    *,
    lock: bool = True,
) -> Any:
    value = cache_get(key)
    if value is not None:
        return value

    if not lock:
        value = compute()
        cache_set(key, value, timeout)
        return value

    lock_key = key + _LOCK_SUFFIX
    won = cache_add(lock_key, "1", _LOCK_TIMEOUT)

    if won is False:
        deadline = time.monotonic() + _LOCK_MAX_WAIT
        while True:
            time.sleep(_LOCK_POLL_SECONDS)
            value = cache_get(key)
            if value is not None:
                return value
            if time.monotonic() >= deadline:
                break

    value = compute()
    cache_set(key, value, timeout)
    if won:
        cache_delete(lock_key)
    return value


def _lock_gone(key: str) -> bool:
    if not cache_backend_available():
        return True
    try:
        return _cache().get(key) is None
    except Exception:
        return True


@contextmanager
def with_lock(
    key: str,
    timeout: int | float = _LOCK_TIMEOUT,
    wait: int | float = _LOCK_MAX_WAIT,
    poll: int | float = _LOCK_POLL_SECONDS,
) -> Iterator[bool]:
    acquired = cache_add(key, "1", timeout)
    owned = acquired is True
    if acquired is False:
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline and not _lock_gone(key):
            time.sleep(poll)
    try:
        yield owned
    finally:
        if owned:
            cache_delete(key)
