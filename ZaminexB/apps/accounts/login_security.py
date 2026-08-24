from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import LoginAttempt


DEFAULT_LOGIN_FAILURE_LIMIT = 5
DEFAULT_LOGIN_LOCKOUT_SECONDS = 10 * 60
DEFAULT_LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60


def get_failure_limit() -> int:
    return int(getattr(settings, "LOGIN_FAILURE_LIMIT", DEFAULT_LOGIN_FAILURE_LIMIT))


def get_lockout_seconds() -> int:
    return int(getattr(settings, "LOGIN_LOCKOUT_SECONDS", DEFAULT_LOGIN_LOCKOUT_SECONDS))


def get_failure_window_seconds() -> int:
    return int(
        getattr(settings, "LOGIN_FAILURE_WINDOW_SECONDS", DEFAULT_LOGIN_FAILURE_WINDOW_SECONDS)
    )


def normalize_login_identifier(username: str | None) -> str:
    """Normalize the identifier used for account-scoped login protection."""
    return (username or "").strip().casefold()


def remaining_lockout_seconds(locked_until) -> int:
    if not locked_until:
        return 0
    seconds = int((locked_until - timezone.now()).total_seconds())
    return max(seconds, 0)


def format_lockout_message(locked_until) -> str:
    remaining = remaining_lockout_seconds(locked_until)
    minutes = max(1, (remaining + 59) // 60)
    return (
        f"به دلیل چند تلاش ناموفق، ورود با این نام کاربری تا {_to_persian_digits(minutes)} دقیقه دیگر مسدود است. "
        "لطفاً بعداً دوباره تلاش کنید."
    )


def get_active_lock(username: str | None):
    """Return locked_until when the normalized username is currently locked."""
    identifier = normalize_login_identifier(username)
    if not identifier:
        return None

    try:
        attempt = LoginAttempt.objects.get(username=identifier)
    except LoginAttempt.DoesNotExist:
        return None

    now = timezone.now()
    if attempt.locked_until and attempt.locked_until > now:
        return attempt.locked_until

    # Clean expired locks lazily so the next login starts with a fresh state.
    # Do not clear non-locked failed counters here; the rolling failure window
    # is handled in record_failed_login().
    if attempt.locked_until:
        attempt.failed_attempts = 0
        attempt.locked_until = None
        attempt.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
    return None


def record_failed_login(username: str | None, request=None):
    """Persist one failed login attempt and return locked_until if a lock starts."""
    identifier = normalize_login_identifier(username)
    if not identifier:
        return None

    now = timezone.now()
    window_started_after = now - timedelta(seconds=get_failure_window_seconds())

    with transaction.atomic():
        attempt, _ = LoginAttempt.objects.select_for_update().get_or_create(
            username=identifier
        )

        if attempt.locked_until and attempt.locked_until > now:
            return attempt.locked_until

        if attempt.last_failed_at and attempt.last_failed_at < window_started_after:
            attempt.failed_attempts = 0
            attempt.locked_until = None

        attempt.failed_attempts += 1
        attempt.last_failed_at = now

        if request is not None:
            attempt.last_ip = _client_ip(request)
            attempt.last_user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]

        if attempt.failed_attempts >= get_failure_limit():
            attempt.locked_until = now + timedelta(seconds=get_lockout_seconds())

        attempt.save(
            update_fields=[
                "failed_attempts",
                "locked_until",
                "last_failed_at",
                "last_ip",
                "last_user_agent",
                "updated_at",
            ]
        )
        return attempt.locked_until if attempt.locked_until and attempt.locked_until > now else None


def reset_login_attempts(username: str | None) -> None:
    """Clear failed-attempt state after a successful login."""
    identifier = normalize_login_identifier(username)
    if not identifier:
        return
    LoginAttempt.objects.filter(username=identifier).delete()


def _to_persian_digits(value: int) -> str:
    return str(value).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None
