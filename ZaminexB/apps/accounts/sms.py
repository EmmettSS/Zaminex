from __future__ import annotations

import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.common import cache_utils

from .models import (
    AdminProfile,
    ConsultantProfile,
    LoginSettings,
    SmsLoginCode,
    SmsProviderSettings,
    UserRole,
)

logger = logging.getLogger(__name__)


def otp_length() -> int:
    from django.conf import settings

    return int(getattr(settings, "SMS_OTP_LENGTH", 6))


def otp_ttl_seconds() -> int:
    from django.conf import settings

    return int(getattr(settings, "SMS_OTP_TTL_SECONDS", 2 * 60))


def otp_max_attempts() -> int:
    from django.conf import settings

    return int(getattr(settings, "SMS_OTP_MAX_ATTEMPTS", 5))


def otp_resend_cooldown_seconds() -> int:
    from django.conf import settings

    return int(getattr(settings, "SMS_OTP_RESEND_COOLDOWN_SECONDS", 60))


def _request_timeout() -> int:
    from django.conf import settings

    return int(getattr(settings, "SMS_REQUEST_TIMEOUT", 10))


def active_login_method() -> str:
    return LoginSettings.get_solo().method


def set_login_method(method: str) -> None:
    obj = LoginSettings.get_solo()
    obj.method = method
    obj.save(update_fields=["method", "updated_at"])


def is_sms_configured() -> bool:
    config = SmsProviderSettings.get_solo()
    return bool(
        config.smsir_api_key_plain and (config.smsir_template_id or "").strip()
    )


_INVALID_MOBILE_MESSAGE = (
    "شماره موبایل معتبر نیست. شماره باید با ۰۹ شروع شود و ۱۱ رقم باشد."
)


def normalize_mobile(raw: str | None) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    elif len(digits) == 12 and digits.startswith("98"):
        digits = "0" + digits[2:]
    elif not (len(digits) == 11 and digits.startswith("0")):
        raise ValueError(_INVALID_MOBILE_MESSAGE)

    if len(digits) != 11 or not digits.startswith("09"):
        raise ValueError(_INVALID_MOBILE_MESSAGE)
    return digits


def _inactive_account_message() -> str:
    from .forms import INACTIVE_ACCOUNT_MESSAGE

    return INACTIVE_ACCOUNT_MESSAGE


def find_user_by_mobile(mobile: str):
    candidates = []

    consultant = (
        ConsultantProfile.objects.filter(mobile=mobile).select_related("user").first()
    )
    if consultant is not None and consultant.user.role == UserRole.AGENT:
        candidates.append(
            (consultant.user, consultant.is_active, _inactive_account_message())
        )

    admin = AdminProfile.objects.filter(mobile=mobile).select_related("user").first()
    if admin is not None and admin.user.role == UserRole.ADMIN:
        candidates.append((admin.user, admin.is_active, "این حساب کاربری غیرفعال است."))

    for user, profile_active, _reason in candidates:
        if user.is_active and profile_active:
            return user, None

    for user, profile_active, reason in candidates:
        if not user.is_active or not profile_active:
            return None, reason

    return None, None


def _generate_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(otp_length()))


def issue_code(mobile: str) -> str:
    code = _generate_code()
    expires_at = timezone.now() + timedelta(seconds=otp_ttl_seconds())
    with transaction.atomic():
        SmsLoginCode.objects.filter(mobile=mobile).delete()
        SmsLoginCode.objects.create(
            mobile=mobile,
            code_hash=make_password(code),
            expires_at=expires_at,
        )
    return code


def resend_cooldown_remaining(mobile: str) -> int:
    latest = SmsLoginCode.objects.filter(mobile=mobile).order_by("-created_at").first()
    if latest is None:
        return 0
    elapsed = int((timezone.now() - latest.created_at).total_seconds())
    return max(0, otp_resend_cooldown_seconds() - elapsed)


def _attempt_counter_key(mobile: str) -> str:
    return cache_utils.make_key("sms", "attempts", mobile)


def failed_verifies(mobile: str) -> int:
    value = cache_utils.cache_get(_attempt_counter_key(mobile))
    return value if isinstance(value, int) else 0


def mobile_attempt_cap() -> int:
    return otp_max_attempts() * 2


def _note_failed_verify(mobile: str) -> int:
    total = failed_verifies(mobile) + 1
    cache_utils.cache_set(_attempt_counter_key(mobile), total, otp_ttl_seconds() * 2)
    return total


def _clear_failed_verifies(mobile: str) -> None:
    cache_utils.cache_delete(_attempt_counter_key(mobile))


class OtpVerificationError(Exception):
    pass


def verify_code(mobile: str, code: str):
    if failed_verifies(mobile) >= mobile_attempt_cap():
        raise OtpVerificationError(
            "به دلیل چند تلاش ناموفق، ورود با کد پیامکی برای این شماره موقتاً متوقف شد. "
            "کمی بعد دوباره تلاش کنید."
        )

    record = SmsLoginCode.objects.filter(mobile=mobile).order_by("-created_at").first()
    if record is None:
        raise OtpVerificationError(
            "کد تأیید معتبر نیست یا منقضی شده است. دوباره درخواست کد بدهید."
        )

    now = timezone.now()
    if record.consumed_at is not None:
        raise OtpVerificationError(
            "این کد قبلاً استفاده شده است. دوباره درخواست کد بدهید."
        )
    if record.expires_at <= now:
        raise OtpVerificationError("کد تأیید منقضی شده است. دوباره درخواست کد بدهید.")

    if record.attempts >= otp_max_attempts():
        raise OtpVerificationError(
            "به دلیل چند تلاش ناموفق، این کد باطل شد. دوباره درخواست کد بدهید."
        )

    if not check_password(code, record.code_hash):
        record.attempts += 1
        record.save(update_fields=["attempts"])
        _note_failed_verify(mobile)
        raise OtpVerificationError("کد تأیید واردشده صحیح نیست.")

    record.consumed_at = now
    record.save(update_fields=["consumed_at"])
    _clear_failed_verifies(mobile)

    user, reason = find_user_by_mobile(mobile)
    if user is None:
        if reason:
            raise OtpVerificationError(reason)
        raise OtpVerificationError(
            "حسابی برای این شماره یافت نشد. با مدیریت مجموعه تماس بگیرید."
        )
    return user


class SmsSendError(Exception):
    pass


def _truncate(value: str, limit: int = 200) -> str:
    text = (value or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 3] + "…"


def _http_post(url: str, body: bytes, headers: dict, timeout: int) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise SmsSendError(
            f"پاسخ خطا از سرویس پیامک (HTTP {exc.code}): {_truncate(detail)}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SmsSendError(
            f"اتصال به سرویس پیامک برقرار نشد: {_truncate(str(exc))}"
        ) from exc


def _smsir_success(body: str) -> bool:
    text = (body or "").strip()
    if not text:
        return False
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text in {"1", "true", "True"}
    if isinstance(data, dict):
        if data.get("status") in (1, "1", 200, "200"):
            return True
        if data.get("success") in (True, "true", 1, "1"):
            return True
    return False


def _smsir_send(config: SmsProviderSettings, mobile: str, code: str) -> None:
    api_key = config.smsir_api_key_plain.strip()
    template_id = (config.smsir_template_id or "").strip()
    if not api_key:
        raise SmsSendError("سرویس اصلی (sms.ir) پیکربندی نشده است.")
    if not template_id:
        raise SmsSendError("شناسه قالب (templateId) سرویس sms.ir تنظیم نشده است.")

    payload: dict = {
        "mobile": mobile,
        "templateId": int(template_id) if template_id.isdigit() else template_id,
        "parameters": [{"name": "CODE", "value": code}],
    }
    line_number = (config.smsir_line_number or "").strip()
    if line_number:
        payload["lineNumber"] = int(line_number) if line_number.isdigit() else line_number

    status, body = _http_post(
        "https://api.sms.ir/v1/send/verify",
        json.dumps(payload).encode("utf-8"),
        {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "x-api-key": api_key,
        },
        _request_timeout(),
    )
    if status >= 400:
        raise SmsSendError(f"sms.ir پاسخ خطا داد (HTTP {status}).")
    if not _smsir_success(body):
        raise SmsSendError(f"sms.ir ارسال را تأیید نکرد: {_truncate(body)}")


def _kavenegar_send(config: SmsProviderSettings, mobile: str, code: str) -> None:
    api_key = config.kavenegar_api_key_plain.strip()
    if not api_key:
        raise SmsSendError("سرویس پشتیبان (کاوه‌نگار) پیکربندی نشده است.")

    template = (config.kavenegar_template_name or "").strip()
    if template:
        url = f"https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"
        params = {"receptor": mobile, "template": template, "token": code}
    else:
        sender = (config.kavenegar_sender or "").strip()
        if not sender:
            raise SmsSendError("شماره فرستنده کاوه‌نگار تنظیم نشده است.")
        message = (config.kavenegar_message or "کد ورود شما: {code}").replace(
            "{code}", code
        )
        url = f"https://api.kavenegar.com/v1/{api_key}/sms/send.json"
        params = {"receptor": mobile, "sender": sender, "message": message}

    status, body = _http_post(
        url,
        urllib.parse.urlencode(params).encode("utf-8"),
        {"Content-Type": "application/x-www-form-urlencoded"},
        _request_timeout(),
    )
    if status >= 400:
        raise SmsSendError(f"کاوه‌نگار پاسخ خطا داد (HTTP {status}).")

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmsSendError("پاسخ کاوه‌نگار قابل تفسیر نبود.") from exc

    ret = data.get("return") or {}
    if ret.get("status") != 200:
        raise SmsSendError(f"کاوه‌نگار: {ret.get('message') or 'خطای نامشخص'}")


def send_verification_code(mobile: str, code: str) -> None:
    config = SmsProviderSettings.get_solo()

    try:
        _smsir_send(config, mobile, code)
        return
    except Exception as exc:
        logger.warning("sms.ir failed, trying kavenegar: %s", exc)

    try:
        _kavenegar_send(config, mobile, code)
    except Exception as exc:
        logger.error("Both SMS providers failed: %s", exc)
        raise SmsSendError(
            "ارسال کد تأیید از هر دو سرویس پیامک ممکن نشد. "
            "لطفاً چند لحظه بعد دوباره تلاش کنید."
        ) from exc
