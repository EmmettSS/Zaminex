import datetime
from collections import Counter
from decimal import Decimal

import jdatetime

from django.db.models import Q
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ConsultantProfile, UserRole
from apps.followups.models import FollowUp, FollowUpStatus
from apps.listings.models import Listing
from apps.properties.models import Property
from apps.tasks.models import Task

from apps.common import cache_utils
from apps.common.pagination import StandardResultsSetPagination
from apps.common.throttles import ResilientScopedRateThrottle

from .metrics import (
    build_neighborhood_price_stats_map,
    channel_marketing_summary,
    consultant_performance_metrics,
    consultant_ranking_metrics,
    consultant_followups_overdue_count,
    consultant_tasks_overdue_count,
    high_prob_leads_by_property,
    images_count_by_property,
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
    price = _listing_sale_price(listing)
    return Decimal(str(price)) if price else None

SALE_LIKE_DEAL_NAMES = {"sale", "presale", "exchange", "partnership"}
DEPOSIT_DEAL_NAMES = {"mortgage_rent", "full_mortgage"}
DEFAULT_DEAL_NAME = "sale"


def _persian_deal_label(deal_type) -> str:
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
        if deal_name == "mortgage_rent" and listing.monthly_rent:
            total += Decimal(str(listing.monthly_rent)) * Decimal(30)
        return total

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
    if not value:
        return 0.0
    billion = float(value / Decimal("1000000000"))
    return round(billion, 2) if billion < 10 else round(billion, 1)


def _get_monthly_revenue():
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

    status_counts = Counter(tasks_qs.values_list("status", flat=True))
    tasks_by_status = [
        {"status": status, "count": cnt}
        for status, cnt in sorted(status_counts.items(), key=lambda x: -x[1])
    ]

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

    channel_counts = Counter(listings_qs.values_list("publish_channel", flat=True))
    listings_by_channel = [
        {"channel": ch or "WEBSITE", "count": cnt}
        for ch, cnt in sorted(channel_counts.items(), key=lambda x: -x[1])
    ]

    deal_counts = Counter(
        listings_qs.exclude(deal_type__isnull=True).values_list(
            "deal_type__display_name", flat=True
        )
    )
    listings_by_deal_type = [
        {"label": label, "count": cnt}
        for label, cnt in sorted(deal_counts.items(), key=lambda x: -x[1])
    ]

    listing_status_counts = Counter(listings_qs.values_list("status", flat=True))
    listings_by_status = [
        {"status": status, "count": cnt}
        for status, cnt in sorted(
            listing_status_counts.items(), key=lambda x: -x[1]
        )
    ]

    priority_counts = Counter(
        tasks_qs.values_list("priority", flat=True).exclude(priority="")
    )
    tasks_by_priority = [
        {"priority": priority, "count": cnt}
        for priority, cnt in sorted(priority_counts.items(), key=lambda x: -x[1])
    ]

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

    property_type_counts: Counter[str] = Counter()
    for prop in properties_qs.select_related("property_type_ref"):
        property_type_counts[_property_type_label(prop)] += 1
    properties_by_type = [
        {"type": ptype, "count": cnt}
        for ptype, cnt in sorted(property_type_counts.items(), key=lambda x: -x[1])
    ]

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


def _analytics_property_queryset(user):
    qs = Property.objects.prefetch_related("images", "followups", "tasks", "listings")
    if getattr(user, "role", "") != "ADMIN":
        qs = qs.filter(consultant=user)
    return qs.order_by("-created_at")


def _analytics_listing_queryset(user):
    qs = Listing.objects.select_related(
        "property", "created_by", "assigned_to"
    ).prefetch_related(
        "property__images", "property__followups", "property__tasks"
    )
    if getattr(user, "role", "") != "ADMIN":
        qs = qs.filter(Q(created_by=user) | Q(assigned_to=user))
    return qs.order_by("-created_at")


_CHANNEL_SUMMARY_ONLY = (
    "id",
    "property_id",
    "publish_channel",
    "status",
    "start_date",
    "end_date",
    "title",
    "description",
    "sale_price",
    "deposit",
    "monthly_rent",
    "property__status",
    "property__price",
    "property__area",
    "property__neighborhood",
)


def _channel_summary_for(user) -> list[dict]:
    qs = Listing.objects.select_related("property").order_by("-created_at")
    if getattr(user, "role", "") != "ADMIN":
        qs = qs.filter(Q(created_by=user) | Q(assigned_to=user))
    listings = list(qs.only(*_CHANNEL_SUMMARY_ONLY))
    property_ids = [lst.property_id for lst in listings]
    return channel_marketing_summary(
        listings,
        high_prob_leads_by_property(property_ids),
        images_count_by_property(property_ids),
    )


class PropertyAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _analytics_property_queryset(request.user)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        properties = page if page is not None else list(qs)
        neighborhood_stats = build_neighborhood_price_stats_map(properties)
        rows = []
        for prop in properties:
            row = {"id": prop.id, "title": prop.title, "neighborhood": prop.neighborhood}
            row.update(property_market_metrics(prop, neighborhood_stats))
            rows.append(row)
        if page is not None:
            return paginator.get_paginated_response(rows)
        return Response({"properties": rows})


class ListingAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _analytics_listing_queryset(request.user)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(qs, request)
        listings = page if page is not None else list(qs)
        high_prob_leads = high_prob_leads_by_property(
            lst.property_id for lst in listings
        )
        rows = [
            listing_marketing_metrics(lst, high_prob_leads) for lst in listings
        ]
        if page is not None:
            response = paginator.get_paginated_response(rows)
            response.data["channels"] = _channel_summary_for(request.user)
            return response
        return Response(
            {"listings": rows, "channels": channel_marketing_summary(listings, high_prob_leads)}
        )


def _dashboard_kpis(user) -> dict:
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


def _located_property_rows(user, is_admin: bool) -> list[dict]:
    qs = Property.objects.filter(latitude__isnull=False, longitude__isnull=False)
    if not is_admin:
        qs = qs.filter(Q(consultant=user) | Q(is_shared=True))
    rows = (
        qs.values(
            "id",
            "title",
            "latitude",
            "longitude",
            "status",
            "area",
            "consultant_id",
            "consultant__first_name",
            "consultant__last_name",
            "consultant__username",
        )
        .order_by("-created_at")
    )
    out = []
    for row in rows:
        name = None
        if row["consultant_id"]:
            full = f"{row['consultant__first_name'] or ''} {row['consultant__last_name'] or ''}".strip()
            name = full or row["consultant__username"]
        out.append(
            {
                "id": row["id"],
                "title": row["title"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "propertyStatus": (row["status"] or "").lower(),
                "area": row["area"],
                "consultantId": row["consultant_id"],
                "consultantName": name or "نامشخص",
            }
        )
    return out


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    DASHBOARD_TTL = 60

    def get(self, request):
        user = request.user
        key = cache_utils.make_key("dashboard", user.pk)
        bundle = cache_utils.cache_or_compute(
            key, lambda: self._bundle(user, request), self.DASHBOARD_TTL
        )
        return Response(bundle)

    def _bundle(self, user, request) -> dict:
        is_admin = getattr(user, "role", "") == "ADMIN"

        consultant_view = ConsultantAnalyticsView()
        consultant_view.request = request

        c_data = consultant_view.get(request).data
        top_consultants = (c_data.get("consultants") or [])[:5]

        properties = list(_analytics_property_queryset(user))
        neighborhood_stats = build_neighborhood_price_stats_map(properties)
        hot_properties = _hot_property_rows(
            [
                {
                    "id": prop.id,
                    "title": prop.title,
                    "neighborhood": prop.neighborhood,
                    **property_market_metrics(prop, neighborhood_stats),
                }
                for prop in properties
            ]
        )

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

        return {
            "kpis": _dashboard_kpis(user),
            "topConsultants": top_consultants,
            "hotProperties": hot_properties,
            "channelSummary": _channel_summary_for(user),
            "consultantCount": len(c_data.get("consultants") or []),
            "propertyCount": len(properties),
            "listingCount": _analytics_listing_queryset(user).count(),
            "revenueMonthly": revenue_bundle["months"],
            "revenueDealTypes": revenue_bundle["dealTypes"],
            "propertyComposition": _get_property_composition(composition_qs),
            "locatedProperties": _located_property_rows(user, is_admin),
            "myReport": my_report,
        }


def _consultant_ai_data(profile) -> dict:
    """Collect the analytics data sent to the AI for a consultant description."""
    report = consultant_detail_report(profile)
    kpis = report["kpis"]
    charts = dict(report["charts"])
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
    from apps.analytics.metrics import property_market_metrics
    from apps.reports.caching import cached_property_report

    market = property_market_metrics(prop)
    report = cached_property_report(prop)
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
    permission_classes = [IsAuthenticated]

    throttle_classes = [ResilientScopedRateThrottle]
    throttle_scope = "ai"

    def post(self, request, entity, pk):
        from apps.analytics.ai_service import AIError, get_cached_description

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
