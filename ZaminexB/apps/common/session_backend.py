from __future__ import annotations

from typing import Any

from django.contrib.sessions.backends.cached_db import SessionStore as CachedDBSessionStore

from apps.common import cache_utils

__all__ = ["SessionStore"]


class _SessionCacheGuard:
    def __init__(self, wrapped: Any) -> None:
        self._wrapped = wrapped

    def __getattr__(self, name: str) -> Any:
        if name == "_wrapped":
            raise AttributeError(name)
        return getattr(self._wrapped, name)

    def get(self, key: str, default: Any = None, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return default
        return self._wrapped.get(key, default, version)

    def set(self, key: str, value: Any, timeout: Any = None, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return None
        delivered = self._wrapped.set(key, value, timeout, version)
        cache_utils.note_cache_delivered(delivered)
        return delivered

    def delete(self, key: str, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return None
        return self._wrapped.delete(key, version)

    def __contains__(self, key: str) -> bool:
        if not cache_utils.cache_backend_available():
            return False
        return key in self._wrapped

    async def aget(self, key: str, default: Any = None, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return default
        return await self._wrapped.aget(key, default, version)

    async def aset(self, key: str, value: Any, timeout: Any = None, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return None
        delivered = await self._wrapped.aset(key, value, timeout, version)
        cache_utils.note_cache_delivered(delivered)
        return delivered

    async def adelete(self, key: str, version: Any = None) -> Any:
        if not cache_utils.cache_backend_available():
            return None
        return await self._wrapped.adelete(key, version)


class SessionStore(CachedDBSessionStore):
    def __init__(self, session_key: str | None = None) -> None:
        super().__init__(session_key)
        if not isinstance(self._cache, _SessionCacheGuard):
            self._cache = _SessionCacheGuard(self._cache)
