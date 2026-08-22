"""Serve uploaded media only to authenticated users who may access it.

The media root contains consultant avatars and property images. Access rules:

* path traversal protection (``..`` and absolute paths are rejected);
* authentication is always required (anonymous requests are denied);
* property images are visible to every authenticated consultant, matching the
  read-only ``scope=all`` ("همه املاک") policy of the properties API, which
  lets consultants browse every property in the system — including its photos;
* profile avatars remain owner-only for non-admins;
* files not referenced by any database row are never served.
"""

from __future__ import annotations

import posixpath
from pathlib import PurePosixPath

from django.conf import settings
from django.http import Http404, HttpResponseForbidden
from django.views.static import serve

from apps.accounts.models import AdminProfile, ConsultantProfile
from apps.properties.models import PropertyImage


def _safe_relative_path(path: str) -> str | None:
    """Return a safe path relative to MEDIA_ROOT or None if it is not."""
    if not path:
        return None
    # Reject absolute Windows/Unix paths and NUL bytes outright.
    if "\x00" in path or path.startswith(("/", "\\")) or ":\\" in path:
        return None
    normalized = posixpath.normpath(path).replace("\\", "/")
    if normalized in (".", "..") or normalized.startswith("../") or "/../" in normalized:
        return None
    return normalized


def _can_access_media(user, rel_path: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    # Admins can read every uploaded file.
    if getattr(user, "role", "") == "ADMIN":
        return True
    parts = PurePosixPath(rel_path).parts
    if not parts:
        return False
    # Property images: every authenticated consultant may view the photos of
    # ANY property. The properties API already exposes all properties
    # read-only via ``scope=all`` (the consultant panel's "همه املاک" tab),
    # so blocking the images of other consultants' properties made those
    # cards render broken while their data was visible. Write actions remain
    # owner/shared-only at the API level; this view is read-only serving.
    # Files with no PropertyImage row (orphans/unknown) stay protected.
    if parts[0] == "properties":
        return PropertyImage.objects.filter(image=rel_path).exists()
    # Consultant avatars: consultants may see their own avatar only. We do
    # not expose other consultants' profile photos to non-admins.
    if parts[0] == "consultants":
        return ConsultantProfile.objects.filter(user=user, profile_image=rel_path).exists()
    if parts[0] == "admins":
        # Admin avatars are never exposed to consultants; admins already
        # passed the role check above.
        return AdminProfile.objects.filter(user=user, profile_image=rel_path).exists()
    # Unknown media path: deny by default.
    return False


def serve_media(request, path):
    rel_path = _safe_relative_path(path)
    if rel_path is None:
        raise Http404("مسیر فایل نامعتبر است.")
    if not _can_access_media(request.user, rel_path):
        return HttpResponseForbidden("شما به این فایل دسترسی ندارید.")
    return serve(request, rel_path, document_root=settings.MEDIA_ROOT)
