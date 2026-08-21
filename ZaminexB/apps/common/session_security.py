"""Invalidate every stored session that belongs to a user."""

from importlib import import_module

from django.conf import settings


def _session_store():
    engine = getattr(settings, "SESSION_ENGINE", "django.contrib.sessions.backends.db")
    return import_module(engine).SessionStore


def flush_user_sessions(user, *, keep_session_key=None) -> int:
    """Delete all active sessions for ``user``.

    Works regardless of which session backend is configured (db, cached_db,
    file, cache) by iterating the store's own index instead of assuming the
    ``django_session`` table exists. Password changes already rotate
    ``get_session_auth_hash``; wiping the sessions makes that immediate and
    survives stale in-memory cache entries.
    """
    if user is None or not getattr(user, "pk", None):
        return 0

    uid = str(user.pk)
    deleted = 0
    store = _session_store()
    # ``get_model_cls`` is only available on the DB-backed engine, but the
    # iteration helper (iter_sessions/cache) behaves consistently across the
    # built-in backends.
    iterator = getattr(store, "iter_sessions", None)
    if iterator is None:  # pragma: no cover - defensive
        return 0

    for session in iterator():
        # SessionStore exposes the decoded payload either via .get_decoded()
        # (DB stores) or via .items() for cache-backed stores.
        try:
            data = session.get_decoded() if hasattr(session, "get_decoded") else dict(session)
        except Exception:
            continue
        if str(data.get("_auth_user_id") or "") != uid:
            continue
        if keep_session_key and getattr(session, "session_key", None) == keep_session_key:
            continue
        try:
            session.delete()
            deleted += 1
        except Exception:
            continue
    return deleted


# Backwards-compatible alias.
flush_user_sessions = flush_user_sessions
