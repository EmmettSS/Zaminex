from __future__ import annotations

import threading
from typing import Any

from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    UserRateThrottle,
)

from . import cache_utils

__all__ = [
    "PasswordResetRateThrottle",
    "ResilientAnonRateThrottle",
    "ResilientScopedRateThrottle",
    "ResilientUserRateThrottle",
]

_local_history: dict[str, list[float]] = {}
_local_history_lock = threading.Lock()

_LOCAL_MAX_KEYS = 10_000


def _remember_local(key: str, history: list[float]) -> None:
    with _local_history_lock:
        _local_history[key] = list(history)
        while len(_local_history) > _LOCAL_MAX_KEYS:
            _local_history.pop(next(iter(_local_history)))


def _read_local(key: str) -> list[float] | None:
    with _local_history_lock:
        history = _local_history.get(key)
        return list(history) if history is not None else None


def _clear_local_history() -> None:
    with _local_history_lock:
        _local_history.clear()


class _ResilientCacheProxy:
    def __init__(self, shared: Any) -> None:
        self._shared = shared

    def get(self, key: str, default: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            history = _read_local(key)
            return default if history is None else history
        return self._shared.get(key, default)

    def set(self, key: str, value: Any, timeout: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            _remember_local(key, value)
            return True
        delivered = self._shared.set(key, value, timeout)
        cache_utils.note_cache_delivered(delivered)
        if not delivered and cache_utils.backend_reports_delivery():
            _remember_local(key, value)
        return delivered


class _ResilientRateThrottle:
    def allow_request(self, request: Any, view: Any) -> bool:
        if not isinstance(self.cache, _ResilientCacheProxy):
            self.cache = _ResilientCacheProxy(self.cache)
        return super().allow_request(request, view)


class ResilientAnonRateThrottle(_ResilientRateThrottle, AnonRateThrottle):
    """"""


class ResilientUserRateThrottle(_ResilientRateThrottle, UserRateThrottle):
    """"""


class ResilientScopedRateThrottle(_ResilientRateThrottle, ScopedRateThrottle):
    """"""


class PasswordResetRateThrottle(ResilientAnonRateThrottle):
    scope = "password_reset"
