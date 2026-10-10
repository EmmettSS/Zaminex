from importlib import import_module

from django.conf import settings


def _session_store():
    engine = getattr(settings, "SESSION_ENGINE", "django.contrib.sessions.backends.db")
    return import_module(engine).SessionStore


def flush_user_sessions(user, *, keep_session_key=None) -> int:
    if user is None or not getattr(user, "pk", None):
        return 0

    uid = str(user.pk)
    deleted = 0
    store = _session_store()
    
    iterator = getattr(store, "iter_sessions", None)
    if iterator is None:
        return 0

    for session in iterator():
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


flush_user_sessions = flush_user_sessions
