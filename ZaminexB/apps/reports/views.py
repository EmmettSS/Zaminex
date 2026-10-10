from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.properties.models import Property

from .caching import cached_consultant_scope_report, cached_property_report
from .services import (
    accessible_properties,
    get_property_for_user_or_403,
    property_report_csv_rows,
    render_csv,
)


class IsAuthenticatedRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def _parse_date(raw):
    import datetime

    if not raw:
        return None
    try:
        return datetime.datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class PropertyReportView(APIView):
    permission_classes = [IsAuthenticatedRole]

    def _report(self, request, property_id):
        try:
            pid = int(property_id)
        except (TypeError, ValueError):
            raise ValueError("شناسه ملک نامعتبر است.")
        prop = get_property_for_user_or_403(request.user, pid)
        filters = {
            "date_from": _parse_date(request.query_params.get("date_from")),
            "date_to": _parse_date(request.query_params.get("date_to")),
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        return pid, cached_property_report(prop, filters=filters)

    def get(self, request, property_id):
        try:
            _, report = self._report(request, property_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(report)


class PropertyReportExportView(APIView):
    permission_classes = [IsAuthenticatedRole]

    def get(self, request, property_id):
        view = PropertyReportView()
        view.request = request
        view.format_kwarg = None
        try:
            pid, report = view._report(request, property_id)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        from apps.activity.activity import log_activity
        from apps.activity.models import ActivityLog

        title = report.get("property", {}).get("title") or f"ملک {pid}"
        log_activity(
            user=request.user,
            action=ActivityLog.ActionType.EXPORT,
            target_type=ActivityLog.TargetType.PROPERTY,
            target_id=pid,
            description=f"گزارش کامل ملک «{title}» به‌صورت CSV دریافت شد",
            metadata={
                "format": "csv",
                "property_id": pid,
                "date_from": request.query_params.get("date_from"),
                "date_to": request.query_params.get("date_to"),
            },
        )

        rows = property_report_csv_rows(report)
        from .services import CSV_TRANSLATIONS as _TR

        key_to_label = {
            "propertyId": "شناسه ملک",
            "title": "عنوان",
            "internalCode": "کد داخلی",
        }
        for k, lbl in _TR.items():
            key_to_label[k] = lbl
        fieldnames = ["شناسه ملک", "عنوان", "کد داخلی"] + [
            label for label in _TR.values() if label not in {"شناسه ملک", "عنوان", "کد داخلی"}
        ]
        persian_rows = [
            {key_to_label.get(k, k): v for k, v in r.items()} for r in rows
        ]
        csv_text = render_csv(persian_rows, fieldnames=fieldnames)
        resp = HttpResponse(csv_text, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = (
            f'attachment; filename="property-report-{pid}.csv"'
        )
        return resp


def _print_error(request, status_code: int, title: str, message: str):
    from django.template.response import TemplateResponse

    return TemplateResponse(
        request,
        "reports/print_error.html",
        {"title": title, "message": message},
        status=status_code,
    )


@login_required
def property_report_print(request, property_id):
    from apps.common.access import can_access_property
    from apps.properties.models import Property as PropertyModel

    try:
        pid = int(property_id)
    except (TypeError, ValueError):
        return _print_error(request, 400, "آدرس نامعتبر است.", "شناسه ملک نامعتبر است.")

    prop = (
        PropertyModel.objects.select_related(
            "consultant",
            "property_type_ref",
            "property_usage",
            "district",
            "district__city",
            "district__city__province",
        )
        .prefetch_related("listings__deal_type", "tasks", "followups", "images")
        .filter(pk=pid)
        .first()
    )
    if prop is None:
        return _print_error(request, 404, "ملک پیدا نشد.", "ملک مورد نظر وجود ندارد.")
    if not can_access_property(request.user, prop):
        return _print_error(
            request, 403, "دسترسی ندارید.", "شما به گزارش این ملک دسترسی ندارید."
        )

    filters = {
        "date_from": _parse_date(request.GET.get("date_from")),
        "date_to": _parse_date(request.GET.get("date_to")),
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    report = cached_property_report(prop, filters=filters)

    from apps.activity.activity import log_activity
    from apps.activity.models import ActivityLog

    log_activity(
        user=request.user,
        action=ActivityLog.ActionType.EXPORT,
        target_type=ActivityLog.TargetType.PROPERTY,
        target_id=prop.pk,
        description=f"گزارش کامل ملک «{prop.title}» برای چاپ یا ذخیره PDF باز شد",
        metadata={
            "format": "print",
            "property_id": prop.pk,
            "date_from": request.GET.get("date_from"),
            "date_to": request.GET.get("date_to"),
        },
    )

    from django.template.response import TemplateResponse

    from .printing import build_print_report_context

    context = build_print_report_context(prop, report, request.user)
    return TemplateResponse(request, "reports/print_report.html", context)


class ConsultantScopeReportView(APIView):
    permission_classes = [IsAuthenticatedRole]

    def get(self, request):
        data = cached_consultant_scope_report(request.user)
        return Response(data)


class PropertyOptionsView(APIView):
    permission_classes = [IsAuthenticatedRole]

    def get(self, request):
        qs = accessible_properties(request.user).order_by("-created_at").values_list(
            "id", "title", "internal_code", "neighborhood", "status"
        )
        options = [
            {
                "id": pid,
                "title": title,
                "internalCode": code,
                "neighborhood": nb,
                "status": st,
            }
            for pid, title, code, nb, st in qs[:200]
        ]
        return Response({"properties": options, "count": len(options)})
