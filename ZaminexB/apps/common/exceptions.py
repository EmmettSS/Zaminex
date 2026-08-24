import re

from django.utils.encoding import force_str
from rest_framework.views import exception_handler


_EXACT_TRANSLATIONS = {
    "Authentication credentials were not provided.": "برای دسترسی ابتدا وارد حساب کاربری خود شوید.",
    "Invalid username/password.": "نام کاربری یا رمز عبور واردشده صحیح نیست.",
    "Not found.": "موردی یافت نشد.",
    "Permission denied.": "شما اجازه انجام این عملیات را ندارید.",
    "You do not have permission to perform this action.": "شما اجازه انجام این عملیات را ندارید.",
    "You do not have permission to access this page.": "شما اجازه دسترسی به این صفحه را ندارید.",
    "This field is required.": "این فیلد الزامی است.",
    "This field may not be blank.": "این فیلد نمی‌تواند خالی باشد.",
    "This field may not be null.": "این فیلد نمی‌تواند بدون مقدار باشد.",
    "A valid integer is required.": "یک عدد صحیح معتبر وارد کنید.",
    "A valid number is required.": "یک عدد معتبر وارد کنید.",
    "Enter a valid email address.": "نشانی ایمیل معتبر نیست.",
    "Enter a valid URL.": "نشانی اینترنتی معتبر نیست.",
    "Enter a valid date.": "تاریخ معتبر وارد کنید.",
    "Enter a valid date/time.": "تاریخ و زمان معتبر وارد کنید.",
    "Invalid date.": "تاریخ معتبر نیست.",
    "Invalid datetime.": "تاریخ و زمان معتبر نیست.",
    "No file was submitted.": "فایلی ارسال نشده است.",
    "The submitted data was not a file. Check the encoding type on the form.": "داده ارسال‌شده فایل معتبر نیست.",
    "The submitted file is empty.": "فایل ارسال‌شده خالی است.",
    "Upload a valid image. The file you uploaded was either not an image or a corrupted image.": "تصویر معتبر بارگذاری کنید. فایل ارسالی تصویر نیست یا خراب است.",
    "Ensure this field has no more than 255 characters.": "طول این فیلد نباید بیشتر از ۲۵۵ کاراکتر باشد.",
}

_PATTERN_TRANSLATIONS = [
    (re.compile(r'^"(?P<value>.+)" is not a valid choice\.$'), lambda m: f"«{m.group('value')}» گزینه معتبری نیست."),
    (re.compile(r"^Invalid pk \"(?P<value>.+)\" - object does not exist\.$"), lambda m: "گزینه انتخاب‌شده وجود ندارد."),
    (re.compile(r"^Incorrect type\. Expected pk value, received (?P<value>.+)\.$"), lambda m: "نوع مقدار ارسالی برای شناسه معتبر نیست."),
    (re.compile(r"^Ensure this value is greater than or equal to (?P<value>.+)\.$"), lambda m: f"این مقدار باید بزرگ‌تر یا مساوی {m.group('value')} باشد."),
    (re.compile(r"^Ensure this value is less than or equal to (?P<value>.+)\.$"), lambda m: f"این مقدار باید کوچک‌تر یا مساوی {m.group('value')} باشد."),
    (re.compile(r"^Ensure this field has no more than (?P<value>\d+) characters\.$"), lambda m: f"طول این فیلد نباید بیشتر از {m.group('value')} کاراکتر باشد."),
    (re.compile(r"^Ensure this field has at least (?P<value>\d+) characters\.$"), lambda m: f"طول این فیلد باید حداقل {m.group('value')} کاراکتر باشد."),
    # DecimalField validation (e.g. latitude/longitude, prices). The stock
    # messages are cryptic; rewrite them so the user understands the limit.
    (re.compile(r"^Ensure that there are no more than (?P<value>\d+) digits in total\.$"), lambda m: f"این عدد نباید در مجموع بیشتر از {m.group('value')} رقم داشته باشد."),
    (re.compile(r"^Ensure that there are no more than (?P<value>\d+) decimal places\.$"), lambda m: f"این عدد نباید بیشتر از {m.group('value')} رقم اعشار داشته باشد."),
    (re.compile(r"^Ensure that there are no more than (?P<value>\d+) digits before the decimal point\.$"), lambda m: f"این عدد نباید بیشتر از {m.group('value')} رقم صحیح (قبل از ممیز) داشته باشد."),
    (re.compile(r"^Datetime has wrong format\. Use one of these formats instead: (?P<value>.+)\.$"), lambda m: "فرمت تاریخ و زمان معتبر نیست."),
    (re.compile(r"^Date has wrong format\. Use one of these formats instead: (?P<value>.+)\.$"), lambda m: "فرمت تاریخ معتبر نیست."),
]


def _translate_message(value):
    if isinstance(value, dict):
        return {key: _translate_message(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_translate_message(item) for item in value]

    text = force_str(value)
    if text in _EXACT_TRANSLATIONS:
        return _EXACT_TRANSLATIONS[text]

    for pattern, replacement in _PATTERN_TRANSLATIONS:
        match = pattern.match(text)
        if match:
            return replacement(match)

    return text


# Machine-readable codes the SPA switches on. Everything the API returns is
# translated to Persian for the user, which makes `detail` unusable as a
# signal: "your session ended" and "you may not do this" are both a 403 with a
# Persian sentence, and matching on that sentence would break the moment the
# wording is improved.
#
# DRF already assigns every APIException a stable `code` (`not_authenticated`,
# `permission_denied`, `throttled`, …); it simply does not put it in the body.
# Surfacing it alongside `detail` gives the frontend an exact, translation-proof
# discriminator so it can send an expired session back to the login page while
# showing a plain error for a genuine permission denial.
#
# This is purely additive — `detail` keeps its shape and wording, so every
# existing reader is unaffected.
CSRF_FAILED_CODE = "csrf_failed"


def _detail_code(exc, response):
    """The stable code for this error, or None when there isn't a useful one."""
    code = getattr(getattr(exc, "detail", None), "code", None)
    if code is None:
        code = getattr(exc, "default_code", None)
    if not isinstance(code, str) or not code:
        # Django's own Http404 / PermissionDenied carry no DRF code, but the
        # handler has already mapped them onto a status. Derive the code from
        # that so a missing record is still reported consistently.
        return {404: "not_found", 403: "permission_denied"}.get(
            getattr(response, "status_code", None)
        )

    # DRF raises a plain PermissionDenied for a failed CSRF check, which is
    # indistinguishable from a role denial by code alone. The original English
    # detail is the only marker, so it is mapped to a dedicated code before the
    # message is translated.
    if code == "permission_denied":
        raw = force_str(getattr(exc, "detail", "") or "")
        if raw.startswith("CSRF Failed"):
            return CSRF_FAILED_CODE

    return code


def persian_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    code = _detail_code(exc, response)
    response.data = _translate_message(response.data)

    # Only annotate the `{"detail": ...}` envelope. Field-error payloads are
    # keyed by field name and adding a `code` key there could collide with a
    # real model field.
    if code and isinstance(response.data, dict) and "detail" in response.data:
        response.data.setdefault("code", code)

    return response
