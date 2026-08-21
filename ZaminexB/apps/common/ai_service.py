"""Reusable AI service for Zaminex.

This module is the single gateway for calling the configured LLM to produce
concise, structured Persian descriptions ("توصیف هوش مصنوعی") for consultants
and properties.

Design goals
------------
- **Configurable from Django admin**: the API base URL, key and model name are
  stored on ``CompanySettings`` and edited in the admin panel.
- **Provider-agnostic**: speaks the OpenAI-compatible ``/chat/completions``
  format, so it works with OpenAI, DeepSeek, Gemini's OpenAI-compat endpoint,
  local Ollama, vLLM, LM Studio, etc. Only the base URL + key + model change.
- **Deterministic output**: the prompt asks the model for a strict JSON object
  (``{positives, negatives, summary}``) and nothing else. The response is
  parsed defensively (markdown fences, code blocks, partial JSON) so it works
  with any model regardless of formatting quirks.
- **Reusable**: the same ``generate_description`` primitive is used by both the
  consultant and property endpoints, so adding another entity later is trivial.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import AIInsightCache, CompanySettings

# Cache TTL for generated descriptions (seconds). Even if the underlying data
# did not change, we refresh the description at least once per period so it does
# not go stale indefinitely.
AI_CACHE_TTL = 7 * 24 * 3600  # 7 days
CACHE_PREFIX = "ai:desc:"


class AIError(Exception):
    """Raised when AI is disabled or the upstream call fails."""


def ai_config() -> CompanySettings:
    """Return the singleton settings carrying the AI configuration."""
    return CompanySettings.get_solo()


def is_ai_configured() -> bool:
    s = ai_config()
    # The model name is optional: many OpenAI-compatible providers (Ollama,
    # vLLM, LM Studio, …) pick a sensible default when it is omitted, so we only
    # require the switch and the base URL to consider AI "configured".
    return bool(s.ai_enabled and s.ai_api_base_url)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

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
    """Build the prompt for a consultant description from analytics data."""
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
    """Build the prompt for a property description from analytics data."""
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


# ---------------------------------------------------------------------------
# Upstream HTTP call
# ---------------------------------------------------------------------------

def _urlopen(req, timeout):
    """Open the AI request and refuse redirects that leave the public HTTPS web."""
    from apps.common.ai_url import UnsafeAIURL, assert_public_https_url

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
    """Call an OpenAI-compatible chat/completions endpoint and return the text."""
    s = ai_config()
    from apps.common.ai_url import UnsafeAIURL, assert_public_https_url

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
    # The model name is optional. When it is empty we omit the field so the
    # provider can fall back to its own default instead of sending model="".
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
    # Support both OpenAI style (choices[].message.content) and some providers
    # that return `output_text` (Gemini compat) or `content`.
    content = (
        parsed.get("choices", [{}])[0].get("message", {}).get("content")
        or parsed.get("output_text")
        or parsed.get("content")
        or ""
    )
    return content


# ---------------------------------------------------------------------------
# Robust response parsing
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> Any:
    """Extract the first JSON object from a model response, tolerantly.

    Handles markdown fences (```json ... ```), surrounding prose, and stray
    characters. Returns the parsed object or raises ValueError.
    """
    if not raw:
        raise ValueError("پاسخ مدل خالی بود.")

    text = raw.strip()

    # 1. Strip markdown code fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    # 2. Try to locate a balanced JSON object within the text.
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

    # 3. Fallback: try to parse the whole (stripped) text.
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
    """Turn a model response into {positives, negatives, summary}."""
    obj = _extract_json(raw)
    positives = _clean_list(obj.get("positives") or obj.get("positive") or [])[:3]
    negatives = _clean_list(obj.get("negatives") or obj.get("negative") or [])[:3]
    summary = str(obj.get("summary") or "").strip()
    # Always ensure the lists have exactly 3 slots (may be empty if model gave fewer).
    return {
        "positives": positives,
        "negatives": negatives,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_description(data: dict[str, Any], *, entity: str) -> dict[str, Any]:
    """Generate a structured AI description for a consultant or property.

    ``entity`` is ``"consultant"`` or ``"property"``. Returns
    ``{positives, negatives, summary}``. Raises ``AIError`` when AI is
    disabled/unconfigured or the upstream call / parsing fails.
    """
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


# ---------------------------------------------------------------------------
# Fingerprint + cache
# ---------------------------------------------------------------------------

# Keys that change because the clock moved, not because the record changed.
# Including them in the fingerprint made some properties re-hit the model on
# every open (daysOnMarket / heatmap week labels / generatedAt).
_VOLATILE_KEYS = {
    "generatedAt",
    "generated_at",
    "meta",
    "tenureDays",
    "daysOnMarket",
    "effectiveExposureAvg",
    "engagementHeatmap",
    "exposureTimeline",
}


def _normalize_for_fingerprint(value: Any) -> Any:
    """Drop clock-derived fields and make numbers/decimals stable."""
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
    """Deterministic fingerprint of *this* entity's analytics data.

    The entity type and id are mixed in so two records with similar KPIs cannot
    collide. Clock-only fields are ignored so reopening the same page does not
    look like new data.
    """
    payload = {
        "entity": entity,
        "entityId": entity_id,
        "data": _normalize_for_fingerprint(data),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cache_key(entity: str, entity_id: Any) -> str:
    """One in-process key per record (fingerprint lives inside the value)."""
    return f"{CACHE_PREFIX}{entity}:{entity_id}"


def _store_description(entity: str, entity_id: Any, fingerprint: str, description: dict) -> None:
    bundle = {"fingerprint": fingerprint, "description": description}
    cache.set(_cache_key(entity, entity_id), bundle, timeout=AI_CACHE_TTL)
    AIInsightCache.objects.update_or_create(
        entity=entity,
        entity_id=int(entity_id),
        defaults={"fingerprint": fingerprint, "payload": description},
    )


def _read_cached(entity: str, entity_id: Any, fingerprint: str) -> dict[str, Any] | None:
    bundle = cache.get(_cache_key(entity, entity_id))
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
    cache.set(
        _cache_key(entity, entity_id),
        {"fingerprint": row.fingerprint, "description": row.payload},
        timeout=AI_CACHE_TTL,
    )
    return row.payload


def get_cached_description(
    data: dict[str, Any], *, entity: str, entity_id: Any
) -> dict[str, Any]:
    """Return a cached AI description or generate a fresh one.

    Strategy (fingerprint + shared store + TTL):

      1. Fingerprint *this* record's stable analytics (entity + id mixed in).
      2. Serve from the in-process cache, then from the database row, if the
         fingerprint still matches and the row is within the TTL.
      3. Otherwise call the model once and persist the result under this
         entity/id so another worker cannot mix it with a different record.

    Raises ``AIError`` when AI is disabled/unconfigured or the call fails.
    """
    if not is_ai_configured():
        raise AIError("هوش مصنوعی فعال نیست یا پیکربندی نشده است.")

    current_fp = data_fingerprint(data, entity=entity, entity_id=entity_id)
    cached = _read_cached(entity, entity_id, current_fp)
    if cached is not None:
        return cached

    description = generate_description(data, entity=entity)
    _store_description(entity, entity_id, current_fp, description)
    return description
