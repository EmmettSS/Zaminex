from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.common import cache_utils
from apps.common.models import CompanySettings

from .models import AIInsightCache

AI_CACHE_TTL = 7 * 24 * 3600

_AI_LOCK_TIMEOUT = 210
_AI_LOCK_WAIT = 15


class AIError(Exception):
    """"""


def ai_config() -> CompanySettings:
    return CompanySettings.get_solo()


def is_ai_configured() -> bool:
    s = ai_config()
    return bool(s.ai_enabled and s.ai_api_base_url)


SYSTEM_ROLE = (
    "تو تحلیلگر ارشد داده در مشاور املاک «زمینکس» هستی. "
    "فقط و فقط بر اساس داده‌های همین یک رکورد که در پیام کاربر آمده تحلیل می‌کنی. "
    "هرگز این رکورد را با ملک یا مشاور دیگری اشتباه نگیر و چیزی را که در داده نیست اختراع نکن. "
    "همیشه فقط یک شیء JSON معتبر برمی‌گردانی و هیچ متن، توضیح یا مقدمه‌ای خارج از JSON نمی‌نویسی."
)

OUTPUT_CONTRACT = (
    "خروجی باید دقیقاً به این شکل باشد و هیچ چیز دیگری (بدون حصار کد، بدون توضیح بیرون از JSON) ننویسی:\n"
    "{\n"
    '  "positives": ["نکته مثبت اول", "نکته مثبت دوم", "نکته مثبت سوم"],\n'
    '  "negatives": ["نکته منفی اول", "نکته منفی دوم", "نکته منفی سوم"],\n'
    '  "summary": "یک بند کامل و حرفه‌ای"\n'
    "}\n"
    "قواعد:\n"
    "- summary حداقل یک بند کامل است (۸۰ تا ۱۴۰ کلمه)، روان و کاربردی؛ هویت همین رکورد (نام و کد) را در بند بیاور.\n"
    "- positives و negatives دقیقاً ۳ مورد دارند. هر مورد یک جملهٔ کوتاه فارسی است و باید به عدد یا شاخص مشخصی از KPIها یا نمودارها اشاره کند.\n"
    "- اگر شاخصی در داده نیست، به‌جای حدس بگو که در داده‌ها ثبت نشده است.\n"
    "- فقط همین رکورد را توصیف کن."
)


def build_consultant_prompt(consultant: dict[str, Any]) -> str:
    data = json.dumps(consultant, ensure_ascii=False, default=str)
    name = consultant.get("fullName") or consultant.get("name") or "این مشاور"
    ident = consultant.get("id")
    ident_bit = f" با شناسه {ident}" if ident is not None else ""
    return (
        f"هویت قطعی رکورد: مشاور «{name}»{ident_bit}. فقط همین مشاور را تحلیل کن.\n\n"
        f"داده‌های تحلیلی (KPI و نمودارها) به شرح زیر است:\n{data}\n\n"
        "بر اساس همهٔ این شاخص‌ها (تکمیل وظایف، انجام به‌موقع، تکمیل پیگیری، پوشش بازاریابی، "
        "تعامل اخیر، ترکیب آگهی و وضعیت پیگیری) یک توصیف حرفه‌ای و کاربردی بنویس.\n"
        + OUTPUT_CONTRACT
    )


def build_property_prompt(property_data: dict[str, Any]) -> str:
    data = json.dumps(property_data, ensure_ascii=False, default=str)
    title = property_data.get("title") or "این ملک"
    code = property_data.get("internalCode") or property_data.get("id") or ""
    code_bit = f" با کد داخلی {code}" if code != "" else ""
    return (
        f"هویت قطعی رکورد: ملک «{title}»{code_bit}. فقط همین ملک را تحلیل کن؛ "
        "املاک دیگر محله صرفاً معیار مقایسهٔ قیمت هستند.\n\n"
        f"داده‌های تحلیلی (مشخصات، KPI و نمودارها) به شرح زیر است:\n{data}\n\n"
        "بر اساس همهٔ شاخص‌ها (قیمت هر متر، انحراف از عرف محله، روزهای حضور در بازار، "
        "تعداد تصاویر، امتیاز تعامل، آگهی‌ها، وظایف و پیگیری‌ها) یک توصیف حرفه‌ای و کاربردی بنویس.\n"
        + OUTPUT_CONTRACT
    )


def _urlopen(req, timeout):
    from apps.analytics.ai_url import UnsafeAIURL, assert_public_https_url

    class _SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            try:
                assert_public_https_url(newurl)
            except UnsafeAIURL as exc:
                raise AIError(str(exc)) from exc
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(_SafeRedirect)
    return opener.open(req, timeout=timeout)


def _chat_completion(system: str, user: str) -> str:
    s = ai_config()
    from apps.analytics.ai_url import UnsafeAIURL, assert_public_https_url

    try:
        base_url = assert_public_https_url(s.ai_api_base_url)
    except UnsafeAIURL as exc:
        raise AIError(str(exc)) from exc
    url = base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": 1400,
    }
    if s.ai_model:
        payload["model"] = s.ai_model
    headers = {"Content-Type": "application/json"}
    if s.ai_api_key_plain:
        headers["Authorization"] = f"Bearer {s.ai_api_key_plain}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = getattr(settings, "AI_REQUEST_TIMEOUT", 60)
    with _urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    content = (
        parsed.get("choices", [{}])[0].get("message", {}).get("content")
        or parsed.get("output_text")
        or parsed.get("content")
        or ""
    )
    return content


def _extract_json(raw: str) -> Any:
    if not raw:
        raise ValueError("پاسخ مدل خالی بود.")

    text = raw.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    start = text.find("{")
    if start == -1:
        raise ValueError("پاسخ مدل حاوی JSON نبود.")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"نمی‌توان پاسخ مدل را تفسیر کرد: {e}") from e


def _clean_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for it in items:
        s = str(it).strip()
        if s and s not in out:
            out.append(s)
    return out


def _parse_description(raw: str) -> dict[str, Any]:
    obj = _extract_json(raw)
    positives = _clean_list(obj.get("positives") or obj.get("positive") or [])[:3]
    negatives = _clean_list(obj.get("negatives") or obj.get("negative") or [])[:3]
    summary = str(obj.get("summary") or "").strip()
    return {
        "positives": positives,
        "negatives": negatives,
        "summary": summary,
    }


def generate_description(data: dict[str, Any], *, entity: str) -> dict[str, Any]:
    if not is_ai_configured():
        raise AIError("هوش مصنوعی فعال نیست یا پیکربندی نشده است.")

    if entity == "consultant":
        system = SYSTEM_ROLE
        user = build_consultant_prompt(data)
    else:
        system = SYSTEM_ROLE
        user = build_property_prompt(data)

    raw = _chat_completion(system, user)
    return _parse_description(raw)


_VOLATILE_KEYS = {
    "generatedAt",
    "generated_at",
    "meta",
    "tenureDays",
    "daysOnMarket",
    "effectiveExposureAvg",
    "engagementHeatmap",
    "exposureTimeline",
    "spatialScatter",
    "avgLifespanByChannel",
}


def _normalize_for_fingerprint(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _normalize_for_fingerprint(v)
            for k, v in value.items()
            if str(k) not in _VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_fingerprint(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, 6)
    if hasattr(value, "as_tuple") and hasattr(value, "quantize"):
        return str(value)
    return value


def data_fingerprint(
    data: dict[str, Any], *, entity: str | None = None, entity_id: Any = None
) -> str:
    payload = {
        "entity": entity,
        "entityId": entity_id,
        "data": _normalize_for_fingerprint(data),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_key(entity: str, entity_id: Any) -> str:
    return cache_utils.make_key("ai", "desc", entity, entity_id)


def _store_description(entity: str, entity_id: Any, fingerprint: str, description: dict) -> None:
    bundle = {"fingerprint": fingerprint, "description": description}
    cache_utils.cache_set(_cache_key(entity, entity_id), bundle, AI_CACHE_TTL)
    AIInsightCache.objects.update_or_create(
        entity=entity,
        entity_id=int(entity_id),
        defaults={"fingerprint": fingerprint, "payload": description},
    )


def _read_cached(entity: str, entity_id: Any, fingerprint: str) -> dict[str, Any] | None:
    bundle = cache_utils.cache_get(_cache_key(entity, entity_id))
    if isinstance(bundle, dict) and bundle.get("fingerprint") == fingerprint:
        desc = bundle.get("description")
        if isinstance(desc, dict):
            return desc

    row = AIInsightCache.objects.filter(entity=entity, entity_id=int(entity_id)).first()
    if row is None:
        return None
    age = timezone.now() - row.updated_at
    if row.fingerprint != fingerprint or age.total_seconds() > AI_CACHE_TTL:
        return None
    cache_utils.cache_set(
        _cache_key(entity, entity_id),
        {"fingerprint": row.fingerprint, "description": row.payload},
        AI_CACHE_TTL,
    )
    return row.payload


def get_cached_description(
    data: dict[str, Any], *, entity: str, entity_id: Any
) -> dict[str, Any]:
    if not is_ai_configured():
        raise AIError("هوش مصنوعی فعال نیست یا پیکربندی نشده است.")

    current_fp = data_fingerprint(data, entity=entity, entity_id=entity_id)
    cached = _read_cached(entity, entity_id, current_fp)
    if cached is not None:
        return cached

    lock_key = cache_utils.make_key("ai", "lock", entity, entity_id, current_fp)
    with cache_utils.with_lock(
        lock_key, timeout=_AI_LOCK_TIMEOUT, wait=_AI_LOCK_WAIT
    ):
        cached = _read_cached(entity, entity_id, current_fp)
        if cached is not None:
            return cached

        description = generate_description(data, entity=entity)
        _store_description(entity, entity_id, current_fp, description)
        return description


def peek_cached_description(
    data: dict[str, Any], *, entity: str, entity_id: Any
) -> dict[str, Any] | None:
    if not is_ai_configured():
        return None
    current_fp = data_fingerprint(data, entity=entity, entity_id=entity_id)
    return _read_cached(entity, entity_id, current_fp)
