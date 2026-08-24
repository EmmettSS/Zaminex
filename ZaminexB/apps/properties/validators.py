"""Reusable validators for property file uploads."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Only accept common web image formats. Pillow already verifies the actual
# content when ImageField is saved, but rejecting unknown extensions early
# gives a clearer Persian error and prevents HTML/SVG uploads.
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB

# Appraisal reports (گزارش کارشناسی) are PDF-only, capped at 10 MB.
ALLOWED_APPRAISAL_EXTENSION = "pdf"
MAX_APPRAISAL_SIZE = 10 * 1024 * 1024  # 10 MB
# A valid PDF always carries the "%PDF-" magic header within its first
# kilobyte (the spec allows leading junk, in practice it is at offset 0).
PDF_MAGIC = b"%PDF-"


def validate_property_image(file):
    if not file:
        return
    # Size guard. Django's FILE_UPLOAD_MAX_MEMORY_SIZE is global; this is
    # specific to property images.
    if getattr(file, "size", 0) and file.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            _("حجم تصویر نباید بیشتر از ۵ مگابایت باشد.")
        )
    name = (getattr(file, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            _("فقط فایل‌های JPG، PNG و WebP مجاز هستند.")
        )
    # Pillow-based content check. If the bytes are not a real image, this
    # raises a clear validation error instead of a 500.
    try:
        from PIL import Image
    except Exception:
        return
    pos = file.tell()
    try:
        file.seek(0)
        with Image.open(file) as im:
            # verify() checks structural integrity without decoding
            # pixels; load() forces full decoding so truncated files
            # are rejected too.
            im.verify()
        file.seek(0)
        with Image.open(file) as im:
            im.load()
            fmt = (im.format or "").upper()
        if fmt not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError(
                _("فقط فایل‌های JPG، PNG و WebP مجاز هستند.")
            )
    except Exception as exc:
        raise ValidationError(
            _("فایل ارسال‌شده یک تصویر معتبر نیست.")
        ) from exc
    finally:
        file.seek(pos)


def validate_appraisal_pdf(file):
    """Validate an uploaded appraisal report (گزارش کارشناسی).

    The tab accepts exactly one PDF per property. Guards, in order:

    * size cap of 10 MB;
    * `.pdf` extension, so browsers and users get a clear Persian error
      before anything hits the disk;
    * the ``%PDF-`` magic header, so a renamed non-PDF never reaches
      storage. The browser's Content-Type is trivially spoofed, and a
      disguised HTML/JS file served under our origin would be a stored
      XSS vector, so the bytes themselves are inspected.
    """
    if not file:
        return
    if getattr(file, "size", 0) and file.size > MAX_APPRAISAL_SIZE:
        raise ValidationError(
            _("حجم گزارش کارشناسی نباید بیشتر از ۱۰ مگابایت باشد.")
        )
    name = (getattr(file, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext != ALLOWED_APPRAISAL_EXTENSION:
        raise ValidationError(
            _("فقط فایل PDF برای گزارش کارشناسی مجاز است.")
        )

    pos = 0
    try:
        pos = file.tell()
        file.seek(0)
        head = file.read(1024)
    except (AttributeError, ValueError, OSError):
        head = b""
    finally:
        try:
            file.seek(pos)
        except (AttributeError, ValueError, OSError):
            pass

    if not head or PDF_MAGIC not in head:
        raise ValidationError(
            _("فایل ارسال‌شده یک PDF معتبر نیست.")
        )
