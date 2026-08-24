import threading

_thread_locals = threading.local()


def get_current_user():
    return getattr(_thread_locals, "user", None)


def set_current_user(user):
    _thread_locals.user = user


def clear_current_user():
    if hasattr(_thread_locals, "user"):
        del _thread_locals.user
