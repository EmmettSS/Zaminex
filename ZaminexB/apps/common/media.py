from __future__ import annotations

import posixpath
from pathlib import PurePosixPath

from django.conf import settings
from django.http import Http404, HttpResponseForbidden
from django.views.static import serve

from apps.accounts.models import AdminProfile, ConsultantProfile
from apps.properties.models import PropertyAppraisalReport, PropertyImage


def _safe_relative_path(path: str) -> str | None:
    if not path:
        return None
    
    if "\x00" in path or path.startswith(("/", "\\")) or ":\\" in path:
        return None
    normalized = posixpath.normpath(path).replace("\\", "/")
    if normalized in (".", "..") or normalized.startswith("../") or "/../" in normalized:
        return None
    return normalized


def _can_access_media(user, rel_path: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    
    if getattr(user, "role", "") == "ADMIN":
        return True
    parts = PurePosixPath(rel_path).parts
    if not parts:
        return False
    
    if parts[0] == "properties" and len(parts) > 1 and parts[1] == "appraisals":
        report = (
            PropertyAppraisalReport.objects.select_related("property")
            .filter(file=rel_path)
            .only("property__consultant_id", "property__is_shared")
            .first()
        )
        if report is None:
            return False
        prop = report.property
        return bool(prop and (prop.consultant_id == user.pk or prop.is_shared))
    
    if parts[0] == "properties":
        return PropertyImage.objects.filter(image=rel_path).exists()
    
    if parts[0] == "consultants":
        return ConsultantProfile.objects.filter(user=user, profile_image=rel_path).exists()
    if parts[0] == "admins":
        return AdminProfile.objects.filter(user=user, profile_image=rel_path).exists()
    
    return False


def serve_media(request, path):
    rel_path = _safe_relative_path(path)
    if rel_path is None:
        raise Http404("مسیر فایل نامعتبر است.")
    if not _can_access_media(request.user, rel_path):
        return HttpResponseForbidden("شما به این فایل دسترسی ندارید.")
    return serve(request, rel_path, document_root=settings.MEDIA_ROOT)
