"""Report / analytics service layer.

All heavy lifting for the Reports pages lives here so views stay thin,
queries stay optimized, and calculations are easy to unit-test.

Scoping rules (security-critical):
- Property-level reports are ALWAYS computed from the single Property and its
  related records (tasks, followups, listings, images). No global leakage.
- Consultant / admin aggregate reports filter related records by the
  consultant/owner scope and never bypass permissions of the caller.
"""

from __future__ import annotations

import datetime
import csv
import io
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from django.db.models import (
    Avg,
    Case,
    Count,
    DateField,
    ExpressionWrapper,
    F,
    IntegerField,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.accounts.models import ConsultantProfile, UserRole
from apps.followups.models import FollowUp, FollowUpStatus
from apps.listings.models import Listing
from apps.properties.models import Property, PropertyImage
from apps.tasks.models import Task


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

BINS_TENURE_DAYS = [
    (0, 30, "0–30"),
    (30, 90, "30–90"),
    (90, 180, "90–180"),
    (180, 365, "180–365"),
    (365, 730, "1–2 سال"),
    (730, 1_000_000, "2+ سال"),
]

BINS_IMAGES_COUNT = [
    (0, 1, "0"),
    (1, 3, "1–2"),
    (3, 6, "3–5"),
    (6, 10, "6–9"),
    (10, 1_000_000, "10+"),
]

BINS_DAYS_ON_MARKET = [
    (0, 7, "0–7"),
    (7, 30, "7–30"),
    (30, 90, "30–90"),
    (90, 180, "90–180"),
    (180, 365, "6–12 ماه"),
    (365, 1_000_000, "12+ ماه"),
]

HEAT_WINDOW_DAYS = 30


def _today() -> datetime.date:
    return timezone.now().date()


def _as_date(v):
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    return v


def _days_between(start, end=None) -> int | None:
    start = _as_date(start)
    if start is None:
        return None
    end = _as_date(end) or _today()
    return max(0, (end - start).days)


def _safe_div(n: float, d: float) -> float | None:
    if not d:
        return None
    return round(n / d, 4)


def _bin_histogram(values: Iterable[int | float | None], bins) -> list[dict[str, Any]]:
    """Group numeric values into bins (min-inclusive, max-exclusive)."""
    counts = {label: 0 for _, _, label in bins}
    for v in values:
        if v is None:
            continue
        for lo, hi, label in bins:
            if lo <= v < hi:
                counts[label] += 1
                break
    return [{"label": label, "count": counts[label]} for _, _, label in bins]


def _round(value, digits=2):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Access-controlled querysets
# ---------------------------------------------------------------------------


def accessible_properties(user) -> Any:
    """Queryset of properties the user can access. Admin sees all, agents see theirs."""
    qs = Property.objects.select_related("consultant")
    if getattr(user, "role", None) != "ADMIN":
        qs = qs.filter(consultant=user)
    return qs


def get_property_for_user_or_403(user, property_id: int) -> Property:
    """Return the property if the user can access it; otherwise raise PermissionError."""
    qs = Property.objects.select_related("consultant")
    qs = qs.prefetch_related("images", "tasks", "followups", "listings")
    obj = qs.filter(pk=property_id).first()
    if obj is None:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("ملک مورد نظر وجود ندارد یا به آن دسترسی ندارید.")
    if getattr(user, "role", None) != "ADMIN" and obj.consultant_id != user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("شما به گزارش این ملک دسترسی ندارید.")
    return obj


# ---------------------------------------------------------------------------
# Single-property report
# ---------------------------------------------------------------------------


@dataclass
class PropertyReportResult:
    property_id: int
    title: str
    internal_code: str
    kpis: dict[str, Any]
    charts: dict[str, Any]
    warnings: list[str]
    meta: dict[str, Any]


def _property_tasks(prop: Property):
    return Task.objects.filter(property=prop).select_related("assigned_to", "created_by")


def _property_followups(prop: Property):
    return FollowUp.objects.filter(property=prop, is_archived=False).select_related(
        "consultant"
    )


def _property_listings(prop: Property):
    return Listing.objects.filter(property=prop).select_related(
        "created_by", "assigned_to"
    )


def compute_property_report(prop: Property, *, filters: dict | None = None) -> dict[str, Any]:
    """Compute the full scoped report for a single property.

    `filters` currently honours:
      - date_from, date_to (YYYY-MM-DD) — restricts the creation window used
        for follow-up / task / listing based counts and charts.
    """
    filters = filters or {}
    today = _today()
    now = timezone.now()
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")

    # ---- related data (scoped by property) ----------------------------------
    tasks_qs = Task.objects.filter(property=prop).exclude(
        status=Task.Status.CANCELLED
    )
    followups_qs = FollowUp.objects.filter(property=prop, is_archived=False)
    listings_qs = Listing.objects.filter(property=prop)
    images_qs = PropertyImage.objects.filter(property=prop)

    if date_from:
        tasks_qs = tasks_qs.filter(created_at__date__gte=date_from)
        followups_qs = followups_qs.filter(created_at__date__gte=date_from)
        listings_qs = listings_qs.filter(created_at__date__gte=date_from)
    if date_to:
        tasks_qs = tasks_qs.filter(created_at__date__lte=date_to)
        followups_qs = followups_qs.filter(created_at__date__lte=date_to)
        listings_qs = listings_qs.filter(created_at__date__lte=date_to)

    tasks = list(tasks_qs)
    followups = list(followups_qs)
    listings = list(
        listings_qs.annotate(
            start_date_date=ExpressionWrapper(
                F("start_date"), output_field=DateField()
            ),
            end_date_date=ExpressionWrapper(F("end_date"), output_field=DateField()),
        )
    )
    images_count = images_qs.count()

    warnings: list[str] = []

    # ---- 1. Tenure_Days -----------------------------------------------------
    tenure_days = _days_between(prop.created_at) if prop.created_at else None

    # ---- 2. Tasks_Overdue_Count (open overdue tasks by type) ----------------
    overdue_tasks = [
        t
        for t in tasks
        if t.status not in (Task.Status.COMPLETED, Task.Status.CANCELLED)
        and t.due_date
        and t.due_date < today
    ]
    overdue_followups = [
        f_
        for f_ in followups
        if f_.status == FollowUpStatus.SCHEDULED
        and not f_.is_archived
        and f_.scheduled_at
        and f_.scheduled_at < now
    ]
    overdue_followups_by_type: Counter[str] = Counter()
    for f_ in overdue_followups:
        overdue_followups_by_type[f_.get_follow_up_type_display() or f_.follow_up_type] += 1
    followups_overdue_chart = [
        {"label": label, "count": cnt}
        for label, cnt in sorted(overdue_followups_by_type.items(), key=lambda x: -x[1])
    ]
    if not followups_overdue_chart:
        followups_overdue_chart = [{"label": "بدون تأخیر", "count": 0}]
    overdue_by_type: Counter[str] = Counter()
    for t in overdue_tasks:
        overdue_by_type[t.get_task_type_display() or t.task_type] += 1
    tasks_overdue_chart = [
        {"label": label, "count": cnt}
        for label, cnt in sorted(overdue_by_type.items(), key=lambda x: -x[1])
    ]
    if not tasks_overdue_chart:
        tasks_overdue_chart = [{"label": "بدون تأخیر", "count": 0}]

    # ---- 3. Work completion (follow-ups + tasks), not self-reported odds ----
    by_type: dict[str, list[FollowUp]] = {}
    for f_ in followups:
        label = f_.get_follow_up_type_display() or f_.follow_up_type
        by_type.setdefault(label, []).append(f_)
    completion_chart = []
    for label, rows in sorted(by_type.items()):
        done = sum(1 for f_ in rows if f_.status == FollowUpStatus.COMPLETED)
        total = len(rows)
        completion_chart.append(
            {
                "label": label,
                "rate": round(done / total * 100, 1) if total else 0,
                "count": total,
                "completedCount": done,
            }
        )
    fu_done = sum(1 for f_ in followups if f_.status == FollowUpStatus.COMPLETED)
    task_done = sum(1 for t in tasks if t.status == Task.Status.COMPLETED)
    work_total = len(followups) + len(tasks)
    work_completion_rate = (
        round((fu_done + task_done) / work_total * 100, 1) if work_total else None
    )
    if work_completion_rate is None:
        warnings.append("هنوز پیگیری یا وظیفه‌ای برای این ملک ثبت نشده است.")

    # ---- 4. Price_Per_Sqm (map points) --------------------------------------
    # Pricing lives on the listing now; `effective_sale_price` reads the
    # property's sale listings and falls back to the legacy column.
    from apps.common.metrics import effective_sale_price as _sale_price

    pps = None
    _price = _sale_price(prop)
    if prop.area and float(prop.area) > 0 and _price is not None:
        pps = round(float(_price) / float(prop.area), 2)
    map_points = []
    if prop.latitude and prop.longitude and pps is not None:
        map_points.append(
            {
                "lat": float(prop.latitude),
                "lng": float(prop.longitude),
                "value": pps,
                "label": prop.title or prop.internal_code,
            }
        )
    else:
        warnings.append(
            "موقعیت جغرافیایی یا قیمت/متراژ برای نمایش روی نقشه ناقص است."
        )

    # ---- 5. Images_Count (histogram bucket is singular for this property;
    #         chart represents the distribution across THIS property's
    #         galleries vs listing richness – we use a simple bar since a
    #         single point histogram is useless. Kept as histogram-style bar.)
    images_histogram = [{"label": "تصاویر ثبت‌شده", "count": images_count}]

    # ---- 6. Days_On_Market --------------------------------------------------
    # Heuristic: earliest listing start_date; if no listing has a start_date
    # fall back to created_at. End is latest end_date of non-active listings,
    # otherwise today.
    listing_starts = [
        l.start_date_date for l in listings if l.start_date_date is not None
    ]
    dom_start = min(listing_starts) if listing_starts else _as_date(prop.created_at)
    # If all listings are ACTIVE/DRAFT/PAUSED, treat as still on market.
    still_active = any(
        l.status in (Listing.Status.ACTIVE, Listing.Status.DRAFT, Listing.Status.PAUSED)
        for l in listings
    )
    listing_ends = [l.end_date_date for l in listings if l.end_date_date is not None]
    if still_active or not listing_ends:
        dom_end = today
    else:
        dom_end = max(listing_ends)
    days_on_market = _days_between(dom_start, dom_end) if dom_start else None
    if not listing_starts:
        warnings.append(
            "روزهای حضور در بازار به‌صورت fallback از تاریخ ایجاد ملک محاسبه شد (آگهی با start_date یافت نشد)."
        )

    # Single-point "histogram" is not useful, so we bucket the listing
    # windows that contributed to the DoM calculation.
    dom_buckets = []
    if listings:
        durations = []
        for l in listings:
            s = l.start_date_date
            if s is None:
                durations.append(
                    _days_between(l.created_at.date() if l.created_at else today)
                )
            else:
                e = l.end_date_date if l.end_date_date else today
                durations.append(_days_between(s, e) or 0)
        dom_buckets = _bin_histogram(durations, BINS_DAYS_ON_MARKET)

    # ---- 7. Spatial_Density_Ratio (rooms/area). Scatter across listings. ----
    sdr = None
    if prop.area and float(prop.area) > 0:
        sdr = round(float(prop.rooms or 0) / float(prop.area), 4)
    scatter = []
    for l in listings:
        # x = days exposure, y = content-ish quality: priority * is_featured
        if l.start_date_date:
            eff_end = l.end_date_date if l.end_date_date else today
            eff = _days_between(l.start_date_date, eff_end)
        else:
            eff = _days_between(l.created_at)
        priority_val = int(l.priority or 0)
        scatter.append(
            {
                "x": eff or 0,
                "y": priority_val + (2 if l.is_featured else 0),
                "label": l.title or f"Listing #{l.pk}",
                "channel": l.publish_channel,
            }
        )
    if not scatter:
        warnings.append("تابع پراکندگی فضایی: هیچ آگهی برای این ملک ثبت نشده است.")

    # ---- 8. Price_Deviation_Index -------------------------------------------
    # Compare against comparable (same neighborhood, same deal_type). Require
    # at least 2 comparables; otherwise fall back to all neighborhood props.
    from apps.common.metrics import build_neighborhood_price_per_sqm_map as _build_map

    neighborhood_avg: float | None = None
    # Comparable neighbourhood properties, ALWAYS excluding the property itself
    # so it never compares against its own price and reports a false 0%.
    comparables_qs = Property.active_objects.exclude(area=0).filter(
        neighborhood=prop.neighborhood, deal_type=prop.deal_type
    ).exclude(pk=prop.pk)
    comp_count = comparables_qs.count()
    if comp_count >= 1:
        avg_map = _build_map(
            list(comparables_qs), exclude_id=prop.pk
        )
        neighborhood_avg = avg_map.get(prop.neighborhood)
        comparables_source = (
            "همسایه‌های هم‌نوع" if comp_count >= 2 else "همسایه‌های هم‌نوع (۱ مورد)"
        )
    else:
        # No comparable of the same deal type: fall back to all properties in
        # the neighbourhood (still excluding this property). If none exist,
        # leave the deviation as None instead of comparing against the property
        # itself and reporting a false 0%.
        fallback_qs = Property.active_objects.exclude(area=0).filter(
            neighborhood=prop.neighborhood
        ).exclude(pk=prop.pk)
        fallback_rows = list(fallback_qs)
        if fallback_rows:
            avg_map = _build_map(fallback_rows, exclude_id=prop.pk)
            neighborhood_avg = avg_map.get(prop.neighborhood)
            comparables_source = "همسایه‌ها (با فال‌بک به تمام معاملات)"
            warnings.append(
                "شاخص انحراف قیمت با فال‌بک به تمام معاملات محله محاسبه شد (تعداد مقایسه‌پذیر هم‌نوع کمتر از ۲ بود)."
            )
        else:
            warnings.append(
                "شاخص انحراف قیمت قابل محاسبه نیست (هیچ ملک مقایسه‌پذیری در این محله یافت نشد)."
            )
    price_deviation_index = None
    if pps is not None and neighborhood_avg:
        price_deviation_index = round((pps - neighborhood_avg) / neighborhood_avg, 4)

    deviation_chart = [
        {
            "label": "ملک",
            "value": pps or 0,
            "type": "property",
        },
        {
            "label": "میانگین محله",
            "value": round(neighborhood_avg, 2) if neighborhood_avg else 0,
            "type": "benchmark",
        },
    ]
    # Diverging bar: positive/negative deviation
    diverging = []
    if price_deviation_index is not None:
        diverging.append(
            {
                "label": "انحراف قیمت",
                "deviation": round(price_deviation_index * 100, 2),  # percent
            }
        )
    else:
        warnings.append(
            "شاخص انحراف قیمت قابل محاسبه نیست (میانگین محله یا قیمت/متراژ در دسترس نیست)."
        )

    # ---- 9. Geo_Precision_Flag ----------------------------------------------
    from apps.common.metrics import geo_precision_flag as _geo_flag

    geo_flag = _geo_flag(prop.latitude, prop.longitude)
    geo_donut = [
        {
            "name": "دقیق",
            "value": 1 if geo_flag else 0,
        },
        {
            "name": "نادقیق",
            "value": 0 if geo_flag else 1,
        },
    ]

    # ---- 10. Engagement_Heat_Score ------------------------------------------
    since = now - datetime.timedelta(days=HEAT_WINDOW_DAYS)
    recent_followups = [f_ for f_ in followups if f_.created_at and f_.created_at >= since]
    heat = len(recent_followups)
    task_weights = {
        Task.TaskType.VIEWING: 3,
        Task.TaskType.SITE_VISIT: 3,
        Task.TaskType.NEGOTIATION: 2,
        Task.TaskType.CONTRACT: 2,
    }
    for t in tasks:
        if not t.created_at or t.created_at < since:
            continue
        if t.status == Task.Status.CANCELLED:
            continue
        heat += task_weights.get(t.task_type, 1)
    # Build heatmap: week x activity_type over last 4 weeks
    heatmap = _build_engagement_heatmap(tasks, followups, since)

    # ---- 11. Publish_Channel ------------------------------------------------
    channel_counts: Counter[str] = Counter()
    for l in listings:
        channel_counts[l.get_publish_channel_display() or l.publish_channel or "نامشخص"] += 1
    channel_chart = [
        {"label": ch, "count": cnt} for ch, cnt in sorted(channel_counts.items())
    ] or [{"label": "WEBSITE", "count": 0}]

    # ---- 12. Avg_Lifespan per channel ---------------------------------------
    channel_lifespans: dict[str, list[int]] = {}
    for l in listings:
        ch_label = l.get_publish_channel_display() or l.publish_channel or "نامشخص"
        s = l.start_date_date or (l.created_at.date() if l.created_at else None)
        if not s:
            continue
        e = l.end_date_date if l.end_date_date else today
        days = _days_between(s, e) or 0
        channel_lifespans.setdefault(ch_label, []).append(days)
    lifespan_chart = []
    for ch, days_list in channel_lifespans.items():
        lifespan_chart.append(
            {
                "label": ch,
                "avgLifespan": round(sum(days_list) / len(days_list), 1),
                "count": len(days_list),
            }
        )
    lifespan_chart.sort(key=lambda r: -r["avgLifespan"])

    # ---- 13. Effective_Exposure_Days (timeline / Gantt) ---------------------
    timeline = []
    for l in listings:
        s = l.start_date_date or (l.created_at.date() if l.created_at else None)
        if not s:
            continue
        e = l.end_date_date if l.end_date_date and l.status != Listing.Status.ACTIVE else today
        days = _days_between(s, e)
        if days is None or days < 0:
            continue
        timeline.append(
            {
                "id": l.pk,
                "label": l.title or f"آگهی #{l.pk}",
                "channel": l.get_publish_channel_display() or l.publish_channel,
                "start": s.isoformat(),
                "end": e.isoformat(),
                "status": l.status,
                "days": days,
            }
        )
    timeline.sort(key=lambda r: r["start"])

    # ---- 14. Delegation_Indicator (stacked bar per channel) -----------------
    delegation_counts: dict[str, Counter[str]] = {}
    for l in listings:
        ch_label = l.get_publish_channel_display() or l.publish_channel or "نامشخص"
        if not l.assigned_to_id:
            bucket = "UNASSIGNED"
        elif l.created_by_id and l.assigned_to_id != l.created_by_id:
            bucket = "DELEGATED"
        else:
            bucket = "SELF_MANAGED"
        delegation_counts.setdefault(ch_label, Counter())[bucket] += 1
    delegation_chart = []
    for ch, ctr in delegation_counts.items():
        delegation_chart.append(
            {
                "label": ch,
                "unassigned": ctr.get("UNASSIGNED", 0),
                "selfManaged": ctr.get("SELF_MANAGED", 0),
                "delegated": ctr.get("DELEGATED", 0),
            }
        )
    if not delegation_chart:
        delegation_chart = [
            {"label": "—", "unassigned": 0, "selfManaged": 0, "delegated": 0}
        ]

    # ---- 15. Listing_Burn_Rate (gauge: 0..1) --------------------------------
    if listings:
        burned = sum(
            1
            for l in listings
            if l.status == Listing.Status.EXPIRED
            or (
                l.status == Listing.Status.ARCHIVED
                and prop.status != Property.Status.SOLD
            )
        )
        burn_rate = round(burned / len(listings), 4)
    else:
        burn_rate = None
        warnings.append(
            "نرخ اتلاف آگهی قابل محاسبه نیست (هیچ آگهی برای این ملک ثبت نشده)."
        )

    # ---- KPI rollups --------------------------------------------------------
    kpis = {
        "tenureDays": tenure_days,
        "tasksOverdueCount": len(overdue_tasks),
        "followupsOverdueCount": len(overdue_followups),
        "openTasksCount": sum(
            1 for t in tasks if t.status != Task.Status.COMPLETED
        ),
        "workCompletionRate": work_completion_rate,
        "pricePerSqm": pps,
        "imagesCount": images_count,
        "daysOnMarket": days_on_market,
        "spatialDensityRatio": sdr,
        "priceDeviationIndex": price_deviation_index,
        "geoPrecisionFlag": bool(geo_flag),
        "engagementHeatScore": heat,
        "listingCount": len(listings),
        "followupCount": len(followups),
        "listingBurnRate": burn_rate,
        "effectiveExposureAvg": _round(
            sum(item["days"] for item in timeline) / len(timeline) if timeline else None
        ),
    }

    charts = {
        "tenureHistogram": _bin_histogram([tenure_days] if tenure_days is not None else [], BINS_TENURE_DAYS),
        "tasksOverdueByType": tasks_overdue_chart,
        "followupsOverdueByType": followups_overdue_chart,
        "workCompletionByType": completion_chart,
        "priceMap": map_points,
        "imagesHistogram": images_histogram,
        "daysOnMarketHistogram": dom_buckets
        or [{"label": "0–7", "count": 0}],
        "spatialScatter": scatter,
        "priceDeviation": {
            "bars": deviation_chart,
            "diverging": diverging,
        },
        "geoDonut": geo_donut,
        "engagementHeatmap": heatmap,
        "publishChannel": channel_chart,
        "avgLifespanByChannel": lifespan_chart,
        "exposureTimeline": timeline,
        "delegationByChannel": delegation_chart,
        "burnRateGauge": {
            "value": burn_rate if burn_rate is not None else 0,
            "label": "نرخ اتلاف",
            "status": _burn_rate_label(burn_rate),
            "available": burn_rate is not None,
        },
    }

    return {
        "property": {
            "id": prop.pk,
            "title": prop.title,
            "internalCode": prop.internal_code,
            "neighborhood": prop.neighborhood,
            "status": prop.status,
            "consultantId": prop.consultant_id,
        },
        "kpis": kpis,
        "charts": charts,
        "warnings": warnings,
        "meta": {
            "filters": filters or {},
            "comparablesSource": comparables_source if price_deviation_index is not None else None,
            "generatedAt": timezone.now().isoformat(),
        },
    }


def _burn_rate_label(rate: float | None) -> str:
    if rate is None:
        return "ناموجود"
    if rate < 0.2:
        return "سالم"
    if rate < 0.5:
        return "متوسط"
    return "بحرانی"


def _build_engagement_heatmap(tasks, followups, since) -> list[dict[str, Any]]:
    """Return a 4-week × activity-type matrix of activity counts."""
    weeks = []
    now = timezone.now().date()
    for i in range(3, -1, -1):
        start_w = now - datetime.timedelta(days=(i + 1) * 7)
        end_w = now - datetime.timedelta(days=i * 7)
        weeks.append(
            {
                "label": f"{(3-i)+1} هفته پیش" if i else "این هفته",
                "start": start_w,
                "end": end_w,
            }
        )

    rows = [
        {"key": "followups", "label": "پیگیری"},
        {"key": "viewings", "label": "بازدید"},
        {"key": "negotiations", "label": "مذاکره/قرارداد"},
        {"key": "other_tasks", "label": "سایر وظایف"},
    ]
    for r in rows:
        r["values"] = [0] * len(weeks)

    def add_activity(ts: datetime.datetime | None, key: str, weight: int = 1):
        if ts is None:
            return
        d = ts.date() if isinstance(ts, datetime.datetime) else ts
        for i, w in enumerate(weeks):
            if w["start"] <= d < w["end"] or (i == len(weeks) - 1 and d >= w["start"]):
                for r in rows:
                    if r["key"] == key:
                        r["values"][i] += weight

    for f_ in followups:
        if f_.created_at and f_.created_at >= since:
            add_activity(f_.created_at, "followups")

    for t in tasks:
        if t.status == Task.Status.CANCELLED:
            continue
        if not t.created_at or t.created_at < since:
            continue
        if t.task_type in (Task.TaskType.VIEWING, Task.TaskType.SITE_VISIT):
            add_activity(t.created_at, "viewings", 1)
        elif t.task_type in (Task.TaskType.NEGOTIATION, Task.TaskType.CONTRACT):
            add_activity(t.created_at, "negotiations", 1)
        else:
            add_activity(t.created_at, "other_tasks", 1)

    return {"weeks": [w["label"] for w in weeks], "rows": rows}


# ---------------------------------------------------------------------------
# Aggregate (consultant/admin) reports
# ---------------------------------------------------------------------------


def compute_consultant_scope_report(user) -> dict[str, Any]:
    """Cross-property aggregate within the caller's accessible scope.

    - Admin: all active properties, aggregated across the portfolio.
    - Consultant: only their own properties.
    """
    qs = accessible_properties(user)
    props = list(
        qs.prefetch_related("images", "tasks", "followups", "listings").order_by(
            "-created_at"
        )
    )
    warnings: list[str] = []

    tenure_values = [
        _days_between(p.created_at) for p in props if p.created_at
    ]
    tenure_hist = _bin_histogram(tenure_values, BINS_TENURE_DAYS)

    img_values = [p.images.count() for p in props]
    img_hist = _bin_histogram(img_values, BINS_IMAGES_COUNT)

    # overdue tasks per property (sorted)
    today = _today()
    overdue_per_prop: list[dict[str, Any]] = []
    tasks_overdue_total = 0
    for p in props:
        cnt = (
            p.tasks.exclude(status=Task.Status.COMPLETED)
            .filter(due_date__lt=today)
            .count()
        )
        tasks_overdue_total += cnt
        overdue_per_prop.append(
            {"label": p.title or p.internal_code, "count": cnt}
        )
    overdue_per_prop.sort(key=lambda r: -r["count"])
    overdue_per_prop = overdue_per_prop[:20]

    followups_overdue_total = 0
    now = timezone.now()
    for p in props:
        followups_overdue_total += (
            p.followups.filter(
                is_archived=False,
                status=FollowUpStatus.SCHEDULED,
                scheduled_at__lt=now,
            ).count()
        )

    # price per sqm scatter (lat/lng → value)
    # One query resolves every property's sale price, so the map does not fire
    # a lookup per row.
    from apps.common.metrics import annotate_effective_prices as _price_map_for

    _prices = _price_map_for(props)
    price_map = []
    for p in props:
        _price = _prices.get(p.id, p.price)
        if p.latitude and p.longitude and p.area and float(p.area) > 0 and _price:
            price_map.append(
                {
                    "lat": float(p.latitude),
                    "lng": float(p.longitude),
                    "value": round(float(_price) / float(p.area), 2),
                    "label": p.title or p.internal_code,
                }
            )
    if not price_map:
        warnings.append(
            "نقشه قیمت/متر به‌دلیل نبود مختصات جغرافیایی در داده‌ها خالی است."
        )

    # publish channels across all listings in scope
    accessible_listings = Listing.objects.filter(property__in=props).select_related(
        "property"
    )
    channel_counts: Counter[str] = Counter()
    for l in accessible_listings:
        channel_counts[l.get_publish_channel_display() or l.publish_channel] += 1
    channel_chart = [{"label": k, "count": v} for k, v in channel_counts.items()]

    # geo precision donut
    from apps.common.metrics import geo_precision_flag

    geo_good = sum(1 for p in props if geo_precision_flag(p.latitude, p.longitude))
    geo_bad = len(props) - geo_good

    kpis = {
        "propertyCount": len(props),
        "listingCount": accessible_listings.count(),
        "avgTenureDays": _round(
            sum(tenure_values) / len(tenure_values) if tenure_values else None
        ),
        "tasksOverdueTotal": tasks_overdue_total,
        "followupsOverdueTotal": followups_overdue_total,
        "geoPrecisePercent": _round(geo_good / len(props) * 100) if props else None,
    }

    return {
        "kpis": kpis,
        "charts": {
            "tenureHistogram": tenure_hist,
            "imagesHistogram": img_hist,
            "overduePerProperty": overdue_per_prop,
            "priceMap": price_map,
            "publishChannel": channel_chart,
            "geoDonut": [
                {"name": "دقیق", "value": geo_good},
                {"name": "نادقیق", "value": geo_bad},
            ],
        },
        "warnings": warnings,
        "meta": {
            "scope": "ALL" if getattr(user, "role", None) == "ADMIN" else "OWNED",
            "generatedAt": timezone.now().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

CSV_TRANSLATIONS = {
    "propertyId": "شناسه ملک",
    "title": "عنوان",
    "internalCode": "کد داخلی",
    "neighborhood": "محله",
    "tenureDays": "روزهای تصدی",
    "tasksOverdueCount": "وظایف تأخیردار",
    "followupsOverdueCount": "پیگیری‌های تأخیردار",
    "openTasksCount": "وظایف باز",
    "workCompletionRate": "نرخ تکمیل کار",
    "pricePerSqm": "قیمت هر متر",
    "imagesCount": "تعداد تصاویر",
    "daysOnMarket": "روز در بازار",
    "spatialDensityRatio": "تراکم فضایی",
    "priceDeviationIndex": "شاخص انحراف قیمت",
    "geoPrecisionFlag": "دقت جغرافیایی",
    "engagementHeatScore": "امتیاز تعامل",
    "listingCount": "تعداد آگهی",
    "followupCount": "تعداد پیگیری",
    "listingBurnRate": "نرخ اتلاف",
    "effectiveExposureAvg": "میانگین روز نمایش",
}


def property_report_csv_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a single-property report into one CSV row with KPIs."""
    prop = report["property"]
    kpis = report["kpis"]
    row = {"propertyId": prop["id"], "title": prop["title"], "internalCode": prop["internalCode"]}
    for k, label in CSV_TRANSLATIONS.items():
        if k in kpis:
            v = kpis[k]
            if isinstance(v, bool):
                v = "true" if v else "false"
            row[label] = v
    return [row]


def _sanitize_csv_cell(value: Any) -> Any:
    """Neutralise formula injection in spreadsheet cells.

    Excel/LibreOffice treat cells beginning with ``=``, ``+``, ``-``, ``@``,
    tab or carriage return as formulas. An attacker who can control a field
    that ends up in a CSV export can otherwise turn it into a malicious
    formula. Prefixing a single quote keeps the visible text intact while
    preventing formula evaluation.
    """
    if not isinstance(value, str):
        return value
    if value and value[0] in {"=", "+", "-", "@", "\t", "\r"}:
        return f"\'{value}"
    return value


def render_csv(rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> str:
    if not rows:
        return ""
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    # BOM so Excel opens Persian correctly
    buf.write("\ufeff")
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {k: _sanitize_csv_cell(r.get(k, "")) for k in fieldnames}
        )
    return buf.getvalue()
