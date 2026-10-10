from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_APPRAISAL_EXTENSION = "pdf"
MAX_APPRAISAL_SIZE = 10 * 1024 * 1024

PDF_MAGIC = b"%PDF-"


def validate_property_image(file):
    if not file:
        return
    
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
    
    try:
        from PIL import Image
    except Exception:
        return
    pos = file.tell()
    try:
        file.seek(0)
        with Image.open(file) as im:
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
