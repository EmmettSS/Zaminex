import datetime
from collections import Counter
from decimal import Decimal

import jdatetime

from django.db.models import Q
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import ConsultantProfile, UserRole
from apps.followups.models import FollowUp, FollowUpStatus
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

from .metrics import (
    build_neighborhood_price_stats_map,
    channel_marketing_summary,
    consultant_performance_metrics,
    consultant_ranking_metrics,
    consultant_followups_overdue_count,
    consultant_tasks_overdue_count,
    listing_marketing_metrics,
    property_market_metrics,
    annotate_effective_prices,
    _listing_sale_price,
)


def _month_start(d: datetime.date, offset: int) -> datetime.date:
    """First day of the month `offset` months from `d` (offset may be negative)."""
    m = d.month - 1 + offset
    y = d.year + m // 12
    return datetime.date(y, m % 12 + 1, 1)


PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _jalali_month_buckets(count: int = 6) -> list[dict]:
    """Last `count` Jalali months, oldest → newest, with Gregorian [start, end)."""
    today = timezone.now().date()
    j_today = jdatetime.date.fromgregorian(date=today)
    buckets = []
    for offset in range(-(count - 1), 1):
        m = j_today.month + offset
        y = j_today.year
        while m <= 0:
            m += 12
            y -= 1
        g_start = jdatetime.date(year=y, month=m, day=1).togregorian()
        nm, ny = (m + 1, y) if m < 12 else (1, y + 1)
        g_end = jdatetime.date(year=ny, month=nm, day=1).togregorian()
        buckets.append(
            {
                "year": y,
                "month": m,
                "label": PERSIAN_MONTHS[m - 1],
                "start": g_start,
                "end": g_end,
                "iso": g_start.isoformat(),
            }
        )
    return buckets


def _sale_listing_value(listing) -> Decimal | None:
    """Comparable sale figure only — rent deposits are not revenue."""
    price = _listing_sale_price(listing)
    return Decimal(str(price)) if price else None


# Deal-type ``name``s whose monetary value is an outright purchase figure.
# Kept in sync with apps.common.metrics.SALE_LIKE_DEAL_TYPES.
SALE_LIKE_DEAL_NAMES = {"sale", "presale", "exchange", "partnership"}
# Deal types whose headline figure is the deposit/رهن. A companion monthly rent
# (اجاره) is added on top when present.
DEPOSIT_DEAL_NAMES = {"mortgage_rent", "full_mortgage"}
# Deal type name used when a sold record predates the deal-type split or has no
# deal type attached. Matches the seed-data key for "فروش".
DEFAULT_DEAL_NAME = "sale"


def _persian_deal_label(deal_type) -> str:
    """Persian label for a DealType row, with a safe fallback."""
    if getattr(deal_type, "display_name", None):
        return deal_type.display_name
    name = getattr(deal_type, "name", None) or DEFAULT_DEAL_NAME
    return {
        "sale": "فروش",
        "mortgage_rent": "رهن و اجاره",
        "full_mortgage": "رهن کامل",
        "presale": "پیش‌فروش",
        "exchange": "معاوضه",
        "partnership": "مشارکت در ساخت",
    }.get(name, name)


def _deal_value(
    listing,
    *,
    deal_name: str | None,
    property_price: Decimal | None,
) -> Decimal:
    """Toman volume of one closed deal, according to its deal type.

    - فروش / پیش‌فروش / معاوضه / مشارکت: ``sale_price`` (fallback to the
      property's sale listings / legacy price).
    - رهن کامل: ``deposit``.
    - رهن و اجاره: ``deposit`` plus the contracted ``monthly_rent``.

    Returns ``Decimal(0)`` when no usable figure is recorded so the count still
    reflects a closed deal even if the agent omitted the amount.
    """
    total = Decimal(0)

    if deal_name in SALE_LIKE_DEAL_NAMES:
        price = _listing_sale_price(listing)
        if price:
            total += Decimal(str(price))
        elif property_price:
            total += Decimal(str(property_price))
        return total

    if deal_name in DEPOSIT_DEAL_NAMES:
        if listing.deposit:
            total += Decimal(str(listing.deposit))
        # رهن و اجاره علاوه بر ودیعه، اجارهٔ یک ماه (۳۰ روز) را نیز به حجم
        # معامله اضافه می‌کند — این رقم «ارزش معاملهٔ بسته‌شده» است، نه درآمد
        # سالانه، و با منطق گزارش‌های موجود پروژه هم‌خوان است.
        if deal_name == "mortgage_rent" and listing.monthly_rent:
            total += Decimal(str(listing.monthly_rent)) * Decimal(30)
        return total

    # Unknown / future deal type: use whichever money column is populated.
    if listing.sale_price:
        total += Decimal(str(listing.sale_price))
    elif listing.deposit:
        total += Decimal(str(listing.deposit))
        if listing.monthly_rent:
            total += Decimal(str(listing.monthly_rent))
    elif property_price:
        total += Decimal(str(property_price))
    return total


def _to_billion(value: Decimal) -> float:
    """Normalise a Toman decimal to billion-Toman, rounded for charts."""
    if not value:
        return 0.0
    billion = float(value / Decimal("1000000000"))
    return round(billion, 2) if billion < 10 else round(billion, 1)


def _get_monthly_revenue():
    """Closed-deal volume for the last 6 Jalali months (billion Toman).

    The chart is fully driven by **listings**: a deal contributes only while
    its listing has status ``SOLD``. If a listing is reopened (set back to
    ACTIVE/DRAFT/PAUSED/...) it disappears from the chart on the next refresh,
    and if it is sold again it returns. This keeps the chart truthful about
    what is actually closed instead of trusting a denormalised property flag.

    Volumes are split by deal type so the dashboard can render فروش، رهن و
    اجاره، رهن کامل و سایر نوع‌ها به‌صورت سری‌های جدا:

    - فروش / پیش‌فروش / معاوضه / مشارکت در ساخت: ``sale_price``.
    - رهن کامل: ``deposit``.
    - رهن و اجاره: ``deposit`` به‌علاوهٔ اجارهٔ یک ماه (۳۰ روز).

    When a listing has no deal type yet (legacy data), it falls back to
    ``sale``. Records are bucketed by the Jalali month of their last update —
    the closest available proxy for the close date. Six months are always
    returned, so the chart never falls back to static data.
    """
    buckets = _jalali_month_buckets(6)
    oldest = buckets[0]["start"]
    start_dt = timezone.make_aware(datetime.datetime.combine(oldest, datetime.time.min))
    bucket_by_key = {(b["year"], b["month"]): b for b in buckets}

    for b in buckets:
        b["by_deal"] = {}

    sold_listings = list(
        Listing.objects.filter(status=Listing.Status.SOLD, updated_at__gte=start_dt)
        .select_related("property", "deal_type")
    )
    sold_property_prices = annotate_effective_prices(
        [lst.property_id for lst in sold_listings if lst.property_id]
    )

    deal_labels: dict[str, str] = {}

    def _bucket(d):
        jd = jdatetime.date.fromgregorian(date=d)
        return bucket_by_key.get((jd.year, jd.month))

    def _add(bucket, deal_name, label, value):
        deal_labels.setdefault(deal_name, label)
        slot = bucket["by_deal"].setdefault(
            deal_name,
            {"sum": Decimal(0), "count": 0, "label": label},
        )
        if value > 0:
            slot["sum"] += value
        slot["count"] += 1

    # Deduplicate by (property, deal type) so two SOLD listings of the same
    # property on the same deal type count once. This guards against duplicate
    # listings while still allowing a property to have both a sold sale listing
    # and a sold rent listing (two genuinely different closed deals).
    seen: set[tuple] = set()
    for lst in sold_listings:
        upd = lst.updated_at
        if not upd:
            continue
        b = _bucket(upd.date() if hasattr(upd, "date") else upd)
        if b is None:
            continue

        deal_type = lst.deal_type
        deal_name = getattr(deal_type, "name", None) or DEFAULT_DEAL_NAME
        label = _persian_deal_label(deal_type)

        dedup_key = (lst.property_id, deal_name)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        property_price = None
        if lst.property_id:
            property_price = sold_property_prices.get(lst.property_id)
            if property_price is None and lst.property:
                property_price = lst.property.price

        value = _deal_value(
            lst,
            deal_name=deal_name,
            property_price=property_price,
        )
        _add(b, deal_name, label, value)

    preferred_order = [
        "sale",
        "presale",
        "mortgage_rent",
        "full_mortgage",
        "exchange",
        "partnership",
    ]
    ordered_deal_names = [n for n in preferred_order if n in deal_labels] + sorted(
        (n for n in deal_labels if n not in preferred_order),
        key=lambda n: deal_labels[n],
    )

    monthly_data = []
    for b in buckets:
        deal_volumes = {}
        total_sum = Decimal(0)
        total_count = 0
        for deal_name in ordered_deal_names:
            slot = b["by_deal"].get(deal_name)
            if not slot:
                deal_volumes[deal_name] = 0.0
                continue
            deal_volumes[deal_name] = _to_billion(slot["sum"])
            total_sum += slot["sum"]
            total_count += slot["count"]

        revenue_billion = _to_billion(total_sum)
        monthly_data.append(
            {
                "month": b["label"],
                "revenue": revenue_billion,
                "count": total_count,
                "total": int(total_sum),
                "dealVolumes": deal_volumes,
            }
        )

    return {
        "months": monthly_data,
        "dealTypes": [
            {"name": name, "label": deal_labels[name]} for name in ordered_deal_names
        ],
    }


def _property_type_label(prop) -> str:
    if getattr(prop, "property_type_ref", None) and prop.property_type_ref.display_name:
        return prop.property_type_ref.display_name
    raw_type = str(prop.property_type or "").strip()
    legacy_map = {
        "APARTMENT": "آپارتمان", "apartment": "آپارتمان", "Apartment": "آپارتمان",
        "VILLA": "ویلا", "villa": "ویلا", "Villa": "ویلا",
        "TOWNHOUSE": "خانه ویلایی", "townhouse": "خانه ویلایی", "Townhouse": "خانه ویلایی",
        "STUDIO": "استودیو", "studio": "استودیو", "Studio": "استودیو",
        "PENTHOUSE": "پنت‌هاوس", "penthouse": "پنت‌هاوس", "Penthouse": "پنت‌هاوس",
        "COMMERCIAL": "تجاری", "commercial": "تجاری", "Commercial": "تجاری",
        "OFFICE": "اداری", "office": "اداری", "Office": "اداری",
        "SHOP": "مغازه", "shop": "مغازه", "Shop": "مغازه",
        "LAND": "زمین", "land": "زمین", "Land": "زمین",
        "OTHER": "سایر", "other": "سایر", "Other": "سایر",
    }
    return legacy_map.get(raw_type) or legacy_map.get(raw_type.upper()) or raw_type or "سایر"


def _get_property_composition(qs=None):
    """Dynamic property composition by type: count, percentage, Persian name."""
    if qs is None:
        qs = Property.active_objects.all()
    qs = qs.select_related("property_type_ref")

    type_counts: dict[str, int] = {}
    for prop in qs:
        name = _property_type_label(prop)
        type_counts[name] = type_counts.get(name, 0) + 1

    total = sum(type_counts.values()) or 1
    sorted_types = sorted(type_counts.items(), key=lambda x: -x[1])

    result = []
    for name, count in sorted_types:
        pct = round((count / total) * 100, 1)
        result.append({
            "name": name,
            "value": count,
            "count": count,
            "percentage": pct,
            "label": f"{name} {pct}٪",
        })

    return result


def consultant_detail_report(profile) -> dict:
    """Drill-down analytics for a single consultant profile.

    All metrics are scoped to the consultant's linked user account:
      - tasks: assigned to the consultant
      - follow-ups: owned by the consultant (non-archived)
      - listings: created by or assigned to the consultant
      - properties: properties the consultant is responsible for
    """
    user = profile.user
    now = timezone.now()
    today = now.date()
    since_30 = now - datetime.timedelta(days=30)

    tasks_qs = Task.objects.filter(assigned_to=user).exclude(
        status=Task.Status.CANCELLED
    )
    followups_qs = FollowUp.objects.filter(consultant=user, is_archived=False)
    listings_qs = Listing.objects.filter(Q(created_by=user) | Q(assigned_to=user))
    properties_qs = Property.objects.filter(consultant=user)
    properties_count = properties_qs.count()

    # ---- KPIs --------------------------------------------------------------
    open_tasks = tasks_qs.exclude(status=Task.Status.COMPLETED)
    completed_tasks = tasks_qs.filter(status=Task.Status.COMPLETED)
    total_tasks = tasks_qs.count()
    completed_count = completed_tasks.count()
    active_listings = listings_qs.filter(status=Listing.Status.ACTIVE).count()
    followup_count = followups_qs.count()
    overdue_count = consultant_tasks_overdue_count(user)
    followups_overdue_count = consultant_followups_overdue_count(user)
    rank = consultant_ranking_metrics(user)
    completion_rate = (
        round(completed_count / total_tasks * 100) if total_tasks else None
    )

    # ---- Monthly activity (last 6 Jalali months) ---------------------------
    buckets = _jalali_month_buckets(6)

    def _in_bucket(dt, b) -> bool:
        if dt is None:
            return False
        d = dt.date() if isinstance(dt, datetime.datetime) else dt
        return b["start"] <= d < b["end"]

    monthly = []
    for b in buckets:
        monthly.append(
            {
                "month": b["iso"],
                "label": b["label"],
                "tasksCompleted": sum(
                    1 for t in completed_tasks if _in_bucket(t.completed_at, b)
                ),
                "followups": sum(
                    1 for f in followups_qs if _in_bucket(f.created_at, b)
                ),
                "listings": sum(
                    1 for l in listings_qs if _in_bucket(l.created_at, b)
                ),
            }
        )

    # ---- Tasks by status ----------------------------------------------------
    status_counts = Counter(tasks_qs.values_list("status", flat=True))
    tasks_by_status = [
        {"status": status, "count": cnt}
        for status, cnt in sorted(status_counts.items(), key=lambda x: -x[1])
    ]

    # ---- Follow-ups by type --------------------------------------------------
    followups_by_type = []
    types_seen = Counter(followups_qs.values_list("follow_up_type", flat=True))
    for fu_type, cnt in sorted(types_seen.items(), key=lambda x: -x[1]):
        done = followups_qs.filter(
            follow_up_type=fu_type, status=FollowUpStatus.COMPLETED
        ).count()
        followups_by_type.append(
            {
                "type": fu_type,
                "count": cnt,
                "completedCount": done,
                "completionRate": round(done / cnt * 100, 1) if cnt else None,
            }
        )

    # ---- Listings by publish channel ----------------------------------------
    channel_counts = Counter(listings_qs.values_list("publish_channel", flat=True))
    listings_by_channel = [
        {"channel": ch or "WEBSITE", "count": cnt}
        for ch, cnt in sorted(channel_counts.items(), key=lambda x: -x[1])
    ]

    # ---- Deal-type distribution of the consultant's listings -----------------
    deal_counts = Counter(
        listings_qs.exclude(deal_type__isnull=True).values_list(
            "deal_type__display_name", flat=True
        )
    )
    listings_by_deal_type = [
        {"label": label, "count": cnt}
        for label, cnt in sorted(deal_counts.items(), key=lambda x: -x[1])
    ]

    # ---- Listing status distribution -----------------------------------------
    listing_status_counts = Counter(listings_qs.values_list("status", flat=True))
    listings_by_status = [
        {"status": status, "count": cnt}
        for status, cnt in sorted(
            listing_status_counts.items(), key=lambda x: -x[1]
        )
    ]

    # ---- Task priority distribution ------------------------------------------
    priority_counts = Counter(
        tasks_qs.values_list("priority", flat=True).exclude(priority="")
    )
    tasks_by_priority = [
        {"priority": priority, "count": cnt}
        for priority, cnt in sorted(priority_counts.items(), key=lambda x: -x[1])
    ]

    # ---- Follow-up status distribution ----------------------------------------
    # Overdue scheduled follow-ups are split out so charts reflect missed
    # deadlines instead of lumping them in with still-upcoming work.
    completed_followups = followups_qs.filter(status=FollowUpStatus.COMPLETED).count()
    scheduled_followups = followups_qs.filter(status=FollowUpStatus.SCHEDULED).count()
    upcoming_followups = max(0, scheduled_followups - followups_overdue_count)
    followups_by_status = [
        {"status": status, "count": cnt}
        for status, cnt in (
            ("overdue", followups_overdue_count),
            ("scheduled", upcoming_followups),
            ("completed", completed_followups),
        )
        if cnt
    ]

    # ---- Property type distribution of the consultant's properties -----------
    property_type_counts: Counter[str] = Counter()
    for prop in properties_qs.select_related("property_type_ref"):
        property_type_counts[_property_type_label(prop)] += 1
    properties_by_type = [
        {"type": ptype, "count": cnt}
        for ptype, cnt in sorted(property_type_counts.items(), key=lambda x: -x[1])
    ]

    # ---- Property locations (for the map chart) -------------------------------
    property_locations = [
        {
            "id": p.pk,
            "title": p.title,
            "lat": float(p.latitude),
            "lng": float(p.longitude),
            "status": p.status,
            "area": p.area,
        }
        for p in properties_qs.filter(
            latitude__isnull=False, longitude__isnull=False
        )
    ]

    # ---- Performance profile (radar, 0..100 per axis) ------------------------
    open_count = open_tasks.count()
    open_items = open_count + scheduled_followups
    overdue_items = overdue_count + followups_overdue_count
    punctuality = (
        max(0, round((1 - overdue_items / open_items) * 100)) if open_items else 100
    )
    recent_activity = (
        followups_qs.filter(created_at__gte=since_30).count()
        + completed_tasks.filter(completed_at__gte=since_30).count()
    )
    performance_profile = [
        {"metric": "تکمیل وظایف", "score": completion_rate if completion_rate is not None else 0},
        {"metric": "انجام به‌موقع", "score": punctuality},
        {"metric": "تکمیل پیگیری", "score": round(rank["followupCompletionRate"] or 0)},
        {
            "metric": "پوشش بازاریابی",
            "score": min(100, round(active_listings / properties_count * 100)) if properties_count else 0,
        },
        {"metric": "تعامل اخیر", "score": min(100, round(recent_activity / 20 * 100))},
    ]

    return {
        "consultant": {
            "id": profile.pk,
            "fullName": profile.full_name,
            "branch": profile.branch,
            "userId": profile.user_id,
        },
        "kpis": {
            "propertyCount": properties_count,
            "activeListings": active_listings,
            "openTasks": open_count,
            "completedTasks": completed_count,
            "followupCount": followup_count,
            "closedDealsCount": rank["closedDealsCount"],
            "completedWorkCount": rank["completedWorkCount"],
            "overdueWorkCount": rank["overdueWorkCount"],
            "headlineValue": rank["headlineValue"],
            "headlineLabel": rank["headlineLabel"],
            "workCompletionRate": rank["workCompletionRate"],
            "followupCompletionRate": rank["followupCompletionRate"],
            "tasksOverdueCount": overdue_count,
            "followupsOverdueCount": followups_overdue_count,
            "completionRate": completion_rate,
        },
        "charts": {
            "monthlyActivity": monthly,
            "tasksByStatus": tasks_by_status,
            "followupsByType": followups_by_type,
            "listingsByChannel": listings_by_channel,
            "performanceProfile": performance_profile,
            "listingsByDealType": listings_by_deal_type,
            "listingsByStatus": listings_by_status,
            "tasksByPriority": tasks_by_priority,
            "followupsByStatus": followups_by_status,
            "propertiesByType": properties_by_type,
            "propertyLocations": property_locations,
        },
        "meta": {"generatedAt": now.isoformat()},
    }


class ConsultantDetailAnalyticsView(APIView):
    """Detailed analytics for a single consultant profile.

    GET /common/api/analytics/consultants/<pk>/
    Admin: any consultant. Agent: only their own profile.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        profile = (
            ConsultantProfile.objects.select_related("user")
            .filter(pk=pk, user__role=UserRole.AGENT)
            .first()
        )
        if profile is None:
            return Response({"error": "مشاور یافت نشد"}, status=404)
        if (
            getattr(request.user, "role", "") != "ADMIN"
            and profile.user_id != request.user.pk
        ):
            return Response(
                {"error": "شما به گزارش این مشاور دسترسی ندارید."}, status=403
            )
        return Response(consultant_detail_report(profile))


class ConsultantAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profiles = ConsultantProfile.objects.select_related("user").filter(
            is_active=True, user__role=UserRole.AGENT
        )
        rows = []
        for profile in profiles:
            image = profile.profile_image
            base = {
                "id": profile.id,
                "fullName": profile.full_name,
                "branch": profile.branch,
                "userId": profile.user_id,
                "profile_image": image.url if image else None,
            }
            base.update(consultant_performance_metrics(profile))
            rows.append(base)
        rows.sort(
            key=lambda r: (
                -(r.get("closedDealsCount") or 0),
                -(r.get("completedWorkCount") or 0),
                (r.get("overdueWorkCount") or 0),
            )
        )
        return Response({"consultants": rows})


class PropertyAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = Property.objects.prefetch_related("images")
        if getattr(user, "role", "") != "ADMIN":
            qs = qs.filter(consultant=user)
        properties = list(qs.order_by("-created_at"))
        neighborhood_stats = build_neighborhood_price_stats_map(properties)
        rows = []
        for prop in properties:
            row = {"id": prop.id, "title": prop.title, "neighborhood": prop.neighborhood}
            row.update(property_market_metrics(prop, neighborhood_stats))
            rows.append(row)
        return Response({"properties": rows})


class ListingAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = Listing.objects.select_related("property", "created_by", "assigned_to").prefetch_related(
            "property__images"
        )
        if getattr(user, "role", "") != "ADMIN":
            from django.db.models import Q

            qs = qs.filter(Q(created_by=user) | Q(assigned_to=user))
        listings = list(qs.order_by("-created_at"))
        rows = [listing_marketing_metrics(lst) for lst in listings]
        channels = channel_marketing_summary(listings)
        return Response({"listings": rows, "channels": channels})


def _dashboard_kpis(user) -> dict:
    """Live, role-scoped counts for the dashboard KPI strip."""
    is_admin = getattr(user, "role", "") == "ADMIN"
    props = Property.active_objects.all()
    listings = Listing.objects.filter(status=Listing.Status.ACTIVE)
    tasks = Task.objects.exclude(
        status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED]
    )
    followups = FollowUp.objects.filter(
        is_archived=False,
        status=FollowUpStatus.SCHEDULED,
        scheduled_at__gte=timezone.now(),
    )
    if not is_admin:
        props = props.filter(Q(consultant=user) | Q(is_shared=True))
        listings = listings.filter(Q(created_by=user) | Q(assigned_to=user))
        tasks = tasks.filter(Q(assigned_to=user) | Q(created_by=user))
        followups = followups.filter(consultant=user)
    consultants = ConsultantProfile.objects.filter(user__role=UserRole.AGENT)
    return {
        "totalProperties": props.count(),
        "activeListings": listings.count(),
        "openTasks": tasks.count(),
        "followUpsDue": followups.count(),
        "consultants": consultants.count(),
        "consultantsActive": consultants.filter(is_active=True).count(),
    }


def _hot_property_rows(properties: list[dict]) -> list[dict]:
    ranked = sorted(
        properties or [],
        key=lambda x: x.get("engagementHeatScore") or 0,
        reverse=True,
    )
    out = []
    for row in ranked[:5]:
        if not (row.get("engagementHeatScore") or 0):
            continue
        out.append(
            {
                "id": row.get("id") or row.get("propertyId"),
                "title": row.get("title") or "—",
                "neighborhood": row.get("neighborhood") or "—",
                "engagementHeatScore": row.get("engagementHeatScore") or 0,
                "daysOnMarket": row.get("daysOnMarket"),
                "pricePerSqm": row.get("pricePerSqm"),
            }
        )
    return out


class AnalyticsDashboardView(APIView):
    """Compact bundle for reports / admin dashboard widgets."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = getattr(user, "role", "") == "ADMIN"

        consultant_view = ConsultantAnalyticsView()
        consultant_view.request = request
        property_view = PropertyAnalyticsView()
        property_view.request = request
        listing_view = ListingAnalyticsView()
        listing_view.request = request

        c_data = consultant_view.get(request).data
        p_data = property_view.get(request).data
        l_data = listing_view.get(request).data

        top_consultants = (c_data.get("consultants") or [])[:5]
        hot_properties = _hot_property_rows(p_data.get("properties") or [])

        if is_admin:
            composition_qs = Property.active_objects.all()
        else:
            composition_qs = Property.active_objects.filter(
                Q(consultant=user) | Q(is_shared=True)
            )

        my_report = None
        if not is_admin:
            profile = (
                ConsultantProfile.objects.select_related("user")
                .filter(user=user, user__role=UserRole.AGENT)
                .first()
            )
            if profile is not None:
                report = consultant_detail_report(profile)
                my_report = {
                    "kpis": report["kpis"],
                    "charts": {
                        "monthlyActivity": report["charts"]["monthlyActivity"],
                        "tasksByStatus": report["charts"]["tasksByStatus"],
                        "performanceProfile": report["charts"]["performanceProfile"],
                        "propertiesByType": report["charts"]["propertiesByType"],
                        "followupsByStatus": report["charts"]["followupsByStatus"],
                    },
                }

        revenue_bundle = _get_monthly_revenue()

        return Response(
            {
                "kpis": _dashboard_kpis(user),
                "topConsultants": top_consultants,
                "hotProperties": hot_properties,
                "channelSummary": l_data.get("channels") or [],
                "consultantCount": len(c_data.get("consultants") or []),
                "propertyCount": len(p_data.get("properties") or []),
                "listingCount": len(l_data.get("listings") or []),
                # Backwards-compatible flat list (month, revenue, count, total,
                # dealVolumes) plus the per-deal-type legend for the chart.
                "revenueMonthly": revenue_bundle["months"],
                "revenueDealTypes": revenue_bundle["dealTypes"],
                "propertyComposition": _get_property_composition(composition_qs),
                "myReport": my_report,
            }
        )


# ---------------------------------------------------------------------------
# AI description endpoints (consultant & property)
# ---------------------------------------------------------------------------

def _consultant_ai_data(profile) -> dict:
    """Collect the analytics data sent to the AI for a consultant description."""
    report = consultant_detail_report(profile)
    kpis = report["kpis"]
    charts = dict(report["charts"])
    # Map pins name other properties and confuse the model; KPIs already
    # cover portfolio size.
    charts.pop("propertyLocations", None)
    return {
        "entity": "consultant",
        "id": profile.pk,
        "fullName": profile.full_name,
        "branch": profile.branch,
        "kpis": kpis,
        "charts": charts,
    }


def _property_ai_data(prop) -> dict:
    """Collect the analytics data sent to the AI for a property description."""
    from apps.common.metrics import property_market_metrics
    from apps.reports.services import compute_property_report

    market = property_market_metrics(prop)
    report = compute_property_report(prop)
    charts = dict(report["charts"])
    charts.pop("engagementHeatmap", None)
    charts.pop("exposureTimeline", None)
    return {
        "entity": "property",
        "id": prop.pk,
        "title": prop.title,
        "internalCode": prop.internal_code,
        "neighborhood": (prop.district.display_name if prop.district else (prop.neighborhood or "")),
        "status": prop.status,
        "area": prop.area,
        "rooms": prop.rooms,
        "kpis": report["kpis"],
        "charts": charts,
        "marketIndicators": market,
    }


class AIInsightView(APIView):
    """Generate a structured AI description (positives/negatives/summary).

    POST /common/api/ai/consultant/<pk>/
    POST /common/api/ai/property/<pk>/
    """

    permission_classes = [IsAuthenticated]

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request, entity, pk):
        from apps.common.ai_service import AIError, get_cached_description

        # Resolve the object with permission scoping.
        if entity == "consultant":
            profile = (
                ConsultantProfile.objects.select_related("user")
                .filter(pk=pk, user__role=UserRole.AGENT)
                .first()
            )
            if profile is None:
                return Response({"detail": "مشاور یافت نشد."}, status=404)
            if (
                getattr(request.user, "role", "") != "ADMIN"
                and profile.user_id != request.user.pk
            ):
                return Response({"detail": "دسترسی مجاز نیست."}, status=403)
            data = _consultant_ai_data(profile)
            entity_id = profile.pk
        elif entity == "property":
            from apps.properties.models import Property as PropModel

            prop = PropModel.objects.filter(pk=pk).first()
            if prop is None:
                return Response({"detail": "ملک یافت نشد."}, status=404)
            # Admin can see any; consultants only their own or shared.
            user = request.user
            if getattr(user, "role", "") != "ADMIN":
                from django.db.models import Q
                if not PropModel.objects.filter(
                    Q(pk=pk), Q(consultant=user) | Q(is_shared=True)
                ).exists():
                    return Response({"detail": "دسترسی مجاز نیست."}, status=403)
            data = _property_ai_data(prop)
            entity_id = prop.pk
        else:
            return Response({"detail": "موجودیت نامعتبر است."}, status=400)

        try:
            description = get_cached_description(
                data, entity=entity, entity_id=entity_id
            )
        except AIError as e:
            return Response({"detail": str(e)}, status=503)
        except Exception as e:  # noqa: BLE001
            return Response(
                {"detail": "خطا در ارتباط با هوش مصنوعی: " + str(e)}, status=502
            )

        return Response(description)
